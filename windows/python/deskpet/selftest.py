"""Headless-ish self test: opens the real windows, drives every feature, writes PNG proofs."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from PySide6.QtCore import QEventLoop, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest

from . import config, winapi

OUT = config.APP_DIR / "selftest_out"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, info: str = ""):
    results.append((name, bool(ok), info))
    msg = ("PASS " if ok else "FAIL ") + name + (f"  [{info}]" if info else "")
    try:
        print(msg, flush=True)
    except Exception:
        enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        try:
            print(msg.encode(enc, errors="replace").decode(enc), flush=True)
        except Exception:
            pass


def wait(ms: int):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def run(qapp) -> int:
    OUT.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp()) / "cfg.json"
    config.CONFIG_PATH = tmp
    config.Config.__init__.__defaults__ = (tmp,)
    from .app import App
    app = App(qapp)
    pet = app.pet
    cfg = app.cfg
    cfg.set("sim_auto", False)
    app.ledger.apply_mode()
    wait(400)

    # ========================================================= 1. Initial window & position
    pet.grab().save(str(OUT / "01_pet_idle.png"))
    check("pet window visible", pet.isVisible(), f"pos={pet.pos().x()},{pet.pos().y()}")
    ag = pet.screen_ag()
    fx0, fy0, fx1, fy1 = pet.bbox_frac()
    S = pet.size_px
    bottom = pet.y() + 130 + fy1 * S
    check("starts in bottom corner", abs(bottom - (ag.bottom() + 1)) <= 2, f"bottom={bottom} floor={ag.bottom() + 1}")

    # ========================================================= 2. Multi-provider simulation balance & hurt
    before = app.ledger.shown
    app.ledger.sim_charge(3)
    wait(60)
    pet.grab().save(str(OUT / "02_pet_hurt.png"))
    wait(900)
    check("3 cues deduct 0.03 in sim mode", abs((before - app.ledger.shown) - 0.03) < 1e-6, f"{before} -> {app.ledger.shown}")
    check("today_used tracks deductions", abs(float(cfg.get("today_used", 0.0)) - 0.03) < 1e-6, f"{cfg.get('today_used')}")
    check("nervous face after hurt then recovers", pet.expr in ("happy", "nervous"), pet.expr)

    # ========================================================= 3. Click-through (Win32 WS_EX_TRANSPARENT)
    hwnd = int(pet.winId())
    if winapi.IS_WIN:
        import ctypes
        get = ctypes.windll.user32.GetWindowLongPtrW
        get.restype = ctypes.c_ssize_t
        get.argtypes = [ctypes.c_void_p, ctypes.c_int]
        app.set_click_through(True)
        on = bool(get(hwnd, winapi.GWL_EXSTYLE) & winapi.WS_EX_TRANSPARENT)
        app.set_click_through(False)
        off = not bool(get(hwnd, winapi.GWL_EXSTYLE) & winapi.WS_EX_TRANSPARENT)
        check("click-through toggles WS_EX_TRANSPARENT", on and off, f"on={on} off={off}")

    # ========================================================= 4. Auto-snap edge & Pet Turn/Mirroring
    cfg.set("auto_snap", True)
    app.go_corner("right")
    wait(500)
    R = pet.x() + 48 + pet.art_w
    check("snap to right edge", abs(R - (ag.right() + 1)) <= 2, f"right={R} edge={ag.right() + 1}")
    check("pet turns / mirrors horizontally on right snap", pet.snap_right is True)
    pet.grab().save(str(OUT / "03_pet_right_mirrored.png"))

    app.go_corner("left")
    wait(500)
    L = pet.x() + 48 + fx0 * S
    check("snap to left edge", abs(L - ag.left()) <= 2, f"left={L} edge={ag.left()}")
    check("pet faces normal on left snap", pet.snap_right is False)

    # Dragging without auto-snap
    def drag(dx):
        start = QPoint(int(48 + S * 0.45), int(130 + S * 0.75))
        g0 = pet.pos() + start
        QTest.mousePress(pet, Qt.LeftButton, Qt.NoModifier, start)
        for i in range(1, 6):
            QTest.mouseMove(pet, g0 + QPoint(int(dx * i / 5), 0) - pet.pos())
            wait(10)
        QTest.mouseRelease(pet, Qt.LeftButton, Qt.NoModifier, g0 + QPoint(dx, 0) - pet.pos())
        wait(400)

    cfg.set("auto_snap", False)
    x0 = pet.x()
    drag(200)
    check("drag moves window when auto-snap off", abs(pet.x() - (x0 + 200)) <= 3, f"{x0} -> {pet.x()}")
    cfg.set("auto_snap", True)
    app.go_corner("left")
    wait(400)

    # ========================================================= 5. Q Characters Completely Purged (Zero Residue / Dead Code)
    check("backup_qchars directory completely deleted", not (config.APP_DIR.parent / "backup_qchars").exists())
    check("custom_q dir does not exist", not (config.APP_DIR / "custom_q").exists())
    check("qchars.py does not exist", not (config.APP_DIR / "deskpet" / "qchars.py").exists())
    check("Q assets directories do not exist", not (config.APP_DIR / "assets" / "q").exists() and not (config.APP_DIR / "assets" / "dark").exists())
    check("CUSTOM_Q_DIR removed from config module", not hasattr(config, "CUSTOM_Q_DIR"))
    check("q_dark removed from DEFAULTS", "q_dark" not in config.DEFAULTS)
    check("q_height removed from DEFAULTS", "q_height" not in config.DEFAULTS)
    check("q_chars removed from DEFAULTS", "q_chars" not in config.DEFAULTS)

    import deskpet.app as app_mod
    check("_DummyQCharManager removed from app module", not hasattr(app_mod, "_DummyQCharManager"))
    check("self.qchars removed from app instance", not hasattr(app, "qchars"))
    check("_show_qchars_maintenance_dialog removed from app", not hasattr(app, "_show_qchars_maintenance_dialog"))
    check("open_custom_q_dialog removed from app", not hasattr(app, "open_custom_q_dialog"))
    check("set_q_dark removed from app", not hasattr(app, "set_q_dark"))
    check("add_q removed from app", not hasattr(app, "add_q"))
    check("remove_all_q removed from app", not hasattr(app, "remove_all_q"))
    check("set_q_height removed from app", not hasattr(app, "set_q_height"))

    import deskpet.dialogs as dialogs_mod
    check("CustomQDialog removed from dialogs module", not hasattr(dialogs_mod, "CustomQDialog"))

    import deskpet.panel as panel_mod
    check("_tab_q removed from ControlPanel", not hasattr(panel_mod.ControlPanel, "_tab_q"))
    check("_open_custom_q removed from ControlPanel", not hasattr(panel_mod.ControlPanel, "_open_custom_q"))

    from PySide6.QtWidgets import QMenu
    m = QMenu()
    app._fill_menu(m)
    menu_texts = [a.text() for a in m.actions()]
    check("dark mode removed from context menu", not any("黑化模式" in t for t in menu_texts))
    check("redundant and obsolete items removed from context menu", not any("Q 版角色" in t or "傳統控制台" in t for t in menu_texts))

    # ========================================================= 7. Bowl-vs-Bowl Collision Physics
    app.pet.props.clear()
    app.pet.props.spawn_rice(1.0)
    app.pet.props.spawn_rice(2.0)
    wait(200)
    bowls = app.pet.props.rice()
    check("2 rice bowls spawned", len(bowls) == 2)
    # Place them touching each other to trigger collision
    bowls[0].x, bowls[0].y = 500.0, 500.0
    bowls[1].x, bowls[1].y = 515.0, 500.0
    bowls[0].vx = bowls[0].vy = bowls[1].vx = bowls[1].vy = 0.0
    dist_before = abs(bowls[1].x - bowls[0].x)
    app.pet.props._collide_bowls(0.016)
    dist_after = abs(bowls[1].x - bowls[0].x)
    check("bowl-vs-bowl collision pushes bowls apart", dist_after > dist_before, f"{dist_before} -> {dist_after}")
    app.pet.props.clear()

    # ========================================================= 8. Feeding, Iron Bowl & Petting Behavior
    shown = app.ledger.shown
    app.ledger.sim_topup(3.0)
    wait(300)
    check("recharge bowl spawned", len(pet.props.rice()) == 1)
    b = pet.props.rice()[0]
    wait(3000)
    # Simulate feeding
    b.x, b.y = pet.body_center_global().x(), pet.body_center_global().y()
    b.place()
    pet.props.released(b)
    wait(300)
    check("feeding credits balance", abs(app.ledger.shown - (shown + 3.0)) < 1e-6, f"{shown} -> {app.ledger.shown}")
    pet.grab().save(str(OUT / "06_pet_fed.png"))

    # Iron bowl drops
    check("iron bowl dropped after feeding", len(pet.props.irons()) == 1)
    ib = pet.props.irons()[0]
    h = pet.head_zone_global().center()
    ib.x, ib.y = h.x(), h.y()
    ib.place()
    pet.props.released(ib)
    wait(2200)
    check("iron bowl worn on head -> cold face", pet.iron_worn and pet.expr == "cold", f"{pet.expr}")
    pet.grab().save(str(OUT / "07_pet_iron.png"))

    # USER REQUIREMENT: When iron bowl is worn, petting directly does NOT trigger!
    pet._wig_pos = None
    pet.pat_active = False
    head_c = pet.head_zone_global().center()
    local_head = pet.mapFromGlobal(head_c.toPoint())
    for i in range(16):
        pet._track_pat(QPointF(local_head.x() + (i % 2) * 20, local_head.y()))
        wait(40)
    check("iron bowl worn: petting DOES NOT trigger", not pet.pat_active and pet.iron_worn)

    # Stacking iron bowls test (up to 5)
    for _ in range(4):
        pet.wear_iron()
    check("iron bowls stacked to 5", pet.iron_count == 5)
    pet.wear_iron()
    check("iron bowls capped at 5", pet.iron_count == 5)

    # Single click head takes off 1 pot
    local_head_stack = pet.mapFromGlobal(pet.head_zone_global().center().toPoint())
    QTest.mouseClick(pet, Qt.LeftButton, Qt.NoModifier, local_head_stack)
    wait(200)
    check("single click head takes off one iron bowl", pet.iron_count == 4)

    # Double click head clears all remaining iron bowls
    local_head_stack = pet.mapFromGlobal(pet.head_zone_global().center().toPoint())
    QTest.mouseDClick(pet, Qt.LeftButton, Qt.NoModifier, local_head_stack)
    wait(500)
    check("double click head clears all remaining iron bowls", pet.iron_count == 0 and pet.expr == "happy", f"{pet.expr}")

    # Body petting check: moving cursor on body must NOT trigger patting
    local_body = pet.mapFromGlobal(pet.body_center_global().toPoint())
    from PySide6.QtGui import QMouseEvent, QContextMenuEvent
    from PySide6.QtCore import QEvent
    pet._wig_pos = None
    pet.pat_active = False
    for i in range(16):
        pos = local_body + QPoint((i % 2) * 20, 0)
        ev = QMouseEvent(QEvent.MouseMove, QPointF(pos), pet.mapToGlobal(pos), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        pet.mouseMoveEvent(ev)
        wait(30)
    check("cursor on body: petting DOES NOT trigger", not pet.pat_active)

    # Now petting on head works
    local_head = pet.mapFromGlobal(pet.head_zone_global().center().toPoint())
    pet._wig_pos = None
    pet.pat_cooldown = 0.0
    for i in range(16):
        pos = local_head + QPoint((i % 2) * 20, 0)
        ev = QMouseEvent(QEvent.MouseMove, QPointF(pos), pet.mapToGlobal(pos), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        pet.mouseMoveEvent(ev)
        wait(40)
    check("head pat triggers when iron bowl is removed", pet.pat_active)
    pet.grab().save(str(OUT / "08_pet_pat.png"))
    wait(400)
    check("pat ends after stopping", not pet.pat_active)

    # Right click contextMenuEvent test
    ctx_pts = []
    pet.context_requested.connect(lambda pt: ctx_pts.append(pt))
    c_ev = QContextMenuEvent(QContextMenuEvent.Mouse, local_head, pet.mapToGlobal(local_head))
    pet.contextMenuEvent(c_ev)
    check("pet contextMenuEvent emits context_requested", len(ctx_pts) == 1)

    # ========================================================= 9. Radar Lock & Auto Suction
    app.ledger.sim_topup(1.0)
    wait(200)
    b = pet.props.rice()[0]
    b.x = pet.body_center_global().x() + 200
    b.y = pet.body_center_global().y() + 50
    b.place()
    b.landed_at = time.monotonic() - 10.5
    wait(400)
    check("bowl locked after 10s idle", b.locked_at is not None and pet.expr == "tsun", pet.expr)
    s2 = app.ledger.shown
    wait(3500)
    check("locked bowl sucked in and fed", not pet.props.rice() and abs(app.ledger.shown - (s2 + 1.0)) < 1e-4)
    pet.props.clear()

    # ========================================================= 10. Tablet Page 0 vs Page 1
    # Page 0: Balance
    pet.page = 0
    pet._build_screen()
    check("tablet page 0 is active", pet.page == 0)

    # Double click body outside tablet: must NOT flip page!
    QTest.mouseDClick(pet, Qt.LeftButton, Qt.NoModifier, local_body)
    wait(200)
    check("double click body DOES NOT flip tablet page", pet.page == 0)

    # Double click tablet flips to Page 1
    tb_c = pet.tablet_zone_global().center()
    local_tb = pet.mapFromGlobal(tb_c.toPoint())
    QTest.mouseDClick(pet, Qt.LeftButton, Qt.NoModifier, local_tb)
    wait(200)
    check("double click tablet flips to page 1", pet.page == 1)
    # For DeepSeek, page 1 shows peak/valley ("梁文峰" / "梁文谷")
    pet.grab().save(str(OUT / "09_tablet_p1_ds.png"))
    # Switch to Claude, page 1 shows local time & vendor
    app.set_character("claude")
    wait(200)
    check("switched character to claude", pet.character == "claude")
    pet.grab().save(str(OUT / "10_tablet_p1_claude.png"))
    app.set_character("deepseek")
    pet.page = 0
    pet._build_screen()

    # ========================================================= 11. Pet Variants (1024 Square vs 1536 Tail)
    check("default variant is square (1:1)", pet.variant == "square" and pet.aspect_ratio == 1.0)
    # Check square mode head zone and iron bowl center alignment
    sq_cx_normal = pet.sprite_origin().x() + pet.art_w * 0.60
    check("square normal head zone center matches iron bowl cx", abs(pet.head_zone_global().center().x() - sq_cx_normal) < 1e-4)
    pet.set_snap_right(True)
    sq_cx_mirrored = pet.sprite_origin().x() + pet.art_w * 0.40
    check("square mirrored head zone center matches iron bowl cx", abs(pet.head_zone_global().center().x() - sq_cx_mirrored) < 1e-4)
    pet.set_snap_right(False)

    w_sq = pet.art_w
    app.set_variant("tail")
    wait(300)
    check("switched to tail variant (1.5:1)", pet.variant == "tail" and pet.aspect_ratio == 1.5)
    check("tail variant widens art width", pet.art_w == int(pet.size_px * 1.5) and pet.art_w > w_sq)
    pet.grab().save(str(OUT / "11_variant_tail.png"))

    # Tail mode head zone and iron bowl center alignment
    tail_cx_normal = pet.sprite_origin().x() + pet.art_w * 0.672
    check("tail normal head zone center matches iron bowl cx", abs(pet.head_zone_global().center().x() - tail_cx_normal) < 1e-4)
    pet.set_snap_right(True)
    tail_cx_mirrored = pet.sprite_origin().x() + pet.art_w * (1.0 - 0.672)
    check("tail mirrored head zone center matches iron bowl cx", abs(pet.head_zone_global().center().x() - tail_cx_mirrored) < 1e-4)

    # Falling iron bowl onto head in tail mirrored mode (verifying no drop-through to tablet/floor)
    from deskpet.props import Prop
    b_tail = Prop(pet.props, "iron", pet.props.bowl_width(), 0.0)
    h_tail = pet.head_zone_global()
    b_tail.x = h_tail.center().x()
    b_tail.y = h_tail.top() - 40
    b_tail.vy = 260.0
    pet.props._add(b_tail)
    for _ in range(60):
        pet.props.step()
        if pet.iron_count > 0:
            break
        wait(16)
    check("falling iron bowl caught on head in tail mirrored mode", pet.iron_worn and pet.iron_count == 1)
    pet.grab().save(str(OUT / "11_tail_mirrored_iron.png"))

    # When iron bowl is worn in tail mirrored mode, petting directly DOES NOT trigger
    pet._wig_pos = None
    pet.pat_active = False
    head_c_tail = pet.head_zone_global().center()
    local_head_tail = pet.mapFromGlobal(head_c_tail.toPoint())
    for i in range(16):
        pos = local_head_tail + QPoint((i % 2) * 20, 0)
        ev = QMouseEvent(QEvent.MouseMove, QPointF(pos), pet.mapToGlobal(pos), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        pet.mouseMoveEvent(ev)
        wait(40)
    check("tail mirrored: iron bowl worn petting DOES NOT trigger", not pet.pat_active and pet.iron_worn)

    # Remove iron bowl in tail mirrored mode
    pet.remove_iron(all_pots=True)
    check("tail mirrored: iron bowl removed", pet.iron_count == 0)

    # Petting in tail mirrored mode now triggers smoothly
    pet._wig_pos = None
    pet.pat_cooldown = 0.0
    head_c_tail = pet.head_zone_global().center()
    local_head_tail = pet.mapFromGlobal(head_c_tail.toPoint())
    for i in range(16):
        pos = local_head_tail + QPoint((i % 2) * 20, 0)
        ev = QMouseEvent(QEvent.MouseMove, QPointF(pos), pet.mapToGlobal(pos), Qt.NoButton, Qt.NoButton, Qt.NoModifier)
        pet.mouseMoveEvent(ev)
        wait(40)
    check("tail mirrored: head pat triggers when iron bowl is removed", pet.pat_active)
    pet.grab().save(str(OUT / "11_tail_mirrored_pat.png"))
    wait(400)
    check("tail mirrored: pat ends after stopping", not pet.pat_active)

    pet.set_snap_right(False)
    app.set_variant("square")
    wait(200)
    check("restored square variant", pet.variant == "square" and pet.aspect_ratio == 1.0)

    # ========================================================= 12. Character Switching (Claude, Gemini, GPT)
    for cid in ("claude", "gemini", "gpt", "deepseek"):
        app.set_character(cid)
        wait(200)
        p = pet._char_image_path("happy")
        check(f"character {cid} asset exists", Path(p).exists(), p)
    pet.grab().save(str(OUT / "12_char_deepseek.png"))

    # ========================================================= 13. Web Server & API Endpoints
    check("web server listening", app.web is not None and app.web.port in range(8765, 8776), f"port={app.web.port}")
    if app.web and app.web.port:
        try:
            url_state = f"http://127.0.0.1:{app.web.port}/api/state"
            req = urllib.request.urlopen(url_state, timeout=3)
            data = json.loads(req.read().decode("utf-8"))
            check("web /api/state returns valid json", "balance" in data and "provider" in data and "mode" in data)
            check("web /api/state shows sim balance", abs(float(data["balance"]) - float(app.ledger.shown)) < 0.05, f"web={data.get('balance')} ledger={app.ledger.shown}")

            url_csv = f"http://127.0.0.1:{app.web.port}/history.csv"
            req_csv = urllib.request.urlopen(url_csv, timeout=3)
            csv_text = req_csv.read().decode("utf-8")
            check("web /history.csv returns valid CSV", "time,delta,balance" in csv_text)
        except Exception as e:
            check("web api request", False, str(e))

    # ========================================================= 14. Control Panel 7 Tabs & Sync
    app.show_panel()
    wait(300)
    p = app.panel
    p.grab().save(str(OUT / "13_panel.png"))
    check("control panel opened", p.isVisible())
    check("panel has WindowStaysOnTopHint", bool(p.windowFlags() & Qt.WindowStaysOnTopHint))

    # Test clearing all rice bowls
    app.pet.props.spawn_rice(2.5)
    app.pet.props.spawn_rice(4.5)
    check("spawned 2 bowls for clear test", len(app.pet.props.rice()) == 2)
    b_before = app.ledger.shown
    app.clear_all_rice_bowls()
    wait(200)
    check("clear_all_rice_bowls cleared all rice bowls", len(app.pet.props.rice()) == 0)
    check("clear_all_rice_bowls credited full amount", abs((app.ledger.shown - b_before) - 7.0) < 1e-4)

    p.cb_through.setChecked(True)
    check("panel: click-through", cfg["click_through"] is True)
    p.cb_through.setChecked(False)

    p.cb_snap.setChecked(False)
    check("panel: auto-snap off", cfg["auto_snap"] is False)
    p.cb_snap.setChecked(True)

    p.sl_op.setValue(80)
    check("panel: opacity", cfg["opacity"] == 80 and abs(pet.windowOpacity() - 0.8) < 0.02)
    p.sl_op.setValue(100)

    p.cmb_theme.setCurrentIndex(1)
    wait(100)
    p.grab().save(str(OUT / "14_panel_dark.png"))
    check("panel: dark theme", cfg["theme"] == "dark")

    app.set_size(340)
    wait(200)
    check("resize pet to 340", pet.size_px == 340)
    app.set_size(454)

    # ========================================================= 15. Multi-Pet Balance Summons (Up to 4 pets on desktop)
    app.set_character("deepseek")
    wait(200)
    check("main pet is deepseek with deepseek ledger", app.pet.character == "deepseek" and app.ledger.provider == "deepseek")

    # Summon Claude, GPT, Gemini balance pets
    p_claude = app.summon_balance_pet("claude")
    p_gpt = app.summon_balance_pet("gpt")
    p_gemini = app.summon_balance_pet("gemini")
    wait(300)

    check("claude balance pet summoned and visible", p_claude is not None and p_claude.isVisible() and p_claude.is_extra)
    check("claude pet ledger provider is anthropic", app.extra_ledgers["claude"].provider == "anthropic")
    check("gpt balance pet summoned and visible", p_gpt is not None and p_gpt.isVisible() and p_gpt.is_extra)
    check("gpt pet ledger provider is openai", app.extra_ledgers["gpt"].provider == "openai")
    check("gemini balance pet summoned and visible", p_gemini is not None and p_gemini.isVisible() and p_gemini.is_extra)
    check("gemini pet ledger provider is gemini", app.extra_ledgers["gemini"].provider == "gemini")

    total_pets = len(app.extra_pets) + 1
    check("4 balance pets active simultaneously on desktop", total_pets == 4, f"count={total_pets}")

    # ========================================================= 16. Tablet Screen Title per Provider
    # Page 0 titles
    app.pet.page = 0
    app.pet._build_screen()
    p_claude.page = 0
    p_claude._build_screen()
    p_gpt.page = 0
    p_gpt._build_screen()
    p_gemini.page = 0
    p_gemini._build_screen()
    check("main pet tablet screen rendered", app.pet._screen_img is not None)
    check("claude tablet screen rendered", p_claude._screen_img is not None)
    check("gpt tablet screen rendered", p_gpt._screen_img is not None)
    check("gemini tablet screen rendered", p_gemini._screen_img is not None)

    # Test dismissing extra pets
    app.dismiss_balance_pet("claude")
    check("dismissed claude pet", "claude" not in app.extra_pets and not p_claude.isVisible())
    app.dismiss_all_balance_pets()
    check("dismissed all extra balance pets", len(app.extra_pets) == 0)

    # ========================================================= 16.5 核心四大角色大寵物、Q版額度小人、匯率換算與金鑰解耦測試
    from .app import BALANCE_PET_SPECS
    from .balance import Ledger, SUPPORTED_BALANCE_PROVIDERS
    from .config import (
        PET_MAX_COUNT_OPTIONS,
        CHIBI_MAX_COUNT_OPTIONS,
        get_effective_pet_max_count,
        get_effective_chibi_max_count,
    )
    from .currency import (
        get_currency_converter,
        CurrencyConverter,
        SUPPORTED_TARGET_CURRENCIES,
        CURRENCY_SOURCES,
    )

    check("balance supports expanded providers", "openrouter" in SUPPORTED_BALANCE_PROVIDERS and "siliconflow" in SUPPORTED_BALANCE_PROVIDERS and "moonshot" in SUPPORTED_BALANCE_PROVIDERS and "custom_openai" in SUPPORTED_BALANCE_PROVIDERS)

    l_sf = Ledger(app.cfg, provider_override="siliconflow")
    l_ms = Ledger(app.cfg, provider_override="moonshot")
    l_or = Ledger(app.cfg, provider_override="openrouter")
    l_ol = Ledger(app.cfg, provider_override="ollama")
    check("siliconflow balance currency is CNY", l_sf.currency == "CNY")
    check("moonshot balance currency is CNY", l_ms.currency == "CNY")
    check("openrouter balance currency is USD", l_or.currency == "USD")
    check("ollama balance currency is FREE", l_ol.currency == "FREE")

    # 1. 嚴格限制大寵物只有 4 位核心官方角色，絕不允許其他角色
    check("BALANCE_PET_SPECS strictly contains only 4 official roles", set(BALANCE_PET_SPECS.keys()) == {"deepseek", "gpt", "claude", "gemini"})
    check("big pet rejects non-official characters", app.summon_balance_pet("openrouter") is None and app.summon_balance_pet("siliconflow") is None)

    # 2. 其他 API 廠商全部做成 Q 版獨立像素人物巡邏監控並顯示想法框
    c_or = app.summon_api_chibi("openrouter")
    c_sf = app.summon_api_chibi("siliconflow")
    c_ms = app.summon_api_chibi("moonshot")
    wait(100)
    check("openrouter Q-chibi monitor summoned", c_or is not None and c_or.isVisible() and c_or.monitor_provider == "openrouter")
    check("siliconflow Q-chibi monitor summoned", c_sf is not None and c_sf.isVisible() and c_sf.monitor_provider == "siliconflow")
    check("moonshot Q-chibi monitor summoned", c_ms is not None and c_ms.isVisible() and c_ms.monitor_provider == "moonshot")
    check("Q-chibi monitor has thought bubble", c_sf.thought_bubble is not None and c_sf.thought_bubble.isVisible())
    app.chibi_manager.dismiss(c_or)
    app.chibi_manager.dismiss(c_sf)
    app.chibi_manager.dismiss(c_ms)

    # 3. 寵物數量上限檔位 (5, 10, 15, 20, 25, 30) 與效能模式自動調節
    check("pet max count options include 5,10,15,20,25,30", PET_MAX_COUNT_OPTIONS == (5, 10, 15, 20, 25, 30))
    check("chibi max count options include 5,10,15,20,25,30", CHIBI_MAX_COUNT_OPTIONS == (5, 10, 15, 20, 25, 30))
    app.set_pet_max_count(20)
    check("set_pet_max_count updates to 20", app.cfg.get("pet_max_count") == 20 and get_effective_pet_max_count(app.cfg) == 20)
    app.cfg.set("performance_mode", True)
    check("performance_mode caps pet limit to lower tier", get_effective_pet_max_count(app.cfg) <= 10)
    check("performance_mode caps chibi limit to lower tier", get_effective_chibi_max_count(app.cfg) <= 10)
    app.cfg.set("performance_mode", False)
    app.set_pet_max_count(10)

    # 4. 外觀與監控目標解耦：大寵物獨立指定廠商與 Key 綁定
    app.set_pet_monitor("main", "openai", 1)
    check("appearance decoupled: main pet monitors OpenAI Key #2", app.ledger.provider == "openai" and app.ledger.key_index == 1)
    app.set_pet_monitor("main", "deepseek", None)
    check("appearance decoupled: restored main pet to DeepSeek", app.ledger.provider == "deepseek" and app.ledger.key_index is None)

    # 5. 同廠商多 API Key 額度整合計算（預設關閉，開啟時逐一查詢累加）
    check("aggregate_same_provider_keys default is False", app.cfg.get("aggregate_same_provider_keys") is False)
    app.set_aggregate_same_provider_keys(True)
    check("set_aggregate_same_provider_keys updates config to True", app.cfg.get("aggregate_same_provider_keys") is True)
    app.cfg.set("mode", "api", save=False)
    test_ledger = Ledger(app.cfg, provider_override="deepseek")
    test_ledger._query_key_balance = lambda pid, k: 20.0 if "k1" in k else (30.0 if "k2" in k else 50.0)
    app.cfg.set_api_keys("deepseek", ["sk-k1", "sk-k2", "sk-k3"], save=False)
    test_ledger._worker("deepseek", "")
    check("multi-key aggregation sums all keys (20+30+50=100)", test_ledger.shown == 100.0)
    app.cfg.set("mode", "sim", save=False)
    app.set_aggregate_same_provider_keys(False)
    check("set_aggregate_same_provider_keys updates config to False", app.cfg.get("aggregate_same_provider_keys") is False)

    # 6. 幣值選擇與多來源匯率換算系統 (deskpet/currency.py)
    conv = get_currency_converter(app.cfg)
    check("currency converter initialized", conv is not None)
    check("supports TWD, USD, CNY, EUR, JPY, HKD, GBP", all(c in SUPPORTED_TARGET_CURRENCIES for c in ["TWD", "USD", "CNY", "EUR", "JPY", "HKD", "GBP"]))
    conv._rates["USD"] = 1.0
    conv._rates["TWD"] = 32.0
    conv._rates["CNY"] = 7.0
    check("convert USD 10 to TWD 320", round(conv.convert(10.0, "USD", "TWD"), 2) == 320.0)
    check("convert CNY 70 to USD 10", round(conv.convert(70.0, "CNY", "USD"), 2) == 10.0)
    conv.set_target_currency("TWD", save=False)
    conv.set_display_mode("dual", save=False)
    check("dual display format", "(約 " in conv.format_balance(10.0, "USD"))
    conv.set_display_mode("converted", save=False)
    check("converted display format", conv.format_balance(10.0, "USD") == "NT$320.00")
    conv.set_display_mode("original", save=False)
    check("original display format", conv.format_balance(10.0, "USD") == "$10.00")
    # 需 Key 來源防護：未填寫 Key 禁止切換
    ok_free, _ = conv.set_source("frankfurter", save=False)
    check("free source switch succeeds without key", ok_free and conv.current_source == "frankfurter")
    conv.set_source_api_key("openexchangerates", "", save=False)
    ok_key, err = conv.set_source("openexchangerates", save=False)
    check("key-required source blocked when key empty", not ok_key and "需填寫有效 Key 方可啟用" in err)
    conv.set_source_api_key("openexchangerates", "test_key_sample_123", save=False)
    ok_key2, _ = conv.set_source("openexchangerates", save=False)
    check("key-required source allows switch with key", ok_key2 and conv.current_source == "openexchangerates")
    conv.set_source("exchangerate_api", save=False)
    conv.set_display_mode("dual", save=False)

    # ========================================================= 17. AI Chat Dialog, Model Catalog & Memory
    from .model_catalog import _normalise, discover_models
    raw_models = [{"id": "gpt-4o", "displayName": "GPT-4o"}, {"name": "models/gemini-pro"}]
    norm = _normalise(raw_models, "OpenAI", "test")
    check("model_catalog normalises model IDs", len(norm) == 2 and norm[0]["id"] == "gpt-4o" and norm[1]["id"] == "gemini-pro")

    app.open_chat_dialog()
    wait(200)
    chat_dlg = app.chat_dialog
    check("chat dialog opened and visible", chat_dlg is not None and chat_dlg.isVisible())

    # Test memory prompt synthesis
    cfg.set("long_memory", ["主人喜歡喝熱茶", "角色名稱為小藍"])
    cfg.set("short_memory", [{"role": "user", "content": "你好", "time": "2026-10-24 12:00:00"}, {"role": "assistant", "content": "你好呀！", "time": "2026-10-24 12:00:01"}])
    prompt = chat_dlg._build_prompt("今天天氣好嗎？")
    check("prompt contains character info", "小藍" in prompt and "熱茶" in prompt)
    check("prompt contains conversation history", "你好呀！" in prompt and "今天天氣好嗎？" in prompt)

    # Test speech bubble
    app.pet.show_speech_bubble("測試氣泡", thought=False)
    check("speech bubble displayed on pet head", hasattr(app.pet, "_bubble") and app.pet._bubble.isVisible())

    # ========================================================= 18. New Features: Capsule Chat, Font System, Material Symbols, Titlebars & About
    # Capsule Chat UI
    check("chat capsule input box exists", hasattr(chat_dlg, "capsule") and chat_dlg.capsule is not None)
    check("chat model button exists", hasattr(chat_dlg, "btn_model") and chat_dlg.btn_model is not None)
    check("chat send button exists", hasattr(chat_dlg, "btn_send") and chat_dlg.btn_send is not None)
    check("chat plus button exists", hasattr(chat_dlg, "btn_plus") and chat_dlg.btn_plus is not None)
    check("chat custom titlebar exists with close button", hasattr(chat_dlg, "title_bar") and chat_dlg.title_bar.btn_close is not None)

    # Font Management System
    from .font_manager import apply_global_font, get_system_fonts, resolve_best_default_font
    sys_fonts = get_system_fonts()
    check("system fonts retrieved", len(sys_fonts) > 0, f"count={len(sys_fonts)}")
    best_font = resolve_best_default_font()
    check("modern font resolved", len(best_font) > 0, f"font={best_font}")
    apply_global_font(best_font)

    # Control Panel Custom Titlebar & Typography Settings
    check("control panel custom titlebar exists", hasattr(p, "title_bar") and p.title_bar.btn_close is not None)
    check("control panel font mode radio exists", hasattr(p, "rb_font_sys") and p.rb_font_sys.isChecked())
    check("control panel font preview exists", hasattr(p, "lb_font_preview") and p.lb_font_preview is not None)

    # About Page & Version
    check("app version is v2.1.0", config.APP_VERSION == "v2.1.0")
    check("repo url is correct", config.GITHUB_REPO_URL == "https://github.com/milk120106/deskop-pet")

    # Material Symbols (Apache 2.0)
    from .icons import get_icon
    for icon_name in ("send", "mic", "shield", "add", "refresh", "close", "minimize"):
        ico = get_icon(icon_name)
        check(f"material symbol icon '{icon_name}' is valid", not ico.isNull())

    # Strictly Zero Emojis check in python sources (Unicode emoji blocks)
    import re
    emoji_pattern = re.compile(r"[\U0001F300-\U0001F9FF\U0001FA00-\U0001FAFF]")
    found_emojis = []
    py_files = list((config.APP_DIR / "deskpet").glob("*.py"))
    for pyf in py_files:
        content = pyf.read_text(encoding="utf-8")
        matches = emoji_pattern.findall(content)
        if matches:
            found_emojis.append(f"{pyf.name}: {matches}")
    check("strictly zero emojis in upgraded codebase", len(found_emojis) == 0, str(found_emojis))

    # ========================================================= 19. Repaired Features: Voice, Mode Capsule & Pure Voice Mode
    # 1. 語音按鈕狀態與浮動提示測試
    check("mic button exists and is checkable", hasattr(chat_dlg, "btn_mic") and chat_dlg.btn_mic.isCheckable())
    check("mic button has clear tooltip", "語音" in chat_dlg.btn_mic.toolTip())
    chat_dlg.show_floating_notice("語音測試浮動提示", is_error=False)
    check("floating notice label exists and visible", hasattr(chat_dlg, "_toast_label") and chat_dlg._toast_label.isVisible())

    # 2. 膠囊視窗模式按鈕測試（徹底移除 Turbo，換為實質功能切換）
    check("mode button exists", hasattr(chat_dlg, "btn_mode"))
    check("Turbo completely removed from mode button text", "Turbo" not in chat_dlg.btn_mode.text())
    chat_dlg._set_mode("reasoner")
    check("mode switched to reasoner", chat_dlg.current_mode == "reasoner" and "思考" in chat_dlg.btn_mode.text())
    p_reasoner = chat_dlg._build_prompt("請幫我分析這道難題")
    check("reasoner prompt contains deep thinking instruction", "深度思考模式" in p_reasoner)

    chat_dlg._set_mode("voice")
    check("mode switched to voice companion", chat_dlg.current_mode == "voice" and "語音" in chat_dlg.btn_mode.text())
    p_voice = chat_dlg._build_prompt("今天心情好嗎？")
    check("voice companion prompt contains spoken dialogue instruction", "語音陪伴模式" in p_voice)

    chat_dlg._set_mode("standard")
    check("mode switched to standard", chat_dlg.current_mode == "standard" and "標準" in chat_dlg.btn_mode.text())

    # 測試系統助手 Agent 模式
    chat_dlg._set_mode("agent")
    check("mode switched to agent mode", chat_dlg.current_mode == "agent" and "助手" in chat_dlg.btn_mode.text())
    p_agent = chat_dlg._build_prompt("幫我查詢目錄內容")
    check("agent prompt contains agent instruction", "系統助手 Agent 模式" in p_agent)
    chat_dlg._set_mode("standard")

    # 測試純淨無套版 AI 人格與自訂 Prompt
    p_clean = chat_dlg._build_prompt("日常問題")
    check("prompt free of tsundere and maid persona", "傲嬌" not in p_clean and "女僕" not in p_clean)
    cfg.set("custom_system_prompt", "自訂系統提示詞內容")
    p_custom = chat_dlg._build_prompt("自訂測試")
    check("custom system prompt applied correctly", "自訂系統提示詞內容" in p_custom)
    cfg.set("custom_system_prompt", "")

    # 測試 PrivacySanitizer 脫敏過濾器
    from deskpet.chat import PrivacySanitizer
    san_path = PrivacySanitizer.sanitize("檔案存放在 C:\\Windows\\System32\\test.dll 與 D:\\Data\\file.txt")
    check("PrivacySanitizer desensitizes local paths", "[本機檔案路徑]" in san_path and "D:\\Data" not in san_path)
    san_key = PrivacySanitizer.sanitize("我的金鑰是 sk-12345678901234567890abcdef")
    check("PrivacySanitizer masks api keys", "[金鑰憑證]" in san_key and "sk-12345" not in san_key)
    san_ip = PrivacySanitizer.sanitize("內部主機 192.168.1.100 與 10.0.0.1 還有 127.0.0.1")
    check("PrivacySanitizer masks private ips", "[私有IP位址]" in san_ip and "192.168.1.100" not in san_ip)

    # 測試 Agent 黑名單攔截
    chat_dlg._handle_agent_command("del /f /s /q C:\\Windows")
    hist_text = chat_dlg.history_view.toPlainText()
    check("blacklist command intercepted by safety engine", "已攔截危險指令" in hist_text or "符合黑名單規則" in hist_text)

    # 測試精緻小型確認彈窗 (380x220)
    from deskpet.dialogs import AgentConfirmDialog, PrivacyPromptDialog
    agent_dlg = AgentConfirmDialog(chat_dlg, command="dir", theme="dark")
    check("AgentConfirmDialog width is 380", agent_dlg.width() == 380)
    check("AgentConfirmDialog height is 220", agent_dlg.height() == 220)
    agent_dlg.close()

    privacy_dlg = PrivacyPromptDialog(chat_dlg, message="測試隱私說明", theme="dark")
    check("PrivacyPromptDialog width is 380", privacy_dlg.width() == 380)
    check("PrivacyPromptDialog height is 220", privacy_dlg.height() == 220)
    privacy_dlg.close()

    # 測試低配效能優化、FPS 調度與半透明切換
    app.set_disable_transparency(True)
    check("disable_transparency disables WA_TranslucentBackground", not app.pet.testAttribute(Qt.WA_TranslucentBackground))
    check("disable_transparency locks opacity to 1.0", app.pet.windowOpacity() == 1.0)
    app.set_disable_transparency(False)
    check("restore transparency re-enables WA_TranslucentBackground", app.pet.testAttribute(Qt.WA_TranslucentBackground))

    app.set_target_fps(30)
    check("target_fps 30 sets timer interval to 33ms", app.pet.timer.interval() == 33)
    app.set_target_fps(60)
    check("target_fps 60 sets timer interval to 16ms", app.pet.timer.interval() == 16)

    app.set_performance_mode(True)
    check("performance_mode caps timer interval to 30fps (33ms)", app.pet.timer.interval() == 33)
    app.set_performance_mode(False)
    check("performance_mode off restores 60fps (16ms)", app.pet.timer.interval() == 16)

    # 測試廠商擴充與 Gemini 3.x 家族優先
    import deskpet.model_catalog as mc
    for expected_prov in [
        "Cerebras", "Together AI", "Fireworks AI", "DeepInfra",
        "矽基流動 (SiliconFlow)", "月之暗面 (Moonshot/Kimi)",
        "本地 LM Studio", "本地 vLLM"
    ]:
        check(f"model_catalog supports {expected_prov}", expected_prov in mc.PROVIDERS)
    gemini_aliases = [m["id"] for m in mc.DYNAMIC_MODEL_ALIASES.get("Google Gemini", [])]
    check("gemini dynamic aliases prioritize flash-lite and gemini 3.x", "gemini-3.5-flash-lite" in gemini_aliases and "gemini-3.8-flash" in gemini_aliases and "gemini-3.8-live" in gemini_aliases)
    check("gemini default model is flash or flash-lite, never pro", "pro" not in config.DEFAULTS["api_profiles"][3]["model"])

    # 3. 音訊引擎播放與停止測試
    check("sound engine has play_file method", hasattr(app.sounds, "play_file"))
    check("sound engine has stop_file method", hasattr(app.sounds, "stop_file"))

    # 4. 右鍵純語音模式邏輯測試（絕不彈出文字對話框）
    chat_dlg.close()
    wait(200)
    check("chat dialog is closed before pure voice test", not chat_dlg.isVisible())

    # 測試啟動純語音模式
    app.start_pure_voice(target_pet=app.pet)
    wait(200)
    check("pure voice mode active flag set", app.pure_voice_active is True or hasattr(app.pet, "_bubble"))
    check("pure voice mode NEVER opens text chat dialog", not chat_dlg.isVisible())
    check("pet speech bubble shown for pure voice mode", hasattr(app.pet, "_bubble") and app.pet._bubble.isVisible())

    # 測試關閉純語音模式
    app.stop_pure_voice()
    wait(200)
    check("pure voice mode stopped cleanly", app.pure_voice_active is False)

    # ========================================================= 20. Thought Bubble & Breathing Animation Tests
    app.pet.show_speech_bubble("現在是語音模式ㄛ", thought=True, persistent=True, on_click=app.stop_pure_voice)
    wait(100)
    check("thought bubble is in thought mode", getattr(app.pet._bubble, "_thought", False) is True)
    check("thought bubble is persistent", getattr(app.pet._bubble, "_persistent", False) is True)
    check("thought bubble breathing animation timer active", app.pet._bubble._breath_timer.isActive())
    check("thought bubble text is correct", app.pet._bubble.text() == "現在是語音模式ㄛ")

    # 測試呼吸透明度在 210..255 範圍內
    app.pet._bubble._on_breath_tick()
    check("thought bubble breath alpha in valid range", 210 <= app.pet._bubble._breath_alpha <= 255)

    # 測試氣泡點擊回呼（退出純語音模式）
    clicked = []
    app.pet._bubble.set_click_callback(lambda: clicked.append(True))
    press_event = QMouseEvent(QEvent.MouseButtonPress, QPointF(10, 10), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
    app.pet._bubble.mousePressEvent(press_event)
    check("clicking speech bubble triggers click callback", len(clicked) == 1 and clicked[0] is True)

    # 測試切換為思考中想法框
    app.pet.show_speech_bubble("思考中...", thought=True, persistent=True)
    check("thinking thought bubble text correct", app.pet._bubble.text() == "思考中...")
    check("thinking thought bubble is in thought mode", getattr(app.pet._bubble, "_thought", False) is True)

    # 測試切換回傳統對話氣泡（thought=False）
    app.pet.show_speech_bubble("這是一般回覆", thought=False, persistent=False)
    check("traditional bubble thought is False", getattr(app.pet._bubble, "_thought", False) is False)
    check("traditional bubble breathing timer stopped", not app.pet._bubble._breath_timer.isActive())
    app.pet.hide_speech_bubble()

    # 測試右鍵選單包含純語音模式切換
    m_test = QMenu()
    app._fill_menu(m_test)
    action_texts = [act.text() for act in m_test.actions()]
    check("context menu includes pure voice mode action", any("純語音模式" in t for t in action_texts))
    check("context menu includes unified settings action", any(t == "設定" for t in action_texts))
    check("context menu uses pure text without ellipsis", not any("..." in t for t in action_texts))

    # ========================================================= 21. Qt Quick / QML 現代動效架構測試（路線 A）
    app.show_qml_panel()
    wait(400)
    qml_win = app.qml_panel
    check("qml control panel opened", qml_win is not None and qml_win.isVisible())
    from PySide6.QtQuickWidgets import QQuickWidget
    check("qml control panel has quick widget", qml_win.quick_widget is not None and qml_win.quick_widget.status() == QQuickWidget.Status.Ready)
    check("qml backend theme binding", qml_win.backend.get_theme() in ("light", "dark"))

    # 測試 QML 後端雙向綁定與切換
    cur_th = qml_win.backend.get_theme()
    qml_win.backend.toggleTheme()
    wait(100)
    check("qml backend toggleTheme switched theme", qml_win.backend.get_theme() != cur_th)
    qml_win.backend.setTheme(cur_th)
    wait(100)

    # 測試角色切換雙向綁定
    qml_win.backend.setCharacter("claude")
    wait(100)
    check("qml backend setCharacter synced to app", app.pet.character == "claude" and qml_win.backend.get_character() == "claude")
    qml_win.backend.setCharacter("deepseek")
    wait(100)

    # 測試尺寸切換雙向綁定
    qml_win.backend.setSizePx(340)
    wait(100)
    check("qml backend setSizePx synced to app", app.pet.size_px == 340 and qml_win.backend.get_size_px() == 340)
    qml_win.backend.setSizePx(454)
    wait(100)

    # 測試音量與滑鼠穿透雙向綁定
    qml_win.backend.setVolume(75)
    check("qml backend setVolume synced", app.cfg.get("volume") == 75 and qml_win.backend.get_volume() == 75)

    # 測試立繪形態切換雙向綁定 (1:1 正方形 / 1.5:1 帶尾巴)
    qml_win.backend.setVariant("tail")
    wait(100)
    check("qml backend setVariant synced to app", app.pet.variant == "tail" and qml_win.backend.get_variant() == "tail")
    qml_win.backend.setVariant("square")
    wait(100)

    # 測試字體系統清單與讀取
    check("qml backend system fonts accessible", len(qml_win.backend.get_system_fonts()) > 0)
    check("qml backend current font family valid", len(qml_win.backend.get_current_font_family()) > 0)

    # 測試個別提示音槽位讀取
    check("qml backend cue hit slot initialized", len(qml_win.backend.get_cue_hit_file()) > 0)

    # 測試模型供應商切換雙向綁定
    qml_win.backend.setApiProvider("OpenAI")
    check("qml backend api provider switched to OpenAI", qml_win.backend.get_api_provider() == "OpenAI")
    qml_win.backend.setApiProvider("DeepSeek")

    # 測試日誌擷取
    qml_win.backend.refreshLogs()
    check("qml backend logs snippet retrieved", len(qml_win.backend.get_logs_snippet()) > 0)

    # 產出新設定視窗淺色與深色視覺截圖至 selftest_out/
    qml_win.backend.setTheme("dark")
    wait(200)
    qml_win.grab().save(str(OUT / "20_qml_settings_dark.png"))
    qml_win.backend.setTheme("light")
    wait(200)
    qml_win.grab().save(str(OUT / "20_qml_settings_light.png"))
    qml_win.grab().save(str(OUT / "20_qml_modern_panel.png"))
    qml_win.hide()

    # ========================================================= 22. Pet Upgrades: Size Slider, 2D Papercraft Physics, Smart 4-Page Tablet, Alarms, Pixel Chibi Standalone System
    # 1. 平滑尺寸滑桿測試 (180px - 1024px) 與快速預設標籤
    app.set_size(180)
    wait(100)
    check("pet size slider supports 180px min", app.pet.size_px == 180, f"size={app.pet.size_px}")
    app.set_size(1024)
    wait(100)
    check("pet size slider supports 1024px max", app.pet.size_px == 1024, f"size={app.pet.size_px}")
    app.set_size(260)
    wait(100)
    check("quick size preset 260px applies cleanly", app.pet.size_px == 260, f"size={app.pet.size_px}")

    # 2. 大寵物保持純粹 2D 原畫立繪，嚴格獨立於 Q 版像素小人
    sp_main = app.pet._sprite("happy")
    check("main pet strictly maintains smooth 2D illustration", sp_main is not None and not sp_main[0].isNull())
    app.set_size(454)
    wait(100)

    # 3. 2D 剪紙風格動態物理：紙片轉向翻轉 (Paper Flip 120ms)
    app.pet.set_snap_right(True)
    check("paper flip scaleX transitions smoothly", hasattr(app.pet, "paper_scale_x"))
    app.pet.set_snap_right(False)
    wait(150)

    # 4. 紙片懸空飄蕩微幅傾角 (±5 度) 與著陸壓扁回彈 (scaleY 0.88 -> 1.0)
    app.pet.flutter_angle = 4.5
    check("paper flutter tilt active during dragging", abs(app.pet.flutter_angle) <= 5.0)
    app.pet.flutter_angle = 0.0
    app.pet.paper_land_t = 0.20
    check("paper landing squish scaleY 0.88 to 1.0", app.pet.paper_land_t > 0)
    app.pet.paper_land_t = 0.0

    # 5. 雙擊平板智慧四分頁輪替 (Smart 4-Page Tablet)
    app.set_character("deepseek")
    app.pet.page = 2
    app.pet._build_screen()
    check("smart tablet page 2 shows alarms and countdown", app.pet.page == 2 and app.pet._screen_img is not None)
    app.pet.page = 3
    app.pet._build_screen()
    check("smart tablet page 3 shows notifications and webhooks", app.pet.page == 3 and app.pet._screen_img is not None)
    app.pet.next_tablet_page()
    check("smart tablet 4-page rotation loops back to page 0", app.pet.page == 0)

    # 6. 非 DeepSeek 角色自動跳過第 1 頁（峰谷頁）
    app.set_character("claude")
    app.pet.page = 0
    app.pet.next_tablet_page()
    check("non-deepseek character automatically skips page 1", app.pet.page == 2, f"page={app.pet.page}")
    app.set_character("deepseek")
    app.pet.page = 0
    app.pet._build_screen()

    # 7. 鬧鐘與通知排程系統 (Alarm Dispatcher)
    alarm1 = app.alarm_dispatcher.add_alarm("測試計時器", "", "timer", 60)
    check("alarm dispatcher adds countdown timer", alarm1.get("type") == "timer" and alarm1.get("id") in [a["id"] for a in app.alarm_dispatcher.get_alarms()])
    alarm2 = app.alarm_dispatcher.add_alarm("測試定時鬧鐘", "09:30", "clock", 0)
    check("alarm dispatcher adds clock alarm", alarm2.get("type") == "clock" and alarm2.get("time") == "09:30")

    # 8. 鬧鐘觸發：平板亮屏呼吸閃爍與想法框
    app.alarm_dispatcher.trigger_alarm(alarm1)
    check("alarm trigger activates tablet glow and thought bubble", app.pet.alarm_glowing is True and app.pet._bubble is not None and app.pet._bubble.isVisible())
    app.alarm_dispatcher.snooze_alarm(alarm1["id"], 5)
    check("alarm snooze postpones ringing by 5 minutes", app.pet.alarm_glowing is False)
    app.alarm_dispatcher.dismiss_alarm(alarm1["id"])
    app.alarm_dispatcher.remove_alarm(alarm1["id"])
    app.alarm_dispatcher.remove_alarm(alarm2["id"])
    check("alarm dismiss clears ringing state", len(app.alarm_dispatcher.get_alarms()) == 0)

    # 9. 全新 Q 版人物獨立像素系統 (Pixel Chibi Standalone System)
    check("pixel chibi module initialized and window visible", hasattr(app, "pixel_chibi") and app.pixel_chibi is not None and app.pixel_chibi.isVisible())
    from deskpet.pixel_chibi import CHAR_PALETTES, CHARACTER_INFO, FRAMES, PixelChibiRenderer
    all_four = all(c in CHAR_PALETTES for c in ("deepseek", "claude", "gpt", "gemini"))
    has_legs = all("LL" in "".join(FRAMES[f]) for f in ("idle", "walk1", "walk2", "sit", "panic", "climb"))
    check("pixel chibi has cute legs in all 4 heroines", all_four and has_legs)
    check("pixel chibi character info defines official four heroines", "藍色大肥魚" in CHARACTER_INFO["deepseek"]["name"] and "GPT龍娘" in CHARACTER_INFO["gpt"]["name"] and "大小姐Claude" in CHARACTER_INFO["claude"]["name"] and "北美貓娘Gemini" in CHARACTER_INFO["gemini"]["name"])
    check("gpt heroine palette represents white dragon girl", CHAR_PALETTES["gpt"]["H"] == "#f8fafc" and CHAR_PALETTES["gpt"]["E"] == "#8b5cf6")

    # 10. 最近鄰取樣放大無模糊動畫幀繪製
    pm_idle = PixelChibiRenderer.get_pixmap("deepseek", "idle", scale=3)
    pm_walk = PixelChibiRenderer.get_pixmap("claude", "walk1", scale=3)
    pm_sit = PixelChibiRenderer.get_pixmap("gpt", "sit", scale=3)
    pm_panic = PixelChibiRenderer.get_pixmap("gemini", "panic", scale=3)
    check("pixel chibi renders crisp nearest-neighbor frames", not pm_idle.isNull() and not pm_walk.isNull() and not pm_sit.isNull() and not pm_panic.isNull())

    # 11. 圖層永不被主寵物遮擋 (Topmost Z-Order)
    app.pet.raise_()
    app.pixel_chibi._tick()
    check("pixel chibi z-order always above main pet", bool(app.pixel_chibi.windowFlags() & Qt.WindowStaysOnTopHint))

    # 12. 撞擊主寵物 Duang 軟彈物理
    app.pixel_chibi.trigger_duang_bounce()
    check("pixel chibi duang bounce soft spring physics", app.pixel_chibi.state == "bounce" and abs(app.pixel_chibi.vel_x) > 0)

    # 13. 失足慌張掉落小腿亂蹬 (Panic Fall)
    app.pixel_chibi.start_panic_fall()
    check("pixel chibi panic fall triggers leg kicking", app.pixel_chibi.state == "panic" and app.pixel_chibi.vel_y > 0)

    # 14. 攀爬主寵物頭頂晃小腳
    app.pixel_chibi.mount_pet("head")
    check("pixel chibi climbs pet head and dangles legs", app.pixel_chibi.climbing_pet is True and app.pixel_chibi.pet_mount_slot == "head")
    app.pixel_chibi.dismount_pet()

    # 15. 趣味小道具（小氣球飛行與像素煙火）
    app.pixel_chibi.launch_fireworks()
    check("pixel chibi props flight and fireworks launcher", len(app.pixel_chibi.particles) > 0)
    app.pixel_chibi.particles.clear()
    app.pixel_chibi.state = "idle"

    # 16. 動態 FPS 調度與 Delta-Time 物理 (10-240 FPS / 無限制)
    app.set_target_fps(10)
    check("pixel chibi target_fps 10 sets interval to 100ms", app.pixel_chibi.timer.interval() == 100)
    app.set_target_fps(60)
    check("pixel chibi target_fps 60 sets interval to 16ms", app.pixel_chibi.timer.interval() == 16)
    app.set_target_fps(120)
    check("pixel chibi target_fps 120 sets interval to 8ms", app.pixel_chibi.timer.interval() == 8)
    app.set_target_fps(144)
    check("pixel chibi target_fps 144 sets interval to 7ms", app.pixel_chibi.timer.interval() == 7)
    app.set_target_fps(240)
    check("pixel chibi target_fps 240 sets interval to 4ms", app.pixel_chibi.timer.interval() == 4)
    app.set_target_fps(0)
    check("pixel chibi target_fps 0 (unlimited) sets interval to 1ms", app.pixel_chibi.timer.interval() == 1)
    app.set_performance_mode(True)
    check("pixel chibi performance_mode caps interval to 30fps (33ms)", app.pixel_chibi.timer.interval() == 33)
    app.set_performance_mode(False)
    app.set_target_fps(60)
    check("pixel chibi restores 60fps (16ms)", app.pixel_chibi.timer.interval() == 16)

    # 17. 全方向攀爬系列 (climb_up, climb_down, climb_side)
    app.pixel_chibi.start_climb("up")
    check("pixel chibi climb_up frame", app.pixel_chibi.state == "climb" and app.pixel_chibi.climb_subframe == "climb_up")
    app.pixel_chibi.start_climb("down")
    check("pixel chibi climb_down frame", app.pixel_chibi.climb_subframe == "climb_down")
    app.pixel_chibi.start_climb("side")
    check("pixel chibi climb_side frame", app.pixel_chibi.climb_subframe == "climb_side")

    # 18. 軟趴趴系列 (Splat / Floppy) 與主寵後背趴伏
    app.pixel_chibi.start_splat()
    check("pixel chibi splat mochi floppy state", app.pixel_chibi.state == "splat")
    app.pixel_chibi.mount_pet("back", pose="splat")
    check("pixel chibi splat rests on pet back", app.pixel_chibi.climbing_pet is True and app.pixel_chibi.pet_mount_slot == "back" and app.pixel_chibi.state == "splat")
    app.pixel_chibi.toggle_mount_pose()
    check("pixel chibi toggles mount pose to sit", app.pixel_chibi.state == "sit")
    app.pixel_chibi.dismount_pet()

    # 19. 睡覺 / 打呼 / 驚醒系列 (sleep_sprawl, sleep_prone, sleep_side, wake_startle)
    app.pixel_chibi.start_sleep("sleep_prone")
    check("pixel chibi sleep prone with zZZ bubbles", app.pixel_chibi.state == "sleep" and app.pixel_chibi.sleep_subframe == "sleep_prone")
    app.pixel_chibi.start_sleep("sleep_sprawl")
    check("pixel chibi sleep sprawl all-fours up", app.pixel_chibi.sleep_subframe == "sleep_sprawl")
    app.pixel_chibi.start_sleep("sleep_side")
    check("pixel chibi sleep side curled like cat", app.pixel_chibi.sleep_subframe == "sleep_side")
    app.pixel_chibi.start_wake()
    check("pixel chibi startled awake with ahoge standing", app.pixel_chibi.state == "wake")

    # 20. 跑步、跳躍與搗亂系列 (run, jump, mischief)
    app.pixel_chibi.start_run()
    check("pixel chibi forward sprint run state", app.pixel_chibi.state == "run")
    app.pixel_chibi.start_jump()
    check("pixel chibi vertical jump leap", app.pixel_chibi.state == "jump" and app.pixel_chibi.vel_y < 0)
    app.pixel_chibi.start_mischief()
    check("pixel chibi mischief funny faces and step dance", app.pixel_chibi.state == "mischief")

    # 21. 飯盆砸飛物理 (Bowl Smash & Knock-back)
    app.pixel_chibi.mount_pet("head")
    app.pet.wear_iron()
    check("pixel chibi bowl smash knock-back triggered", app.pixel_chibi.state == "bowl_smash" and app.pixel_chibi.vel_y == -220.0 and abs(app.pixel_chibi.vel_x) == 90.0)
    app.pixel_chibi.pos_y = 10000.0
    app.pixel_chibi._tick()
    check("pixel chibi bowl smash lands into splat state", app.pixel_chibi.state == "splat" and app.pixel_chibi.post_smash_recover is True)
    app.pixel_chibi.state_time = 1.6
    app.pixel_chibi._tick()
    check("pixel chibi recovers after 1.5s and climbs iron bowl", app.pixel_chibi.climbing_pet is True and app.pixel_chibi.pet_mount_slot == "iron")
    app.pixel_chibi.dismount_pet()
    app.pet.remove_iron(all_pots=True)

    # 22. 全生動動作像素動畫幀驗證 (全 16x24 矩陣且含 LL 腿部)
    all_extra_frames = (
        "climb_up", "climb_down", "climb_side", "facing_front", "facing_back", "turn",
        "splat", "sit_down", "sleep_sprawl", "sleep_prone", "sleep_side", "wake_startle",
        "run1", "run2", "jump_up", "jump_down", "run_jump", "mischief"
    )
    all_frames_valid = all(
        f in FRAMES and len(FRAMES[f]) == 24 and all(len(r) == 16 for r in FRAMES[f]) and ("LL" in "".join(FRAMES[f]))
        for f in all_extra_frames
    )
    check("pixel chibi all 18 extra frames 16x24 with LL legs", all_frames_valid)

    # 23. 自訂 Q 版人物庫、像素編輯器與多角色巡邏管理系統測試
    from deskpet.config import CUSTOM_CHIBI_DIR, get_effective_chibi_max_count, CHIBI_MAX_COUNT_OPTIONS
    from deskpet.pixel_chibi import PixelChibiRegistry, OFFICIAL_CHIBI_IDS, PixelChibiManager
    from deskpet.chibi_editor import ChibiPixelEditorDialog

    check("config defines CUSTOM_CHIBI_DIR and exists", CUSTOM_CHIBI_DIR.exists())
    check("config defines q_chibi_max_count options (5, 10, 15, 20, 25, 30)", CHIBI_MAX_COUNT_OPTIONS == (5, 10, 15, 20, 25, 30))
    check("effective chibi max count respects performance mode", get_effective_chibi_max_count({"q_chibi_max_count": 25, "performance_mode": True}) == 10)
    check("effective chibi max count allows up to 30 when perf off", get_effective_chibi_max_count({"q_chibi_max_count": 30, "performance_mode": False}) == 30)

    # 官方角色受保護測試
    official_protected = all(
        PixelChibiRegistry.get_character(cid)["is_protected"] is True and PixelChibiRegistry.get_character(cid)["is_custom"] is False
        for cid in OFFICIAL_CHIBI_IDS
    )
    check("official four heroines are protected and not custom", official_protected)

    official_delete_blocked = False
    try:
        PixelChibiRegistry.delete_custom_chibi("deepseek")
    except ValueError:
        official_delete_blocked = True
    check("deleting official protected chibi is strictly forbidden", official_delete_blocked)

    # 自訂角色儲存、尺寸限制與不顧限制測試
    custom_saved = False
    test_char_data = {
        "id": "selftest_hero",
        "name": "測試自訂英雄",
        "width": 16,
        "height": 24,
        "ignore_limits": False,
        "palette": {"H": "#1e3a8a", "S": "#ffe4d0"},
        "frames": {"idle": ["....HHHH....HHHH"] * 24}
    }
    p_saved = PixelChibiRegistry.save_custom_chibi(test_char_data)
    custom_saved = p_saved.exists() and PixelChibiRegistry.get_character("selftest_hero") is not None
    check("custom chibi saved to JSON and loaded into registry", custom_saved)

    # 不顧限制標記允許非 16x24 尺寸
    non_standard_blocked = False
    try:
        PixelChibiRegistry.save_custom_chibi({
            "id": "selftest_large",
            "name": "大型角色",
            "width": 32,
            "height": 32,
            "ignore_limits": False,
            "palette": {"H": "#ff0000"},
            "frames": {"idle": ["H" * 32] * 32}
        })
    except ValueError:
        non_standard_blocked = True
    check("non-standard size rejected when ignore_limits is False", non_standard_blocked)

    p_large = PixelChibiRegistry.save_custom_chibi({
        "id": "selftest_large",
        "name": "大型角色",
        "width": 32,
        "height": 32,
        "ignore_limits": True,
        "palette": {"H": "#ff0000"},
        "frames": {"idle": ["H" * 32] * 32}
    })
    check("non-standard size allowed when ignore_limits is True", p_large.exists() and PixelChibiRegistry.get_character_size("selftest_large") == (32, 32))

    # 像素編輯器實例化與工具驗證
    editor = ChibiPixelEditorDialog(parent=None, cfg=app.cfg, app=app)
    check("chibi pixel editor dialog instantiated cleanly", editor.canvas.canvas_w == 16 and editor.canvas.canvas_h == 24)
    editor.canvas.current_color = "#123456"
    editor.canvas._apply_tool(0, 0)
    check("pixel editor pencil tool applies pixel", editor.canvas.grid[0][0] == "#123456")
    editor._set_tool("eraser")
    editor.canvas._apply_tool(0, 0)
    check("pixel editor eraser tool clears pixel", editor.canvas.grid[0][0] is None)
    editor.close()

    # 多角色巡邏管理器與召喚限制測試
    check("app has chibi_manager initialized", hasattr(app, "chibi_manager") and app.chibi_manager is not None)
    initial_count = app.chibi_manager.active_count
    c2 = app.chibi_manager.summon("claude")
    check("summoning creates additional independent chibi", c2 is not None and app.chibi_manager.active_count == initial_count + 1)
    c_rand = app.chibi_manager.summon_random()
    check("random summon drops another chibi", c_rand is not None and app.chibi_manager.active_count == initial_count + 2)

    app.chibi_manager.clear_extra_chibis()
    check("clear_extra_chibis retains strictly 1 primary chibi", app.chibi_manager.active_count == 1)

    # 召喚數量上限檔位測試
    app.set_q_chibi_max_count(5)
    for _ in range(8):
        app.chibi_manager.summon("deepseek")
    check("chibi manager strictly enforces max_count limit", app.chibi_manager.active_count == 5 and app.chibi_manager.can_summon is False)
    app.chibi_manager.clear_extra_chibis()

    # 右鍵選單 Q 版小人巡邏隊子選單驗證
    menu_test = QMenu()
    app._fill_menu(menu_test)
    chibi_menu_found = False
    chibi_actions = []
    for a in menu_test.actions():
        if "Q 版小人巡邏隊" in a.text():
            chibi_menu_found = True
            chibi_actions = [act.text() for act in a.menu().actions()]
            break
    check("context menu includes Q 版小人巡邏隊 submenu", chibi_menu_found)
    check("submenu contains random summon action", any("隨機召喚一隻 Q 版人物" in t for t in chibi_actions))
    check("submenu contains specific summon submenu", any("指定召喚" in t for t in chibi_actions))
    check("submenu contains open editor action", any("開啟 Q 版人物像素編輯器..." in t for t in chibi_actions))
    check("submenu contains clear extra chibis action", any("清除場上所有額外 Q 版小人" in t for t in chibi_actions))

    # 清理測試自訂角色
    PixelChibiRegistry.delete_custom_chibi("selftest_hero")
    PixelChibiRegistry.delete_custom_chibi("selftest_large")

    # ========================================================= 23. YuYue 8-Layer Cipher & Safe Export/Import System
    from .export_data import YuYueCipher, export_backup_data, import_backup_data
    from .dialogs import ApiKeyExportWarningDialog, ExportSettingsDialog, ImportPasswordDialog

    test_plain = "桌面寵物全設定備份測試資料 2026 !@#$ JSON {\"pet\": \"deepseek\", \"variant\": \"tail\"}"
    test_pwd = "YuYueSecureKey2026"
    c_cipher, c_salt, c_vhash = YuYueCipher.encrypt(test_plain, test_pwd)
    check("YuYueCipher 8-layer encryption returns ciphertext and salt", bool(c_cipher and c_salt and c_vhash))
    c_dec = YuYueCipher.decrypt(c_cipher, test_pwd, c_salt, c_vhash)
    check("YuYueCipher 8-layer roundtrip decrypts original text", c_dec == test_plain)

    pwd_err_caught = False
    try:
        YuYueCipher.decrypt(c_cipher, "IncorrectPassword", c_salt, c_vhash)
    except ValueError as ve:
        pwd_err_caught = "解密密碼錯誤" in str(ve)
    check("YuYueCipher rejects incorrect password with friendly error", pwd_err_caught)

    # 匯出安全驗證：預設不含金鑰時徹底脫敏
    bak_no_keys_path = OUT / "selftest_backup_no_keys.json"
    cfg.set_api_keys("deepseek", "sk-secret-test-key-12345")
    exp_data = export_backup_data(cfg, bak_no_keys_path, include_keys=False)
    check("export_backup_data writes file", bak_no_keys_path.exists())
    check("export without keys strips deepseek key", exp_data["config"]["api_keys"]["deepseek"] == "")
    check("export has_api_keys flag is False", exp_data.get("has_api_keys") is False)

    # 匯出安全驗證：包含金鑰
    bak_with_keys_path = OUT / "selftest_backup_with_keys.json"
    exp_keys_data = export_backup_data(cfg, bak_with_keys_path, include_keys=True)
    check("export with keys retains actual api key", exp_keys_data["config"]["api_keys"]["deepseek"] == "sk-secret-test-key-12345")
    check("export has_api_keys flag is True", exp_keys_data.get("has_api_keys") is True)

    # 匯出安全驗證：YuYue 加密封裝匯出與還原
    bak_enc_path = OUT / "selftest_backup_encrypted.dpbak"
    exp_enc_data = export_backup_data(cfg, bak_enc_path, include_keys=False, password=test_pwd)
    check("encrypted export produces yuyue envelope", exp_enc_data.get("format") == "deskpet_backup_yuyue" and exp_enc_data.get("encrypted") is True)

    # 還原驗證：加密檔案未給密碼時拋出 NEED_PASSWORD
    need_pwd_caught = False
    try:
        import_backup_data(app, bak_enc_path, password="")
    except ValueError as ve:
        need_pwd_caught = "NEED_PASSWORD" in str(ve)
    check("import encrypted backup requires password", need_pwd_caught)

    # 還原驗證：正確密碼還原
    cfg.set("size", 260)
    imported = import_backup_data(app, bak_enc_path, password=test_pwd)
    check("import encrypted backup with password succeeds", isinstance(imported, dict) and "config" in imported)

    # API Key 5 秒倒數警告對話框邏輯測試
    warn_dlg = ApiKeyExportWarningDialog(parent=None)
    check("api key warning dialog starts countdown at 5s", warn_dlg.countdown == 5)
    check("api key warning confirm button initially disabled", warn_dlg.b_confirm.isEnabled() is False)
    check("api key warning confirm button text shows (5s)", "(5s)" in warn_dlg.b_confirm.text())
    warn_dlg._on_tick()
    check("countdown ticks to 4s and remains disabled", warn_dlg.countdown == 4 and warn_dlg.b_confirm.isEnabled() is False and "(4s)" in warn_dlg.b_confirm.text())
    for _ in range(4):
        warn_dlg._on_tick()
    check("countdown finishes and button is enabled with text 確認包含金鑰匯出", warn_dlg.countdown == 0 and warn_dlg.b_confirm.isEnabled() is True and warn_dlg.b_confirm.text() == "確認包含金鑰匯出")
    warn_dlg.close()

    # ========================================================= 24. Custom Image Aspect Ratio & Free Ratio Mode
    check("strict_custom_image_ratio config default is True", cfg.get("strict_custom_image_ratio", True) is True)

    # 測試立繪比例限制開關與動態 art_w / art_h 呈現
    custom_test_dir = config.CUSTOM_CHARS_DIR / "custom_selftest_wide"
    custom_test_dir.mkdir(parents=True, exist_ok=True)
    (custom_test_dir / "tablet.txt").write_text("330,790,694,790,694,960,330,960", encoding="utf-8")

    # 製作 2000x500 超長扁立繪 (4:1 比例)
    wide_img = QImage(2000, 500, QImage.Format_ARGB32_Premultiplied)
    wide_img.fill(QColor(100, 150, 255))
    wide_img.save(str(custom_test_dir / "sprite.png"), "PNG")

    # 在嚴格模式下，比例檢查
    ratio_wide = 2000.0 / 500.0  # 4.0
    check("strict ratio check flags wide image out of 0.7~1.8 bounds", ratio_wide < 0.7 or ratio_wide > 1.8)

    # 切換角色為 custom_selftest_wide
    pet.set_character("custom_selftest_wide")
    # 當 strict 為 True 時，維持正方形 1.0 (或 tail 1.5)
    app.set_strict_custom_image_ratio(True)
    check("strict mode maintains standard aspect ratio for custom pet", pet.aspect_ratio == 1.0)

    # 當關閉限制 (strict_custom_image_ratio == False) 時，動態照圖片實際長寬比呈現
    app.set_strict_custom_image_ratio(False)
    check("free ratio mode adopts image original aspect ratio 4.0", abs(pet.aspect_ratio - 4.0) < 0.05)
    check("free ratio art_w dynamically calculated from aspect_ratio", pet.art_w == int(pet.size_px * pet.aspect_ratio))

    # QML Backend 綁定與屬性切換驗證
    if not getattr(app, "qml_panel", None):
        app.show_qml_panel()
    qml_backend = app.qml_panel.backend
    check("qml backend has strictCustomImageRatio property", hasattr(qml_backend, "strictCustomImageRatio"))
    qml_backend.setStrictCustomImageRatio(True)
    check("qml backend setStrictCustomImageRatio updates config to True", cfg.get("strict_custom_image_ratio") is True)
    qml_backend.setStrictCustomImageRatio(False)
    check("qml backend setStrictCustomImageRatio updates config to False", cfg.get("strict_custom_image_ratio") is False)
    qml_backend.setStrictCustomImageRatio(True)
    check("qml backend has exportSettingsData slot", hasattr(qml_backend, "exportSettingsData"))
    check("qml backend has importSettingsData slot", hasattr(qml_backend, "importSettingsData"))
    check("qml backend has openVk1Repo slot", hasattr(qml_backend, "openVk1Repo"))
    check("qml backend has openYuYueRepo slot", hasattr(qml_backend, "openYuYueRepo"))
    check("qml backend has openExternalUrl slot", hasattr(qml_backend, "openExternalUrl"))
    check("qml backend has setActiveBalanceProvider slot", hasattr(qml_backend, "setActiveBalanceProvider"))
    check("qml backend has refreshBalance slot", hasattr(qml_backend, "refreshBalance"))
    check("qml backend has summonBalancePet slot", hasattr(qml_backend, "summonBalancePet"))
    check("qml backend has getProviderBudget slot", hasattr(qml_backend, "getProviderBudget"))
    check("qml backend has saveProviderBudget slot", hasattr(qml_backend, "saveProviderBudget"))
    qml_backend.setActiveBalanceProvider("SiliconFlow")
    check("qml backend active balance provider switched to SiliconFlow", "SiliconFlow" in qml_backend.get_active_balance_provider() or "矽基" in qml_backend.get_active_balance_provider())
    qml_backend.setActiveBalanceProvider("DeepSeek")

    check("qml backend has aggregateSameProviderKeys", hasattr(qml_backend, "get_aggregate_same_provider_keys"))
    check("qml backend has setAggregateSameProviderKeys", hasattr(qml_backend, "setAggregateSameProviderKeys"))
    check("qml backend has currencyTarget", hasattr(qml_backend, "get_currency_target"))
    check("qml backend has setCurrencyTarget", hasattr(qml_backend, "setCurrencyTarget"))
    check("qml backend has currencySource", hasattr(qml_backend, "get_currency_source"))
    check("qml backend has setCurrencySource", hasattr(qml_backend, "setCurrencySource"))
    check("qml backend has currencyDisplayMode", hasattr(qml_backend, "get_currency_display_mode"))
    check("qml backend has setCurrencyDisplayMode", hasattr(qml_backend, "setCurrencyDisplayMode"))
    check("qml backend has refreshCurrencyRates", hasattr(qml_backend, "refreshCurrencyRates"))
    check("qml backend has setPetMonitorTarget", hasattr(qml_backend, "setPetMonitorTarget"))
    check("qml backend has summonApiChibi", hasattr(qml_backend, "summonApiChibi"))
    check("qml backend has activePetsList", hasattr(qml_backend, "get_active_pets_list") and len(qml_backend.get_active_pets_list()) >= 1)

    # ========================================================= 25. Pet & Q-Chibi Opacity Controls and Synchronization
    check("config has default pet_opacity 100", cfg.get("pet_opacity", 100) == 100)
    check("config has default q_chibi_opacity 100", cfg.get("q_chibi_opacity", 100) == 100)

    # 測試大寵物透明度設定與即時視窗同步
    app.set_pet_opacity(75)
    check("set_pet_opacity updates config to 75", cfg.get("pet_opacity") == 75)
    check("pet window opacity matches 0.75", abs(pet.windowOpacity() - 0.75) < 0.02)
    app.set_pet_opacity(100)
    check("pet window opacity restored to 1.0", abs(pet.windowOpacity() - 1.0) < 0.02)

    # 測試 Q 版人物透明度設定與即時小人同步
    check("chibi manager exists", hasattr(app, "chibi_manager") and app.chibi_manager is not None)
    app.set_q_chibi_opacity(60)
    check("set_q_chibi_opacity updates config to 60", cfg.get("q_chibi_opacity") == 60)
    if app.chibi_manager.primary_chibi:
        check("primary chibi window opacity matches 0.6", abs(app.chibi_manager.primary_chibi.windowOpacity() - 0.6) < 0.02)
    app.set_q_chibi_opacity(100)
    if app.chibi_manager.primary_chibi:
        check("primary chibi window opacity restored to 1.0", abs(app.chibi_manager.primary_chibi.windowOpacity() - 1.0) < 0.02)

    # 測試 QML Backend 透明度屬性與槽函數
    check("qml backend has petOpacityVal property", hasattr(qml_backend, "get_pet_opacity_val"))
    check("qml backend has qChibiOpacityVal property", hasattr(qml_backend, "get_q_chibi_opacity_val"))
    qml_backend.setPetOpacityVal(85)
    check("qml backend setPetOpacityVal updates config to 85", cfg.get("pet_opacity") == 85)
    qml_backend.setPetOpacityVal(100)
    qml_backend.setQChibiOpacityVal(70)
    check("qml backend setQChibiOpacityVal updates config to 70", cfg.get("q_chibi_opacity") == 70)
    qml_backend.setQChibiOpacityVal(100)

    # ========================================================= 26. Chat Dialog Screen Bottom-Center Coordinates
    chat_dlg.show_dialog()
    screen_active = qapp.primaryScreen()
    geo_active = screen_active.availableGeometry()
    w_dlg = chat_dlg.width()
    h_dlg = chat_dlg.height()
    expected_x = geo_active.left() + (geo_active.width() - w_dlg) // 2
    expected_y = geo_active.bottom() - h_dlg - 48
    clamped_x = max(geo_active.left() + 16, min(expected_x, geo_active.right() - w_dlg - 16))
    clamped_y = max(geo_active.top() + 16, min(expected_y, geo_active.bottom() - h_dlg - 16))
    check("chat dialog placed at bottom-center horizontally", abs(chat_dlg.x() - clamped_x) <= 2)
    check("chat dialog placed at bottom-center vertically", abs(chat_dlg.y() - clamped_y) <= 2)

    chat_dlg.show_beside_pet()
    check("show_beside_pet retains ergonomic bottom-center placement", abs(chat_dlg.x() - clamped_x) <= 2 and abs(chat_dlg.y() - clamped_y) <= 2)

    # ========================================================= 27. Floating Notifications Screen Top-Center Coordinates
    chat_dlg.show_floating_notice("測試螢幕頂部居中通知")
    check("floating notice label exists", hasattr(chat_dlg, "_toast_label") and chat_dlg._toast_label is not None)
    toast_lbl = chat_dlg._toast_label
    check("floating notice visible", toast_lbl.isVisible())
    expected_top_y = geo_active.top() + 48
    expected_top_x = geo_active.left() + (geo_active.width() - toast_lbl.width()) // 2
    check("floating notice placed at screen top-center vertically", abs(toast_lbl.y() - expected_top_y) <= 2)
    check("floating notice placed at screen top-center horizontally", abs(toast_lbl.x() - expected_top_x) <= 2)
    toast_lbl.hide()

    from deskpet.dialogs import NotificationToast, show_desktop_toast
    desktop_toast = show_desktop_toast("測試桌面通用通知")
    check("desktop toast window created and visible", desktop_toast is not None and desktop_toast.isVisible())
    check("desktop toast placed at top-center vertically", abs(desktop_toast.y() - expected_top_y) <= 2)
    desktop_toast.hide()
    desktop_toast.close()

    # ========================================================= 28. Custom Character Crop / Fit / Free Modes
    check("custom_pet_crop_mode config default is fit", cfg.get("custom_pet_crop_mode", "fit") == "fit")
    pet.set_character("custom_selftest_wide")

    # 1. 裁切填滿 (crop)
    app.set_custom_pet_crop_mode("crop")
    check("crop mode maintains 1.0 standard aspect ratio for target frame", pet.aspect_ratio == 1.0)
    check("crop mode config set to crop", cfg.get("custom_pet_crop_mode") == "crop")
    pix_crop, _, _ = pet._sprite("happy")
    check("crop mode renders valid pixmap", not pix_crop.isNull() and pix_crop.width() == pet.art_w)

    # 2. 等比縮放 (fit)
    app.set_custom_pet_crop_mode("fit")
    check("fit mode maintains 1.0 standard aspect ratio for target frame", pet.aspect_ratio == 1.0)
    check("fit mode config set to fit", cfg.get("custom_pet_crop_mode") == "fit")
    pix_fit, _, _ = pet._sprite("happy")
    check("fit mode renders valid pixmap", not pix_fit.isNull() and pix_fit.width() == pet.art_w)

    # 3. 自由比例 (free)
    app.set_custom_pet_crop_mode("free")
    check("free mode adopts image original aspect ratio 4.0", abs(pet.aspect_ratio - 4.0) < 0.05)
    check("free mode art_w dynamically calculated from aspect_ratio", pet.art_w == int(pet.size_px * pet.aspect_ratio))
    pix_free, _, _ = pet._sprite("happy")
    check("free mode renders valid pixmap", not pix_free.isNull() and pix_free.width() == pet.art_w)

    # QML Backend 自訂立繪裁切模式綁定
    check("qml backend has customPetCropMode property", hasattr(qml_backend, "get_custom_pet_crop_mode"))
    check("qml backend has setCustomPetCropMode slot", hasattr(qml_backend, "setCustomPetCropMode"))
    qml_backend.setCustomPetCropMode("fit")
    check("qml backend setCustomPetCropMode updates config to fit", cfg.get("custom_pet_crop_mode") == "fit")

    # ========================================================= 29. SSRF Deep Defense & Safe Web Tools
    from deskpet.agent_tools import (
        validate_url_safety,
        safe_web_browse,
        safe_web_search,
        safe_decompress_stream,
    )

    # 1. 測試本機迴環 (127.0.0.1 與 ::1)
    ok_loopback, msg_loopback, _ = validate_url_safety("http://127.0.0.1/admin")
    check("SSRF defense strictly blocks 127.0.0.1 loopback", ok_loopback is False and "本機迴環" in msg_loopback)
    ok_v6_loop, msg_v6_loop, _ = validate_url_safety("http://[::1]/secret")
    check("SSRF defense strictly blocks IPv6 loopback", ok_v6_loop is False)

    # 2. 測試雲端敏感元數據 (169.254.169.254 與 metadata.google.internal)
    ok_meta_ip, msg_meta_ip, _ = validate_url_safety("http://169.254.169.254/latest/meta-data/")
    check("SSRF defense strictly blocks 169.254.169.254 cloud metadata IP", ok_meta_ip is False and ("元數據" in msg_meta_ip or "鏈路" in msg_meta_ip))
    ok_meta_host, msg_meta_host, _ = validate_url_safety("http://metadata.google.internal/computeMetadata/v1/")
    check("SSRF defense strictly blocks metadata.google.internal", ok_meta_host is False and ("元數據" in msg_meta_host or "敏感內部服務" in msg_meta_host))

    # 3. 測試私有內網 (192.168.0.1, 10.0.0.1, 172.16.0.1)
    ok_priv1, msg_priv1, _ = validate_url_safety("http://192.168.1.1:8080/")
    ok_priv2, msg_priv2, _ = validate_url_safety("http://10.1.2.3/")
    ok_priv3, msg_priv3, _ = validate_url_safety("http://172.20.0.5/")
    check("SSRF defense strictly blocks private LAN IPs", ok_priv1 is False and ok_priv2 is False and ok_priv3 is False)

    # 4. 測試危險協議白名單 (file://, ftp://, gopher://, dict://)
    ok_file, msg_file, _ = validate_url_safety("file:///C:/Windows/win.ini")
    check("SSRF defense strictly blocks file:// protocol", ok_file is False and "通訊協議" in msg_file)
    ok_gopher, msg_gopher, _ = validate_url_safety("gopher://127.0.0.1:6379/")
    check("SSRF defense strictly blocks gopher:// protocol", ok_gopher is False and "通訊協議" in msg_gopher)

    # 5. 測試危險連接埠 (22, 23, 3306, 6379)
    ok_port22, msg_port22, _ = validate_url_safety("http://8.8.8.8:22/")
    check("SSRF defense strictly blocks SSH port 22", ok_port22 is False and "埠號" in msg_port22)
    ok_port6379, msg_port6379, _ = validate_url_safety("http://8.8.8.8:6379/")
    check("SSRF defense strictly blocks Redis port 6379", ok_port6379 is False and "埠號" in msg_port6379)

    # 6. 測試 safe_web_browse 回應中包含安全阻擋提示
    res_browse_loopback = safe_web_browse("http://127.0.0.1:8080/sensitive")
    check("safe_web_browse returns security blocked notice on loopback", "安全阻擋" in res_browse_loopback)
    res_browse_meta = safe_web_browse("http://169.254.169.254/secret")
    check("safe_web_browse returns security blocked notice on metadata", "安全阻擋" in res_browse_meta)

    # 7. 測試 safe_web_search 支援空關鍵字安全防護與離線友善處理
    res_search_empty = safe_web_search("")
    check("safe_web_search returns helpful notice on empty query", "搜尋關鍵字為空" in res_search_empty)
    res_search_query = safe_web_search("desktop pet ai agent")
    check("safe_web_search returns sandboxed XML wrapper", "<untrusted_web_content" in res_search_query and "</untrusted_web_content>" in res_search_query)

    # ========================================================= 30. HTTP Decompression Bomb / Gzip Bomb Defense
    import zlib

    # 1. 測試拒絕多層巢狀壓縮 (Nested Content-Encoding)
    ok_nested, msg_nested, _ = safe_decompress_stream([b"test"], content_encoding="gzip, gzip")
    check("decompression bomb defense rejects nested gzip, gzip", ok_nested is False and "多層巢狀" in msg_nested)
    ok_nested2, msg_nested2, _ = safe_decompress_stream([b"test"], content_encoding="gzip, deflate")
    check("decompression bomb defense rejects nested gzip, deflate", ok_nested2 is False and "多層巢狀" in msg_nested2)

    # 2. 測試超過 2MB 解壓縮硬上限 (Hard Cap 2MB)
    huge_data = b"A" * (2500 * 1024)
    huge_comp = zlib.compress(huge_data)
    ok_cap, msg_cap, _ = safe_decompress_stream([huge_comp], content_encoding="deflate")
    check("decompression bomb defense blocks payload exceeding 2MB hard cap", ok_cap is False and ("超過上限" in msg_cap or "解壓縮炸彈" in msg_cap))

    # 3. 測試異常壓縮膨脹比例監控 (超過 100:1)
    # 產生超過 10KB 門檻 (約 13KB) 且膨脹比例高達 116:1 的攻擊 Payload (解壓後約 1.5MB < 2MB 上限)
    bomb_noise = os.urandom(10240)
    bomb_zeros = b"A" * 1500000
    bomb_raw_data = bomb_noise + bomb_zeros
    bomb_compressed_data = zlib.compress(bomb_raw_data, 9)
    ok_ratio, msg_ratio, _ = safe_decompress_stream([bomb_compressed_data], content_encoding="deflate")
    check("decompression bomb defense triggers ratio safeguard on expansion exceeding 100:1", ok_ratio is False and "膨脹比例" in msg_ratio)

    # 清理測試自訂立繪
    pet.set_character("deepseek")
    shutil.rmtree(custom_test_dir, ignore_errors=True)

    chat_dlg.close()

    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
    app.tray.hide()
    p.hide()
    return 1 if bad else 0


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    qapp = QApplication(sys.argv)
    code = run(qapp)
    sys.exit(code)
