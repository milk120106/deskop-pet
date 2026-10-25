"""Brand-new standalone Q-Chibi pixel patrol system.
Features 4 heroine styles (DeepSeek whale, Claude spark, GPT tech, Gemini cat)
with full bodies, two cute legs/feet, pure-code 2D pixel matrices, nearest-neighbor
crisp rendering, dynamic Delta-Time physics and FPS scheduling (10-240 FPS / unlimited),
comprehensive animation frames (climb, splat, sleep, wake, run, jump, mischief),
main pet head/back/iron bowl mounting, bowl smash knock-back physics,
and bamboo copter / pixel fireworks props. Strictly zero emojis.
"""
from __future__ import annotations

import json
import math
import random
import time
from pathlib import Path
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QWidget

from .config import CUSTOM_CHIBI_DIR, get_effective_chibi_max_count, id_to_provider_name, log, provider_to_id


# =====================================================================
# 16x24 Pixel Art Matrix Data & Color Palettes
# =====================================================================
# Palette Symbols:
# . = Transparent
# H = Primary Hair
# h = Secondary Hair / Shadow
# S = Skin
# s = Skin shadow
# B = Blush (pink)
# E = Eyes
# e = Eye highlight / white
# A = Accessory (fin / spark / ear / headset)
# a = Accessory detail / glow
# T = Collar / Tie / Neck detail
# D = Dress / Top primary
# d = Dress / Top shadow / trim
# K = Skirt / Bottom primary
# k = Skirt / Bottom shadow
# L = Legs (bare skin or tights)
# W = Socks (white)
# F = Feet / Boots / Shoes
# f = Soles / Shoe detail
# P = Balloon string / thread
# R = Balloon body / sphere

CHAR_PALETTES = {
    "deepseek": {
        # 藍色大肥魚 (DeepSeek 鯨魚娘)：深藍長髮、小鯨魚鰭髮飾、鯨魚大尾巴、水手裙、海藍短靴
        "H": "#1e3a8a", "h": "#172554",  # Deep royal blue long hair
        "S": "#ffe4d0", "s": "#fbcfe8", "B": "#f472b6",  # Fair skin & pink blush
        "E": "#0284c7", "e": "#e0f2fe",  # Sky blue eyes
        "A": "#38bdf8", "a": "#bae6fd",  # Whale fin hairpin & blue whale tail
        "T": "#ffffff", "D": "#1d4ed8", "d": "#1e40af",  # Navy sailor maid top
        "K": "#1e3a8a", "k": "#172554",  # Sailor pleated skirt
        "L": "#ffe4d0", "W": "#ffe4d0",  # Cute bare legs
        "F": "#1e3a8a", "f": "#0f172a",  # Sailor short boots
        "P": "#ffffff", "R": "#38bdf8",  # Sky blue balloon
    },
    "gpt": {
        # GPT龍娘 (OpenAI 白龍娘)：銀白長髮微帶丁香紫、白龍角、仙氣白紫長裙、白龍尾巴
        "H": "#f8fafc", "h": "#cbd5e1",  # Silvery white hair with soft violet shadow
        "S": "#fff5f5", "s": "#fed7aa", "B": "#f472b6",  # Fair translucent skin & blush
        "E": "#8b5cf6", "e": "#ede9fe",  # Lilac purple eyes
        "A": "#f1f5f9", "a": "#c4b5fd",  # White dragon horns & violet cord tassel
        "T": "#ffffff", "D": "#f8fafc", "d": "#e2e8f0",  # Ethereal white dragon gown with silver lace
        "K": "#ede9fe", "k": "#ddd6fe",  # Flowing lilac pleated skirt & dragon tail
        "L": "#fff5f5", "W": "#ffffff",  # Fair slender legs
        "F": "#ede9fe", "f": "#8b5cf6",  # White & lilac dragon boots
        "P": "#ffffff", "R": "#34d399",  # Dragon pearl emerald green balloon
    },
    "claude": {
        # 大小姐Claude (Anthropic 大小姐)：暖橘波浪捲髮、黑緞帶金色花朵髮飾、維多利亞宮廷馬甲裙、典雅皮靴
        "H": "#ea580c", "h": "#c2410c",  # Warm orange ojou-sama wavy hair
        "S": "#ffedd5", "s": "#fed7aa", "B": "#fb7185",  # Warm fair skin & rose blush
        "E": "#b45309", "e": "#fef3c7",  # Amber eyes
        "A": "#1f2937", "a": "#fbbf24",  # Black ribbon & golden flower ornament
        "T": "#fef3c7", "D": "#78350f", "d": "#451a03",  # Victorian cream blouse & brown corset
        "K": "#78350f", "k": "#451a03",  # Victorian brown flared skirt
        "L": "#ffedd5", "W": "#ffedd5",  # Elegant slender legs
        "F": "#78350f", "f": "#451a03",  # Ojou-sama brown leather boots
        "P": "#ffffff", "R": "#fb923c",  # Warm coral balloon
    },
    "gemini": {
        # 北美貓娘Gemini (Google 北美貓娘)：紫藍雙色漸層長髮、毛茸茸貓耳與漸層貓尾巴、金黃星芒髮飾、星空魔法洋裝
        "H": "#7c3aed", "h": "#38bdf8",  # Purple base with bright blue gradient hair
        "S": "#ffe4e6", "s": "#fecdd3", "B": "#fb7185",  # Soft rosy skin & blush
        "E": "#ec4899", "e": "#fce7f3",  # Vivid magenta starry eyes
        "A": "#1e1b4b", "a": "#fbbf24",  # Midnight cat ears & radiant golden starburst
        "T": "#fbbf24", "D": "#1e1b4b", "d": "#312e81",  # Midnight blue starry dress with gold trim
        "K": "#1e1b4b", "k": "#0f172a",  # Midnight skirt & fluffy curved cat tail
        "L": "#ffe4e6", "W": "#ffffff",  # White knee-high socks
        "F": "#1e1b4b", "f": "#312e81",  # Dark Mary Jane shoes
        "P": "#ffffff", "R": "#c084fc",  # Radiant purple balloon
    },
}

CHARACTER_INFO = {
    "deepseek": {
        "id": "deepseek",
        "name": "藍色大肥魚",
        "subtitle": "DeepSeek 鯨魚娘",
        "description": "深藍長髮、小鯨魚鰭髮飾、鯨魚大尾巴與水手裙",
    },
    "gpt": {
        "id": "gpt",
        "name": "GPT龍娘",
        "subtitle": "OpenAI 龍娘",
        "description": "銀白長髮、白龍角、白龍尾巴與仙氣白紫長裙",
    },
    "claude": {
        "id": "claude",
        "name": "大小姐Claude",
        "subtitle": "Anthropic 大小姐",
        "description": "暖橘波浪捲髮、黑緞帶金色花朵髮飾、維多利亞古典洋裝與皮靴",
    },
    "gemini": {
        "id": "gemini",
        "name": "北美貓娘Gemini",
        "subtitle": "Google 北美貓娘",
        "description": "紫藍雙色漸層長髮、毛茸茸漸層貓耳與貓尾、金黃星芒髮飾",
    },
}

