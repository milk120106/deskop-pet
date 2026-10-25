"""Brand-new standalone Q-Chibi pixel patrol system.
Features 4 heroine styles (DeepSeek whale, Claude spark, GPT tech, Gemini cat)
with full bodies, two cute legs/feet, pure-code 2D pixel matrices, nearest-neighbor
crisp rendering, dynamic Delta-Time physics and FPS scheduling (10-240 FPS / unlimited),
comprehensive animation frames (climb, splat, sleep, wake, run, jump, mischief),
main pet head/back/iron bowl mounting, bowl smash knock-back physics,
and bamboo copter / pixel fireworks props. Strictly zero emojis.
"""
from __future__ import annotations

import math
import random
import time
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from .config import log


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
        "...LL......LL...",
        "...LL......LL...",
        "...LL......LL...",
        "..WW........WW..",
        "..WW........WW..",
        ".FFF........FFF.",
        ".fff........fff.",
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
        "....LL....LL....",
        "....LL....LL....",
        "...LL......LL...",
        "...WW......WW...",
        "...WW......WW...",
        "..FFF......FFF..",
        "..fff......fff..",
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
        "...LL......LL...",
        "..LL........LL..",
        "..LL........LL..",
        ".WW..........WW.",
        ".WW..........WW.",
        "FFF..........FFF",
        "fff..........fff",
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
        "....LL....LL....",
        "...LL......LL...",
        "..LL........LL..",
        ".WW..........WW.",
        "FFF..........WW.",
        "fff.........FFF.",
        "............fff.",
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


class PixelChibiRenderer:
    """純代碼 2D 像素陣列與色盤精確繪製器，最近鄰無失真放大。"""
    _cache: dict[tuple, QPixmap] = {}

    @classmethod
    def get_pixmap(cls, character: str, frame_name: str, facing_right: bool = False, scale: int = 3, has_balloon: bool = False, balloon_idx: int = 0) -> QPixmap:
        char_key = character.lower()
        if char_key not in CHAR_PALETTES:
            char_key = "deepseek"
        cache_key = (char_key, frame_name, facing_right, scale, has_balloon, balloon_idx)
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        palette = CHAR_PALETTES[char_key]
        raw_rows = FRAMES.get(frame_name, FRAMES["idle"])
        w, h = 16, 24
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)

        for y, row_str in enumerate(raw_rows):
            for x, ch in enumerate(row_str):
                if ch == "." or ch not in palette:
                    continue
                color_hex = palette[ch]
                img.setPixelColor(x, y, QColor(color_hex))

        # 疊加小氣球漂浮道具
        if has_balloon:
            b_rows = BALLOON_FRAMES[balloon_idx % len(BALLOON_FRAMES)]
            for by, brow in enumerate(b_rows):
                for bx, bch in enumerate(brow):
                    if bch in palette:
                        img.setPixelColor(bx, by, QColor(palette[bch]))

        if facing_right:
            img = img.mirrored(True, False)

        # 最近鄰取樣放大 (Qt.FastTransformation) 確保 100% 俐落像素邊緣
        target_w = w * scale
        target_h = h * scale
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

        if self.pet:
            self.pet.pixel_chibi = self

        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setMouseTracking(True)
        self.setWindowTitle("Pixel Chibi Patrol")

        self.scale_factor = 3  # 16x24 -> 48x72 px
        self.char_w = 16 * self.scale_factor
        self.char_h = 24 * self.scale_factor
        self.setFixedSize(self.char_w, self.char_h)

        # 狀態機
        self.character = cfg.get("character", "deepseek")
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
        if self.pet:
            self.pet.pixel_chibi = self

    def set_character(self, ch: str):
        self.character = ch
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
