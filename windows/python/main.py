from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from PIL import Image
from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QColorDialog, QDialog, QDialogButtonBox, QFileDialog,
    QComboBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPushButton, QSlider, QSpinBox, QSystemTrayIcon,
    QTabWidget, QVBoxLayout, QWidget, QStyle,
)

APP_NAME = "Python Desktop Pet v4"
ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CUSTOM = ROOT / "custom_characters"
CONFIG_PATH = ROOT / "pet_config.json"
CANVAS = (1536, 1024)
BUILTIN_CHARACTERS = {
    "藍色大肥魚（DeepSeek）": "sprite.png",
    "GPT 龍娘": "sprite-gpt.png",
    "大小姐 Claude": "sprite-claude.png",
    "北美貓娘 Gemini": "sprite-gemini.png",
    "DeepSeek 離線抱盆": "sprite-deepseek-offline.png",
}


def fit_to_canvas(source: Path, target: Path) -> None:
    """Create a 1536x1024 transparent canvas; never crop the imported artwork."""
    with Image.open(source).convert("RGBA") as im:
        im.thumbnail(CANVAS, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
        x = (CANVAS[0] - im.width) // 2
        y = (CANVAS[1] - im.height) // 2
        canvas.alpha_composite(im, (x, y))
        target.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(target, "PNG")


def ensure_default_asset() -> Path:
    target = ASSETS / "sprite_full.png"
    canonical = ASSETS / "sprite.png"
    if canonical.exists():
        return canonical
    if target.exists():
        return target
    legacy = ROOT / "reference" / "windows" / "sprite.png"
    if legacy.exists():
        fit_to_canvas(legacy, target)
    else:
        target.parent.mkdir(exist_ok=True)
        Image.new("RGBA", CANVAS, (0, 0, 0, 0)).save(target)
    return target


class SettingsDialog(QDialog):
    changed = Signal(dict)

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("桌寵設定")
        self.setMinimumWidth(380)
        self.config = dict(config)
        form = QFormLayout(self)
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(20, 100)
        self.opacity.setValue(int(self.config.get("opacity", 100)))
        self.opacity_label = QLabel(f"{self.opacity.value()}%")
        self.opacity.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        row = QHBoxLayout(); row.addWidget(self.opacity); row.addWidget(self.opacity_label)
        form.addRow("角色透明度", row)
        self.scale = QSpinBox(); self.scale.setRange(180, 900); self.scale.setValue(int(self.config.get("size", 520))); self.scale.setSuffix(" px")
        form.addRow("顯示寬度", self.scale)
        self.auto_feed = QCheckBox("啟用自動火控 / 飯盆")
        self.auto_feed.setChecked(bool(self.config.get("auto_feed", True)))
        form.addRow(self.auto_feed)
        self.interval = QSpinBox(); self.interval.setRange(1, 1440); self.interval.setValue(int(self.config.get("interval", 30))); self.interval.setSuffix(" 分鐘")
        form.addRow("自動間隔", self.interval)
        self.click_through = QCheckBox("啟用滑鼠穿透（右鍵托盤可恢復）")
        self.click_through.setChecked(bool(self.config.get("click_through", False)))
        form.addRow(self.click_through)
        self.pin = QCheckBox("固定在最上層"); self.pin.setChecked(bool(self.config.get("always_on_top", True))); form.addRow(self.pin)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def accept(self):
        self.config.update({"opacity": self.opacity.value(), "size": self.scale.value(), "auto_feed": self.auto_feed.isChecked(), "interval": self.interval.value(), "click_through": self.click_through.isChecked(), "always_on_top": self.pin.isChecked()})
        self.changed.emit(self.config)
        super().accept()


class ImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent); self.setWindowTitle("匯入自訂角色"); self.setMinimumWidth(460)
        form = QFormLayout(self)
        self.name = QLabel("尚未選擇圖片")
        self.path: Optional[str] = None
        pick = QPushButton("選擇 PNG / JPG / WEBP…"); pick.clicked.connect(self.pick)
        form.addRow("角色圖片", pick); form.addRow("檔案", self.name)
        note = QLabel("圖片會以 Pillow 等比例縮放置中到 1536×1024 透明畫布，完整保留尾巴與頭髮，不會裁切。")
        note.setWordWrap(True); form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "選擇角色圖片", "", "圖片 (*.png *.jpg *.jpeg *.webp)")
        if p: self.path = p; self.name.setText(Path(p).name)

    def accept(self):
        if not self.path:
            QMessageBox.warning(self, "尚未選擇", "請先選擇角色圖片。"); return
        super().accept()