# 16 columns x 24 rows character matrices (嚴格保證包含 "LL" 雙腿雙腳與四位主角色盤相容)
FRAMES = {
    # ------------------ Idle: 站立呼吸 (偏右側) ------------------
    "idle": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "..SDDKKKKKKKDDS.",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "....LL....LL....",
        "....LL....LL....",
        "....LL....LL....",
        "....WW....WW....",
        "....WW....WW....",
        "...FFF....FFF...",
        "...fff....fff...",
    ],
    # ------------------ Facing Front: 正臉面向用戶眨眼/招手 ------------------
    "facing_front": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "..ShTDDDDDDTh...",
        ".S.DDDDDDDDDD...",
        "...DDDDDDDDDDS..",
        "..SDDKKKKKKKDD..",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "....LL....LL....",
        "....LL....LL....",
        "....LL....LL....",
        "....WW....WW....",
        "....WW....WW....",
        "...FFF....FFF...",
        "...fff....fff...",
    ],
    # ------------------ Facing Back: 背影望向螢幕深處 ------------------
    "facing_back": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHHHHHHHHHHHH.",
        "HHHhHHHHHHHHHhHH",
        "HHHhHHHHHHHHHhHH",
        "HHHhHHHHHHHHHhHH",
        ".HHhHHHHHHHHhH..",
        "..HhHHHHHHHHshH.",
        "...hTddddddTh...",
        "...DDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "..SDDKKKKKKKDDS.",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "....LL....LL....",
        "....LL....LL....",
        "....LL....LL....",
        "....WW....WW....",
        "....WW....WW....",
        "...FFF....FFF...",
        "...fff....fff...",
    ],
    # ------------------ Turn: 轉身過渡 3/4 視角 ------------------
    "turn": [
        "....AAAA...AAAA.",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSSEeSSSSEshH",
        "HHHhSSEESSSSEshH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "..SDDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "...DDKKKKKKKDD..",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "...LL....LL.....",
        "...LL....LL.....",
        "...LL....LL.....",
        "...WW....WW.....",
        "...WW....WW.....",
        "..FFF....FFF....",
        "..fff....fff....",
    ],
    # ------------------ Walk 1: 邁出左腳，雙腿分明 ------------------
    "walk1": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "..SDDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "...DDKKKKKKKDD..",
        "...SDKKKKKKKD...",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        ".....LL..LL.....",
        ".....LL...LL....",
        "....LL....LL....",
        "....WW.....WW...",
        "....WW.....WW...",
        "...FFF.....FFF..",
        "...fff.....fff..",
    ],
    # ------------------ Walk 2: 邁出右腳，雙腿分明 ------------------
    "walk2": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDDS..",
        "..SDDDDDDDDDDDS.",
        "..DDKKKKKKKDD...",
        "...DKKKKKKKDS...",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        ".....LL..LL.....",
        "....LL...LL.....",
        "....LL....LL....",
        "...WW.....WW....",
        "...WW.....WW....",
        "..FFF.....FFF...",
        "..fff.....fff..",
    ],
    # ------------------ Run 1: 身體大幅前傾衝刺，左腿大步 ------------------
    "run1": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "..SDDDDDDDDDD...",
        ".SDDDDDDDDDDDS..",
        "...DDKKKKKKKDDS.",
        "....SDKKKKKKDS..",
        ".....KKKKKKKK...",
        ".....KKKKKKKK...",
        ".....LL..LL.....",
        "....LL....LL....",
        "...LL......LL...",
        "...WW......WW...",
        "...WW......WW...",
        "..FFF......FFF..",
        "..fff......fff..",
    ],
    # ------------------ Run 2: 身體大幅前傾衝刺，右腿大步 ------------------
    "run2": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDDS..",
        "..SDDDDDDDDDDDS.",
        "..SDDKKKKKKKDD..",
        "...SDKKKKKKKDS..",
        ".....KKKKKKKK...",
        ".....KKKKKKKK...",
        ".....LL..LL.....",
        ".....LL..LL.....",
        "....LL....LL....",
        "....WW....WW....",
        "....WW....WW....",
        "...FFF....FFF...",
        "...fff....fff...",
    ],
    # ------------------ Jump Up: 向上跳躍起飛，雙手上舉 ------------------
    "jump_up": [
        "S..............S",
        "S...AAAA....AAAS",
        ".S.AAHHAAAAHHAS.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDD...",
        "...DDDDDDDDDD...",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        ".....LLLLLL.....",
        "....LL....LL....",
        "....LL....LL....",
        "....WW....WW....",
        "....WW....WW....",
        "...FFF....FFF...",
        "...fff....fff...",
        "................",
        "................",
    ],
    # ------------------ Jump Down: 下落俯衝，雙腿伸直 ------------------
    "jump_down": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "S..hTDDDDDDTh..S",
        ".S.DDDDDDDDDD.S.",
        "..SDDDDDDDDDDDS.",
        "...DDKKKKKKKDD..",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        ".....LL..LL.....",
        ".....LL..LL.....",
        ".....LL..LL.....",
        ".....WW..WW.....",
        ".....WW..WW.....",
        "....FFF..FFF....",
        "....fff..fff....",
    ],
    # ------------------ Run Jump: 飛撲躍起 ------------------
    "run_jump": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        ".S.DDDDDDDDDD...",
        "..SDDDDDDDDDDS..",
        "...DDKKKKKKKDDS.",
        "....SDKKKKKKDS..",
        ".....KKKKKKKK...",
        ".....KKKKKKKK...",
        "..LLLL..........",
        "...LLLL.........",
        "....WWWW........",
        ".....FFFF.......",
        ".....ffff.......",
        "................",
        "................",
    ],
    # ------------------ Sit: 坐姿，小短腿懸空晃動 ------------------
    "sit": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "...DDKKKKKKKDD..",
        "...KKKKKKKKKK...",
        "...KKKKKKKKKK...",
        "...LLLL..LLLL...",
        "...WWWW..WWWW...",
        "...FFFF..FFFF...",
        "...ffff..ffff...",
        "................",
        "................",
        "................",
        "................",
    ],
    # ------------------ Sit Down: 坐下過渡動作，屈膝蹲下 ------------------
    "sit_down": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSEShHH",
        "HHHhSEESSSSEESHH",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "..SDDKKKKKKKDDS.",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "...LLLL..LLLL...",
        "..LLLL....LLLL..",
        "..LLLL....LLLL..",
        "..WWWW....WWWW..",
        "..WWWW....WWWW..",
        "..FFFF....FFFF..",
        "..ffff....ffff..",
    ],
    # ------------------ Splat: 麻糬般軟趴趴攤平 ------------------
    "splat": [
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        ".....a....a.....",
        "....AAA..AAA....",
        "..AAHHHHHHHHAA..",
        ".HHHHHHHHHHHHHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSBeSSeBShHHH",
        "SSShTDDDDDDThSSS",
        "SSSDDDDDDDDDDSSS",
        "..SDDKKKKKKKDDS.",
        "...KKKKKKKKKK...",
        "..LLLL....LLLL..",
        "..LLLL....LLLL..",
        ".WWWW......WWWW.",
        "FFFF........FFFF",
    ],
    # ------------------ Panic: 失足驚慌亂蹬小腿 ------------------
    "panic": [
        "..AA........AA..",
        ".AAAHHHHHHHHAAA.",
        ".HHHHHHHHHHHHHH.",
        "HHhSSSSSSSSSSshH",
        "HhSSEESSSEEESshH",
        "HhSEEEEEEEEEshH.",
        "HhSSEESSSEEESshH",
        ".HhSBBSSSSBBshH.",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "..SDDDDDDDDDDDS.",
        ".SDDDDDDDDDDDDDS",
        "S..DDKKKKKKKD..S",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "...LL......LL...",
        "..LL........LL..",
        "..LL........LL..",
        ".WW..........WW.",
        ".WW..........WW.",
        "FFF..........FFF",
        "fff..........fff",
        "................",
    ],
    # ------------------ Climb: 向上攀爬 (舊相容別名) ------------------
    "climb": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHHHHHHHHHHHH.",
        "HHhHHHHHHHHHHshH",
        "HHhHHHHHHHHHHshH",
        "HHhHHHHHHHHHHshH",
        ".HhHHHHHHHHHHshH",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "..SDDDDDDDDDDDS.",
        "..SDDDDDDDDDDDS.",
        "...DDKKKKKKKDD..",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "....LL....LL....",
        "...LL......LL...",
        "...LL......LL...",
        "...WW......WW...",
        "..FFF......WW...",
        "..fff.....FFF...",
        "..........fff...",
    ],
    # ------------------ Climb Up: 向上攀爬，背影雙手抓攀 ------------------
    "climb_up": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHHHHHHHHHHHH.",
        "HHhHHHHHHHHHHshH",
        "HHhHHHHHHHHHHshH",
        "HHhHHHHHHHHHHshH",
        ".HhHHHHHHHHHHshH",
        "..HhSSSSSSSSshH.",
        ".ShTDDDDDDThS...",
        ".SDDDDDDDDDDS...",
        ".SDDDDDDDDDDDS..",
        "..DDKKKKKKKDD...",
        "..SDKKKKKKKDS...",
        "...KKKKKKKK.....",
        "...KKKKKKKK.....",
        "...LL......LL...",
        "...LL......LL...",
        "...WW......LL...",
        "..FFF......WW...",
        "..fff......WW...",
        "..........FFF...",
        "..........fff...",
    ],
    # ------------------ Climb Down: 向下攀爬，小腿小心探路 ------------------
    "climb_down": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSSSeSSSSeshH",
        "HHHhSSEESSSSEESh",
        ".HHhSBSSSSSBShH.",
        "..HhSSSSSSSSshH.",
        ".ShTDDDDDDThS...",
        ".SDDDDDDDDDDS...",
        ".SDDDDDDDDDDDS..",
        "..DDKKKKKKKDD...",
        "..SDKKKKKKKDS...",
        "...KKKKKKKK.....",
        "...KKKKKKKK.....",
        "....LL....LL....",
        "....LL....LL....",
        "...LL......LL...",
        "...WW......WW...",
        "..FFF......WW...",
        "..fff.....FFF...",
        "..........fff...",
    ],
    # ------------------ Climb Side: 側攀貼牆走 ------------------
    "climb_side": [
        ".AAAA....AAAA...",
        "AAHHAAAAHHAA....",
        "HHHHHHHHHHHH....",
        "HHHHHHHHHHHHHH..",
        "HHHhSSSSSSShHH..",
        "HHhSSSSSSSSShHH.",
        "HHhSEeSSSSEShHH.",
        "HHhSEESSSSEESHH.",
        ".HhSBSSSSSBShH..",
        ".HhSSSSSSSSshH..",
        "ShTDDDDDDThS....",
        "SDDDDDDDDDDS....",
        "SDDDDDDDDDDDS...",
        ".DDKKKKKKKDD....",
        ".SDKKKKKKKDS....",
        "..KKKKKKKK......",
        "..KKKKKKKK......",
        ".LL......LL.....",
        ".LL......LL.....",
        ".WW......LL.....",
        "FFF......WW.....",
        "fff......WW.....",
        "........FFF.....",
        "........fff.....",
    ],
    # ------------------ Sleep Sprawl: 四腳朝天仰躺呼呼大睡 ------------------
    "sleep_sprawl": [
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        "HHHhSSssSSssShHH",
        "HHHhSBSSSSSBShHH",
        "S..hTDDDDDDTh..S",
        "SDDDDDDDDDDDDDDS",
        "..SDDKKKKKKKDDS.",
        "...KKKKKKKKKK...",
        "..LL........LL..",
        "..LL........LL..",
        "..LL........LL..",
        "..WW........WW..",
        "..WW........WW..",
        ".FFF........FFF.",
        ".fff........fff.",
    ],
    # ------------------ Sleep Prone: 趴在地上埋頭睡覺，zZZ 氣泡 ------------------
    "sleep_prone": [
        "..........a.....",
        ".........aaa....",
        "..........a.....",
        "......a.........",
        ".....aaa........",
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        "HHHhHHHHHHHHHhHH",
        "...hTDDDDDDTh...",
        "...DDDDDDDDDD...",
        "..SDDDDDDDDDDDS.",
        "...DDKKKKKKKDD..",
        "....KKKKKKKK....",
        "....LL....LL....",
        "....LL....LL....",
        "....LL....LL....",
        "....WW....WW....",
        "....WW....WW....",
        "...FFF....FFF...",
        "...fff....fff...",
        "................",
        "................",
    ],
    # ------------------ Sleep Side: 側臥蜷縮小貓睡姿 ------------------
    "sleep_side": [
        "................",
        "................",
        "................",
        "................",
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        "HHHhSSssSssShHH.",
        ".HHhSBSSSSshH...",
        "..HhSSSSSSSSshH.",
        "...hTDDDDDDTh...",
        "...DDDDDDDDD....",
        "..SDDDDDDDDD....",
        "...DDKKKKKKK....",
        "....KKKKKKKK....",
        "....LLLL........",
        "....LLLL........",
        "....LLLL........",
        "....WWWW........",
        "...FFFF.........",
        "...ffff.........",
        "................",
        "................",
    ],
    # ------------------ Wake Startle: 被驚醒，炸毛彈起，呆毛豎立 ------------------
    "wake_startle": [
        ".......HH.......",
        "......HHHH......",
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        "HHHhSEEEESEEEhHH",
        "HHHhSEEEESEEEhHH",
        ".HHhSBEEssEEBSh.",
        "..HhSSSSSSSSshH.",
        "S..hTDDDDDDTh..S",
        "S..DDDDDDDDDD..S",
        ".S.DDDDDDDDDDS..",
        "...DDKKKKKKKDD..",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "...LL......LL...",
        "..LL........LL..",
        "..LL........LL..",
        "..WW........WW..",
        ".WW..........WW.",
        ".WW..........WW.",
        "FFF..........FFF",
        "fff..........fff",
    ],
    # ------------------ Mischief: 做鬼臉、手舞足蹈 ------------------
    "mischief": [
        "....AAAA....AAAA",
        "...AAHHAAAAHHAA.",
        "..HHHHHHHHHHHH..",
        ".HHHHHHHHHHHHHH.",
        ".HHHhSSSSSSShHH.",
        "HHHhSSSSSSSSShHH",
        "HHHhSEeSSSSaShHH",
        "HHHhSEESSSSaShHH",
        ".HHhSBSSBBSBShH.",
        "..HhSSSSSSSSshH.",
        "S..hTDDDDDDTh...",
        ".S.DDDDDDDDDDS..",
        "..SDDDDDDDDDDS..",
        "...DDKKKKKKKDD..",
        "...SDKKKKKKKDS..",
        "....KKKKKKKK....",
        "....KKKKKKKK....",
        "...LL......LL...",
        "...LL......LL...",
        "...LL.....LLLL..",
        "..WW......WWWW..",
        "..WW......FFFF..",
        ".FFF......ffff..",
        ".fff............",
    ],
}

# 小氣球飛行道具像素幀 (Balloon Overlays, Row 0-5)
BALLOON_FRAMES = [
    [
        ".....RRRRRR.....",
        "....RRRRRRRR....",
        "....RRRRRRRR....",
        ".....RRRRRR.....",
        ".......RR.......",
        ".......PP.......",
    ],
    [
        "......RRRRRR....",
        ".....RRRRRRRR...",
        ".....RRRRRRRR...",
        "......RRRRRR....",
        "........RR......",
        ".......PP.......",
    ],
]


