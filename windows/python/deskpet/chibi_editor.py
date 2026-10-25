"""Brand-new standalone Q-Chibi visual pixel art editor (ChibiPixelEditorDialog).
Features canvas grid (default 16x24 or custom size via ignore_limits),
drawing tools (Pencil, Eraser, Bucket, Picker), color palette (current color,
preset swatches, official heroine swatches, custom HEX input), action frame tabs
(idle, walk1, walk2, climb, sit, splat, sleep, run, jump, mischief),
clear canvas warning confirmation, overwrite save warning confirmation,
JSON export, external JSON/PNG import, and protected official repository management.
Strictly zero emojis.
"""
from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import CUSTOM_CHIBI_DIR, log
from .dialogs import DIALOG_DARK_QSS, DIALOG_LIGHT_QSS, ModernMessageBox
from .pixel_chibi import (
    CHAR_PALETTES,
    CHARACTER_INFO,
    FRAMES,
    OFFICIAL_CHIBI_IDS,
    PixelChibiRegistry,
    PixelChibiRenderer,
)
from .titlebar import CustomTitleBar

ACTION_FRAMES = [
    ("idle", "站立 (idle)"),
    ("walk1", "走步左腳 (walk1)"),
    ("walk2", "走步右腳 (walk2)"),
    ("climb", "攀爬 (climb)"),
    ("sit", "坐姿 (sit)"),
    ("splat", "軟趴趴 (splat)"),
    ("sleep", "睡覺 (sleep)"),
    ("run", "快跑 (run)"),
    ("jump", "跳躍 (jump)"),
    ("mischief", "搗亂 (mischief)"),
]

BASIC_PALETTE = [
    # 膚色與腮紅
    "#ffe4d0", "#ffedd5", "#ffe4e6", "#fed7aa", "#fbcfe8", "#f472b6", "#fb7185",
    # 藍色系 (DeepSeek)
    "#1e3a8a", "#1d4ed8", "#1e40af", "#0284c7", "#38bdf8", "#bae6fd", "#e0f2fe",
    # 紫色與銀白系 (GPT 龍娘)
    "#f8fafc", "#e2e8f0", "#cbd5e1", "#8b5cf6", "#c4b5fd", "#ede9fe", "#34d399",
    # 暖橘與棕色系 (Claude 大小姐)
    "#ea580c", "#c2410c", "#fb923c", "#b45309", "#fef3c7", "#78350f", "#451a03",
    # 漸層紫藍與金黃系 (Gemini 貓娘)
    "#7c3aed", "#1e1b4b", "#312e81", "#ec4899", "#fce7f3", "#fbbf24", "#c084fc",
    # 黑白灰
    "#ffffff", "#94a3b8", "#475569", "#1e293b", "#0f172a", "#000000",
]


