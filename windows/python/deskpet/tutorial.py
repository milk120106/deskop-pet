"""Novice tutorial walkthrough for Desktop Pet: Material Design 3 style guide."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

TUTORIAL_STEPS = [
    {
        "title": "歡迎使用 Desktop Pet 桌面寵物",
        "subtitle": "專為桌面設計的智慧互動掛件與多模型 API 餘額即時監控助手",
        "items": [
            ("桌面常駐", "透明無邊框，常駐在螢幕邊界，隨時伴隨在旁。"),
            ("滑鼠穿透", "隨時可在選單中開啟滑鼠穿透，不干擾日常辦公與游標點擊。"),
            ("智慧吸附", "拖曳放開後自動平滑貼合螢幕邊角，並根據左/右側自動轉向鏡像。"),
        ],
    },
    {
        "title": "平板螢幕與多模型餘額",
        "subtitle": "手持平板即時監控 API 餘額與峰谷時段",
        "items": [
            ("即時餘額顯示", "正面第一頁清晰呈現目前 AI 模型的剩餘額度或今日使用量。"),
            ("雙擊平板翻頁", "滑鼠左鍵雙擊平板區域，即可切換至「第二頁：峰谷時段與用量資訊」。"),
            ("多模型支援", "支援 DeepSeek、Claude、OpenAI、Gemini，切換角色即時更新對應餘額。"),
        ],
    },
    {
        "title": "互動、摸頭與餵食防護",
        "subtitle": "生動的物理碰撞、情緒反饋與道具玩法",
        "items": [
            ("摸頭按壓", "在角色頭頂來回滑動滑鼠撫摸，角色會產生彈性按壓形變、飄出愛心並轉為害羞表情。"),
            ("充值餵食", "餘額充值時會從空中掉落香噴噴的米飯盆，多個飯盆之間具有物理彈開推擠碰撞。"),
            ("防護鐵盆", "吃完飯後鐵盆會扣在頭頂防護；點擊或雙擊頭頂即可清脆取下鐵盆。"),
            ("火控雷達", "飯盆閒置 10 秒後，角色進入傲嬌狀態並啟動重力吸引，自動吸入食入帳。"),
        ],
    },
    {
        "title": "AI 對話視窗與控制台",
        "subtitle": "完整的生產力工具與豐富設定",
        "items": [
            ("AI 對話視窗", "隨時透過右鍵選單呼叫對話小視窗，支援文字輸入、語音辨識、模型自由切換與長期記憶。"),
            ("控制台中心", "右鍵點擊寵物或系統匣選單選擇「控制台」，可自由設定尺寸、透明度、主題與全域日誌。"),
            ("快捷操作", "右鍵點擊寵物即可彈出完整功能選單，回到角落預設置於右下角。"),
        ],
    },
]

MD3_DIALOG_LIGHT_QSS = """
QDialog {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 16px;
}
QLabel {
    color: #1e293b;
    font-family: 'Segoe UI Variable Text', 'Microsoft JhengHei UI', 'PingFang TC', 'Noto Sans TC', sans-serif;
    background: transparent;
}
#TitleLabel {
    font-size: 20px;
    font-weight: bold;
    color: #1e40af;
}
#SubtitleLabel {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 8px;
}
QFrame#CardFrame {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 12px;
}
QLabel#ItemTitle {
    font-size: 14px;
    font-weight: bold;
    color: #1d4ed8;
}
QLabel#ItemDesc {
    font-size: 12px;
    color: #475569;
    line-height: 1.4;
}
QPushButton {
    background-color: #e2e8f0;
    color: #1e293b;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #cbd5e1;
    border-color: #94a3b8;
}
QPushButton:pressed {
    background-color: #b0c0d0;
}
QPushButton#PrimaryBtn {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    font-weight: bold;
}
QPushButton#PrimaryBtn:hover {
    background-color: #1d4ed8;
}
QPushButton#PrimaryBtn:pressed {
    background-color: #1e40af;
}
"""

MD3_DIALOG_QSS = """
QDialog {
    background-color: #1a1c1e;
    border: 1px solid #43474e;
    border-radius: 16px;
}
QLabel {
    color: #e2e2e6;
    font-family: 'Segoe UI Variable Text', 'Microsoft JhengHei UI', 'PingFang TC', 'Noto Sans TC', sans-serif;
    background: transparent;
}
#TitleLabel {
    font-size: 20px;
    font-weight: bold;
    color: #90caf9;
}
#SubtitleLabel {
    font-size: 13px;
    color: #8c9199;
    margin-bottom: 8px;
}
QFrame#CardFrame {
    background-color: #212429;
    border: 1px solid #32373f;
    border-radius: 12px;
    padding: 12px;
}
QLabel#ItemTitle {
    font-size: 14px;
    font-weight: bold;
    color: #c4e7ff;
}
QLabel#ItemDesc {
    font-size: 12px;
    color: #c4c7c5;
    line-height: 1.4;
}
QPushButton {
    background-color: #2e333d;
    color: #e2e2e6;
    border: 1px solid #43474e;
    border-radius: 8px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #3b424e;
    border-color: #72777f;
}
QPushButton:pressed {
    background-color: #232832;
}
QPushButton#PrimaryBtn {
    background-color: #3b82f6;
    color: #ffffff;
    border: none;
    font-weight: bold;
}
QPushButton#PrimaryBtn:hover {
    background-color: #2563eb;
}
QPushButton#PrimaryBtn:pressed {
    background-color: #1d4ed8;
}
"""


class TutorialDialog(QDialog):
    def __init__(self, parent=None, theme="dark"):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(MD3_DIALOG_QSS if theme == "dark" else MD3_DIALOG_LIGHT_QSS)
        self.resize(520, 480)
        self.step_idx = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(14)

        # Header
        top_bar = QHBoxLayout()
        self.title_lbl = QLabel()
        self.title_lbl.setObjectName("TitleLabel")
        top_bar.addWidget(self.title_lbl)
        top_bar.addStretch()
        close_btn = QPushButton("關閉")
        close_btn.setFixedSize(60, 28)
        close_btn.clicked.connect(self.reject)
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)

        self.sub_lbl = QLabel()
        self.sub_lbl.setObjectName("SubtitleLabel")
        self.sub_lbl.setWordWrap(True)
        layout.addWidget(self.sub_lbl)

        # Pages Stack
        self.stack = QStackedWidget()
        for s in TUTORIAL_STEPS:
            page = QWidget()
            pl = QVBoxLayout(page)
            pl.setContentsMargins(0, 4, 0, 4)
            pl.setSpacing(10)
            for it_title, it_desc in s["items"]:
                card = QFrame()
                card.setObjectName("CardFrame")
                cl = QVBoxLayout(card)
                cl.setContentsMargins(12, 10, 12, 10)
                cl.setSpacing(4)
                t = QLabel(it_title)
                t.setObjectName("ItemTitle")
                d = QLabel(it_desc)
                d.setObjectName("ItemDesc")
                d.setWordWrap(True)
                cl.addWidget(t)
                cl.addWidget(d)
                pl.addWidget(card)
            pl.addStretch()
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

        # Bottom Bar: step indicator + navigation buttons
        bar = QHBoxLayout()
        bar.setSpacing(12)

        self.indicator_lbl = QLabel()
        self.indicator_lbl.setStyleSheet("color: #8c9199; font-size: 12px;")
        bar.addWidget(self.indicator_lbl)
        bar.addStretch()

        self.prev_btn = QPushButton("上一步")
        self.prev_btn.clicked.connect(self.go_prev)
        bar.addWidget(self.prev_btn)

        self.next_btn = QPushButton("下一步")
        self.next_btn.setObjectName("PrimaryBtn")
        self.next_btn.clicked.connect(self.go_next)
        bar.addWidget(self.next_btn)

        layout.addLayout(bar)
        self._update_step()

    def showEvent(self, e):
        super().showEvent(e)
        from PySide6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.x() + max(0, (geo.width() - self.width()) // 2)
            y = geo.y() + max(0, (geo.height() - self.height()) // 2)
            self.move(x, y)
        self.raise_()
        self.activateWindow()

    def _update_step(self):
        s = TUTORIAL_STEPS[self.step_idx]
        self.title_lbl.setText(s["title"])
        self.sub_lbl.setText(s["subtitle"])
        self.stack.setCurrentIndex(self.step_idx)
        self.indicator_lbl.setText(f"步驟 {self.step_idx + 1} / {len(TUTORIAL_STEPS)}")
        self.prev_btn.setEnabled(self.step_idx > 0)
        if self.step_idx == len(TUTORIAL_STEPS) - 1:
            self.next_btn.setText("開始體驗")
        else:
            self.next_btn.setText("下一步")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if getattr(self, "_drag_pos", None) and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def go_prev(self):
        if self.step_idx > 0:
            self.step_idx -= 1
            self._update_step()

    def go_next(self):
        if self.step_idx < len(TUTORIAL_STEPS) - 1:
            self.step_idx += 1
            self._update_step()
        else:
            self.accept()