CHAR_SPECIFIC_FRAMES = {
    "deepseek": {
        "idle": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTTTTDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK.AAA",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "facing_front": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "..ShTDDTTDDTh...",
            ".S.DDTTTTDDDD...",
            "...DDDDDDDDDDS..",
            "..SDDKKKKKKKDD.A",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK.AAA",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "facing_back": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHHHHHHHHHHH..",
            "HHHhHHHHHHHHHhHH",
            "HHHhHHHHHHHHHhHH",
            "HHHhHHHHHHHHHhHH",
            ".HHhHHHHHHHHhH..",
            "..HhHHHHHHHHshH.",
            "...hTddddddTh...",
            "...DDTTTTDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK.AAA",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "turn": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSSEeSSSSEshH",
            "HHHhSSEESSSSEshH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "..SDDDTTTTDDD...",
            "..SDDDDDDDDDDDS.",
            "...DDKKKKKKKDD.A",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK.AAA",
            ".....LL..LL.....",
            "....LL...LL.....",
            "....LL...LL.....",
            "....WW...WW.....",
            "....WW...WW.....",
            "...FFF...FFF....",
            "...fff...fff....",
        ],
        "walk1": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "..SDDDTTTTDDD...",
            "..SDDDDDDDDDDDS.",
            "...DDKKKKKKKDD.A",
            "...SDKKKKKKKD.AA",
            "....KKKKKKKK.AAA",
            "....KKKKKKKK..AA",
            ".....LL..LL.....",
            ".....LL...LL....",
            "....LL....LL....",
            "....WW.....WW...",
            "....WW.....WW...",
            "...FFF.....FFF..",
            "...fff.....fff..",
        ],
        "walk2": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDDTTTTDDDS..",
            "..SDDDDDDDDDDDS.",
            "..DDKKKKKKKDD..A",
            "...DKKKKKKKDS.AA",
            "....KKKKKKKK.AAA",
            "....KKKKKKKK....",
            ".....LL..LL.....",
            "....LL...LL.....",
            "....LL....LL....",
            "...WW.....WW....",
            "...WW.....WW....",
            "..FFF.....FFF...",
            "..fff.....fff...",
        ],
        "run1": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "..SDDDTTTTDDD...",
            ".SDDDDDDDDDDDS..",
            "...DDKKKKKKKDDS.",
            "....SDKKKKKKDS.A",
            ".....KKKKKKKK.AA",
            ".....KKKKKKKKAAA",
            ".....LL..LL.....",
            "....LL....LL....",
            "...LL......LL...",
            "...WW......WW...",
            "...WW......WW...",
            "..FFF......FFF..",
            "..fff......fff..",
        ],
        "run2": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDDTTTTDDDDS.",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDD.A",
            "...SDKKKKKKKDS.A",
            ".....KKKKKKKK..A",
            ".....KKKKKKKKAAA",
            ".....LL..LL.....",
            ".....LL..LL.....",
            "....LL....LL....",
            "....WW....WW....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
        ],
        "sit": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTTTTDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "..KKKKKKKKKKKK.A",
            "..KKKKKKKKKKKKAA",
            "...dKKKKKKKKdAAA",
            ".....LL....LL...",
            ".....WW....WW...",
            "....FFF....FFF..",
            "....fff....fff..",
            "................",
            "................",
            "................",
        ],
        "sit_down": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTTTTDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK.AAA",
            ".....LL..LL.....",
            "....LL....LL....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
            "................",
            "................",
        ],
        "splat": [
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "...Aa..........A",
            "..AAA....Aa...AA",
            ".HHHHHHHHHHHHHH.",
            "HHHHSSSSSSSSHHHH",
            "HHSSSEeSSSSEsSHH",
            ".HSDDDTTTTDDDS.A",
            "..KKKKKKKKKKKKAA",
            "..FF..WWWW..FFAA",
            "..ff........ff..",
        ],
        "jump_up": [
            "S..............S",
            "S..Aa..........S",
            ".S.AAA........S.",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTTTTDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK.AAA",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
            "................",
            "................",
        ],
        "jump_down": [
            "...Aa...........",
            "..AAA...........",
            "..HHHHHHHHHHH...",
            ".HHHHHHHHHHHHH..",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTTTTDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK.AAA",
            ".....LL..LL.....",
            "....LL....LL....",
            "....WW....WW....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
            "................",
        ],
    },
    "gpt": {
        "idle": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..Ak",
            "....KKKKKKKK.Akk",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "facing_front": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "..ShTddddddTh...",
            ".S.DDDDDDDDDD...",
            "...DDDDDDDDDDS..",
            "..SDDKKKKKKKDD.A",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..Ak",
            "....KKKKKKKK.Akk",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "facing_back": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            "HHHhHHHHHHHHHhHH",
            "HHHhHHHHHHHHHhHH",
            "HHHhHHHHHHHHHhHH",
            ".HHhHHHHHHHHhH..",
            "..HhHHHHHHHHshH.",
            "...hTddddddTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..Ak",
            "....KKKKKKKK.Akk",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "turn": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSSEeSSSSEshH",
            "HHHhSSEESSSSEshH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "..SDDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "...DDKKKKKKKDD.A",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..Ak",
            "....KKKKKKKK.Akk",
            ".....LL..LL.....",
            "....LL...LL.....",
            "....LL...LL.....",
            "....WW...WW.....",
            "....WW...WW.....",
            "...FFF...FFF....",
            "...fff...fff....",
        ],
        "walk1": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "..SDDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "...DDKKKKKKKDD.A",
            "...SDKKKKKKKD.Ak",
            "....KKKKKKKK.Akk",
            "....KKKKKKKK..Ak",
            ".....LL..LL.....",
            ".....LL...LL....",
            "....LL....LL....",
            "....WW.....WW...",
            "....WW.....WW...",
            "...FFF.....FFF..",
            "...fff.....fff..",
        ],
        "walk2": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "...DDDDDDDDDDS..",
            "..SDDDDDDDDDDDS.",
            "..DDKKKKKKKDD..A",
            "...DKKKKKKKDS.Ak",
            "....KKKKKKKK.Akk",
            "....KKKKKKKK....",
            ".....LL..LL.....",
            "....LL...LL.....",
            "....LL....LL....",
            "...WW.....WW....",
            "...WW.....WW....",
            "..FFF.....FFF...",
            "..fff.....fff...",
        ],
        "run1": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "..SDDDDDDDDDD...",
            ".SDDDDDDDDDDDS..",
            "...DDKKKKKKKDDS.",
            "....SDKKKKKKDS.A",
            ".....KKKKKKKK.Ak",
            ".....KKKKKKKKAkk",
            ".....LL..LL.....",
            "....LL....LL....",
            "...LL......LL...",
            "...WW......WW...",
            "...WW......WW...",
            "..FFF......FFF..",
            "..fff......fff..",
        ],
        "run2": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "...DDDDDDDDDDS..",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDD.A",
            "...SDKKKKKKKDS.A",
            ".....KKKKKKKK..A",
            ".....KKKKKKKKAkk",
            ".....LL..LL.....",
            ".....LL..LL.....",
            "....LL....LL....",
            "....WW....WW....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
        ],
        "sit": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "..KKKKKKKKKKKK.A",
            "..KKKKKKKKKKKKAk",
            "...dKKKKKKKKdAkk",
            ".....LL....LL...",
            ".....WW....WW...",
            "....FFF....FFF..",
            "....fff....fff..",
            "................",
            "................",
            "................",
        ],
        "sit_down": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..Ak",
            "....KKKKKKKK.Akk",
            ".....LL..LL.....",
            "....LL....LL....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
            "................",
            "................",
        ],
        "splat": [
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "..AA........AA.A",
            "..AaH......HaAAk",
            ".HHHHHHHHHHHHHH.",
            "HHHHSSSSSSSSHHHH",
            "HHSSSEeSSSSEsSHH",
            ".HSDDDDDDDDDDDS.",
            "..KKKKKKKKKKKK..",
            "..FF..WWWW..FF..",
            "..ff........ff..",
        ],
        "jump_up": [
            "S..............S",
            "S.AA........AA.S",
            ".SAaH......HaAS.",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK.Akk",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
            "................",
            "................",
        ],
        "jump_down": [
            "..AA........AA..",
            "..AaH......HaA..",
            ".HHHHHHHHHHHHHH.",
            ".HHHHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTddddddTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..Ak",
            "....KKKKKKKK.Akk",
            ".....LL..LL.....",
            "....LL....LL....",
            "....WW....WW....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
            "................",
        ],
    },
    "claude": {
        "idle": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTDDDDTTD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS..",
            "....KKKKKKKK....",
            "...dKKKKKKKKd...",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "facing_front": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "..ShTDDTTDDTh...",
            ".S.DDTDDDDTTD...",
            "...DDDDDDDDDDS..",
            "..SDDKKKKKKKDD..",
            "...SDKKKKKKKDS..",
            "....KKKKKKKK....",
            "...dKKKKKKKKd...",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "facing_back": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHHHHHHHHHHHHH",
            "HHHhHHHHHHHHHhHH",
            "HHHhHHHHHHHHHhHH",
            "HHHhHHHHHHHHHhHH",
            ".HHhHHHHHHHHhH..",
            "..HhHHHHHHHHshH.",
            "...hTddddddTh...",
            "...DDTDDDDTTD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS..",
            "....KKKKKKKK....",
            "...dKKKKKKKKd...",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "turn": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSSEeSSSSEshH",
            "HHHhSSEESSSSEshH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "..SDDTDDDDTTD...",
            "..SDDDDDDDDDDDS.",
            "...DDKKKKKKKDD..",
            "...SDKKKKKKKDS..",
            "....KKKKKKKK....",
            "...dKKKKKKKKd...",
            ".....LL..LL.....",
            "....LL...LL.....",
            "....LL...LL.....",
            "....WW...WW.....",
            "....WW...WW.....",
            "...FFF...FFF....",
            "...fff...fff....",
        ],
        "walk1": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "..SDDTDDDDTTD...",
            "..SDDDDDDDDDDDS.",
            "...DDKKKKKKKDD..",
            "...SDKKKKKKKD...",
            "....KKKKKKKK....",
            "...dKKKKKKKKd...",
            ".....LL..LL.....",
            ".....LL...LL....",
            "....LL....LL....",
            "....WW.....WW...",
            "....WW.....WW...",
            "...FFF.....FFF..",
            "...fff.....fff..",
        ],
        "walk2": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTDDDDTTDS..",
            "..SDDDDDDDDDDDS.",
            "..DDKKKKKKKDD...",
            "...DKKKKKKKDS...",
            "....KKKKKKKK....",
            "...dKKKKKKKKd...",
            ".....LL..LL.....",
            "....LL...LL.....",
            "....LL....LL....",
            "...WW.....WW....",
            "...WW.....WW....",
            "..FFF.....FFF...",
            "..fff.....fff...",
        ],
        "run1": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "..SDDTDDDDTTD...",
            ".SDDDDDDDDDDDS..",
            "...DDKKKKKKKDDS.",
            "....SDKKKKKKDS..",
            ".....KKKKKKKK...",
            "....dKKKKKKKKd..",
            ".....LL..LL.....",
            "....LL....LL....",
            "...LL......LL...",
            "...WW......WW...",
            "...WW......WW...",
            "..FFF......FFF..",
            "..fff......fff..",
        ],
        "run2": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTDDDDTTDDS.",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDD..",
            "...SDKKKKKKKDS..",
            ".....KKKKKKKK...",
            "....dKKKKKKKKd..",
            ".....LL..LL.....",
            ".....LL..LL.....",
            "....LL....LL....",
            "....WW....WW....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
        ],
        "sit": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTDDDDTTD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "..KKKKKKKKKKKK..",
            "..KKKKKKKKKKKK..",
            "...dKKKKKKKKd...",
            ".....LL....LL...",
            ".....WW....WW...",
            "....FFF....FFF..",
            "....fff....fff..",
            "................",
            "................",
            "................",
        ],
        "sit_down": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTDDDDTTD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS..",
            "....KKKKKKKK....",
            "...dKKKKKKKKd...",
            ".....LL..LL.....",
            "....LL....LL....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
            "................",
            "................",
        ],
        "splat": [
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "..AAaAA.........",
            ".AAAAAAA........",
            ".HHHHHHHHHHHHHH.",
            "HHHHSSSSSSSSHHHH",
            "HHSSSEeSSSSEsSHH",
            ".HSDDDTTTTDDDS..",
            "..KKKKKKKKKKKK..",
            "..FF..WWWW..FF..",
            "..ff........ff..",
        ],
        "jump_up": [
            "S..............S",
            "S.AAaAA........S",
            ".SAAAAAAA.....S.",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTDDDDTTD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS..",
            "....KKKKKKKK....",
            ".....LL..LL.....",
            ".....LL..LL.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
            "................",
            "................",
        ],
        "jump_down": [
            "..AAaAA.........",
            ".AAAAAAA........",
            "..HHHHHHHHHHHH..",
            ".HHHHHHHHHHHHHH.",
            "HHHHhSSSSSSShHHH",
            "HHHhSSSSSSSSShHH",
            "HHHhSEeSSSSEShHH",
            "HHHhSEESSSSEESHH",
            ".HHhSBSSSSSBShH.",
            "..HhSSSSSSSSshH.",
            "...hTDDTTDDTh...",
            "...DDTDDDDTTD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS..",
            "....KKKKKKKK....",
            "...dKKKKKKKKd...",
            ".....LL..LL.....",
            "....LL....LL....",
            "....WW....WW....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
            "................",
        ],
    },
    "gemini": {
        "idle": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK...A",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "facing_front": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "..ShTDDTTDDTh...",
            ".S.DDDDDDDDDD...",
            "...DDDDDDDDDDS..",
            "..SDDKKKKKKKDD.A",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK...A",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "facing_back": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".hhhhhhhhhhhhhh.",
            "hhhhhHHHHHHHHhhh",
            "hhhhhHHHHHHHHhhh",
            "hhhhhHHHHHHHHhhh",
            ".hhhHHHHHHHHhhh.",
            "..hhHHHHHHHHshh.",
            "...hTddddddTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK...A",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
        ],
        "turn": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSSEeSSSSEshh",
            "hhhhSSEESSSSEshh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "..SDDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "...DDKKKKKKKDD.A",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK...A",
            ".....LL..LL.....",
            "....WW...WW.....",
            "....WW...WW.....",
            "....WW...WW.....",
            "....WW...WW.....",
            "...FFF...FFF....",
            "...fff...fff....",
        ],
        "walk1": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "..SDDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "...DDKKKKKKKDD.A",
            "...SDKKKKKKKD.AA",
            "....KKKKKKKK...A",
            "....KKKKKKKK..AA",
            ".....LL..LL.....",
            ".....WW...WW....",
            "....WW....WW....",
            "....WW.....WW...",
            "....WW.....WW...",
            "...FFF.....FFF..",
            "...fff.....fff..",
        ],
        "walk2": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "...DDDDDDDDDDS..",
            "..SDDDDDDDDDDDS.",
            "..DDKKKKKKKDD..A",
            "...DKKKKKKKDS.AA",
            "....KKKKKKKK...A",
            "....KKKKKKKK....",
            ".....LL..LL.....",
            "....WW...WW.....",
            "....WW....WW....",
            "...WW.....WW....",
            "...WW.....WW....",
            "..FFF.....FFF...",
            "..fff.....fff...",
        ],
        "run1": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "..SDDDDDDDDDD...",
            ".SDDDDDDDDDDDS..",
            "...DDKKKKKKKDDS.",
            "....SDKKKKKKDS.A",
            ".....KKKKKKKK..A",
            ".....KKKKKKKK.AA",
            ".....LL..LL.....",
            "....WW....WW....",
            "...WW......WW...",
            "...WW......WW...",
            "...WW......WW...",
            "..FFF......FFF..",
            "..fff......fff..",
        ],
        "run2": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "...DDDDDDDDDDS..",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDD.A",
            "...SDKKKKKKKDS.A",
            ".....KKKKKKKK..A",
            ".....KKKKKKKK.AA",
            ".....LL..LL.....",
            ".....WW..WW.....",
            "....WW....WW....",
            "....WW....WW....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
        ],
        "sit": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "..KKKKKKKKKKKK.A",
            "..KKKKKKKKKKKKAA",
            "...dKKKKKKKKd..A",
            ".....LL....LL...",
            ".....WW....WW...",
            "....FFF....FFF..",
            "....fff....fff..",
            "................",
            "................",
            "................",
        ],
        "sit_down": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK...A",
            ".....LL..LL.....",
            "....WW....WW....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
            "................",
            "................",
        ],
        "splat": [
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "................",
            "..AA........AA.A",
            "..AsH......HsAAA",
            ".HaHHHHHHHHHHH..",
            "hhhhSSSSSSSSshhh",
            "hhSSSEeSSSSEsShh",
            ".HSDDDDDDDDDDDS.",
            "..KKKKKKKKKKKK..",
            "..FF..WWWW..FF..",
            "..ff........ff..",
        ],
        "jump_up": [
            "S..............S",
            "S.AA........AA.S",
            ".SAsH......HsAS.",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            ".....LL..LL.....",
            ".....WW..WW.....",
            ".....WW..WW.....",
            "....FFF..FFF....",
            "....fff..fff....",
            "................",
            "................",
        ],
        "jump_down": [
            "..AA........AA..",
            "..AsH......HsA..",
            "..HaHHHHHHHHHH..",
            ".HaaHHHHHHHHHHH.",
            ".HHHhSSSSSSShHH.",
            "hhhhSSSSSSSSshhh",
            "hhhhSEeSSSSEShhh",
            "hhhhSEESSSSEEShh",
            ".hhhSBSSSSSBshh.",
            "..hhSSSSSSSSshh.",
            "...hTDDTTDDTh...",
            "...DDDDDDDDDD...",
            "..SDDDDDDDDDDDS.",
            "..SDDKKKKKKKDDS.",
            "...SDKKKKKKKDS.A",
            "....KKKKKKKK..AA",
            "....KKKKKKKK...A",
            ".....LL..LL.....",
            "....WW....WW....",
            "....WW....WW....",
            "....WW....WW....",
            "...FFF....FFF...",
            "...fff....fff...",
            "................",
        ],
    },
}


