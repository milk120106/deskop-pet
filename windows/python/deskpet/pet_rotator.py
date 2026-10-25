# -*- coding: utf-8 -*-
"""寵物自由旋轉器與角度調節視窗。"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .dialogs import DIALOG_LIGHT_QSS


class PetRotationDialog(QDialog):
    """寵物自由旋轉角度調節對話框。"""

    def __init__(self, target_pet, parent: QWidget | None = None):
        super().__init__(parent)
        self.pet = target_pet
        self.setWindowTitle("寵物自由旋轉調節")
        self.setFixedSize(360, 260)
        self.setStyleSheet(DIALOG_LIGHT_QSS)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        # 標題與說明
        title_lbl = QLabel("寵物旋轉角度調節 (0° ~ 360°)")
        title_lbl.setFont(QFont("Microsoft JhengHei UI", 12, QFont.Bold))
        lay.addWidget(title_lbl)

        # 數值控制列 (滑桿 + SpinBox)
        val_lay = QHBoxLayout()
        val_lay.setSpacing(10)

        cur_rot = int(round(getattr(self.pet, "rotation_angle", 0.0))) % 360

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 360)
        self.slider.setValue(cur_rot)
        self.slider.valueChanged.connect(self._on_slider_changed)
        val_lay.addWidget(self.slider, 1)

        self.spin = QSpinBox()
        self.spin.setRange(0, 360)
        self.spin.setValue(cur_rot)
        self.spin.setSuffix("°")
        self.spin.setFixedWidth(75)
        self.spin.valueChanged.connect(self._on_spin_changed)
        val_lay.addWidget(self.spin)

        lay.addLayout(val_lay)

        # 快捷微調列 (-15°, +15°, 水平鏡像)
        step_lay = QHBoxLayout()
        step_lay.setSpacing(8)

        btn_step_m15 = QPushButton("－15°")
        btn_step_m15.clicked.connect(lambda: self._adjust_by(-15))
        step_lay.addWidget(btn_step_m15)

        btn_step_p15 = QPushButton("＋15°")
        btn_step_p15.clicked.connect(lambda: self._adjust_by(15))
        step_lay.addWidget(btn_step_p15)

        btn_flip = QPushButton("水平鏡像翻轉")
        btn_flip.clicked.connect(self._on_flip)
        step_lay.addWidget(btn_flip)

        lay.addLayout(step_lay)

        # 常用固定角度預設
        preset_lay = QHBoxLayout()
        preset_lay.setSpacing(6)

        presets = [
            ("0° (正立)", 0),
            ("90°", 90),
            ("180°", 180),
            ("270°", 270),
        ]
        for text, deg in presets:
            btn = QPushButton(text)
            btn.clicked.connect(lambda _=False, d=deg: self._set_angle(d))
            preset_lay.addWidget(btn)

        lay.addLayout(preset_lay)

        # 底部確定按鈕
        btn_close = QPushButton("完成")
        btn_close.setDefault(True)
        btn_close.clicked.connect(self.accept)
        lay.addWidget(btn_close)

    def _on_slider_changed(self, val: int):
        self.spin.blockSignals(True)
        self.spin.setValue(val)
        self.spin.blockSignals(False)
        self._apply_to_pet(val)

    def _on_spin_changed(self, val: int):
        self.slider.blockSignals(True)
        self.slider.setValue(val)
        self.slider.blockSignals(False)
        self._apply_to_pet(val)

    def _adjust_by(self, delta: int):
        new_val = (self.slider.value() + delta) % 360
        self.slider.setValue(new_val)

    def _set_angle(self, angle: int):
        self.slider.setValue(angle % 360)

    def _on_flip(self):
        if hasattr(self.pet, "toggle_mirror"):
            self.pet.toggle_mirror()

    def _apply_to_pet(self, angle: int):
        if hasattr(self.pet, "set_rotation_angle"):
            self.pet.set_rotation_angle(float(angle))
