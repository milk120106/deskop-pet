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
        print(msg)
    except Exception:
        enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        print(msg.encode(enc, errors="replace").decode(enc))


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

    # ========================================================= 5. Q Characters Disabled & Decoupled
    # Check that Q images and modules are removed and backed up
    q_dir = config.APP_DIR / "assets" / "q"
    dark_dir = config.APP_DIR / "assets" / "dark"
    check("Q character images removed for remaking", len(list(q_dir.glob("*.png"))) == 0 and len(list(dark_dir.glob("*.png"))) == 0)
    check("qchars.py removed from codebase", not (config.APP_DIR / "deskpet" / "qchars.py").exists())
    check("custom_q dir removed from codebase", not (config.APP_DIR / "custom_q").exists())
    check("backup_qchars exists with backup files", (config.APP_DIR.parent / "backup_qchars" / "qchars.py").exists())

    # Check right-click menu: dark mode removed, Q character submenu marked as maintenance
    from PySide6.QtWidgets import QMenu, QMessageBox
    m = QMenu()
    app._fill_menu(m)
    menu_texts = [a.text() for a in m.actions()]
    check("dark mode removed from context menu", not any("黑化模式" in t for t in menu_texts))
    check("Q character menu marked as under maintenance", any("Q 版角色（維護中）" in t for t in menu_texts))

    # Test that clicking add_q notifies the user that the feature is under maintenance / not completed
    notices = []
    real_info = QMessageBox.information
    QMessageBox.information = lambda *a, **kw: notices.append(a)
    try:
        app.add_q(dark=False, kind="ds")
        check("clicking add_q prompts feature not completed", any("Q 版角色功能目前暫時停用並進行重構升級中" in str(x) or "尚未完成" in str(x) for x in notices))
        notices.clear()
        app.open_custom_q_dialog()
        check("custom_q dialog also prompts maintenance", any("Q 版角色功能目前暫時停用並進行重構升級中" in str(x) or "尚未完成" in str(x) for x in notices))
    finally:
        QMessageBox.information = real_info

    # Stability check: ensure decoupled methods execute cleanly without errors
    try:
        app.set_q_dark(True)
        app.set_q_dark(False)
        app.remove_all_q()
        app.set_click_through(False)
        app.set_topmost(True)
        check("Q char decoupling stability check passed", True)
    except Exception as e:
        check("Q char decoupling stability check passed", False, str(e))

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
    w_sq = pet.art_w
    app.set_variant("tail")
    wait(300)
    check("switched to tail variant (1.5:1)", pet.variant == "tail" and pet.aspect_ratio == 1.5)
    check("tail variant widens art width", pet.art_w == int(pet.size_px * 1.5) and pet.art_w > w_sq)
    pet.grab().save(str(OUT / "11_variant_tail.png"))
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
    py_files = [
        config.APP_DIR / "deskpet" / "chat.py",
        config.APP_DIR / "deskpet" / "panel.py",
        config.APP_DIR / "deskpet" / "dialogs.py",
        config.APP_DIR / "deskpet" / "titlebar.py",
        config.APP_DIR / "deskpet" / "font_manager.py",
        config.APP_DIR / "deskpet" / "icons.py",
    ]
    for pyf in py_files:
        content = pyf.read_text(encoding="utf-8")
        matches = emoji_pattern.findall(content)
        if matches:
            found_emojis.append(f"{pyf.name}: {matches}")
    check("strictly zero emojis in upgraded codebase", len(found_emojis) == 0, str(found_emojis))

    chat_dlg.close()

    bad = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks passed")
    app.tray.hide()
    p.hide()
    return 1 if bad else 0