OFFICIAL_CHIBI_IDS = {"deepseek", "gpt", "claude", "gemini"}


class PixelChibiRegistry:
    """自訂 Q 版人物儲存庫與註冊表管理器。
    支援讀寫 JSON、匯入 PNG/JSON、尺寸限制檢查（支援不顧限制）、官方預設保護。
    """
    _custom_cache: dict[str, dict] = {}
    _cache_mtime: float = 0.0

    @classmethod
    def reload(cls):
        """重新整理 custom_chibi 目錄並載入所有自訂人物。"""
        CUSTOM_CHIBI_DIR.mkdir(parents=True, exist_ok=True)
        cls._custom_cache.clear()
        for f in CUSTOM_CHIBI_DIR.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                cid = (data.get("id") or f.stem).strip().lower()
                if cid in OFFICIAL_CHIBI_IDS:
                    continue  # 官方角色受保護，禁止被自訂檔案覆寫
                data["id"] = cid
                data["is_custom"] = True
                data["is_protected"] = False
                data["mtime"] = f.stat().st_mtime
                cls._custom_cache[cid] = data
            except Exception as e:
                log("PixelChibiRegistry", f"讀取自訂人物檔案 {f.name} 失敗：{e}")
        cls._cache_mtime = time.time()

    @classmethod
    def get_character(cls, cid: str) -> dict | None:
        """獲取指定角色的完整資料（官方或自訂）。"""
        cid = (cid or "").lower().strip()
        if cid in CHARACTER_INFO:
            info = dict(CHARACTER_INFO[cid])
            info["palette"] = CHAR_PALETTES.get(cid, {})
            frames = dict(FRAMES)
            if cid in CHAR_SPECIFIC_FRAMES:
                frames.update(CHAR_SPECIFIC_FRAMES[cid])
            info["frames"] = frames
            info["width"] = 16
            info["height"] = 24
            info["ignore_limits"] = False
            info["is_custom"] = False
            info["is_protected"] = True
            info["mtime"] = 0.0
            return info

        if not cls._custom_cache:
            cls.reload()

        if cid in cls._custom_cache:
            return cls._custom_cache[cid]

        # 嘗試從檔案讀取
        f = CUSTOM_CHIBI_DIR / f"{cid}.json"
        if f.exists():
            cls.reload()
            return cls._custom_cache.get(cid)

        return None

    @classmethod
    def get_character_size(cls, cid: str) -> tuple[int, int]:
        """取得指定角色的寬高尺寸 (width, height)。"""
        info = cls.get_character(cid)
        if info:
            return int(info.get("width", 16)), int(info.get("height", 24))
        return 16, 24

    @classmethod
    def list_official_characters(cls) -> dict[str, dict]:
        """列出官方 4 位預設角色。"""
        res = {}
        for cid in ["deepseek", "gpt", "claude", "gemini"]:
            res[cid] = cls.get_character(cid)
        return res

    @classmethod
    def list_custom_characters(cls) -> dict[str, dict]:
        """列出所有自訂角色。"""
        cls.reload()
        return dict(cls._custom_cache)

    @classmethod
    def list_all_characters(cls) -> dict[str, dict]:
        """列出官方 + 自訂所有角色。"""
        all_chars = cls.list_official_characters()
        all_chars.update(cls.list_custom_characters())
        return all_chars

    @classmethod
    def list_all_ids(cls) -> list[str]:
        """列出所有角色識別碼清單（供隨機召喚抽選）。"""
        return list(cls.list_all_characters().keys())

    @classmethod
    def character_exists(cls, cid: str) -> bool:
        """檢查角色代號是否已存在（官方或自訂）。"""
        cid = (cid or "").lower().strip()
        if cid in OFFICIAL_CHIBI_IDS:
            return True
        f = CUSTOM_CHIBI_DIR / f"{cid}.json"
        return f.exists() or (cid in cls._custom_cache)

    @classmethod
    def find_existing_by_name(cls, name: str) -> str | None:
        """根據角色名稱尋找已存在的角色 ID。"""
        name = (name or "").strip()
        for cid, char in cls.list_all_characters().items():
            if char.get("name", "").strip() == name:
                return cid
        return None

    @classmethod
    def save_custom_chibi(cls, data: dict) -> Path:
        """儲存自訂 Q 版人物至 CUSTOM_CHIBI_DIR。
        包含 id, name, palette, frames, width, height, ignore_limits 等。
        """
        CUSTOM_CHIBI_DIR.mkdir(parents=True, exist_ok=True)
        raw_id = str(data.get("id", "")).strip().lower()
        safe_id = "".join(c for c in raw_id if c.isalnum() or c in ("_", "-")).strip()
        if not safe_id:
            safe_id = f"chibi_{int(time.time())}"

        if safe_id in OFFICIAL_CHIBI_IDS:
            raise ValueError(f"角色代號「{safe_id}」為官方預設受保護角色，絕不允許覆蓋！")

        name = str(data.get("name", safe_id)).strip() or safe_id
        w = int(data.get("width", 16))
        h = int(data.get("height", 24))
        ignore_limits = bool(data.get("ignore_limits", False))

        if not ignore_limits and (w != 16 or h != 24):
            raise ValueError(f"角色尺寸為 {w}x{h}，超出預設 16x24 限制。請勾選「不顧限制」標記！")

        save_dict = {
            "id": safe_id,
            "name": name,
            "width": w,
            "height": h,
            "ignore_limits": ignore_limits,
            "palette": dict(data.get("palette", {})),
            "frames": dict(data.get("frames", {})),
        }

        target_file = CUSTOM_CHIBI_DIR / f"{safe_id}.json"
        target_file.write_text(json.dumps(save_dict, ensure_ascii=False, indent=2), encoding="utf-8")

        PixelChibiRenderer.clear_cache(safe_id)
        cls.reload()
        log("PixelChibiRegistry", f"自訂 Q 版人物「{name}」({safe_id}) 儲存成功：{target_file}")
        return target_file

    @classmethod
    def delete_custom_chibi(cls, cid: str) -> bool:
        """刪除已有的自訂 Q 版人物。官方角色絕不允許刪除！"""
        cid = (cid or "").lower().strip()
        if cid in OFFICIAL_CHIBI_IDS:
            raise ValueError("官方預設角色（藍色大肥魚、GPT龍娘、大小姐Claude、北美貓娘Gemini）受保護，絕不允許刪除！")

        f = CUSTOM_CHIBI_DIR / f"{cid}.json"
        if f.exists():
            try:
                f.unlink()
                PixelChibiRenderer.clear_cache(cid)
                cls.reload()
                log("PixelChibiRegistry", f"已成功刪除自訂 Q 版人物：{cid}")
                return True
            except Exception as e:
                log("PixelChibiRegistry", f"刪除自訂人物 {cid} 失敗：{e}")
                raise
        return False

    @classmethod
    def import_from_json(cls, file_or_data: str | Path | dict, ignore_limits_override: bool = False) -> dict:
        """匯入外部 Q 版人物 JSON，支援不顧限制標記。"""
        if isinstance(file_or_data, (str, Path)):
            p = Path(file_or_data)
            data = json.loads(p.read_text(encoding="utf-8"))
        else:
            data = dict(file_or_data)

        if ignore_limits_override:
            data["ignore_limits"] = True

        cls.save_custom_chibi(data)
        return data

    @classmethod
    def import_from_png(cls, png_path: str | Path, name: str, char_id: str = "", ignore_limits: bool = False) -> dict:
        """匯入外部 PNG 精靈圖檔案轉換為自訂 Q 版人物，支援不顧限制匯入。"""
        img = QImage(str(png_path))
        if img.isNull():
            raise ValueError("無法讀取或解析 PNG 圖片檔案！")

        w = img.width()
        h = img.height()
        if not ignore_limits and (w != 16 or h != 24):
            raise ValueError(f"PNG 尺寸為 {w}x{h}，超出預設 16x24 限制。若欲匯入請開啟「不顧限制」！")

        palette: dict[str, str] = {}
        symbol_pool = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()-_+=~"
        color_to_sym: dict[str, str] = {}
        rows: list[str] = []

        for y in range(h):
            row_chars = []
            for x in range(w):
                c = img.pixelColor(x, y)
                if c.alpha() < 16:
                    row_chars.append(".")
                else:
                    hex_code = c.name(QColor.HexRgb).lower()
                    if hex_code not in color_to_sym:
                        idx = len(color_to_sym)
                        sym = symbol_pool[idx] if idx < len(symbol_pool) else f"C{idx}"
                        color_to_sym[hex_code] = sym
                        palette[sym] = hex_code
                    row_chars.append(color_to_sym[hex_code])
            rows.append("".join(row_chars))

        safe_id = char_id or f"custom_{int(time.time())}"
        data = {
            "id": safe_id,
            "name": name or safe_id,
            "width": w,
            "height": h,
            "ignore_limits": ignore_limits or (w != 16 or h != 24),
            "palette": palette,
            "frames": {
                "idle": rows,
                "walk1": rows,
                "walk2": rows,
                "sit": rows,
                "splat": rows,
            },
        }
        cls.save_custom_chibi(data)
        return data

    @classmethod
    def export_to_json(cls, cid: str, target_path: str | Path) -> Path:
        """匯出自訂或官方 Q 版人物為 JSON 檔案。"""
        info = cls.get_character(cid)
        if not info:
            raise ValueError(f"找不到角色：{cid}")

        export_data = {
            "id": info["id"],
            "name": info["name"],
            "width": info.get("width", 16),
            "height": info.get("height", 24),
            "ignore_limits": info.get("ignore_limits", False),
            "palette": info.get("palette", {}),
            "frames": info.get("frames", {}),
        }
        out_p = Path(target_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_p


class PixelChibiRenderer:
    """純代碼 2D 像素陣列與色盤精確繪製器，最近鄰無失真放大。支援官方與自訂人物。"""
    _cache: dict[tuple, QPixmap] = {}

    @classmethod
    def clear_cache(cls, char_id: str | None = None):
        if char_id is None:
            cls._cache.clear()
        else:
            cid = char_id.lower()
            cls._cache = {k: v for k, v in cls._cache.items() if k[0] != cid}

    @classmethod
    def get_pixmap(cls, character: str, frame_name: str, facing_right: bool = False, scale: int = 3, has_balloon: bool = False, balloon_idx: int = 0) -> QPixmap:
        char_key = character.lower()
        info = PixelChibiRegistry.get_character(char_key)
        if not info:
            char_key = "deepseek"
            info = PixelChibiRegistry.get_character("deepseek")

        cache_key = (char_key, frame_name, facing_right, scale, has_balloon, balloon_idx, info.get("mtime", 0.0))
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        w = int(info.get("width", 16))
        h = int(info.get("height", 24))
        palette = info.get("palette", {})
        frames = info.get("frames", {})

        raw_rows = frames.get(frame_name)
        if not raw_rows:
            raw_rows = frames.get("idle") or FRAMES.get(frame_name, FRAMES["idle"])

        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)

        for y, row_str in enumerate(raw_rows):
            if y >= h:
                break
            if isinstance(row_str, str):
                for x, ch in enumerate(row_str):
                    if x >= w:
                        break
                    if ch == "." or ch == " ":
                        continue
                    color_hex = palette.get(ch)
                    if color_hex and color_hex != "transparent":
                        img.setPixelColor(x, y, QColor(color_hex))
            elif isinstance(row_str, (list, tuple)):
                for x, val in enumerate(row_str):
                    if x >= w:
                        break
                    if not val or val in (".", " ", "transparent"):
                        continue
                    col_str = palette.get(val, val)
                    if col_str and col_str != "transparent":
                        img.setPixelColor(x, y, QColor(col_str))

        # 疊加小氣球漂浮道具
        if has_balloon:
            b_rows = BALLOON_FRAMES[balloon_idx % len(BALLOON_FRAMES)]
            for by, brow in enumerate(b_rows):
                if by >= h:
                    break
                for bx, bch in enumerate(brow):
                    if bx >= w:
                        break
                    if bch in palette:
                        img.setPixelColor(bx, by, QColor(palette[bch]))

        if facing_right:
            img = img.mirrored(True, False)

        # 最近鄰取樣放大 (Qt.FastTransformation) 確保 100% 俐落像素邊緣
        target_w = max(1, w * scale)
        target_h = max(1, h * scale)
        scaled_img = img.scaled(target_w, target_h, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        pm = QPixmap.fromImage(scaled_img)
        cls._cache[cache_key] = pm
        return pm


class PixelParticle:
    """像素煙火粒子。"""
    def __init__(self, x: float, y: float, vx: float, vy: float, color: QColor, life: float = 1.0):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.life = life
        self.age = 0.0

    def update(self, dt: float) -> bool:
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vy += 80.0 * dt  # 重力
        return self.age < self.life


class ChibiThoughtBubble(QWidget):
    """Q 版小人專屬想法框，展示被監控 API 的即時額度/餘額與即時匯率換算。"""
    def __init__(self, owner: PixelChibiWindow):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        )
        self.owner = owner
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.title_text = ""
        self.body_text = "--"
        self.setFixedSize(140, 52)
        self.hide()

    def set_content(self, title: str, body: str):
        self.title_text = title
        self.body_text = body
        fm = QFontMetrics(QFont("Microsoft JhengHei UI", 9, QFont.Bold))
        w1 = fm.horizontalAdvance(self.title_text)
        w2 = fm.horizontalAdvance(self.body_text)
        new_w = max(130, min(240, max(w1, w2) + 24))
        if new_w != self.width():
            self.setFixedWidth(new_w)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.owner and hasattr(self.owner, "ledger") and self.owner.ledger:
                self.owner.ledger.refresh()
            e.accept()
        else:
            super().mousePressEvent(e)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        is_dark = (self.owner.cfg.get("theme", "light") == "dark") if (self.owner and self.owner.cfg) else False
        bg_col = QColor(22, 24, 29, 235) if is_dark else QColor(255, 255, 255, 240)
        border_col = QColor(70, 80, 100, 180) if is_dark else QColor(210, 220, 235, 220)
        text_title_col = QColor(148, 163, 184) if is_dark else QColor(100, 116, 139)
        text_body_col = QColor(56, 189, 248) if is_dark else QColor(14, 116, 144)

        # 1. 繪製想法框主圓角矩形
        main_rect = QRectF(4, 2, self.width() - 8, self.height() - 14)
        path = QPainterPath()
        path.addRoundedRect(main_rect, 10, 10)

        # 2. 繪製底部延伸小圓泡泡
        cx = self.width() / 2.0
        path.addEllipse(QPointF(cx - 2, self.height() - 9), 3, 3)
        path.addEllipse(QPointF(cx + 4, self.height() - 4), 2, 2)

        painter.setPen(QPen(border_col, 1.2))
        painter.setBrush(QBrush(bg_col))
        painter.drawPath(path)

        # 3. 繪製文字
        f_title = QFont("Microsoft JhengHei UI", 8)
        painter.setFont(f_title)
        painter.setPen(text_title_col)
        painter.drawText(QRectF(8, 5, self.width() - 16, 16), Qt.AlignCenter, self.title_text)

        f_body = QFont("Microsoft JhengHei UI", 9, QFont.Bold)
        painter.setFont(f_body)
        painter.setPen(text_body_col)
        painter.drawText(QRectF(8, 20, self.width() - 16, 18), Qt.AlignCenter, self.body_text)


