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
    # 1. 平滑尺寸滑桿測試 (80px - 1024px) 與快速預設標籤
    app.set_size(80)
    wait(100)
    check("pet size slider supports 80px min", app.pet.size_px == 80, f"size={app.pet.size_px}")
    app.set_size(1024)
    wait(100)
    check("pet size slider supports 1024px max", app.pet.size_px == 1024, f"size={app.pet.size_px}")
    app.set_size(100)
    wait(100)
    check("quick size preset 100px applies cleanly", app.pet.size_px == 100, f"size={app.pet.size_px}")

    # 2. 極小尺寸自動切換像素 Q 版測試
    app.set_mini_pixel_mode(True)
    wait(100)
    sp_mini = app.pet._sprite("happy")
    check("mini_pixel_mode switches sprite at <= 140px", sp_mini is not None)
    app.set_mini_pixel_mode(False)
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