class ApiKeyDialog(QDialog):
    def __init__(self, pet: "PetWindow"):
        super().__init__(pet); self.pet = pet; self.setWindowTitle("API Key 管理"); self.setMinimumWidth(460)
        form = QFormLayout(self)
        self.provider = QComboBox(); self.provider.addItems(["DeepSeek", "OpenAI", "Anthropic", "Google Gemini"]); form.addRow("供應商", self.provider)
        self.key = QLineEdit(); self.key.setEchoMode(QLineEdit.Password); form.addRow("API Key", self.key)
        self.show_key = QCheckBox("顯示 Key"); self.show_key.toggled.connect(lambda on: self.key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password)); form.addRow(self.show_key)
        self.note = QLabel("API Key 會只儲存在本機 pet_config.json。切換模式是獨立操作，不會因儲存 Key 自動改變模式。")
        self.note.setWordWrap(True); form.addRow(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def save(self):
        keys = dict(self.pet.config.get("api_keys", {})); keys[self.provider.currentText()] = self.key.text().strip(); self.pet.config["api_keys"] = keys; self.pet.save_config(); self.accept()


class SimulationDialog(QDialog):
    def __init__(self, pet: "PetWindow"):
        super().__init__(pet); self.pet = pet; self.setWindowTitle("模擬模式控制"); self.setMinimumWidth(480)
        form = QFormLayout(self)
        self.enabled = QCheckBox("啟用自動模擬事件"); self.enabled.setChecked(bool(pet.config.get("simulation_enabled", True))); form.addRow(self.enabled)
        self.balance = QDoubleSpinBox(); self.balance.setRange(-999999, 999999); self.balance.setDecimals(2); self.balance.setValue(float(pet.config.get("sim_balance", 50.0))); form.addRow("目前餘額", self.balance)
        self.interval = QSpinBox(); self.interval.setRange(1, 86400); self.interval.setValue(int(pet.config.get("simulation_interval", 30))); self.interval.setSuffix(" 秒"); form.addRow("事件間隔", self.interval)
        self.debit_min = QDoubleSpinBox(); self.debit_min.setRange(0, 9999); self.debit_min.setDecimals(2); self.debit_min.setValue(float(pet.config.get("debit_min", .01))); form.addRow("扣款下限", self.debit_min)
        self.debit_max = QDoubleSpinBox(); self.debit_max.setRange(0, 9999); self.debit_max.setDecimals(2); self.debit_max.setValue(float(pet.config.get("debit_max", .10))); form.addRow("扣款上限", self.debit_max)
        self.credit_min = QDoubleSpinBox(); self.credit_min.setRange(0, 9999); self.credit_min.setDecimals(2); self.credit_min.setValue(float(pet.config.get("credit_min", 1.0))); form.addRow("充值下限", self.credit_min)
        self.credit_max = QDoubleSpinBox(); self.credit_max.setRange(0, 9999); self.credit_max.setDecimals(2); self.credit_max.setValue(float(pet.config.get("credit_max", 5.0))); form.addRow("充值上限", self.credit_max)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); form.addRow(buttons)
        test = QPushButton("立即模擬一次事件"); test.clicked.connect(pet.simulate_event); form.addRow(test)

    def save(self):
        self.pet.config.update({"simulation_enabled": self.enabled.isChecked(), "sim_balance": self.balance.value(), "simulation_interval": self.interval.value(), "debit_min": self.debit_min.value(), "debit_max": self.debit_max.value(), "credit_min": self.credit_min.value(), "credit_max": self.credit_max.value()})
        self.pet.save_config(); self.pet.sim_timer.setInterval(self.interval.value() * 1000); self.accept()