class PixelChibiWindow(QWidget):
    """Q 版小人獨立桌面巡邏與互動視窗。"""
    panic_fall_started = Signal()
    panic_landed = Signal()
    duang_bounce = Signal()

    def __init__(self, cfg, sounds, pet=None, app=None):
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint | Qt.NoDropShadowWindowHint
        )
        self.cfg = cfg
        self.sounds = sounds
        self.pet = pet
        self.app = app

        # 獨立 API 額度監控與想法框
        self.monitor_provider: str | None = None
        self.monitor_key_index: int | None = None
        self.ledger = None
        self.thought_bubble: ChibiThoughtBubble | None = None

        if self.pet and (not getattr(self.pet, "pixel_chibi", None) or getattr(self.pet, "pixel_chibi", None) == self):
            self.pet.pixel_chibi = self

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setWindowTitle("Pixel Chibi Patrol")
        self.sync_opacity()

        self.scale_factor = 3  # 16x24 -> 48x72 px (或自訂尺寸 x 3)
        self.character = cfg.get("character", "deepseek")
        w, h = PixelChibiRegistry.get_character_size(self.character)
        self.char_w = w * self.scale_factor
        self.char_h = h * self.scale_factor
        self.setFixedSize(self.char_w, self.char_h)

        # 狀態機
        self.state = "idle"  # idle, walk, run, jump, sit, splat, sleep, wake, panic, climb, flight, bowl_smash, bounce
        self.facing_right = True
        self.pos_x = 200.0
        self.pos_y = 600.0
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.on_ground = True
        self.state_time = 0.0
        self.walk_phase = 0.0
        self.balloon_idx = 0
        self.balloon_timer = 0.0

        # 子動作幀指標
        self.climb_subframe = "climb_up"
        self.sleep_subframe = "sleep_prone"
        self.post_smash_recover = False

        # 主寵互動
        self.climbing_pet = False
        self.pet_mount_slot = "floor"  # floor, head, iron, back, tablet

        # 道具
        self.particles: list[PixelParticle] = []

        # 動態真實時間差 (Delta-Time) 與幀率調度定時器
        self._last_tick = time.monotonic()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.sync_fps()
        self.timer.start()

        self._init_position()

    def sync_opacity(self, val: int | float | None = None):
        """同步 Q 版人物視窗不透明度 (20..100)。"""
        if val is None:
            val = float(self.cfg.get("q_chibi_opacity", 100))
        op = max(0.2, min(1.0, float(val) / 100.0))
        self.setWindowOpacity(op)

    def sync_fps(self) -> int:
        """根據 target_fps 與 performance_mode 動態調度定時器幀率 (10-240 FPS / 無限制)。"""
        perf = bool(self.cfg.get("performance_mode", False))
        fps = int(self.cfg.get("target_fps", 60))
        if perf:
            effective_fps = min(30, fps) if fps > 0 else 30
        else:
            effective_fps = fps

        if effective_fps <= 0:
            interval = 1
        elif effective_fps == 144:
            interval = 7
        else:
            interval = max(1, int(1000 / effective_fps))

        self.timer.setInterval(interval)
        return interval

    def set_pet(self, pet):
        self.pet = pet
        if self.pet and (not getattr(self.pet, "pixel_chibi", None) or getattr(self.pet, "pixel_chibi", None) == self):
            self.pet.pixel_chibi = self

    def set_character(self, ch: str):
        self.character = ch
        w, h = PixelChibiRegistry.get_character_size(ch)
        self.char_w = w * self.scale_factor
        self.char_h = h * self.scale_factor
        self.setFixedSize(self.char_w, self.char_h)
        self.update()

    def _screen_rect(self) -> QRect:
        s = QGuiApplication.screenAt(self.geometry().center()) or QGuiApplication.primaryScreen()
        return s.availableGeometry()

    def _init_position(self):
        ag = self._screen_rect()
        floor_y = ag.bottom() + 1 - self.char_h
        self.pos_x = float(ag.left() + 160)
        self.pos_y = float(floor_y)
        self.move(int(self.pos_x), int(self.pos_y))
        self.show()
        self.raise_()

    def _tick(self):
        """真實時間差 (Delta-Time) 物理更新週期。"""
        now = time.monotonic()
        raw_dt = now - self._last_tick
        self._last_tick = now

        if raw_dt <= 0.0001:
            fps = int(self.cfg.get("target_fps", 60))
            dt = 1.0 / max(1, fps if fps > 0 else 60)
        else:
            dt = min(raw_dt, 0.08)

        self.state_time += dt
        ag = self._screen_rect()
        floor_y = float(ag.bottom() + 1 - self.char_h)

        # 1. 確保圖層永遠高於主寵物 (Z-Order Topmost)
        self.raise_()

        # 2. 更新煙火粒子
        if self.particles:
            self.particles = [p for p in self.particles if p.update(dt)]
            self.update()

        # 3. 飛行道具模式 (小氣球)
        flight_on = bool(self.cfg.get("q_flight_prop", False))
        if flight_on:
            self.state = "flight"
            self.balloon_timer += dt
            if self.balloon_timer > 0.12:
                self.balloon_timer = 0.0
                self.balloon_idx = 1 - self.balloon_idx

            self.pos_x += (28.0 if self.facing_right else -28.0) * dt
            target_air_y = floor_y - 180.0 + 40.0 * math.sin(self.state_time * 2.5)
            self.pos_y += (target_air_y - self.pos_y) * min(1.0, 4.0 * dt)

            if self.pos_x > ag.right() - self.char_w - 40:
                self.facing_right = False
            elif self.pos_x < ag.left() + 40:
                self.facing_right = True

            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 4. 視窗與按鈕攀爬辨識 (q_climb_windows)
        climb_enabled = bool(self.cfg.get("q_climb_windows", False))
        if climb_enabled and self.state not in ("panic", "bounce", "bowl_smash"):
            win_rect = self._get_active_window_rect()
            if win_rect and win_rect.isValid() and not win_rect.isEmpty():
                if abs(self.pos_x - win_rect.left()) < 24 and win_rect.top() <= self.pos_y <= win_rect.bottom():
                    self.state = "climb"
                    self.climb_subframe = "climb_up"
                    self.pos_y -= 30.0 * dt
                    if self.pos_y <= win_rect.top() - self.char_h:
                        self.pos_y = win_rect.top() - self.char_h
                        self.state = "walk"
                    self.move(int(self.pos_x), int(self.pos_y))
                    self.update()
                    return
            else:
                if self.pos_y < floor_y - 20:
                    self.start_panic_fall()

        # 5. 飯盆砸飛拋物線物理 (Bowl Smash & Knock-back)
        if self.state == "bowl_smash":
            self.vel_y += 500.0 * dt
            self.pos_x += self.vel_x * dt
            self.pos_y += self.vel_y * dt
            if self.pos_x < ag.left() + 5:
                self.pos_x = float(ag.left() + 5)
                self.vel_x = -self.vel_x * 0.5
            elif self.pos_x > ag.right() - self.char_w - 5:
                self.pos_x = float(ag.right() - self.char_w - 5)
                self.vel_x = -self.vel_x * 0.5

            if self.pos_y >= floor_y:
                self.pos_y = floor_y
                self.vel_y = 0.0
                self.vel_x = 0.0
                self.state = "splat"
                self.state_time = 0.0
                self.post_smash_recover = True
                if self.sounds:
                    self.sounds.play("land")
                log("PixelChibi", "小人被砸飛落地，進入眼冒金星軟趴趴狀態！")
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 6. 慌張失足掉落物理 (Panic Fall)
        if self.state == "panic":
            self.vel_y += 500.0 * dt
            self.pos_y += self.vel_y * dt
            if self.pos_y >= floor_y:
                self.pos_y = floor_y
                self.vel_y = 0.0
                self.state = "sit"
                self.state_time = 0.0
                self.panic_landed.emit()
                if self.sounds:
                    self.sounds.play("land")
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 7. Duang 軟彈後退坐倒狀態
        if self.state == "bounce":
            self.pos_x += self.vel_x * dt
            self.vel_x *= math.pow(0.85, dt / 0.025)
            if self.state_time > 1.2:
                self.state = "idle"
                self.state_time = 0.0
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 8. 跳躍與飛撲物理 (Jump / Run Jump)
        if self.state in ("jump", "run_jump"):
            self.vel_y += 500.0 * dt
            self.pos_x += self.vel_x * dt
            self.pos_y += self.vel_y * dt
            if self.pos_y >= floor_y:
                self.pos_y = floor_y
                self.vel_y = 0.0
                self.vel_x = 0.0
                self.state = "idle"
                self.state_time = 0.0
                if self.sounds:
                    self.sounds.play("land")
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 9. 主寵物碰撞偵測與「Duang～」軟彈物理
        if self.pet and self.pet.isVisible() and not self.climbing_pet:
            pet_geom = self.pet.geometry()
            my_rect = QRect(int(self.pos_x), int(self.pos_y), self.char_w, self.char_h)
            if pet_geom.intersects(my_rect):
                self.trigger_duang_bounce()
                return

        # 10. 攀爬主寵物狀態 (頭頂、鐵盆、後背、平板)
        if self.climbing_pet and self.pet and self.pet.isVisible():
            if self.pet_mount_slot == "head":
                head_rect = self.pet.head_zone_global()
                self.pos_x = head_rect.center().x() - self.char_w / 2
                self.pos_y = head_rect.top() - (self.char_h * 0.45 if self.state == "splat" else self.char_h * 0.7)
            elif self.pet_mount_slot == "iron":
                head_rect = self.pet.head_zone_global()
                if self.state == "splat":
                    self.pos_x = head_rect.center().x() - self.char_w / 2
                    self.pos_y = head_rect.top() - self.char_h * 0.75
                else:
                    self.pos_x = head_rect.center().x() + 18
                    self.pos_y = head_rect.top() - self.char_h * 0.4
            elif self.pet_mount_slot == "back":
                pet_geom = self.pet.geometry()
                offset_x = pet_geom.width() * (0.2 if not getattr(self.pet, "snap_right", False) else 0.5)
                self.pos_x = pet_geom.left() + offset_x
                self.pos_y = pet_geom.top() + pet_geom.height() * (0.42 if self.state == "splat" else 0.35)
            elif self.pet_mount_slot == "tablet":
                tab_rect = self.pet.tablet_zone_global()
                self.pos_x = tab_rect.center().x() - self.char_w / 2
                self.pos_y = tab_rect.top() - self.char_h * 0.5
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 11. 軟趴趴狀態 (Splat)
        if self.state == "splat":
            if not self.climbing_pet:
                self.pos_y = floor_y
                if self.post_smash_recover:
                    # 著陸後短暫進入眼冒金星軟趴趴狀態 (約 1.5 秒)
                    if self.state_time >= 1.5:
                        self.post_smash_recover = False
                        self.state_time = 0.0
                        if self.pet and getattr(self.pet, "iron_count", 0) > 0 and self.pet.isVisible():
                            # 隨後起身晃頭，好奇爬上主寵頭頂鐵盆
                            self.mount_pet("iron", pose="sit")
                            log("PixelChibi", "小人晃晃小腦袋起身，好奇爬上主寵頭頂鐵盆！")
                        else:
                            self.state = "idle"
                else:
                    if self.state_time > 3.0:
                        self.state = "sit"
                        self.state_time = 0.0
                self.move(int(self.pos_x), int(self.pos_y))
                self.update()
                return

        # 12. 睡覺與驚醒狀態 (Sleep & Wake)
        if self.state == "sleep":
            self.pos_y = floor_y
            if self.state_time > 5.0:
                self.state = "wake"
                self.state_time = 0.0
                log("PixelChibi", "小人呼呼大睡後突然驚醒！呆毛炸毛豎立！")
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        if self.state == "wake":
            self.pos_y = floor_y
            if self.state_time > 0.8:
                self.state = "idle"
                self.state_time = 0.0
            self.move(int(self.pos_x), int(self.pos_y))
            self.update()
            return

        # 13. 地面巡邏與行為狀態輪替
        self.pos_y = floor_y
        if self.state in ("walk", "run"):
            speed = 70.0 if self.state == "run" else 40.0
            dx = (speed if self.facing_right else -speed) * dt
            self.pos_x += dx
            rate = 6.5 if self.state == "run" else 4.5
            self.walk_phase = (self.walk_phase + dt * rate) % 2.0

            if self.pos_x > ag.right() - self.char_w - 10:
                self.facing_right = False
            elif self.pos_x < ag.left() + 10:
                self.facing_right = True

            if self.state == "run" and self.state_time > 2.5:
                self.state = "walk"
                self.state_time = 0.0
            elif self.state == "walk" and self.state_time > 5.0 and random.random() < 0.03:
                r = random.random()
                if r < 0.25:
                    self.state = "run"
                elif r < 0.45:
                    self.state = "sit"
                elif r < 0.60:
                    self.state = "splat"
                elif r < 0.75:
                    self.start_sleep()
                elif r < 0.88:
                    self.state = "mischief"
                else:
                    self.state = "idle"
                self.state_time = 0.0
        elif self.state == "idle":
            if self.state_time > 2.5:
                r = random.random()
                if r < 0.35:
                    self.state = "facing_front"
                elif r < 0.50:
                    self.state = "facing_back"
                elif r < 0.65:
                    self.state = "turn"
                else:
                    self.state = "walk"
                    self.facing_right = (random.random() > 0.5)
                self.state_time = 0.0
        elif self.state == "facing_front":
            if self.state_time > 1.8:
                self.state = "walk"
                self.state_time = 0.0
        elif self.state == "facing_back":
            if self.state_time > 1.8:
                self.state = "turn"
                self.state_time = 0.0
        elif self.state == "turn":
            if self.state_time > 0.4:
                self.state = "walk"
                self.state_time = 0.0
        elif self.state == "mischief":
            if self.state_time > 2.0:
                self.state = "walk"
                self.state_time = 0.0
        elif self.state == "sit":
            if self.state_time > 4.5:
                self.state = "walk"
                self.state_time = 0.0

        self.move(int(self.pos_x), int(self.pos_y))
        self.update()

    def start_panic_fall(self):
        """觸發失足驚慌掉落：四肢揮舞亂蹬掉回工作列。"""
        self.state = "panic"
        self.vel_y = 60.0
        self.state_time = 0.0
        self.panic_fall_started.emit()
        log("PixelChibi", "小人失足慌張掉落！小腿空中亂蹬中！")

    def trigger_duang_bounce(self):
        """撞擊主寵物觸發軟彈物理，後退兩步坐倒。"""
        self.state = "bounce"
        self.state_time = 0.0
        self.vel_x = -90.0 if self.facing_right else 90.0
        self.facing_right = not self.facing_right
        self.duang_bounce.emit()
        if self.sounds:
            self.sounds.play("hit")
        log("PixelChibi", "Duang～撞到主寵物軟彈後退坐倒！")

    def trigger_bowl_smash(self, direction: int | None = None):
        """飯盆砸飛物理 (Bowl Smash & Knock-back)。
        當鐵盆扣在主寵頭上時，若小人正在頭部，帶慌張蹬腿 (panic 幀) 以拋物線被震飛彈開。
        """
        if direction is None:
            direction = -1 if (self.pet and getattr(self.pet, "snap_right", False)) else (1 if self.facing_right else -1)
        self.climbing_pet = False
        self.pet_mount_slot = "floor"
        self.state = "bowl_smash"
        self.vel_y = -220.0
        self.vel_x = -90.0 * direction
        self.state_time = 0.0
        self.post_smash_recover = False
        if self.sounds:
            self.sounds.play("hit")
        log("PixelChibi", f"Duang！飯盆砸落！小人慌張蹬腿被震飛彈開 (vel_x={self.vel_x:.1f}, vel_y={self.vel_y:.1f})")
        self.update()

    def mount_pet(self, slot: str = "head", pose: str = "sit"):
        """爬上主寵物身體（頭頂 head、鐵盆 iron、後背 back、平板 tablet）。"""
        self.climbing_pet = True
        self.pet_mount_slot = slot
        self.state = pose
        self.state_time = 0.0
        log("PixelChibi", f"小人已爬上主寵物位置：{slot} (姿勢: {pose})")

    def dismount_pet(self):
        """離開主寵物回到地面巡邏。"""
        self.climbing_pet = False
        self.pet_mount_slot = "floor"
        self.start_panic_fall()

    def toggle_mount_pose(self):
        """切換在主寵身上的休息姿勢 (坐姿 sit <-> 軟趴趴 splat)。"""
        if self.climbing_pet:
            self.state = "splat" if self.state == "sit" else "sit"
            self.state_time = 0.0
            log("PixelChibi", f"小人切換在主寵身上的休息姿勢：{self.state}")
            self.update()

    def start_climb(self, direction: str = "up"):
        """全方向攀爬 (up, down, side)。"""
        self.state = "climb"
        if direction == "down":
            self.climb_subframe = "climb_down"
        elif direction == "side":
            self.climb_subframe = "climb_side"
        else:
            self.climb_subframe = "climb_up"
        self.state_time = 0.0
        self.update()

    def start_run(self, facing_right: bool | None = None):
        """開始前傾衝刺快跑。"""
        self.state = "run"
        if facing_right is not None:
            self.facing_right = facing_right
        self.state_time = 0.0
        self.walk_phase = 0.0
        self.update()

    def start_jump(self, vel_x: float = 0.0, vel_y: float = -260.0):
        """跳躍起飛。"""
        self.state = "jump"
        self.vel_x = vel_x
        self.vel_y = vel_y
        self.state_time = 0.0
        self.update()

    def start_sleep(self, pose: str = "sleep_prone"):
        """睡覺姿態 (sleep_prone, sleep_sprawl, sleep_side)。"""
        self.state = "sleep"
        self.sleep_subframe = pose if pose in ("sleep_sprawl", "sleep_prone", "sleep_side") else "sleep_prone"
        self.state_time = 0.0
        self.update()

    def start_wake(self):
        """被驚醒 (wake_startle)！大眼睛瞪圓、四肢炸毛彈起，呆毛豎立。"""
        self.state = "wake"
        self.state_time = 0.0
        self.update()

    def start_splat(self):
        """大字型軟趴趴攤平。"""
        self.state = "splat"
        self.state_time = 0.0
        self.post_smash_recover = False
        self.update()

    def start_mischief(self):
        """做鬼臉搗亂踩跳。"""
        self.state = "mischief"
        self.state_time = 0.0
        self.update()

    def launch_fireworks(self):
        """像素煙火發射小道具：綻放繽紛像素火花！"""
        cx = self.char_w / 2.0
        cy = self.char_h * 0.2
        colors = [
            QColor(255, 90, 120), QColor(255, 215, 0), QColor(80, 220, 255),
            QColor(160, 100, 255), QColor(100, 255, 140), QColor(255, 150, 50)
        ]
        for _ in range(24):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(40.0, 140.0)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed - 60.0  # 向上爆開
            col = random.choice(colors)
            self.particles.append(PixelParticle(cx, cy, vx, vy, col, life=random.uniform(0.7, 1.4)))
        self.update()
        log("PixelChibi", "發射慶祝像素煙火！")

    def _get_active_window_rect(self) -> QRect | None:
        """透過 Windows API 獲取當前前景活動視窗邊界。"""
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd or hwnd == int(self.winId()):
                return None
            rect = wintypes.RECT()
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 80 and h > 80:
                    return QRect(rect.left, rect.top, w, h)
        except Exception:
            pass
        return None

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.Antialiasing)

        # 1. 決定當前動畫幀名稱
        if self.state == "walk":
            frame_name = "walk1" if self.walk_phase < 1.0 else "walk2"
        elif self.state == "run":
            frame_name = "run1" if self.walk_phase < 1.0 else "run2"
        elif self.state in ("jump", "run_jump"):
            frame_name = "jump_up" if self.vel_y < 0 else "jump_down"
        elif self.state == "sit" or self.state == "bounce":
            frame_name = "sit"
        elif self.state == "sit_down":
            frame_name = "sit_down"
        elif self.state == "splat":
            frame_name = "splat"
        elif self.state in ("panic", "bowl_smash"):
            frame_name = "panic"
        elif self.state == "climb":
            frame_name = getattr(self, "climb_subframe", "climb_up")
        elif self.state in ("climb_up", "climb_down", "climb_side"):
            frame_name = self.state
        elif self.state == "sleep":
            frame_name = getattr(self, "sleep_subframe", "sleep_prone")
        elif self.state == "wake":
            frame_name = "wake_startle"
        elif self.state == "mischief":
            frame_name = "mischief"
        elif self.state in ("facing_front", "facing_back", "turn"):
            frame_name = self.state
        elif self.state == "flight":
            frame_name = "sit"
        else:
            frame_name = "idle"

        # 2. 獲取像素幀並繪製
        has_balloon = (self.state == "flight") or bool(self.cfg.get("q_flight_prop", False))
        pm = PixelChibiRenderer.get_pixmap(
            self.character,
            frame_name,
            facing_right=self.facing_right,
            scale=self.scale_factor,
            has_balloon=has_balloon,
            balloon_idx=self.balloon_idx,
        )
        p.drawPixmap(0, 0, pm)

        # 3. 繪製煙火像素粒子
        if self.particles:
            for pt in self.particles:
                alpha = max(0, int(255 * (1.0 - pt.age / pt.life)))
                c = QColor(pt.color)
                c.setAlpha(alpha)
                p.fillRect(int(pt.x), int(pt.y), 4, 4, c)

    def set_monitor(self, provider: str, key_index: int | None = None):
        """設定此 Q 版小人監控的 API 供應商與 Key，並啟動專屬想法框。"""
        from .balance import Ledger
        self.monitor_provider = provider
        self.monitor_key_index = key_index
        if self.ledger:
            self.ledger.poll.stop()
            self.ledger.sim.stop()
        self.ledger = Ledger(self.cfg, provider_override=provider, key_index=key_index)
        self.ledger.changed.connect(self._update_bubble_content)
        if self.thought_bubble is None:
            self.thought_bubble = ChibiThoughtBubble(self)
        self._update_bubble_content()
        self._update_thought_bubble_pos()
        self.thought_bubble.show()
        self.thought_bubble.raise_()

    def _update_bubble_content(self):
        if not self.thought_bubble or not self.ledger:
            return
        pname = self.ledger.provider_display_name
        bal_text = self.ledger.text
        self.thought_bubble.set_content(f"{pname} 額度", bal_text)

    def _update_thought_bubble_pos(self):
        if self.thought_bubble and self.thought_bubble.isVisible():
            bx = int(self.pos_x + (self.char_w - self.thought_bubble.width()) / 2)
            by = int(self.pos_y - self.thought_bubble.height() + 4)
            ag = self._screen_rect()
            if by < ag.top() + 4:
                by = int(self.pos_y + self.char_h + 4)
            self.thought_bubble.move(bx, by)
            self.thought_bubble.raise_()

    def moveEvent(self, e):
        super().moveEvent(e)
        self._update_thought_bubble_pos()

    def showEvent(self, e):
        super().showEvent(e)
        if self.thought_bubble and self.monitor_provider:
            self.thought_bubble.show()
            self._update_thought_bubble_pos()

    def hideEvent(self, e):
        super().hideEvent(e)
        if self.thought_bubble:
            self.thought_bubble.hide()

    def closeEvent(self, e):
        if self.thought_bubble:
            self.thought_bubble.close()
            self.thought_bubble.deleteLater()
            self.thought_bubble = None
        if self.ledger:
            self.ledger.poll.stop()
            self.ledger.sim.stop()
        super().closeEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.climbing_pet:
                # 在主寵身上：點擊切換坐姿與軟趴趴，若已軟趴趴則跳下回到地面
                if self.state == "sit":
                    self.state = "splat"
                    self.state_time = 0.0
                    self.update()
                else:
                    self.dismount_pet()
            elif self.cfg.get("q_fireworks_prop", False):
                self.launch_fireworks()
            else:
                if self.state == "walk":
                    self.state = "sit"
                elif self.state == "sit":
                    self.state = "splat"
                elif self.state == "splat":
                    self.state = "walk"
                else:
                    self.state = "walk"
                self.state_time = 0.0
                self.update()

    def contextMenuEvent(self, e):
        """右鍵點擊 Q 版小人時，提供解耦監控目標設定與巡邏選單。"""
        import sys
        if self.monitor_provider and self.ledger:
            m = QMenu()
            theme = self.cfg.get("theme", "light") if self.cfg else "light"
            from .app import get_menu_qss
            m.setStyleSheet(get_menu_qss(theme))
            m.setAttribute(Qt.WA_TranslucentBackground, True)
            m.setWindowFlags(m.windowFlags() | Qt.FramelessWindowHint)

            act_title = m.addAction(f"【{self.ledger.provider_display_name}】Q 版額度小人")
            act_title.setEnabled(False)
            m.addSeparator()

            # 1. 切換監控廠商
            m_prov = m.addMenu(f"切換監控廠商（目前：{self.ledger.provider_display_name}）")
            m_prov.setStyleSheet(m.styleSheet())
            m_prov.setAttribute(Qt.WA_TranslucentBackground, True)
            m_prov.setWindowFlags(m_prov.windowFlags() | Qt.FramelessWindowHint)
            from .balance import SUPPORTED_BALANCE_PROVIDERS
            for prov in SUPPORTED_BALANCE_PROVIDERS:
                pname = id_to_provider_name(prov)
                a = m_prov.addAction(pname)
                a.setCheckable(True)
                a.setChecked(provider_to_id(self.monitor_provider) == provider_to_id(prov))
                a.triggered.connect(lambda _=False, p=prov: self.set_monitor(p, self.monitor_key_index))

            # 2. 切換監控 API Key
            keys = self.cfg.get_api_keys(self.monitor_provider) if hasattr(self.cfg, "get_api_keys") else []
            m_keys = m.addMenu(f"切換監控 API Key（配置 {len(keys)} 組）")
            m_keys.setStyleSheet(m.styleSheet())
            m_keys.setAttribute(Qt.WA_TranslucentBackground, True)
            m_keys.setWindowFlags(m_keys.windowFlags() | Qt.FramelessWindowHint)

            a_all = m_keys.addAction("預設 / 全部 Key 輪替")
            a_all.setCheckable(True)
            a_all.setChecked(self.monitor_key_index is None)
            a_all.triggered.connect(lambda: self.set_monitor(self.monitor_provider, None))

            for kidx, k in enumerate(keys):
                masked = k[:6] + "..." + k[-4:] if len(k) > 12 else k
                label = f"Key #{kidx + 1} ({masked})"
                a_k = m_keys.addAction(label)
                a_k.setCheckable(True)
                a_k.setChecked(self.monitor_key_index == kidx)
                a_k.triggered.connect(lambda _=False, idx=kidx: self.set_monitor(self.monitor_provider, idx))

            # 3. 顯示/隱藏想法框
            if self.thought_bubble:
                is_vis = self.thought_bubble.isVisible()
                a_bubble = m.addAction("隱藏額度想法框" if is_vis else "顯示額度想法框")
                a_bubble.triggered.connect(lambda: self.thought_bubble.hide() if is_vis else (self.thought_bubble.show(), self._update_thought_bubble_pos()))

            # 4. 手動刷新餘額
            m.addAction("即時刷新此 API 餘額").triggered.connect(lambda: self.ledger.refresh())

            # 5. 移除此小人
            if self.app and hasattr(self.app, "chibi_manager") and self.app.chibi_manager:
                m.addAction("移除此額度監控小人").triggered.connect(lambda: self.app.chibi_manager.dismiss(self))

            m.addSeparator()
            m.addAction("開啟全部巡邏隊選單...").triggered.connect(lambda: self.app.pet_menu(e.globalPos()) if (self.app and hasattr(self.app, "pet_menu")) else None)

            if "--selftest" in sys.argv:
                QTimer.singleShot(10, m.close)
            QTimer.singleShot(0, lambda: m.exec(e.globalPos()))
            return

        # 預設行為
        if self.app and hasattr(self.app, "pet_menu"):
            self.app.pet_menu(e.globalPos())


