"""Google Material Symbols vector icons utility.
Licensed under Apache License 2.0 (Google Material Symbols).
Renders crisp vector SVGs directly into QIcon and QPixmap at any DPI and color.
Strictly zero emojis used anywhere.
"""
from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# SVG templates for Google Material Symbols (Apache 2.0)
_SVGS: dict[str, str] = {
    # Send / Arrow Forward
    "send": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M647-440H160v-80h487L423-744l57-56 320 320-320 320-57-56 224-224Z"/>'
        '</svg>'
    ),
    # Microphone
    "mic": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M480-400q-50 0-85-35t-35-85v-240q0-50 35-85t85-35q50 0 85 35t35 85v240q0 50-35 85t-85 35Zm0-240Zm-40 520v-123q-104-14-172-93t-68-184h80q0 83 58.5 141.5T480-320q83 0 141.5-58.5T680-520h80q0 105-68 184t-172 93v123h-80Zm40-360q17 0 28.5-11.5T520-520v-240q0-17-11.5-28.5T480-800q-17 0-28.5 11.5T440-760v240q0 17 11.5 28.5T480-480Z"/>'
        '</svg>'
    ),
    # Microphone Muted
    "mic_off": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="m792-56-64-64H480v-123q104-14 172-93t68-184h-80q0 83-58.5 141.5T480-320q-37 0-70.5-13T351-370l-58-58q-9-22-13.5-45.5T275-520H195q0 105 68 184t172 93v123h-80v80h437ZM480-480Zm120-160v-80q0-50-35-85t-85-35q-50 0-85 35t-35 85v23L160-840l56-56 656 656-56 56-216-216Zm-80-80v-40q0-17-11.5-28.5T480-800q-17 0-28.5 11.5T440-760v120l80 80Z"/>'
        '</svg>'
    ),
    # Add (+)
    "add": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M440-440H200v-80h240v-240h80v240h240v80H520v240h-80v-240Z"/>'
        '</svg>'
    ),
    # Settings (Gear)
    "settings": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="m370-80-16-128q-13-5-24.5-12T307-235l-119 50L78-375l103-78q-1-7-1-13.5v-27q0-6.5 1-13.5L78-585l110-190 119 50q11-8 23-15t24-12l16-128h220l16 128q13 5 24.5 12t22.5 15l119-50 110 190-103 78q1 7 1 13.5v27q0 6.5-2 13.5l103 78-110 190-118-50q-11 8-23 15t-24 12L590-80H370Zm70-80h80l14-106q31-9 57.5-24.5T639-332l99 42 40-68-86-65q4-14 6-29.5t2-31.5q0-16-2-31.5t-6-29.5l86-65-40-68-99 42q-22-23-48.5-38.5T530-614l-14-106h-80l-14 106q-31 9-57.5 24.5T321-628l-99-42-40 68 86 65q-4 14-6 29.5t-2 31.5q0 16 2 31.5t6 29.5l-86 65 40 68 99-42q22 23 48.5 38.5T430-266l14 106Zm40-220q42 0 71-29t29-71q0-42-29-71t-71-29q-42 0-71 29t-29 71q0 42 29 71t71 29Z"/>'
        '</svg>'
    ),
    # Close (✕)
    "close": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="m256-200-56-56 224-224-224-224 56-56 224 224 224-224 56 56-224 224 224 224-56 56-224-224-224 224Z"/>'
        '</svg>'
    ),
    # Minimize (—)
    "minimize": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M200-440v-80h560v80H200Z"/>'
        '</svg>'
    ),
    # Shield (Security / Turbo)
    "shield": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="m480-80-35-18q-98-50-161.5-139T220-438v-282l260-97 260 97v282q0 112-63.5 201T515-98l-35 18Zm0-84q82-46 135-121.5T677-438v-223l-197-74-197 74v223q8 77 61 152.5T480-164Zm0-316Z"/>'
        '</svg>'
    ),
    # Bolt (Turbo / Speed)
    "bolt": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="m380-80 60-280H260l320-520-60 280h180L380-80Z"/>'
        '</svg>'
    ),
    # Refresh / Update
    "refresh": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M480-160q-134 0-227-93t-93-227q0-134 93-227t227-93q69 0 132 28.5T720-690v-110h80v280H520v-80h168q-32-56-87.5-88T480-720q-100 0-170 70t-70 170q0 100 70 170t170 70q77 0 139-44t87-116h84q-26 110-112.5 180T480-160Z"/>'
        '</svg>'
    ),
    # Open in New (External link)
    "open_in_new": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h280v80H200v560h560v-280h80v280q0 33-23.5 56.5T760-120H200Zm188-212-56-56 372-372H600v-80h240v240h-80v-104L388-332Z"/>'
        '</svg>'
    ),
    # Dropdown chevron down
    "arrow_drop_down": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M480-360 280-560h400L480-360Z"/>'
        '</svg>'
    ),
    # Dropdown chevron up
    "arrow_drop_up": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="m280-400 200-200 200 200H280Z"/>'
        '</svg>'
    ),
    # Folder Open
    "folder": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M160-160q-33 0-56.5-23.5T80-240v-480q0-33 23.5-56.5T160-800h240l80 80h320q33 0 56.5 23.5T880-640v400q0 33-23.5 56.5T800-160H160Zm0-80h640v-400H447l-80-80H160v480Zm0 0v-480 480Z"/>'
        '</svg>'
    ),
    # Font / Typography
    "font": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M420-160v-520H240v-80h480v80H540v520H420Z"/>'
        '</svg>'
    ),
    # Palette / Theme
    "palette": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="M480-80q-83 0-156-31.5T197-197q-54-54-85.5-127T80-480q0-83 31.5-156T197-763q54-54 127-85.5T480-880q83 0 156 31.5T763-763q54 54 85.5 127T880-480q0 86-40 137.5T740-291h-89q-17 0-28.5 11.5T611-251q0 9 5.5 18t5.5 18q0 35-23 57.5T543-135h-3q-15 0-30-7.5t-30-17.5l-40-40 56-56 34 34q3 3 5 4.5t5 1.5q5 0 8.5-3.5t3.5-8.5q0-18-9-33t-9-37q0-50 35-85t85-35h89q39 0 64.5-31t25.5-84q0-133-93.5-226.5T480-800q-133 0-226.5 93.5T160-480q0 133 93.5 226.5T480-160v80Zm-200-360q17 0 28.5-11.5T320-480q0-17-11.5-28.5T280-520q-17 0-28.5 11.5T240-480q0 17 11.5 28.5T280-440Zm120-160q17 0 28.5-11.5T440-640q0-17-11.5-28.5T400-680q-17 0-28.5 11.5T360-640q0 17 11.5 28.5T400-600Zm160 0q17 0 28.5-11.5T600-640q0-17-11.5-28.5T560-680q-17 0-28.5 11.5T520-640q0 17 11.5 28.5T560-600Zm120 160q17 0 28.5-11.5T720-480q0-17-11.5-28.5T680-520q-17 0-28.5 11.5T640-480q0 17 11.5 28.5T680-440Z"/>'
        '</svg>'
    ),
    # GitHub / Code
    "code": (
        '<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
        '<path fill="{color}" d="m384-336 56-57-87-87 87-87-56-57-144 144 144 144Zm192 0 144-144-144-144-56 57 87 87-87 87 56 57ZM200-120q-33 0-56.5-23.5T120-200v-560q0-33 23.5-56.5T200-840h560q33 0 56.5 23.5T840-760v560q0 33-23.5 56.5T760-120H200Z"/>'
        '</svg>'
    ),
}

_CACHE: dict[tuple[str, str, int], QIcon] = {}


def get_icon(name: str, color: str = "#ffffff", size: int = 24) -> QIcon:
    """Return a QIcon for the given Material Symbol name, color, and size."""
    key = (name, color, size)
    if key in _CACHE:
        return _CACHE[key]

    template = _SVGS.get(name)
    if not template:
        # Fallback to a clean circle or square
        template = (
            f'<svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24">'
            f'<circle cx="480" cy="-480" r="300" fill="{color}"/>'
            f'</svg>'
        )

    svg_data = template.replace("{color}", color)
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    icon = QIcon(pixmap)
    _CACHE[key] = icon
    return icon


def get_pixmap(name: str, color: str = "#ffffff", size: int = 24) -> QPixmap:
    """Return a QPixmap for the given Material Symbol name, color, and size."""
    icon = get_icon(name, color, size)
    return icon.pixmap(size, size)