class PixelCanvasWidget(QWidget):
    """可視化像素畫布網格，支援鉛筆、橡皮擦、油漆桶、吸管繪製。"""
    color_picked = Signal(str)
    pixel_changed = Signal()

    def __init__(self, width: int = 16, height: int = 24, parent: QWidget | None = None):
        super().__init__(parent)
        self.canvas_w = width
        self.canvas_h = height
        self.tool = "pencil"  # pencil, eraser, bucket, picker
        self.current_color = "#1e3a8a"
        self.grid: list[list[str | None]] = [[None for _ in range(width)] for _ in range(height)]
        self.cell_size = 20
        self.hover_cell: tuple[int, int] | None = None

        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._update_widget_size()

    def _update_widget_size(self):
        w = self.canvas_w * self.cell_size
        h = self.canvas_h * self.cell_size
        self.setFixedSize(w, h)
        self.update()

    def set_dimensions(self, width: int, height: int, preserve: bool = True):
        width = max(4, min(128, int(width)))
        height = max(4, min(128, int(height)))
        new_grid: list[list[str | None]] = [[None for _ in range(width)] for _ in range(height)]
        if preserve:
            for y in range(min(height, self.canvas_h)):
                for x in range(min(width, self.canvas_w)):
                    new_grid[y][x] = self.grid[y][x]
        self.canvas_w = width
        self.canvas_h = height
        self.grid = new_grid
        self._update_widget_size()
        self.pixel_changed.emit()

    def clear_canvas(self):
        """清空當前畫布所有像素為透明。"""
        self.grid = [[None for _ in range(self.canvas_w)] for _ in range(self.canvas_h)]
        self.update()
        self.pixel_changed.emit()

    def get_grid_pixels(self) -> list[list[str | None]]:
        return [row[:] for row in self.grid]

    def set_grid_pixels(self, pixels: list[list[str | None]]):
        h = len(pixels)
        w = len(pixels[0]) if h > 0 else 16
        if w != self.canvas_w or h != self.canvas_h:
            self.canvas_w = w
            self.canvas_h = h
            self._update_widget_size()
        self.grid = [row[:] for row in pixels]
        self.update()
        self.pixel_changed.emit()

    def load_matrix(self, rows: list[str], palette: dict[str, str], w: int = 16, h: int = 24):
        self.canvas_w = w
        self.canvas_h = h
        new_grid: list[list[str | None]] = [[None for _ in range(w)] for _ in range(h)]
        for y, row_str in enumerate(rows):
            if y >= h:
                break
            for x, ch in enumerate(row_str):
                if x >= w:
                    break
                if ch in (".", " "):
                    new_grid[y][x] = None
                else:
                    c = palette.get(ch)
                    new_grid[y][x] = c.lower() if c else None
        self.grid = new_grid
        self._update_widget_size()
        self.pixel_changed.emit()

    def export_matrix(self, color_to_sym: dict[str, str]) -> list[str]:
        rows: list[str] = []
        for y in range(self.canvas_h):
            row_chars = []
            for x in range(self.canvas_w):
                c = self.grid[y][x]
                if not c:
                    row_chars.append(".")
                else:
                    sym = color_to_sym.get(c.lower(), ".")
                    row_chars.append(sym)
            rows.append("".join(row_chars))
        return rows

    def get_used_colors(self) -> set[str]:
        res = set()
        for row in self.grid:
            for cell in row:
                if cell:
                    res.add(cell.lower())
        return res

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)

        cs = self.cell_size
        check1 = QColor(245, 245, 245)
        check2 = QColor(220, 220, 220)

        # 1. 繪製棋盤透明背景與像素色塊
        for y in range(self.canvas_h):
            for x in range(self.canvas_w):
                rx = x * cs
                ry = y * cs
                # 棋盤底圖
                p.fillRect(rx, ry, cs, cs, check1 if ((x + y) % 2 == 0) else check2)

                col_hex = self.grid[y][x]
                if col_hex:
                    p.fillRect(rx, ry, cs, cs, QColor(col_hex))

        # 2. 繪製精細格線
        pen = QPen(QColor(180, 190, 205, 120))
        pen.setWidth(1)
        p.setPen(pen)
        for x in range(self.canvas_w + 1):
            p.drawLine(x * cs, 0, x * cs, self.canvas_h * cs)
        for y in range(self.canvas_h + 1):
            p.drawLine(0, y * cs, self.canvas_w * cs, y * cs)

        # 3. 繪製游標懸停提示邊框
        if self.hover_cell:
            hx, hy = self.hover_cell
            if 0 <= hx < self.canvas_w and 0 <= hy < self.canvas_h:
                hover_pen = QPen(QColor(37, 99, 235), 2)
                p.setPen(hover_pen)
                p.setBrush(Qt.NoBrush)
                p.drawRect(hx * cs, hy * cs, cs, cs)

    def _pos_to_cell(self, pos: QPoint) -> tuple[int, int] | None:
        x = pos.x() // self.cell_size
        y = pos.y() // self.cell_size
        if 0 <= x < self.canvas_w and 0 <= y < self.canvas_h:
            return int(x), int(y)
        return None

    def mousePressEvent(self, e):
        cell = self._pos_to_cell(e.pos())
        if not cell:
            return
        x, y = cell
        if e.button() == Qt.LeftButton:
            self._apply_tool(x, y)
        elif e.button() == Qt.RightButton:
            # 右鍵吸管或快速擦除
            if self.grid[y][x]:
                self.color_picked.emit(self.grid[y][x])
            else:
                self.grid[y][x] = None
                self.update()
                self.pixel_changed.emit()

    def mouseMoveEvent(self, e):
        cell = self._pos_to_cell(e.pos())
        if cell != self.hover_cell:
            self.hover_cell = cell
            self.update()

        if e.buttons() & Qt.LeftButton and cell:
            x, y = cell
            if self.tool in ("pencil", "eraser"):
                self._apply_tool(x, y)

    def leaveEvent(self, _):
        self.hover_cell = None
        self.update()

    def _apply_tool(self, x: int, y: int):
        if self.tool == "pencil":
            target_col = self.current_color.lower()
            if self.grid[y][x] != target_col:
                self.grid[y][x] = target_col
                self.update()
                self.pixel_changed.emit()
        elif self.tool == "eraser":
            if self.grid[y][x] is not None:
                self.grid[y][x] = None
                self.update()
                self.pixel_changed.emit()
        elif self.tool == "picker":
            col = self.grid[y][x]
            if col:
                self.color_picked.emit(col)
        elif self.tool == "bucket":
            self._flood_fill(x, y, self.current_color.lower())

    def _flood_fill(self, start_x: int, start_y: int, fill_color: str):
        target_color = self.grid[start_y][start_x]
        if target_color == fill_color:
            return

        q = deque([(start_x, start_y)])
        visited = set([(start_x, start_y)])

        while q:
            cx, cy = q.popleft()
            self.grid[cy][cx] = fill_color
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < self.canvas_w and 0 <= ny < self.canvas_h:
                    if (nx, ny) not in visited and self.grid[ny][nx] == target_color:
                        visited.add((nx, ny))
                        q.append((nx, ny))

        self.update()
        self.pixel_changed.emit()


class MiniPreviewWidget(QWidget):
    """即時動態小人行走預覽視窗。"""
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(140, 160)
        self.pixmaps: list[QPixmap] = []
        self.frame_idx = 0
        self.timer = QTimer(self)
        self.timer.setInterval(220)
        self.timer.timeout.connect(self._next_frame)
        self.timer.start()

    def _next_frame(self):
        if self.pixmaps:
            self.frame_idx = (self.frame_idx + 1) % len(self.pixmaps)
            self.update()

    def update_frames(self, pixmaps: list[QPixmap]):
        self.pixmaps = pixmaps
        self.frame_idx = 0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), QColor(241, 245, 249))

        if self.pixmaps and self.frame_idx < len(self.pixmaps):
            pm = self.pixmaps[self.frame_idx]
            if not pm.isNull():
                target_w = pm.width() * 2
                target_h = pm.height() * 2
                scaled = pm.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.FastTransformation)
                px = (self.width() - scaled.width()) // 2
                py = (self.height() - scaled.height()) // 2
                p.drawPixmap(px, py, scaled)