class PixelChibiManager:
    """管理桌面上多隻 Q 版小人獨立巡邏、跳躍、攀爬與召喚巡邏隊。
    支援多小人數量限制檔位（5、10、15、20、25、30 隻），並根據效能模式自動調節上限。
    """
    def __init__(self, cfg, sounds, pet=None, app=None):
        self.cfg = cfg
        self.sounds = sounds
        self.pet = pet
        self.app = app
        self.chibis: list[PixelChibiWindow] = []
        if self.cfg.get("q_chibi_enabled", True):
            self.init_primary()

    @property
    def primary_chibi(self) -> PixelChibiWindow | None:
        """主要小人視窗（保持相容舊有 pixel_chibi 呼叫）。"""
        return self.chibis[0] if self.chibis else None

    @property
    def active_count(self) -> int:
        """當前在場巡邏的 Q 版小人數量。"""
        return len(self.chibis)

    @property
    def max_count(self) -> int:
        """當前生效之在場 Q 版小人上限（檔位 5, 10, 15, 20, 25, 30，效能模式最高限制 10）。"""
        return get_effective_chibi_max_count(self.cfg)

    @property
    def can_summon(self) -> bool:
        """在場數量是否未達上限，可繼續召喚。"""
        return self.active_count < self.max_count

    def init_primary(self) -> PixelChibiWindow:
        """初始化首隻主巡邏小人。"""
        if not self.chibis:
            w = PixelChibiWindow(self.cfg, self.sounds, pet=self.pet, app=self.app)
            self.chibis.append(w)
            if self.pet:
                self.pet.pixel_chibi = w
        return self.chibis[0]

    def summon(self, character_id: str | None = None, force: bool = False) -> PixelChibiWindow | None:
        """召喚一隻 Q 版人物降落到桌面上（若未強制且達上限則禁止召喚）。"""
        if not self.can_summon and not force:
            log("PixelChibiManager", f"在場 Q 版小人已達上限 ({self.active_count}/{self.max_count} 隻)，禁止繼續召喚！")
            return None

        all_ids = PixelChibiRegistry.list_all_ids()
        if not character_id or (character_id not in all_ids and character_id not in CHARACTER_INFO):
            character_id = random.choice(all_ids) if all_ids else "deepseek"

        w = PixelChibiWindow(self.cfg, self.sounds, pet=self.pet, app=self.app)
        w.set_character(character_id)

        # 隨機橫向位置與高空跳躍降落物理
        ag = w._screen_rect()
        w.pos_x = float(random.randint(ag.left() + 40, max(ag.left() + 50, ag.right() - w.char_w - 40)))
        w.pos_y = float(ag.top() + 30)
        w.vel_y = 100.0
        w.vel_x = random.choice([-30.0, 30.0, 0.0])
        w.state = "jump"
        w.facing_right = (random.random() > 0.5)
        w.move(int(w.pos_x), int(w.pos_y))
        w.show()
        w.raise_()

        self.chibis.append(w)
        if self.sounds:
            self.sounds.play("land")
        char_info = PixelChibiRegistry.get_character(character_id)
        name = char_info.get("name", character_id) if char_info else character_id
        log("PixelChibiManager", f"成功召喚 Q 版人物「{name}」降落巡邏！目前在場：{self.active_count}/{self.max_count} 隻")
        return w

    def summon_api_monitor(
        self,
        provider: str,
        key_index: int | None = None,
        character_id: str | None = None,
        force: bool = False,
    ) -> PixelChibiWindow | None:
        """召喚專屬 API 額度監控 Q 版小人（於桌面上巡邏、在想法框中顯示該 API 的額度/餘額）。"""
        if not self.can_summon and not force:
            log("PixelChibiManager", f"在場 Q 版小人已達上限 ({self.active_count}/{self.max_count} 隻)")
            return None

        if not character_id:
            pid = provider_to_id(provider)
            if pid in ("deepseek", "siliconflow", "glm", "ollama"):
                character_id = "deepseek"
            elif pid in ("openai", "groq", "grok", "cerebras", "custom_openai"):
                character_id = "gpt"
            elif pid in ("anthropic", "moonshot", "mistral", "deepinfra"):
                character_id = "claude"
            else:
                character_id = "gemini"

        w = self.summon(character_id, force=force)
        if w:
            w.set_monitor(provider, key_index)
            log("PixelChibiManager", f"成功召喚【{id_to_provider_name(provider)}】額度監控 Q 版小人！")
        return w

    def summon_random(self, force: bool = False) -> PixelChibiWindow | None:
        """從預設4隻 + 自訂角色庫隨機抽選一隻降落。"""
        all_ids = PixelChibiRegistry.list_all_ids()
        cid = random.choice(all_ids) if all_ids else "deepseek"
        return self.summon(cid, force=force)

    def dismiss(self, chibi: PixelChibiWindow):
        """移除指定的一隻 Q 版小人。"""
        if chibi in self.chibis:
            self.chibis.remove(chibi)
            if self.pet and getattr(self.pet, "pixel_chibi", None) == chibi:
                self.pet.pixel_chibi = self.primary_chibi
            if chibi.thought_bubble:
                chibi.thought_bubble.hide()
                chibi.thought_bubble.close()
                chibi.thought_bubble.deleteLater()
                chibi.thought_bubble = None
            chibi.hide()
            chibi.close()
            chibi.deleteLater()
            log("PixelChibiManager", f"已移除 Q 版小人，目前在場剩餘 {self.active_count} 隻")

    def clear_extra_chibis(self):
        """清除場上所有額外 Q 版小人（只保留 1 隻）。"""
        if len(self.chibis) <= 1:
            return
        main_chibi = self.chibis[0]
        extras = self.chibis[1:]
        self.chibis = [main_chibi]
        if self.pet and getattr(self.pet, "pixel_chibi", None) in extras:
            self.pet.pixel_chibi = main_chibi
        for c in extras:
            if c.thought_bubble:
                c.thought_bubble.hide()
                c.thought_bubble.close()
                c.thought_bubble.deleteLater()
                c.thought_bubble = None
            c.hide()
            c.close()
            c.deleteLater()
        log("PixelChibiManager", "已清除場上所有額外 Q 版小人，僅保留主要小人 1 隻。")

    def enforce_limit(self):
        """根據當前生效上限發出溫和提醒，絕不霸道阻斷或突兀刪除在場寵物。"""
        limit = self.max_count
        if len(self.chibis) > limit:
            log("PixelChibiManager", f"提示：目前在場 Q 版小人 ({len(self.chibis)} 隻) 超過當前上限檔位 ({limit} 隻)，建議收回部分小人以維持最佳系統效能。")

    def set_enabled(self, on: bool):
        """啟用或隱藏巡邏隊。"""
        if on:
            if not self.chibis:
                self.init_primary()
            for c in self.chibis:
                c.show()
                c.raise_()
        else:
            for c in self.chibis:
                c.hide()

    def set_opacity(self, val: int | float, save: bool = True):
        """設定 Q 版人物不透明度 (20..100) 並即時同步所有活躍小人。"""
        v = max(20, min(100, int(val)))
        self.cfg.set("q_chibi_opacity", v, save=save)
        self.sync_opacity(v)

    def sync_opacity(self, val: int | float | None = None):
        """同步場上所有活躍的 Q 版小人透明度。"""
        if val is None:
            val = self.cfg.get("q_chibi_opacity", 100)
        op = max(0.2, min(1.0, float(val) / 100.0))
        for c in self.chibis:
            c.setWindowOpacity(op)

    def sync_fps(self):
        """同步所有在場小人之 FPS 與定時器間隔。"""
        for c in self.chibis:
            c.sync_fps()

    def set_character(self, ch: str):
        """設定主要小人之角色形象。"""
        if self.primary_chibi:
            self.primary_chibi.set_character(ch)

    def __getattr__(self, name: str):
        """轉發主要小人屬性與方法以保持 100% 向後相容。"""
        if self.primary_chibi and hasattr(self.primary_chibi, name):
            return getattr(self.primary_chibi, name)
        raise AttributeError(f"'PixelChibiManager' object has no attribute '{name}'")

