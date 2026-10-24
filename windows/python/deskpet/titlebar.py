"""Modern custom draggable titlebar with minimize and close controls.
Resolves OS titlebar freezing/disabled glitches in Windows frameless windows.
Strictly zero emojis used anywhere.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from .icons import get_icon


class CustomTitleBar(QWidget):
    def __init__(
        self,
        parent: QWidget,
        title: str = "",
        has_min: bool = True,
        has_close: bool = True,
        theme: str = "dark",
    ):
        super().__init__(parent)
        self._target_window = parent
        self._drag_pos: QPoint | None = None
        self._theme = theme

        self.setFixedHeight(36)
        self.setObjectName("CustomTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 0, 0)
        layout.setSpacing(4)

        self.lb_title = QLabel(title)
        self.lb_title.setObjectName("CustomTitleBarText")
        self.lb_title.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.lb_title)

        layout.addStretch(1)

        if has_min:
            self.btn_min = QPushButton("—")
            self.btn_min.setObjectName("TitleBarMinBtn")
            self.btn_min.setFixedSize(44, 36)
            self.btn_min.setToolTip("最小化")
            self.btn_min.clicked.connect(self._on_minimize)
            layout.addWidget(self.btn_min)
        else:
            self.btn_min = None

        if has_close:
            self.btn_close = QPushButton("✕")
            self.btn_close.setObjectName("TitleBarCloseBtn")
            self.btn_close.setFixedSize(44, 36)
            self.btn_close.setToolTip("關閉視窗")
            self.btn_close.clicked.connect(self._on_close)
            layout.addWidget(self.btn_close)
        else:
            self.btn_close = None

        self.apply_theme(theme)

    def set_title(self, text: str):
        self.lb_title.setText(text)

    def _on_minimize(self):
        win = self.window()
        if win:
            win.showMinimized()

    def _on_close(self):
        win = self.window()
        if win:
            win.close()

    def apply_theme(self, theme: str):
        self._theme = theme
        is_dark = (theme == "dark")
        bg_bar = "#1e1f24" if is_dark else "#edf2f7"
        fg_text = "#e2e8f0" if is_dark else "#1e293b"
        hover_min = "#2e323b" if is_dark else "#cbd5e1"
        btn_fg = "#94a3b8" if is_dark else "#475569"

        self.setStyleSheet(f"""
            QWidget#CustomTitleBar {{
                background-color: {bg_bar};
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }}
            QLabel#CustomTitleBarText {{
                color: {fg_text};
                font-size: 13px;
                font-weight: bold;
                background: transparent;
            }}
            QPushButton#TitleBarMinBtn {{
                background: transparent;
                color: {btn_fg};
                border: none;
                border-radius: 0px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#TitleBarMinBtn:hover {{
                background-color: {hover_min};
                color: {fg_text};
            }}
            QPushButton#TitleBarCloseBtn {{
                background: transparent;
                color: {btn_fg};
                border: none;
                border-top-right-radius: 12px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton#TitleBarCloseBtn:hover {{
                background-color: #e81123;
                color: #ffffff;
            }}
            QPushButton#TitleBarCloseBtn:pressed {{
                background-color: #bf0f1d;
                color: #ffffff;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            win = self.window()
            if win:
                self._drag_pos = event.globalPosition().toPoint() - win.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            win = self.window()
            if win:
                win.move(event.globalPosition().toPoint() - self._drag_pos)
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)