class WalkingCharacter(QWidget):
    """A lightweight transparent companion window that walks horizontally."""
    def __init__(self, image: Path, index: int, pet: "PetWindow", directions: Optional[dict[str, Path]] = None):
        super().__init__()
        self.pet = pet; self.index = index; self.image = image; self.directions = directions or {}; self.direction = 1; self.speed = 2 + index
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setAttribute(Qt.WA_DeleteOnClose)
        self.canvas = QLabel(self); self.canvas.setAlignment(Qt.AlignCenter); self.canvas.setStyleSheet("background: transparent;")
        self.resize(260, 174); self.render()
        self.walk_timer = QTimer(self); self.walk_timer.timeout.connect(self.walk); self.walk_timer.start(35)
        self.move_to_start()

    def render(self):
        pix = QPixmap(str(self.image))
        self.canvas.setPixmap(pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event): self.canvas.resize(self.size()); self.render()

    def move_to_start(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.left() + 30 + self.index * 280, screen.bottom() - self.height() - 30)

    def walk(self):
        screen = QApplication.primaryScreen().availableGeometry(); x = self.x() + self.direction * self.speed
        left, right = screen.left(), screen.right() - self.width()
        if self.pet.config.get("auto_snap", True):
            if x <= left:
                x = left; self.direction = 1
                if self.directions.get("back"): self.image = self.directions["back"]; self.render(); QTimer.singleShot(350, self.show_side)
            elif x >= right:
                x = right; self.direction = -1
                if self.directions.get("front"): self.image = self.directions["front"]; self.render(); QTimer.singleShot(350, self.show_side)
            elif self.directions.get("side") and self.image != self.directions["side"]:
                self.show_side()
        self.move(x, self.y())

    def show_side(self):
        if self.directions.get("side"):
            self.image = self.directions["side"]; self.render()

    def closeEvent(self, event):
        self.walk_timer.stop(); super().closeEvent(event)