class ChibiPixelEditorDialog(QDialog):
    """Q 版人物可視化像素編輯器獨立現代無邊框視窗。
    支援網格自訂、像素工具、調色盤、多動作幀切換、清空警告、覆蓋警告與匯入匯出。
    """
    def __init__(self, parent: QWidget | None = None, cfg=None, app=None):
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint
        )
        self.cfg = cfg
        self.app = app
        theme = (cfg.get("theme", "light") if cfg else "light")
        self.theme = theme
        self.is_dark = (theme == "dark")

        self.setObjectName("ChibiPixelEditorDialog")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(DIALOG_DARK_QSS if self.is_dark else DIALOG_LIGHT_QSS)
        self.resize(980, 720)

        # 動作幀資料結構: frame_name -> list[list[str | None]]
        self.current_frame = "idle"
        self.frames_data: dict[str, list[list[str | None]]] = {}
        for fname, _ in ACTION_FRAMES:
            self.frames_data[fname] = [[None for _ in range(16)] for _ in range(24)]

        self._init_ui()
        self._load_official_template("deepseek")
        self._center_window()

    def _init_ui(self):
        root_lay = QVBoxLayout(self)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # 標題列
        self.title_bar = CustomTitleBar(
            self,
            title="Q 版人物像素可視化編輯器",
            has_min=False,
            has_close=True,
            theme="dark" if self.is_dark else "light",
        )
        root_lay.addWidget(self.title_bar)

        # 主工作區
        main_widget = QWidget(self)
        main_lay = QHBoxLayout(main_widget)
        main_lay.setContentsMargins(14, 10, 14, 12)
        main_lay.setSpacing(14)

        # -------------------------------------------------------------
        # 左側欄：工具列、調色盤與預覽
        # -------------------------------------------------------------
        left_panel = QWidget()
        left_lay = QVBoxLayout(left_panel)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(10)

        # 繪圖工具群組
        tool_box = QGroupBox("繪圖工具")
        tool_lay = QGridLayout(tool_box)
        tool_lay.setSpacing(6)

        self.btn_pencil = QPushButton("鉛筆 (B)")
        self.btn_eraser = QPushButton("橡皮擦 (E)")
        self.btn_bucket = QPushButton("油漆桶 (G)")
        self.btn_picker = QPushButton("吸管取色 (I)")

        self.btn_pencil.setCheckable(True)
        self.btn_eraser.setCheckable(True)
        self.btn_bucket.setCheckable(True)
        self.btn_picker.setCheckable(True)
        self.btn_pencil.setChecked(True)

        self.btn_pencil.clicked.connect(lambda: self._set_tool("pencil"))
        self.btn_eraser.clicked.connect(lambda: self._set_tool("eraser"))
        self.btn_bucket.clicked.connect(lambda: self._set_tool("bucket"))
        self.btn_picker.clicked.connect(lambda: self._set_tool("picker"))

        tool_lay.addWidget(self.btn_pencil, 0, 0)
        tool_lay.addWidget(self.btn_eraser, 0, 1)
        tool_lay.addWidget(self.btn_bucket, 1, 0)
        tool_lay.addWidget(self.btn_picker, 1, 1)
        left_lay.addWidget(tool_box)

        # 調色盤群組
        palette_box = QGroupBox("色彩與色盤")
        pal_lay = QVBoxLayout(palette_box)
        pal_lay.setSpacing(8)

        # 當前色檢視與輸入
        cur_col_row = QHBoxLayout()
        self.color_swatch = QFrame()
        self.color_swatch.setFixedSize(32, 32)
        self.color_swatch.setStyleSheet(f"background-color: #1e3a8a; border: 1px solid #94a3b8; border-radius: 4px;")
        cur_col_row.addWidget(self.color_swatch)

        self.txt_hex = QLineEdit("#1e3a8a")
        self.txt_hex.setFixedWidth(85)
        self.txt_hex.textChanged.connect(self._on_hex_text_changed)
        cur_col_row.addWidget(self.txt_hex)

        btn_pick_color = QPushButton("自訂色彩...")
        btn_pick_color.clicked.connect(self._choose_custom_color)
        cur_col_row.addWidget(btn_pick_color)
        cur_col_row.addStretch(1)
        pal_lay.addLayout(cur_col_row)

        # 色盤範本切換下拉選單
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("色盤預設："))
        self.cmb_palette_preset = QComboBox()
        self.cmb_palette_preset.addItems([
            "基本通用色盤",
            "藍色大肥魚色盤 (DeepSeek)",
            "GPT龍娘色盤 (OpenAI)",
            "大小姐Claude色盤 (Anthropic)",
            "北美貓娘Gemini色盤 (Google)",
        ])
        self.cmb_palette_preset.currentIndexChanged.connect(self._on_palette_preset_changed)
        preset_row.addWidget(self.cmb_palette_preset, 1)
        pal_lay.addLayout(preset_row)

        # 快速色塊網格 (點選立即換色)
        self.swatches_widget = QWidget()
        self.swatches_grid = QGridLayout(self.swatches_widget)
        self.swatches_grid.setSpacing(4)
        self.swatches_grid.setContentsMargins(0, 0, 0, 0)
        self._populate_swatches(BASIC_PALETTE)
        pal_lay.addWidget(self.swatches_widget)

        left_lay.addWidget(palette_box)

        # 即時行走動畫預覽
        prev_box = QGroupBox("動態巡邏預覽")
        prev_lay = QVBoxLayout(prev_box)
        prev_lay.setAlignment(Qt.AlignCenter)
        self.preview_widget = MiniPreviewWidget(self)
        prev_lay.addWidget(self.preview_widget)
        left_lay.addWidget(prev_box)

        left_lay.addStretch(1)
        main_lay.addWidget(left_panel, 0)

        # -------------------------------------------------------------
        # 中央主區：頂部參數列、動作幀頁籤、畫布、底部指令
        # -------------------------------------------------------------
        center_panel = QWidget()
        center_lay = QVBoxLayout(center_panel)
        center_lay.setContentsMargins(0, 0, 0, 0)
        center_lay.setSpacing(8)

        # 頂部參數列 (角色代號、名稱、尺寸、不顧限制標記)
        info_box = QGroupBox("角色資訊與畫布規格")
        info_lay = QHBoxLayout(info_box)
        info_lay.setSpacing(10)

        info_lay.addWidget(QLabel("代號："))
        self.txt_id = QLineEdit("chibi_custom")
        self.txt_id.setFixedWidth(110)
        info_lay.addWidget(self.txt_id)

        info_lay.addWidget(QLabel("名稱："))
        self.txt_name = QLineEdit("自訂人物")
        self.txt_name.setFixedWidth(120)
        info_lay.addWidget(self.txt_name)

        # 寬高調節與不顧限制
        info_lay.addWidget(QLabel("寬度："))
        self.spin_w = QSpinBox()
        self.spin_w.setRange(4, 128)
        self.spin_w.setValue(16)
        self.spin_w.setEnabled(False)
        self.spin_w.valueChanged.connect(self._on_size_spin_changed)
        info_lay.addWidget(self.spin_w)

        info_lay.addWidget(QLabel("高度："))
        self.spin_h = QSpinBox()
        self.spin_h.setRange(4, 128)
        self.spin_h.setValue(24)
        self.spin_h.setEnabled(False)
        self.spin_h.valueChanged.connect(self._on_size_spin_changed)
        info_lay.addWidget(self.spin_h)

        self.chk_ignore_limits = QCheckBox("不顧限制（允許非 16x24 任意尺寸）")
        self.chk_ignore_limits.toggled.connect(self._on_ignore_limits_toggled)
        info_lay.addWidget(self.chk_ignore_limits)

        info_lay.addStretch(1)
        center_lay.addWidget(info_box)

        # 動作幀切換頁籤 (idle, walk1, walk2, climb, sit, splat, sleep, run, jump, mischief)
        frame_bar_row = QHBoxLayout()
        self.tab_frames = QTabBar()
        self.tab_frames.setDrawBase(False)
        for _, label in ACTION_FRAMES:
            self.tab_frames.addTab(label)
        self.tab_frames.currentChanged.connect(self._on_frame_tab_changed)
        frame_bar_row.addWidget(self.tab_frames, 1)

        btn_copy_frame = QPushButton("複製當前幀到其他動作...")
        btn_copy_frame.clicked.connect(self._copy_current_frame_to_all)
        frame_bar_row.addWidget(btn_copy_frame)

        btn_load_template = QPushButton("載入範本幀...")
        btn_load_template.clicked.connect(self._choose_template_frame)
        frame_bar_row.addWidget(btn_load_template)

        center_lay.addLayout(frame_bar_row)

        # 像素畫布滾動區域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setStyleSheet("background-color: #e2e8f0; border: 1px solid #cbd5e1; border-radius: 8px;")

        self.canvas = PixelCanvasWidget(16, 24, self)
        self.canvas.color_picked.connect(self._on_color_picked)
        self.canvas.pixel_changed.connect(self._on_canvas_pixel_changed)
        scroll.setWidget(self.canvas)
        center_lay.addWidget(scroll, 1)

        # 底部動作操作列
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # 清空畫布按鈕 (必須彈出警告確認)
        self.btn_clear = QPushButton("清空當前畫布")
        self.btn_clear.clicked.connect(self._on_clear_canvas_clicked)
        btn_row.addWidget(self.btn_clear)

        # 外部匯入與匯出
        btn_import = QPushButton("匯入外部檔案 (JSON/PNG)...")
        btn_import.clicked.connect(self._import_file)
        btn_row.addWidget(btn_import)

        btn_export = QPushButton("匯出為 .json...")
        btn_export.clicked.connect(self._export_json)
        btn_row.addWidget(btn_export)

        btn_row.addStretch(1)

        # 儲存至角色庫 (覆蓋同名必須彈出確認)
        self.btn_save = QPushButton("儲存至角色庫")
        self.btn_save.setObjectName("primary")
        self.btn_save.setMinimumWidth(120)
        self.btn_save.clicked.connect(self._save_to_repository)
        btn_row.addWidget(self.btn_save)

        btn_close = QPushButton("關閉")
        btn_close.setMinimumWidth(80)
        btn_close.clicked.connect(self.close)
        btn_row.addWidget(btn_close)

        center_lay.addLayout(btn_row)
        main_lay.addWidget(center_panel, 1)

        # -------------------------------------------------------------
        # 右側欄：人物儲存庫管理清單
        # -------------------------------------------------------------
        repo_panel = QWidget()
        repo_panel.setFixedWidth(240)
        repo_lay = QVBoxLayout(repo_panel)
        repo_lay.setContentsMargins(0, 0, 0, 0)
        repo_lay.setSpacing(8)

        repo_box = QGroupBox("角色庫管理器")
        repo_inner = QVBoxLayout(repo_box)
        repo_inner.setSpacing(6)

        self.list_repo = QListWidget()
        self.list_repo.itemClicked.connect(self._on_repo_item_clicked)
        repo_inner.addWidget(self.list_repo, 1)

        self.btn_load_repo = QPushButton("載入此角色至編輯器")
        self.btn_load_repo.clicked.connect(self._load_selected_repo_char)
        repo_inner.addWidget(self.btn_load_repo)

        # 刪除自訂人物 (官方保護絕不允許刪除，刪除自訂必須彈出確認)
        self.btn_del_repo = QPushButton("刪除自訂角色")
        self.btn_del_repo.clicked.connect(self._delete_selected_repo_char)
        repo_inner.addWidget(self.btn_del_repo)

        repo_lay.addWidget(repo_box)
        main_lay.addWidget(repo_panel, 0)

        root_lay.addWidget(main_widget, 1)

        self._refresh_repo_list()

    def _center_window(self):
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.left() + (geo.width() - self.width()) // 2
            y = geo.top() + (geo.height() - self.height()) // 2
            self.move(x, y)

    # ----------------------------------------------------------------- 工具切換與色彩處理
    def _set_tool(self, tool_name: str):
        self.canvas.tool = tool_name
        self.btn_pencil.setChecked(tool_name == "pencil")
        self.btn_eraser.setChecked(tool_name == "eraser")
        self.btn_bucket.setChecked(tool_name == "bucket")
        self.btn_picker.setChecked(tool_name == "picker")

    def _on_color_picked(self, hex_color: str):
        self._set_current_color(hex_color)
        self._set_tool("pencil")

    def _set_current_color(self, hex_color: str):
        hex_color = hex_color.strip().lower()
        if not hex_color.startswith("#"):
            hex_color = "#" + hex_color
        if len(hex_color) == 7 and QColor(hex_color).isValid():
            self.canvas.current_color = hex_color
            self.color_swatch.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #94a3b8; border-radius: 4px;")
            self.txt_hex.blockSignals(True)
            self.txt_hex.setText(hex_color)
            self.txt_hex.blockSignals(False)

    def _on_hex_text_changed(self, text: str):
        t = text.strip().lower()
        if not t.startswith("#"):
            t = "#" + t
        if len(t) == 7 and QColor(t).isValid():
            self._set_current_color(t)

    def _choose_custom_color(self):
        c = QColorDialog.getColor(QColor(self.canvas.current_color), self, "選擇繪圖色彩")
        if c.isValid():
            self._set_current_color(c.name(QColor.HexRgb))

    def _on_palette_preset_changed(self, idx: int):
        if idx == 1:
            colors = list(CHAR_PALETTES.get("deepseek", {}).values())
        elif idx == 2:
            colors = list(CHAR_PALETTES.get("gpt", {}).values())
        elif idx == 3:
            colors = list(CHAR_PALETTES.get("claude", {}).values())
        elif idx == 4:
            colors = list(CHAR_PALETTES.get("gemini", {}).values())
        else:
            colors = BASIC_PALETTE
        self._populate_swatches(colors)

    def _populate_swatches(self, colors: list[str]):
        # 清除舊色塊按鈕
        while self.swatches_grid.count():
            item = self.swatches_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        unique_cols = list(dict.fromkeys(c.lower() for c in colors if c and c.startswith("#")))
        cols_per_row = 7
        for i, col in enumerate(unique_cols):
            btn = QPushButton()
            btn.setFixedSize(22, 22)
            btn.setStyleSheet(f"background-color: {col}; border: 1px solid #64748b; border-radius: 3px;")
            btn.setToolTip(col)
            btn.clicked.connect(lambda _=False, c=col: self._set_current_color(c))
            row = i // cols_per_row
            c_idx = i % cols_per_row
            self.swatches_grid.addWidget(btn, row, c_idx)

    # ----------------------------------------------------------------- 動作幀切換與範本
    def _save_current_frame_to_cache(self):
        self.frames_data[self.current_frame] = self.canvas.get_grid_pixels()

    def _on_frame_tab_changed(self, idx: int):
        if 0 <= idx < len(ACTION_FRAMES):
            self._save_current_frame_to_cache()
            new_fname, _ = ACTION_FRAMES[idx]
            self.current_frame = new_fname
            target_grid = self.frames_data.get(new_fname)
            if target_grid:
                self.canvas.set_grid_pixels(target_grid)
            else:
                self.canvas.clear_canvas()
            self._update_preview()

    def _copy_current_frame_to_all(self):
        cur_pixels = self.canvas.get_grid_pixels()
        for fname, _ in ACTION_FRAMES:
            self.frames_data[fname] = [row[:] for row in cur_pixels]
        ModernMessageBox.information(self, "複製完成", "已將當前動作幀成功複製至所有動作幀中！")
        self._update_preview()

    def _choose_template_frame(self):
        dlg = QDialog(self, Qt.FramelessWindowHint | Qt.Window)
        dlg.setStyleSheet(self.styleSheet())
        dlg.setFixedSize(320, 240)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(0, 0, 0, 0)
        tb = CustomTitleBar(dlg, "選擇範本人物", has_min=False, has_close=True, theme="dark" if self.is_dark else "light")
        lay.addWidget(tb)

        content = QWidget()
        c_lay = QVBoxLayout(content)
        c_lay.addWidget(QLabel("請選擇欲載入之官方角色範本："))
        cmb = QComboBox()
        cmb.addItem("藍色大肥魚 (DeepSeek 鯨魚娘)", "deepseek")
        cmb.addItem("GPT龍娘 (OpenAI 白龍娘)", "gpt")
        cmb.addItem("大小姐Claude (Anthropic 大小姐)", "claude")
        cmb.addItem("北美貓娘Gemini (Google 北美貓娘)", "gemini")
        c_lay.addWidget(cmb)

        chk_all = QCheckBox("載入全部動作幀（覆寫目前所有動作）")
        chk_all.setChecked(True)
        c_lay.addWidget(chk_all)

        btn_ok = QPushButton("確定載入")
        btn_ok.setObjectName("primary")
        btn_ok.clicked.connect(dlg.accept)
        c_lay.addWidget(btn_ok)
        lay.addWidget(content, 1)

        if dlg.exec() == QDialog.Accepted:
            cid = cmb.currentData()
            load_all = chk_all.isChecked()
            if load_all:
                self._load_official_template(cid)
            else:
                raw_rows = FRAMES.get(self.current_frame, FRAMES["idle"])
                pal = CHAR_PALETTES.get(cid, {})
                self.canvas.load_matrix(raw_rows, pal, 16, 24)
                self.frames_data[self.current_frame] = self.canvas.get_grid_pixels()
            self._update_preview()

    def _load_official_template(self, cid: str):
        info = PixelChibiRegistry.get_character(cid)
        if not info:
            return
        w = info.get("width", 16)
        h = info.get("height", 24)
        pal = info.get("palette", {})
        frames = info.get("frames", {})

        self.spin_w.blockSignals(True)
        self.spin_h.blockSignals(True)
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)
        self.spin_w.blockSignals(False)
        self.spin_h.blockSignals(False)

        for fname, _ in ACTION_FRAMES:
            rows = frames.get(fname) or frames.get("idle") or FRAMES.get(fname, FRAMES["idle"])
            grid = [[None for _ in range(w)] for _ in range(h)]
            for y, row_str in enumerate(rows):
                if y >= h:
                    break
                for x, ch in enumerate(row_str):
                    if x >= w:
                        break
                    if ch not in (".", " ") and ch in pal:
                        grid[y][x] = pal[ch].lower()
            self.frames_data[fname] = grid

        cur_grid = self.frames_data.get(self.current_frame, self.frames_data["idle"])
        self.canvas.set_grid_pixels(cur_grid)
        self._update_preview()

    def _on_canvas_pixel_changed(self):
        self._save_current_frame_to_cache()
        self._update_preview()

    def _update_preview(self):
        # 渲染 idle, walk1, walk2 預覽影格
        pixmaps = []
        w = self.canvas.canvas_w
        h = self.canvas.canvas_h
        for f in ["idle", "walk1", "walk2"]:
            grid = self.frames_data.get(f, self.canvas.grid)
            img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            for y in range(h):
                for x in range(w):
                    if y < len(grid) and x < len(grid[y]):
                        c = grid[y][x]
                        if c:
                            img.setPixelColor(x, y, QColor(c))
            pixmaps.append(QPixmap.fromImage(img))
        self.preview_widget.update_frames(pixmaps)

    # ----------------------------------------------------------------- 尺寸與不顧限制
    def _on_ignore_limits_toggled(self, checked: bool):
        self.spin_w.setEnabled(checked)
        self.spin_h.setEnabled(checked)
        if not checked:
            self.spin_w.setValue(16)
            self.spin_h.setValue(24)

    def _on_size_spin_changed(self):
        w = self.spin_w.value()
        h = self.spin_h.value()
        self.canvas.set_dimensions(w, h, preserve=True)
        self._save_current_frame_to_cache()
        self._update_preview()

    # ----------------------------------------------------------------- 清空畫布警告
    def _on_clear_canvas_clicked(self):
        """清空畫布（Clear）：點擊清空時必須彈出警告確認：「確定要清空當前畫布嗎？未儲存的繪圖將會遺失！」"""
        ret = ModernMessageBox.question(
            self,
            "清空畫布警告",
            "確定要清空當前畫布嗎？未儲存的繪圖將會遺失！",
            buttons=ModernMessageBox.Yes | ModernMessageBox.No,
        )
        if ret == ModernMessageBox.Yes:
            self.canvas.clear_canvas()
            self._save_current_frame_to_cache()
            self._update_preview()
            log("ChibiPixelEditorDialog", "使用者確認清空當前畫布。")

    # ----------------------------------------------------------------- 儲存至角色庫 (覆蓋確認)
    def _save_to_repository(self):
        """儲存（Save）：儲存至自訂角色庫。如果要覆蓋舊的某個已存在角色，必須彈出警告確認：「已存在同名自訂角色，確定要覆蓋儲存嗎？」"""
        self._save_current_frame_to_cache()

        raw_id = self.txt_id.text().strip().lower()
        char_name = self.txt_name.text().strip()
        safe_id = "".join(c for c in raw_id if c.isalnum() or c in ("_", "-")).strip()

        if not safe_id:
            ModernMessageBox.warning(self, "輸入錯誤", "請輸入有效的角色代號（英數字或底線）！")
            return
        if not char_name:
            char_name = safe_id

        # 官方受保護檢查
        if safe_id in OFFICIAL_CHIBI_IDS:
            ModernMessageBox.warning(
                self,
                "受保護角色",
                "官方預設角色（藍色大肥魚、GPT龍娘、大小姐Claude、北美貓娘Gemini）受系統保護，絕不允許覆蓋！"
            )
            return

        # 覆蓋確認檢查：檢查是否有同 ID 或同名自訂人物
        is_id_exists = PixelChibiRegistry.character_exists(safe_id)
        existing_name_id = PixelChibiRegistry.find_existing_by_name(char_name)

        if is_id_exists or (existing_name_id and existing_name_id != safe_id):
            ret = ModernMessageBox.question(
                self,
                "覆蓋儲存警告",
                "已存在同名自訂角色，確定要覆蓋儲存嗎？",
                buttons=ModernMessageBox.Yes | ModernMessageBox.No,
            )
            if ret != ModernMessageBox.Yes:
                return

        w = self.canvas.canvas_w
        h = self.canvas.canvas_h
        ignore_limits = self.chk_ignore_limits.isChecked()
        if not ignore_limits and (w != 16 or h != 24):
            ModernMessageBox.warning(self, "規格不符", f"當前尺寸為 {w}x{h}，超出預設 16x24 限制。請勾選「不顧限制」標記！")
            return

        # 整合色盤與編譯像素矩陣
        all_colors = set()
        for f in self.frames_data.values():
            for row in f:
                for c in row:
                    if c:
                        all_colors.add(c.lower())

        symbol_pool = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_+=~"
        color_to_sym: dict[str, str] = {}
        palette: dict[str, str] = {}
        for idx, col in enumerate(sorted(all_colors)):
            sym = symbol_pool[idx] if idx < len(symbol_pool) else f"C{idx}"
            color_to_sym[col] = sym
            palette[sym] = col

        compiled_frames: dict[str, list[str]] = {}
        for fname, _ in ACTION_FRAMES:
            grid = self.frames_data.get(fname, self.canvas.grid)
            rows = []
            for y in range(h):
                r_chars = []
                for x in range(w):
                    c = grid[y][x] if (y < len(grid) and x < len(grid[y])) else None
                    if not c:
                        r_chars.append(".")
                    else:
                        r_chars.append(color_to_sym.get(c.lower(), "."))
                rows.append("".join(r_chars))
            compiled_frames[fname] = rows

        save_dict = {
            "id": safe_id,
            "name": char_name,
            "width": w,
            "height": h,
            "ignore_limits": ignore_limits,
            "palette": palette,
            "frames": compiled_frames,
        }

        try:
            saved_path = PixelChibiRegistry.save_custom_chibi(save_dict)
            ModernMessageBox.information(
                self,
                "儲存成功",
                f"自訂 Q 版人物「{char_name}」({safe_id}) 已成功儲存至自訂角色庫！\n路徑：{saved_path}"
            )
            self._refresh_repo_list()
        except Exception as e:
            ModernMessageBox.warning(self, "儲存失敗", f"無法儲存人物檔案：{e}")

    # ----------------------------------------------------------------- 匯出為 .json
    def _export_json(self):
        """匯出（Export）：匯出為 .json 檔案。"""
        self._save_current_frame_to_cache()
        safe_id = self.txt_id.text().strip().lower() or "custom_chibi"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "匯出 Q 版人物 JSON",
            f"{safe_id}.json",
            "JSON 檔案 (*.json)"
        )
        if not path:
            return

        w = self.canvas.canvas_w
        h = self.canvas.canvas_h
        ignore_limits = self.chk_ignore_limits.isChecked()

        all_colors = set()
        for f in self.frames_data.values():
            for row in f:
                for c in row:
                    if c:
                        all_colors.add(c.lower())

        symbol_pool = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_+=~"
        color_to_sym: dict[str, str] = {}
        palette: dict[str, str] = {}
        for idx, col in enumerate(sorted(all_colors)):
            sym = symbol_pool[idx] if idx < len(symbol_pool) else f"C{idx}"
            color_to_sym[col] = sym
            palette[sym] = col

        compiled_frames: dict[str, list[str]] = {}
        for fname, _ in ACTION_FRAMES:
            grid = self.frames_data.get(fname, self.canvas.grid)
            rows = []
            for y in range(h):
                r_chars = []
                for x in range(w):
                    c = grid[y][x] if (y < len(grid) and x < len(grid[y])) else None
                    if not c:
                        r_chars.append(".")
                    else:
                        r_chars.append(color_to_sym.get(c.lower(), "."))
                rows.append("".join(r_chars))
            compiled_frames[fname] = rows

        export_data = {
            "id": safe_id,
            "name": self.txt_name.text().strip() or safe_id,
            "width": w,
            "height": h,
            "ignore_limits": ignore_limits,
            "palette": palette,
            "frames": compiled_frames,
        }

        try:
            Path(path).write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")
            ModernMessageBox.information(self, "匯出成功", f"人物資料已成功匯出至：\n{path}")
        except Exception as e:
            ModernMessageBox.warning(self, "匯出失敗", f"寫入檔案時發生錯誤：{e}")

    # ----------------------------------------------------------------- 匯入外部檔案 (JSON/PNG)
    def _import_file(self):
        """支援匯入外部 Q 版人物 JSON 或 PNG 精靈圖檔案，支援不顧限制匯入。"""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "匯入外部 Q 版人物檔案",
            "",
            "支援檔案 (*.json *.png);;JSON 檔案 (*.json);;PNG 圖片 (*.png)"
        )
        if not path:
            return

        p = Path(path)
        if p.suffix.lower() == ".json":
            self._import_json(p)
        elif p.suffix.lower() == ".png":
            self._import_png(p)

    def _import_json(self, p: Path):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            w = int(data.get("width", 16))
            h = int(data.get("height", 24))
            ignore_limits = bool(data.get("ignore_limits", False))

            if (w != 16 or h != 24) and not ignore_limits:
                ret = ModernMessageBox.question(
                    self,
                    "非標準尺寸提示",
                    f"此檔案尺寸為 {w}x{h}（非標準 16x24），是否開啟「不顧限制」繼續匯入？",
                    buttons=ModernMessageBox.Yes | ModernMessageBox.No,
                )
                if ret != ModernMessageBox.Yes:
                    return
                ignore_limits = True

            self.chk_ignore_limits.setChecked(ignore_limits)
            self.spin_w.setValue(w)
            self.spin_h.setValue(h)
            self.txt_id.setText(data.get("id", p.stem))
            self.txt_name.setText(data.get("name", p.stem))

            pal = data.get("palette", {})
            frames = data.get("frames", {})

            for fname, _ in ACTION_FRAMES:
                rows = frames.get(fname) or frames.get("idle") or []
                grid = [[None for _ in range(w)] for _ in range(h)]
                for y, row_str in enumerate(rows):
                    if y >= h:
                        break
                    for x, ch in enumerate(row_str):
                        if x >= w:
                            break
                        if ch not in (".", " ") and ch in pal:
                            grid[y][x] = pal[ch].lower()
                self.frames_data[fname] = grid

            self.canvas.set_grid_pixels(self.frames_data.get(self.current_frame, self.frames_data["idle"]))
            self._update_preview()
            ModernMessageBox.information(self, "匯入成功", f"已成功載入外部人物 JSON「{data.get('name', p.stem)}」！")
        except Exception as e:
            ModernMessageBox.warning(self, "匯入失敗", f"解析 JSON 失敗：{e}")

    def _import_png(self, p: Path):
        try:
            img = QImage(str(p))
            if img.isNull():
                raise ValueError("無法讀取圖片內容！")
            w = img.width()
            h = img.height()
            ignore_limits = self.chk_ignore_limits.isChecked()

            if (w != 16 or h != 24) and not ignore_limits:
                ret = ModernMessageBox.question(
                    self,
                    "非標準尺寸提示",
                    f"圖片尺寸為 {w}x{h}（非標準 16x24），是否開啟「不顧限制」繼續匯入？",
                    buttons=ModernMessageBox.Yes | ModernMessageBox.No,
                )
                if ret != ModernMessageBox.Yes:
                    return
                ignore_limits = True

            self.chk_ignore_limits.setChecked(ignore_limits)
            self.spin_w.setValue(w)
            self.spin_h.setValue(h)
            self.txt_id.setText(f"custom_{p.stem}")
            self.txt_name.setText(p.stem)

            # 解析 PNG 色彩填入畫布
            grid = [[None for _ in range(w)] for _ in range(h)]
            for y in range(h):
                for x in range(w):
                    c = img.pixelColor(x, y)
                    if c.alpha() >= 16:
                        grid[y][x] = c.name(QColor.HexRgb).lower()

            for fname, _ in ACTION_FRAMES:
                self.frames_data[fname] = [row[:] for row in grid]

            self.canvas.set_grid_pixels(grid)
            self._update_preview()
            ModernMessageBox.information(self, "匯入成功", f"已成功將 PNG 轉換為像素幀並套用至全動作！")
        except Exception as e:
            ModernMessageBox.warning(self, "匯入失敗", f"解析 PNG 失敗：{e}")

    # ----------------------------------------------------------------- 角色庫管理與刪除確認
    def _refresh_repo_list(self):
        self.list_repo.clear()

        # 1. 官方 4 隻受保護角色
        for cid, info in PixelChibiRegistry.list_official_characters().items():
            item = QListWidgetItem(f"[官方] {info['name']}")
            item.setData(Qt.UserRole, (cid, False))  # is_custom = False
            item.setToolTip(f"官方預設人物：{info.get('subtitle', '')}（受系統保護，絕不允許刪除）")
            self.list_repo.addItem(item)

        # 2. 所有自訂角色
        custom_chars = PixelChibiRegistry.list_custom_characters()
        for cid, info in custom_chars.items():
            w = info.get("width", 16)
            h = info.get("height", 24)
            size_tag = f" ({w}x{h})" if (w != 16 or h != 24) else ""
            item = QListWidgetItem(f"[自訂] {info.get('name', cid)}{size_tag}")
            item.setData(Qt.UserRole, (cid, True))  # is_custom = True
            self.list_repo.addItem(item)

        if self.list_repo.count() > 0:
            self.list_repo.setCurrentRow(0)

    def _on_repo_item_clicked(self, item: QListWidgetItem):
        cid, is_custom = item.data(Qt.UserRole)
        self.btn_del_repo.setEnabled(is_custom)

    def _load_selected_repo_char(self):
        item = self.list_repo.currentItem()
        if not item:
            return
        cid, is_custom = item.data(Qt.UserRole)
        info = PixelChibiRegistry.get_character(cid)
        if not info:
            return

        w = info.get("width", 16)
        h = info.get("height", 24)
        ignore_limits = info.get("ignore_limits", False) or (w != 16 or h != 24)

        self.chk_ignore_limits.setChecked(ignore_limits)
        self.spin_w.setValue(w)
        self.spin_h.setValue(h)
        self.txt_id.setText(info["id"])
        self.txt_name.setText(info.get("name", info["id"]))

        pal = info.get("palette", {})
        frames = info.get("frames", {})

        for fname, _ in ACTION_FRAMES:
            rows = frames.get(fname) or frames.get("idle") or FRAMES.get(fname, FRAMES["idle"])
            grid = [[None for _ in range(w)] for _ in range(h)]
            for y, row_str in enumerate(rows):
                if y >= h:
                    break
                for x, ch in enumerate(row_str):
                    if x >= w:
                        break
                    if ch not in (".", " ") and ch in pal:
                        grid[y][x] = pal[ch].lower()
            self.frames_data[fname] = grid

        self.canvas.set_grid_pixels(self.frames_data.get(self.current_frame, self.frames_data["idle"]))
        self._update_preview()
        log("ChibiPixelEditorDialog", f"已載入角色庫人物「{info.get('name', cid)}」至畫布。")

    def _delete_selected_repo_char(self):
        """刪除已有的自訂 Q 版人物時，必須彈出警告確認（ModernMessageBox 或 ModernConfirmDialog）。
        預設 4 個官方角色受保護，絕不允許刪除！
        """
        item = self.list_repo.currentItem()
        if not item:
            return
        cid, is_custom = item.data(Qt.UserRole)
        if not is_custom or cid in OFFICIAL_CHIBI_IDS:
            ModernMessageBox.warning(
                self,
                "受保護角色",
                "官方預設角色（藍色大肥魚、GPT龍娘、大小姐Claude、北美貓娘Gemini）受系統保護，絕不允許刪除！"
            )
            return

        info = PixelChibiRegistry.get_character(cid)
        char_name = info.get("name", cid) if info else cid

        ret = ModernMessageBox.question(
            self,
            "刪除角色警告",
            f"確定要刪除自訂 Q 版人物「{char_name}」嗎？此操作無法還原！",
            buttons=ModernMessageBox.Yes | ModernMessageBox.No,
        )
        if ret == ModernMessageBox.Yes:
            try:
                PixelChibiRegistry.delete_custom_chibi(cid)
                ModernMessageBox.information(self, "刪除完成", f"自訂人物「{char_name}」已成功自角色庫移除。")
                self._refresh_repo_list()
            except Exception as e:
                ModernMessageBox.warning(self, "刪除失敗", f"無法刪除人物：{e}")