class ControlPanel(QDialog):
    """Full GUI dashboard; the transparent pet remains usable while this is open."""

    def __init__(self, pet: "PetWindow"):
        super().__init__(pet)
        self.pet = pet
        self.setWindowTitle("Python Desktop Pet v4｜控制面板")
        self.setMinimumSize(650, 520)
        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs)

        # Character tab
        character_tab = QWidget(); character_layout = QHBoxLayout(character_tab)
        self.character_list = QListWidget(); character_layout.addWidget(self.character_list, 1)
        preview_col = QVBoxLayout(); self.preview = QLabel(); self.preview.setAlignment(Qt.AlignCenter); self.preview.setMinimumSize(360, 240); preview_col.addWidget(self.preview, 1)
        select_btn = QPushButton("套用選取角色"); select_btn.clicked.connect(self.apply_character); preview_col.addWidget(select_btn)
        import_btn = QPushButton("匯入自訂角色…"); import_btn.clicked.connect(self.pet.import_character); preview_col.addWidget(import_btn)
        character_layout.addLayout(preview_col, 2); tabs.addTab(character_tab, "角色")
        self.character_list.currentRowChanged.connect(self.preview_character)
        self.character_paths = []
        for label, filename in BUILTIN_CHARACTERS.items():
            self.character_paths.append(ASSETS / filename); self.character_list.addItem(label)
        self.character_list.setCurrentRow(0)

        # Appearance tab
        appearance_tab = QWidget(); appearance_form = QFormLayout(appearance_tab)
        self.opacity_slider = QSlider(Qt.Horizontal); self.opacity_slider.setRange(20, 100); self.opacity_slider.setValue(int(pet.config.get("opacity", 100)))
        self.opacity_value = QLabel(); self.opacity_slider.valueChanged.connect(lambda v: self.opacity_value.setText(f"{v}%")); self.opacity_slider.valueChanged.emit(self.opacity_slider.value())
        opacity_row = QHBoxLayout(); opacity_row.addWidget(self.opacity_slider); opacity_row.addWidget(self.opacity_value); appearance_form.addRow("透明度", opacity_row)
        self.size_spin = QSpinBox(); self.size_spin.setRange(180, 900); self.size_spin.setValue(int(pet.config.get("size", 520))); self.size_spin.setSuffix(" px"); appearance_form.addRow("角色寬度", self.size_spin)
        self.top_combo = QComboBox(); self.top_combo.addItems(["固定在最上層", "一般視窗"]); self.top_combo.setCurrentIndex(0 if pet.config.get("always_on_top", True) else 1); appearance_form.addRow("視窗層級", self.top_combo)
        self.click_combo = QComboBox(); self.click_combo.addItems(["可互動", "滑鼠穿透"]); self.click_combo.setCurrentIndex(1 if pet.config.get("click_through", False) else 0); appearance_form.addRow("滑鼠行為", self.click_combo)
        self.snap_check = QCheckBox("角色自動貼齊螢幕左右邊緣"); self.snap_check.setChecked(bool(pet.config.get("auto_snap", True))); appearance_form.addRow(self.snap_check)
        apply_appearance = QPushButton("套用外觀設定"); apply_appearance.clicked.connect(self.apply_appearance); appearance_form.addRow(apply_appearance)
        snap = QPushButton("移到主螢幕左下角"); snap.clicked.connect(pet.snap_bottom_left); appearance_form.addRow(snap); tabs.addTab(appearance_tab, "外觀與位置")

        # Automation tab
        automation_tab = QWidget(); automation_form = QFormLayout(automation_tab)
        self.auto_check = QCheckBox("啟用自動火控／飯盆"); self.auto_check.setChecked(bool(pet.config.get("auto_feed", True))); automation_form.addRow(self.auto_check)
        self.interval_spin = QSpinBox(); self.interval_spin.setRange(1, 1440); self.interval_spin.setValue(int(pet.config.get("interval", 30))); self.interval_spin.setSuffix(" 分鐘"); automation_form.addRow("觸發間隔", self.interval_spin)
        save_auto = QPushButton("儲存排程設定"); save_auto.clicked.connect(self.apply_automation); automation_form.addRow(save_auto)
        actions = QGroupBox("立即操作"); action_layout = QVBoxLayout(actions)
        spawn = QPushButton("立即掉落飯盆／啟動火控"); spawn.clicked.connect(pet.spawn_rice); action_layout.addWidget(spawn)
        clear = QPushButton("清除場上飯盆"); clear.clicked.connect(pet.clear_rice); action_layout.addWidget(clear)
        automation_form.addRow(actions); tabs.addTab(automation_tab, "火控與飯盆")

        simulation_tab = QWidget(); simulation_layout = QVBoxLayout(simulation_tab)
        simulation_status = QLabel(); simulation_status.setWordWrap(True)
        def refresh_sim_status():
            simulation_status.setText(f"目前模式：{self.pet.config.get('mode', 'simulation')}\n模擬餘額：{float(self.pet.config.get('sim_balance', 50.0)):.2f}\n最近事件：{self.pet.config.get('last_sim_event', '尚未發生')}")
        refresh_sim_status(); simulation_layout.addWidget(simulation_status)
        sim_button = QPushButton("開啟模擬控制介面…"); sim_button.clicked.connect(lambda: (SimulationDialog(pet).exec(), refresh_sim_status())); simulation_layout.addWidget(sim_button)
        run_sim = QPushButton("立即模擬一次扣款／充值"); run_sim.clicked.connect(lambda: (pet.simulate_event(), refresh_sim_status())); simulation_layout.addWidget(run_sim)
        simulation_layout.addStretch(); tabs.addTab(simulation_tab, "模擬模式")

        api_tab = QWidget(); api_layout = QVBoxLayout(api_tab)
        api_status = QLabel("API Key 與模式切換分開管理。儲存 Key 不會自動切換模式。")
        api_status.setWordWrap(True); api_layout.addWidget(api_status)
        api_button = QPushButton("開啟 API Key 管理…"); api_button.clicked.connect(lambda: ApiKeyDialog(pet).exec()); api_layout.addWidget(api_button)
        api_layout.addStretch(); tabs.addTab(api_tab, "API 模式")

        close_btn = QPushButton("關閉控制面板"); close_btn.clicked.connect(self.close); root.addWidget(close_btn)

    def preview_character(self, row: int):
        if 0 <= row < len(self.character_paths):
            pix = QPixmap(str(self.character_paths[row])); self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def apply_character(self):
        row = self.character_list.currentRow()
        if 0 <= row < len(self.character_paths): self.pet.select_character(self.character_paths[row].name)

    def apply_appearance(self):
        self.pet.update_config({**self.pet.config, "opacity": self.opacity_slider.value(), "size": self.size_spin.value(), "always_on_top": self.top_combo.currentIndex() == 0, "click_through": self.click_combo.currentIndex() == 1, "auto_snap": self.snap_check.isChecked()})

    def apply_automation(self):
        self.pet.update_config({**self.pet.config, "auto_feed": self.auto_check.isChecked(), "interval": self.interval_spin.value()})


class PetWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.config = self.load_config()
        self.config.setdefault("auto_snap", True)
        self.config.setdefault("mode", "simulation")
        self.config.setdefault("api_keys", {})
        self.current_image = Path(self.config.get("character", str(ensure_default_asset())))
        self.drag_offset: Optional[QPoint] = None
        self.rice: Optional[QLabel] = None
        self.fire: Optional[QLabel] = None
        self.expire_at: Optional[datetime] = None
        self.control_panel: Optional[ControlPanel] = None
        self.walking_characters: list[WalkingCharacter] = []
        self.canvas = QLabel(self)
        self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setStyleSheet("background: transparent;")
        self.setCentralWidget(self.canvas)
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(QIcon(str(ASSETS / "tray.ico")) if (ASSETS / "tray.ico").exists() else self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        self.tray.setToolTip(APP_NAME); self.tray.setContextMenu(self.menu()); self.tray.show()
        self.apply_config(); self.render()
        self.auto_timer = QTimer(self); self.auto_timer.timeout.connect(self.auto_fire); self.auto_timer.setInterval(max(1, int(self.config.get("interval", 30))) * 60_000); self.auto_timer.start()
        self.cleanup_timer = QTimer(self); self.cleanup_timer.timeout.connect(self.cleanup_rice); self.cleanup_timer.start(5_000)
        self.sim_timer = QTimer(self); self.sim_timer.timeout.connect(self.simulate_event); self.sim_timer.setInterval(max(1, int(self.config.get("simulation_interval", 30))) * 1000); self.sim_timer.start()

    def load_config(self):
        try: return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception: return {"opacity": 100, "size": 520, "auto_feed": True, "interval": 30, "always_on_top": True, "click_through": False, "auto_snap": True, "character": str(ensure_default_asset()), "mode": "simulation", "simulation_enabled": True, "simulation_interval": 30, "sim_balance": 50.0, "debit_min": .01, "debit_max": .10, "credit_min": 1.0, "credit_max": 5.0, "api_keys": {}}

    def save_config(self): CONFIG_PATH.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")

    def apply_config(self):
        size = int(self.config.get("size", 520)); h = max(260, round(size * CANVAS[1] / CANVAS[0])); self.resize(size, h)
        self.setWindowOpacity(max(.2, int(self.config.get("opacity", 100)) / 100))
        if hasattr(self, "auto_timer"):
            self.auto_timer.setInterval(max(1, int(self.config.get("interval", 30))) * 60_000)
        flags = Qt.FramelessWindowHint | Qt.Tool
        if self.config.get("always_on_top", True): flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags); self.show(); self.set_click_through(bool(self.config.get("click_through", False)))

    def set_click_through(self, enabled: bool):
        self.config["click_through"] = enabled
        self.setAttribute(Qt.WA_TransparentForMouseEvents, enabled)
        self.show()

    def render(self):
        pix = QPixmap(str(self.current_image))
        if pix.isNull(): pix = QPixmap(str(ensure_default_asset()))
        self.canvas.setPixmap(pix.scaled(self.canvas.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.canvas.setToolTip("左鍵拖曳移動；右鍵開啟功能選單")

    def resizeEvent(self, event): super().resizeEvent(event); self.render()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton: self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft(); event.accept()
        elif event.button() == Qt.RightButton: self.menu().exec(event.globalPosition().toPoint()); event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_offset is not None and event.buttons() & Qt.LeftButton: self.move(event.globalPosition().toPoint() - self.drag_offset)

    def mouseReleaseEvent(self, event): self.drag_offset = None

    def menu(self):
        m = QMenu(self)
        panel = m.addAction("開啟控制面板…"); panel.triggered.connect(self.open_control_panel)
        mode = self.config.get("mode", "simulation")
        mode_menu = m.addMenu(f"模式（目前：{'模擬' if mode == 'simulation' else 'API'}）")
        sim = mode_menu.addAction("切換到 API 餘額模式" if mode == "simulation" else "切換到模擬模式"); sim.triggered.connect(lambda: self.set_mode("api" if mode == "simulation" else "simulation"))
        key = m.addAction("開啟 API Key 管理…" if not self.config.get("api_keys") else "修改 API Key…"); key.triggered.connect(self.open_api_keys)
        sim_settings = m.addAction("開啟模擬模式控制…" if mode == "simulation" else "切換到模擬模式後控制…"); sim_settings.triggered.connect(self.open_simulation)
        m.addSeparator()
        actors = m.addMenu(f"同時角色（{len(self.walking_characters) + 1}/5）")
        for label, filename in list(BUILTIN_CHARACTERS.items())[:4]:
            action = actors.addAction(f"新增：{label}"); action.setEnabled(len(self.walking_characters) < 4); action.triggered.connect(lambda checked=False, name=filename: self.add_walking_character(name))
        normal_walk = actors.addAction("新增：正常 DeepSeek（三方向走動）"); normal_walk.setEnabled(len(self.walking_characters) < 4); normal_walk.triggered.connect(lambda: self.add_direction_walking_character("deepseek"))
        dark_walk = actors.addAction("新增：黑化 DeepSeek（三方向走動）"); dark_walk.setEnabled(len(self.walking_characters) < 4); dark_walk.triggered.connect(lambda: self.add_direction_walking_character("deepseek_dark"))
        remove = actors.addAction("移除所有額外角色"); remove.triggered.connect(self.remove_walking_characters)
        snap = actors.addAction("自動貼邊：開啟" if self.config.get("auto_snap", True) else "自動貼邊：關閉"); snap.triggered.connect(self.toggle_auto_snap)
        m.addSeparator()
        a = m.addAction("匯入自訂角色…"); a.triggered.connect(self.import_character)
        character_menu = m.addMenu("選擇內建角色")
        for label, filename in BUILTIN_CHARACTERS.items():
            action = character_menu.addAction(label)
            action.triggered.connect(lambda checked=False, name=filename: self.select_character(name))
        a = m.addAction("設定透明度、尺寸與自動功能…"); a.triggered.connect(self.open_settings)
        m.addSeparator()
        a = m.addAction("立即觸發火控 / 掉飯盆"); a.triggered.connect(self.spawn_rice)
        a = m.addAction("清除飯盆"); a.triggered.connect(self.clear_rice)
        a = m.addAction("切換滑鼠穿透"); a.triggered.connect(lambda: self.set_click_through(not self.config.get("click_through", False)))
        a = m.addAction("回到左下角"); a.triggered.connect(self.snap_bottom_left)
        m.addSeparator(); a = m.addAction("退出"); a.triggered.connect(QApplication.quit)
        return m

    def open_control_panel(self):
        if self.control_panel is None:
            self.control_panel = ControlPanel(self)
            self.control_panel.finished.connect(lambda _: setattr(self, "control_panel", None))
        self.control_panel.show(); self.control_panel.raise_(); self.control_panel.activateWindow()

    def open_api_keys(self):
        d = ApiKeyDialog(self); d.exec()

    def open_simulation(self):
        d = SimulationDialog(self); d.exec()

    def set_mode(self, mode: str):
        self.config["mode"] = mode; self.save_config(); self.tray.showMessage(APP_NAME, "已切換到模擬模式" if mode == "simulation" else "已切換到 API 餘額模式", QSystemTrayIcon.Information, 1800)

    def add_walking_character(self, filename: str):
        if len(self.walking_characters) >= 4: return
        image = ASSETS / filename
        if image.exists():
            actor = WalkingCharacter(image, len(self.walking_characters) + 1, self); self.walking_characters.append(actor); actor.show()

    def add_direction_walking_character(self, prefix: str):
        if len(self.walking_characters) >= 4: return
        paths = {name: ASSETS / f"{prefix}_{name}.png" for name in ("front", "side", "back")}
        if all(p.exists() for p in paths.values()):
            actor = WalkingCharacter(paths["front"], len(self.walking_characters) + 1, self, paths); self.walking_characters.append(actor); actor.show()

    def remove_walking_characters(self):
        for actor in self.walking_characters: actor.close()
        self.walking_characters.clear()

    def toggle_auto_snap(self):
        self.config["auto_snap"] = not self.config.get("auto_snap", True); self.save_config()

    def simulate_event(self):
        if self.config.get("mode", "simulation") != "simulation" or not self.config.get("simulation_enabled", True): return
        debit = random.random() < .7
        if debit:
            amount = round(random.uniform(float(self.config.get("debit_min", .01)), float(self.config.get("debit_max", .10))), 2)
            self.config["sim_balance"] = round(float(self.config.get("sim_balance", 50.0)) - amount, 2); self.config["last_sim_event"] = f"扣款 -{amount:.2f}（{datetime.now():%H:%M:%S}）"; self.spawn_rice() if random.random() < .1 else None
        else:
            amount = round(random.uniform(float(self.config.get("credit_min", 1.0)), float(self.config.get("credit_max", 5.0))), 2)
            self.config["sim_balance"] = round(float(self.config.get("sim_balance", 50.0)) + amount, 2); self.config["last_sim_event"] = f"充值 +{amount:.2f}（{datetime.now():%H:%M:%S}）"; self.spawn_rice()
        self.save_config()

    def select_character(self, filename: str):
        candidate = ASSETS / filename
        if candidate.exists():
            self.current_image = candidate
            self.config["character"] = str(candidate)
            self.save_config()
            self.render()

    def import_character(self):
        d = ImportDialog(self)
        if d.exec() != QDialog.Accepted: return
        name, ok = self.ask_name()
        if not ok: return
        target = CUSTOM / f"{name}.png"; fit_to_canvas(Path(d.path), target); self.current_image = target; self.config["character"] = str(target); self.save_config(); self.render()

    def ask_name(self):
        from PySide6.QtWidgets import QInputDialog
        return QInputDialog.getText(self, "角色名稱", "請輸入角色名稱（英文或數字較穩定）：", text="custom_character")

    def open_settings(self):
        d = SettingsDialog(self.config, self); d.changed.connect(self.update_config); d.exec()

    def update_config(self, cfg): self.config = cfg; self.save_config(); self.apply_config(); self.render()

    def spawn_rice(self):
        self.clear_rice()
        self.rice = QLabel(self); self.rice.setText("🍚"); self.rice.setAlignment(Qt.AlignCenter); self.rice.setStyleSheet("font-size: 42px; background: rgba(255,255,255,180); border-radius: 24px; padding: 6px;"); self.rice.resize(76, 76); self.rice.move(max(0, self.width()-100), 20); self.rice.show(); self.expire_at = datetime.now() + timedelta(seconds=45)
        self.fire = QLabel("FIRE", self); self.fire.setStyleSheet("color:#ff713b; font-weight:bold; font-size:14px; background:rgba(255,210,100,180); border-radius:8px; padding:3px;"); self.fire.adjustSize(); self.fire.move(self.width()-80, 105); self.fire.show()

    def clear_rice(self):
        for w in (self.rice, self.fire):
            if w: w.deleteLater()
        self.rice = self.fire = None; self.expire_at = None

    def cleanup_rice(self):
        if self.expire_at and datetime.now() >= self.expire_at: self.clear_rice()

    def auto_fire(self):
        if self.config.get("auto_feed", True) and not self.rice and random.random() < .6: self.spawn_rice()

    def snap_bottom_left(self):
        screen = QApplication.primaryScreen().availableGeometry(); self.move(screen.left() + 20, screen.bottom() - self.height() - 20)


def main():
    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False); w = PetWindow(); w.snap_bottom_left(); w.show(); sys.exit(app.exec())


if __name__ == "__main__": main()
