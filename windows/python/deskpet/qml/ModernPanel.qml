import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 840
    height: 620
    radius: 16
    clip: true
    color: themeColors.bg
    border.width: 1
    border.color: themeColors.border

    property string modernFontStack: '"Segoe UI Variable Text", "Microsoft JhengHei UI", "PingFang TC", "Noto Sans TC", sans-serif'
    property int currentTab: 0

    // 監聽後端分頁切換指令
    Connections {
        target: (typeof backend !== "undefined" && backend) ? backend : null
        function onTabSwitched(tab) {
            root.currentTab = Math.max(0, Math.min(4, tab))
        }
        function onNoticeMessage(msg, isErr) {
            toastNotice.show(msg, isErr)
        }
    }

    // ========================================================= 現代主題調色盤（平滑動態過渡）
    QtObject {
        id: themeColors
        property string currentTheme: (typeof backend !== "undefined" && backend) ? backend.theme : "light"
        property color bg: currentTheme === "dark" ? "#10141D" : "#F8FAFC"
        property color surface: currentTheme === "dark" ? "#181D29" : "#FFFFFF"
        property color surfaceHover: currentTheme === "dark" ? "#222938" : "#F1F5F9"
        property color surfaceVariant: currentTheme === "dark" ? "#232A3B" : "#EDF2F7"
        property color border: currentTheme === "dark" ? "#2E3748" : "#E2E8F0"
        property color text: currentTheme === "dark" ? "#F8FAFC" : "#0F172A"
        property color textSub: currentTheme === "dark" ? "#94A3B8" : "#64748B"
        property color primary: currentTheme === "dark" ? "#3B82F6" : "#2563EB"
        property color primaryHover: currentTheme === "dark" ? "#60A5FA" : "#1D4ED8"
        property color primaryContainer: currentTheme === "dark" ? "#1E293B" : "#DBEAFE"
        property color primaryText: currentTheme === "dark" ? "#93C5FD" : "#1D4ED8"
        property color accent: "#10B981"
        property color danger: "#EF4444"

        Behavior on bg { ColorAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on surface { ColorAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on surfaceHover { ColorAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on surfaceVariant { ColorAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on border { ColorAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on text { ColorAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on textSub { ColorAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on primary { ColorAnimation { duration: 250; easing.type: Easing.OutCubic } }
        Behavior on primaryContainer { ColorAnimation { duration: 250; easing.type: Easing.OutCubic } }
    }

    // ========================================================= 標題列（無多餘怪異橢圓，優雅設定標題與向量 Icon 主題切換）
    Rectangle {
        id: titleBar
        width: parent.width
        height: 52
        color: themeColors.surface
        border.width: 1
        border.color: themeColors.border

        // 視窗拖曳感應區
        MouseArea {
            anchors.fill: parent
            anchors.rightMargin: titleActions.width + 12
            property point pressPos: Qt.point(0, 0)
            onPressed: (mouse) => {
                var p = mapToGlobal(mouse.x, mouse.y)
                pressPos = p
                if (typeof backend !== "undefined" && backend) {
                    backend.startWindowDrag(p.x, p.y)
                }
            }
            onPositionChanged: (mouse) => {
                var p = mapToGlobal(mouse.x, mouse.y)
                if (typeof backend !== "undefined" && backend) {
                    backend.dragWindowMove(p.x, p.y)
                }
            }
        }

        // 左側標題：乾淨優雅的「設定」文字標題與小版本標籤（完全移除舊有怪異藍色橢圓）
        Row {
            anchors.left: parent.left
            anchors.leftMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            Text {
                text: "設定"
                color: themeColors.text
                font.pixelSize: 16
                font.bold: true
                font.family: root.modernFontStack
                renderType: Text.NativeRendering
                anchors.verticalCenter: parent.verticalCenter
            }

            Rectangle {
                height: 22
                width: badgeText.width + 14
                radius: 11
                color: themeColors.primaryContainer
                anchors.verticalCenter: parent.verticalCenter

                Text {
                    id: badgeText
                    anchors.centerIn: parent
                    text: (typeof backend !== "undefined" && backend) ? backend.appVersion : "v2.1.0"
                    color: themeColors.primaryText
                    font.pixelSize: 11
                    font.bold: true
                    font.family: root.modernFontStack
                    renderType: Text.NativeRendering
                }
            }
        }

        // 右側動作按鈕群
        Row {
            id: titleActions
            anchors.right: parent.right
            anchors.rightMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 8

            // 主題切換按鈕：向量 Icon 化（深色顯示太陽 SVG，淺色顯示月亮 SVG，附帶平滑旋轉與過渡動效）
            Rectangle {
                id: btnTheme
                width: 36
                height: 32
                radius: 8
                color: mouseTheme.containsMouse ? themeColors.surfaceHover : "transparent"
                border.width: 1
                border.color: mouseTheme.containsMouse ? themeColors.border : "transparent"
                scale: mouseTheme.pressed ? 0.92 : (mouseTheme.containsMouse ? 1.05 : 1.0)
                Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.28 } }

                Image {
                    id: themeIcon
                    anchors.centerIn: parent
                    width: 20
                    height: 20
                    sourceSize: Qt.size(20, 20)
                    source: themeColors.currentTheme === "dark" ? "../../assets/sun.svg" : "../../assets/moon.svg"
                    rotation: mouseTheme.containsMouse ? 25 : 0
                    Behavior on rotation { NumberAnimation { duration: 250; easing.type: Easing.OutCubic } }
                }

                MouseArea {
                    id: mouseTheme
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (typeof backend !== "undefined" && backend) {
                            backend.toggleTheme()
                        }
                    }
                }
            }

            // 最小化按鈕
            Rectangle {
                id: btnMin
                width: 34
                height: 32
                radius: 8
                color: mouseMin.containsMouse ? themeColors.surfaceHover : "transparent"
                scale: mouseMin.pressed ? 0.92 : 1.0
                Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.28 } }

                Text {
                    anchors.centerIn: parent
                    text: "—"
                    color: themeColors.text
                    font.pixelSize: 13
                    font.bold: true
                    font.family: root.modernFontStack
                    renderType: Text.NativeRendering
                }
                MouseArea {
                    id: mouseMin
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (typeof backend !== "undefined" && backend) {
                            backend.minimizeWindow()
                        }
                    }
                }
            }

            // 關閉按鈕
            Rectangle {
                id: btnClose
                width: 34
                height: 32
                radius: 8
                color: mouseClose.containsMouse ? themeColors.danger : "transparent"
                scale: mouseClose.pressed ? 0.92 : 1.0
                Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.28 } }

                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: mouseClose.containsMouse ? "#FFFFFF" : themeColors.text
                    font.pixelSize: 13
                    font.bold: true
                    font.family: root.modernFontStack
                    renderType: Text.NativeRendering
                }
                MouseArea {
                    id: mouseClose
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (typeof backend !== "undefined" && backend) {
                            backend.closeWindow()
                        }
                    }
                }
            }
        }
    }

    // ========================================================= 現代流體導航分頁列（5 大分頁整合）
    Rectangle {
        id: navBar
        anchors.top: titleBar.bottom
        anchors.topMargin: 12
        anchors.left: parent.left
        anchors.leftMargin: 18
        anchors.right: parent.right
        anchors.rightMargin: 18
        height: 44
        radius: 12
        color: themeColors.surfaceVariant

        // 彈性滑動選取指示膠囊
        Rectangle {
            id: navIndicator
            height: parent.height - 8
            y: 4
            radius: 9
            color: themeColors.surface
            border.width: 1
            border.color: themeColors.border

            x: {
                var item = navRow.children[root.currentTab]
                return item ? item.x + 4 : 4
            }
            width: {
                var item = navRow.children[root.currentTab]
                return item ? item.width - 8 : 100
            }

            Behavior on x { SpringAnimation { spring: 3.5; damping: 0.28 } }
            Behavior on width { SpringAnimation { spring: 3.5; damping: 0.28 } }
        }

        Row {
            id: navRow
            anchors.fill: parent

            Repeater {
                model: ["外觀與角色", "音效與自訂", "AI 與 API 金鑰", "字體設定", "關於與日誌"]
                delegate: Rectangle {
                    width: navBar.width / 5
                    height: navBar.height
                    color: "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: modelData
                        color: root.currentTab === index ? themeColors.primary : themeColors.textSub
                        font.pixelSize: 13
                        font.bold: root.currentTab === index
                        font.family: root.modernFontStack
                        renderType: Text.NativeRendering
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            root.currentTab = index
                        }
                    }
                }
            }
        }
    }

    // ========================================================= 浮動提示訊息橫幅 (Toast Notice)
    Rectangle {
        id: toastNotice
        anchors.top: navBar.bottom
        anchors.topMargin: 6
        anchors.horizontalCenter: parent.horizontalCenter
        height: 32
        radius: 8
        z: 99
        visible: opacity > 0
        opacity: 0.0
        color: isError ? "#EF4444" : "#10B981"
        border.width: 1
        border.color: "#FFFFFF"
        property bool isError: false
        property string msg: ""
        width: Math.min(root.width - 60, toastTxt.paintedWidth + 32)
        Behavior on opacity { NumberAnimation { duration: 200 } }

        Text {
            id: toastTxt
            anchors.centerIn: parent
            text: toastNotice.msg
            color: "#FFFFFF"
            font.pixelSize: 12
            font.bold: true
            font.family: root.modernFontStack
            renderType: Text.NativeRendering
        }

        Timer {
            id: toastTimer
            interval: 3200
            onTriggered: toastNotice.opacity = 0.0
        }

        function show(text, isErr) {
            msg = text
            isError = isErr
            opacity = 0.95
            toastTimer.restart()
        }
    }

    // ========================================================= 內容容器（5 大完整分頁）
    Item {
        id: contentContainer
        anchors.top: navBar.bottom
        anchors.topMargin: 12
        anchors.left: parent.left
        anchors.leftMargin: 18
        anchors.right: parent.right
        anchors.rightMargin: 18
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 14
        clip: true

        // ===================================================== 分頁 1【外觀與角色】
        Flickable {
            id: viewTab0
            anchors.fill: parent
            contentHeight: colTab0.height + 24
            clip: true
            opacity: root.currentTab === 0 ? 1.0 : 0.0
            visible: opacity > 0
            y: root.currentTab === 0 ? 0 : 8
            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

            Column {
                id: colTab0
                width: parent.width
                spacing: 14

                // 卡片 1: 角色形象選擇
                Rectangle {
                    width: parent.width
                    height: 146
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "角色形象選擇"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Row {
                            width: parent.width
                            spacing: 12

                            Repeater {
                                model: [
                                    { id: "deepseek", name: "藍色大肥魚", badge: "DeepSeek 鯨魚娘" },
                                    { id: "gpt", name: "GPT龍娘", badge: "OpenAI 龍娘" },
                                    { id: "claude", name: "大小姐Claude", badge: "Anthropic 大小姐" },
                                    { id: "gemini", name: "北美貓娘Gemini", badge: "Google 北美貓娘" }
                                ]
                                delegate: Rectangle {
                                    width: (colTab0.width - 32 - 36) / 4
                                    height: 72
                                    radius: 12
                                    color: (typeof backend !== "undefined" && backend && backend.character === modelData.id) ? themeColors.primaryContainer : (charMouse.containsMouse ? themeColors.surfaceHover : themeColors.surfaceVariant)
                                    border.width: (typeof backend !== "undefined" && backend && backend.character === modelData.id) ? 2 : 1
                                    border.color: (typeof backend !== "undefined" && backend && backend.character === modelData.id) ? themeColors.primary : themeColors.border

                                    scale: charMouse.pressed ? 0.94 : (charMouse.containsMouse ? 1.02 : 1.0)
                                    Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.28 } }

                                    Column {
                                        anchors.centerIn: parent
                                        spacing: 4
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: modelData.name
                                            color: (typeof backend !== "undefined" && backend && backend.character === modelData.id) ? themeColors.primary : themeColors.text
                                            font.pixelSize: 13
                                            font.bold: true
                                            font.family: root.modernFontStack
                                            renderType: Text.NativeRendering
                                        }
                                        Text {
                                            anchors.horizontalCenter: parent.horizontalCenter
                                            text: modelData.badge
                                            color: themeColors.textSub
                                            font.pixelSize: 11
                                            font.family: root.modernFontStack
                                            renderType: Text.NativeRendering
                                        }
                                    }

                                    MouseArea {
                                        id: charMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof backend !== "undefined" && backend) {
                                                backend.setCharacter(modelData.id)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 2: 形態切換與自訂角色匯入
                Rectangle {
                    width: parent.width
                    height: 118
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "寵物立繪形態與自訂角色"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Row {
                            width: parent.width
                            spacing: 14

                            // 正方形 (1:1) 按鈕
                            Rectangle {
                                width: 175
                                height: 38
                                radius: 10
                                color: (typeof backend !== "undefined" && backend && backend.variant === "square") ? themeColors.primaryContainer : (mSquare.containsMouse ? themeColors.surfaceHover : themeColors.surfaceVariant)
                                border.width: (typeof backend !== "undefined" && backend && backend.variant === "square") ? 2 : 1
                                border.color: (typeof backend !== "undefined" && backend && backend.variant === "square") ? themeColors.primary : themeColors.border

                                Text {
                                    anchors.centerIn: parent
                                    text: "正方形 (1:1)"
                                    color: (typeof backend !== "undefined" && backend && backend.variant === "square") ? themeColors.primary : themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    id: mSquare
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setVariant("square")
                                        }
                                    }
                                }
                            }

                            // 帶尾巴 (1.5:1) 按鈕
                            Rectangle {
                                width: 175
                                height: 38
                                radius: 10
                                color: (typeof backend !== "undefined" && backend && backend.variant === "tail") ? themeColors.primaryContainer : (mTail.containsMouse ? themeColors.surfaceHover : themeColors.surfaceVariant)
                                border.width: (typeof backend !== "undefined" && backend && backend.variant === "tail") ? 2 : 1
                                border.color: (typeof backend !== "undefined" && backend && backend.variant === "tail") ? themeColors.primary : themeColors.border

                                Text {
                                    anchors.centerIn: parent
                                    text: "帶尾巴 (1.5:1)"
                                    color: (typeof backend !== "undefined" && backend && backend.variant === "tail") ? themeColors.primary : themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    id: mTail
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setVariant("tail")
                                        }
                                    }
                                }
                            }

                            Item { width: 10; height: 1 }

                            // 匯入自訂角色按鈕
                            Rectangle {
                                width: 190
                                height: 38
                                radius: 10
                                color: themeColors.primary
                                scale: mImportChar.pressed ? 0.94 : (mImportChar.containsMouse ? 1.02 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.28 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: "匯入自訂角色..."
                                    color: "#FFFFFF"
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    id: mImportChar
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.importCustomCharacter()
                                        }
                                    }
                                }
                            }
                        }

                        // 項目: 嚴格限制自訂立繪比例（1:1 或 1.5:1）開關
                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "嚴格限制自訂立繪比例（1:1 或 1.5:1）"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Text {
                                text: "（關閉後可匯入任意超長或超扁圖片，照原始比例趣味呈現）"
                                color: themeColors.textSub
                                font.pixelSize: 11
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Item { width: Math.max(10, parent.width - 550); height: 1 }

                            Rectangle {
                                width: 48
                                height: 26
                                radius: 13
                                color: (typeof backend !== "undefined" && backend && backend.strictCustomImageRatio) ? themeColors.primary : themeColors.border
                                Behavior on color { ColorAnimation { duration: 180 } }

                                Rectangle {
                                    width: 20
                                    height: 20
                                    radius: 10
                                    y: 3
                                    color: "#FFFFFF"
                                    x: (typeof backend !== "undefined" && backend && backend.strictCustomImageRatio) ? 25 : 3
                                    Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setStrictCustomImageRatio(!backend.strictCustomImageRatio)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 3: 寵物尺寸與不透明度 (支援 80px - 1024px 平滑滑桿與極小尺寸像素 Q 版)
                Rectangle {
                    width: parent.width
                    height: colCard3.implicitHeight + 32
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        id: colCard3
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "寵物尺寸與不透明度"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        // 1. 平滑尺寸滑桿 (80px - 1024px)
                        Row {
                            width: parent.width
                            spacing: 14

                            Text {
                                text: "寵物尺寸：" + ((typeof backend !== "undefined" && backend) ? backend.sizePx : 454) + " px"
                                color: themeColors.textSub
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 110
                            }

                            Item {
                                width: 340
                                height: 32
                                anchors.verticalCenter: parent.verticalCenter

                                Rectangle {
                                    id: sizeTrack
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width
                                    height: 8
                                    radius: 4
                                    color: themeColors.surfaceVariant

                                    Rectangle {
                                        height: parent.height
                                        radius: 4
                                        color: themeColors.primary
                                        width: {
                                            var val = (typeof backend !== "undefined" && backend) ? backend.sizePx : 454
                                            return Math.max(0, Math.min(parent.width, (val - 180) / (1024 - 180) * parent.width))
                                        }
                                    }
                                }

                                Rectangle {
                                    id: sizeThumb
                                    width: 18
                                    height: 18
                                    radius: 9
                                    color: themeColors.primary
                                    border.width: 2
                                    border.color: "#FFFFFF"
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: {
                                        var val = (typeof backend !== "undefined" && backend) ? backend.sizePx : 454
                                        return Math.max(0, Math.min(sizeTrack.width - width, (val - 180) / (1024 - 180) * (sizeTrack.width - width)))
                                    }
                                    scale: sizeSliderMouse.pressed ? 1.25 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.28 } }
                                }

                                MouseArea {
                                    id: sizeSliderMouse
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    preventStealing: true
                                    function updatePos(mx) {
                                        var frac = Math.max(0.0, Math.min(1.0, mx / width))
                                        var val = Math.round(180 + frac * (1024 - 180))
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setSizePx(val)
                                        }
                                    }
                                    onPressed: (mouse) => updatePos(mouse.x)
                                    onPositionChanged: (mouse) => {
                                        if (pressed) updatePos(mouse.x)
                                    }
                                }
                            }
                        }

                        // 2. 快速尺寸標籤（精巧 180px、便攜 260px、標準 340px、大杯 454px、特大 640px、巨幕 800px）
                        Row {
                            width: parent.width
                            spacing: 8

                            Repeater {
                                model: [
                                    { size: 180, name: "精巧 180px" },
                                    { size: 260, name: "便攜 260px" },
                                    { size: 340, name: "標準 340px" },
                                    { size: 454, name: "大杯 454px" },
                                    { size: 640, name: "特大 640px" },
                                    { size: 800, name: "巨幕 800px" }
                                ]
                                delegate: Rectangle {
                                    width: (parent.width - 40) / 6
                                    height: 30
                                    radius: 8
                                    color: (typeof backend !== "undefined" && backend && backend.sizePx === modelData.size) ? themeColors.primaryContainer : (presetMouse.containsMouse ? themeColors.surfaceHover : themeColors.surfaceVariant)
                                    border.width: (typeof backend !== "undefined" && backend && backend.sizePx === modelData.size) ? 2 : 1
                                    border.color: (typeof backend !== "undefined" && backend && backend.sizePx === modelData.size) ? themeColors.primary : themeColors.border

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.name
                                        color: (typeof backend !== "undefined" && backend && backend.sizePx === modelData.size) ? themeColors.primary : themeColors.text
                                        font.pixelSize: 11
                                        font.bold: true
                                        font.family: root.modernFontStack
                                        renderType: Text.NativeRendering
                                    }

                                    MouseArea {
                                        id: presetMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof backend !== "undefined" && backend) {
                                                backend.setSizePx(modelData.size)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // 4. 不透明度滑桿
                        Row {
                            width: parent.width
                            spacing: 14

                            Text {
                                text: "不透明度：" + ((typeof backend !== "undefined" && backend) ? backend.opacityVal : 100) + "%"
                                color: themeColors.textSub
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 110
                            }

                            Item {
                                width: 340
                                height: 32
                                anchors.verticalCenter: parent.verticalCenter

                                Rectangle {
                                    id: opTrack
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width
                                    height: 8
                                    radius: 4
                                    color: themeColors.surfaceVariant

                                    Rectangle {
                                        height: parent.height
                                        radius: 4
                                        color: themeColors.primary
                                        width: {
                                            var val = (typeof backend !== "undefined" && backend) ? backend.opacityVal : 100
                                            return Math.max(0, Math.min(parent.width, (val - 20) / 80 * parent.width))
                                        }
                                    }
                                }

                                Rectangle {
                                    id: opThumb
                                    width: 18
                                    height: 18
                                    radius: 9
                                    color: themeColors.primary
                                    border.width: 2
                                    border.color: "#FFFFFF"
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: {
                                        var val = (typeof backend !== "undefined" && backend) ? backend.opacityVal : 100
                                        return Math.max(0, Math.min(opTrack.width - width, (val - 20) / 80 * (opTrack.width - width)))
                                    }
                                    scale: opMouse.pressed ? 1.25 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.28 } }
                                }

                                MouseArea {
                                    id: opMouse
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    preventStealing: true
                                    function updatePos(mx) {
                                        var frac = Math.max(0.0, Math.min(1.0, mx / width))
                                        var val = Math.round(20 + frac * 80)
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setOpacityVal(val)
                                        }
                                    }
                                    onPressed: (mouse) => updatePos(mouse.x)
                                    onPositionChanged: (mouse) => {
                                        if (pressed) updatePos(mouse.x)
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 4: 視窗互動行為（滑鼠穿透、自動貼邊、總在最上層）
                Rectangle {
                    width: parent.width
                    height: 180
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "視窗互動行為"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        // 項目 1: 滑鼠穿透
                        Row {
                            width: parent.width
                            spacing: 12
                            Text {
                                text: "滑鼠穿透（點擊直達桌面底層）"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 340
                            }
                            Item {
                                width: 48
                                height: 26
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 13
                                    color: (typeof backend !== "undefined" && backend && backend.clickThrough) ? themeColors.primary : themeColors.surfaceVariant
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Rectangle {
                                        width: 20
                                        height: 20
                                        radius: 10
                                        y: 3
                                        color: "#FFFFFF"
                                        x: (typeof backend !== "undefined" && backend && backend.clickThrough) ? 25 : 3
                                        Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setClickThrough(!backend.clickThrough)
                                        }
                                    }
                                }
                            }
                        }

                        // 項目 2: 自動貼邊
                        Row {
                            width: parent.width
                            spacing: 12
                            Text {
                                text: "自動貼邊（靠近螢幕邊緣平滑吸附與轉向）"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 340
                            }
                            Item {
                                width: 48
                                height: 26
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 13
                                    color: (typeof backend !== "undefined" && backend && backend.autoSnap) ? themeColors.primary : themeColors.surfaceVariant
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Rectangle {
                                        width: 20
                                        height: 20
                                        radius: 10
                                        y: 3
                                        color: "#FFFFFF"
                                        x: (typeof backend !== "undefined" && backend && backend.autoSnap) ? 25 : 3
                                        Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setAutoSnap(!backend.autoSnap)
                                        }
                                    }
                                }
                            }
                        }

                        // 項目 3: 總在最上層
                        Row {
                            width: parent.width
                            spacing: 12
                            Text {
                                text: "總在最上層（視窗保持前端顯示）"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 340
                            }
                            Item {
                                width: 48
                                height: 26
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 13
                                    color: (typeof backend !== "undefined" && backend && backend.alwaysOnTop) ? themeColors.primary : themeColors.surfaceVariant
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Rectangle {
                                        width: 20
                                        height: 20
                                        radius: 10
                                        y: 3
                                        color: "#FFFFFF"
                                        x: (typeof backend !== "undefined" && backend && backend.alwaysOnTop) ? 25 : 3
                                        Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setAlwaysOnTop(!backend.alwaysOnTop)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 5: 全新 Q 版人物獨立像素系統 (帶雙腿、風格嚴格對齊四位娘化主角)
                Rectangle {
                    width: parent.width
                    height: colCard5.implicitHeight + 32
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        id: colCard5
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "全新 Q 版人物獨立像素系統"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        // 項目 1: 啟用 Q 版小人桌面巡邏
                        Row {
                            width: parent.width
                            spacing: 12
                            Text {
                                text: "啟用 Q 版小人桌面巡邏（全身雙腿雙腳、圖層置頂）"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 340
                            }
                            Item {
                                width: 48
                                height: 26
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 13
                                    color: (typeof backend !== "undefined" && backend && backend.qChibiEnabled) ? themeColors.primary : themeColors.surfaceVariant
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Rectangle {
                                        width: 20
                                        height: 20
                                        radius: 10
                                        y: 3
                                        color: "#FFFFFF"
                                        x: (typeof backend !== "undefined" && backend && backend.qChibiEnabled) ? 25 : 3
                                        Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setQChibiEnabled(!backend.qChibiEnabled)
                                        }
                                    }
                                }
                            }
                        }

                        // 項目 2: 視窗與按鈕攀爬辨識 (預設關閉)
                        Row {
                            width: parent.width
                            spacing: 12
                            Text {
                                text: "視窗與按鈕攀爬辨識（視窗消失失足慌張掉落）"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 340
                            }
                            Item {
                                width: 48
                                height: 26
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 13
                                    color: (typeof backend !== "undefined" && backend && backend.qClimbWindows) ? themeColors.primary : themeColors.surfaceVariant
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Rectangle {
                                        width: 20
                                        height: 20
                                        radius: 10
                                        y: 3
                                        color: "#FFFFFF"
                                        x: (typeof backend !== "undefined" && backend && backend.qClimbWindows) ? 25 : 3
                                        Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setQClimbWindows(!backend.qClimbWindows)
                                        }
                                    }
                                }
                            }
                        }

                        // 項目 3: 小氣球飛行道具 (預設關閉)
                        Row {
                            width: parent.width
                            spacing: 12
                            Text {
                                text: "趣味飛行小道具（小氣球空中漂浮模式）"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 340
                            }
                            Item {
                                width: 48
                                height: 26
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 13
                                    color: (typeof backend !== "undefined" && backend && backend.qFlightProp) ? themeColors.primary : themeColors.surfaceVariant
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Rectangle {
                                        width: 20
                                        height: 20
                                        radius: 10
                                        y: 3
                                        color: "#FFFFFF"
                                        x: (typeof backend !== "undefined" && backend && backend.qFlightProp) ? 25 : 3
                                        Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setQFlightProp(!backend.qFlightProp)
                                        }
                                    }
                                }
                            }
                        }

                        // 項目 4: 像素煙火發射小道具 (預設關閉)
                        Row {
                            width: parent.width
                            spacing: 12
                            Text {
                                text: "像素煙火發射小道具（鬧鐘響鈴或手動觸發慶祝）"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 340
                            }
                            Item {
                                width: 48
                                height: 26
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 13
                                    color: (typeof backend !== "undefined" && backend && backend.qFireworksProp) ? themeColors.primary : themeColors.surfaceVariant
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Rectangle {
                                        width: 20
                                        height: 20
                                        radius: 10
                                        y: 3
                                        color: "#FFFFFF"
                                        x: (typeof backend !== "undefined" && backend && backend.qFireworksProp) ? 25 : 3
                                        Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setQFireworksProp(!backend.qFireworksProp)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 6: 鬧鐘與多管道通知轉發系統 (Windows Toast / Discord / Telegram)
                Rectangle {
                    width: parent.width
                    height: colCard6.implicitHeight + 32
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        id: colCard6
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "鬧鐘與事件通知系統"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Text {
                            text: "支援定時鬧鐘、倒數計時、平板呼吸閃爍與 Windows Toast / Discord / Telegram Webhook 同步轉發"
                            color: themeColors.textSub
                            font.pixelSize: 12
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                            wrapMode: Text.WordWrap
                            width: parent.width
                        }

                        Row {
                            spacing: 10

                            Rectangle {
                                width: 130
                                height: 32
                                radius: 8
                                color: timerBtn5Mouse.containsMouse ? themeColors.surfaceHover : themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border

                                Text {
                                    anchors.centerIn: parent
                                    text: "+5 分鐘快速計時"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                }

                                MouseArea {
                                    id: timerBtn5Mouse
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.addAlarm("5分鐘提醒", "", "timer", 300)
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 130
                                height: 32
                                radius: 8
                                color: timerBtn25Mouse.containsMouse ? themeColors.surfaceHover : themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border

                                Text {
                                    anchors.centerIn: parent
                                    text: "+25 分鐘番茄鐘"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                }

                                MouseArea {
                                    id: timerBtn25Mouse
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.addAlarm("番茄工作鐘", "", "timer", 1500)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ===================================================== 分頁 2【音效與自訂】
        Flickable {
            id: viewTab1
            anchors.fill: parent
            contentHeight: colTab1.height + 24
            clip: true
            opacity: root.currentTab === 1 ? 1.0 : 0.0
            visible: opacity > 0
            y: root.currentTab === 1 ? 0 : 8
            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

            Column {
                id: colTab1
                width: parent.width
                spacing: 14

                // 卡片 1: 音效引擎與音量
                Rectangle {
                    width: parent.width
                    height: 140
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 14

                        Text {
                            text: "音效引擎與主音量"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        // 開關
                        Row {
                            width: parent.width
                            spacing: 16
                            Text {
                                text: "提示音效總開關"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 140
                            }
                            Item {
                                width: 48
                                height: 26
                                Rectangle {
                                    anchors.fill: parent
                                    radius: 13
                                    color: (typeof backend !== "undefined" && backend && backend.soundEnabled) ? themeColors.primary : themeColors.surfaceVariant
                                    Behavior on color { ColorAnimation { duration: 200 } }
                                    Rectangle {
                                        width: 20
                                        height: 20
                                        radius: 10
                                        y: 3
                                        color: "#FFFFFF"
                                        x: (typeof backend !== "undefined" && backend && backend.soundEnabled) ? 25 : 3
                                        Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setSoundEnabled(!backend.soundEnabled)
                                        }
                                    }
                                }
                            }
                        }

                        // 音量滑桿
                        Row {
                            width: parent.width
                            spacing: 16
                            Text {
                                text: "主音量大小：" + ((typeof backend !== "undefined" && backend) ? backend.volume : 80) + "%"
                                color: themeColors.textSub
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 140
                            }

                            Item {
                                width: 340
                                height: 32
                                anchors.verticalCenter: parent.verticalCenter

                                Rectangle {
                                    id: volTrack
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width
                                    height: 8
                                    radius: 4
                                    color: themeColors.surfaceVariant

                                    Rectangle {
                                        height: parent.height
                                        radius: 4
                                        color: themeColors.primary
                                        width: {
                                            var val = (typeof backend !== "undefined" && backend) ? backend.volume : 80
                                            return Math.max(0, Math.min(parent.width, val / 100 * parent.width))
                                        }
                                    }
                                }

                                Rectangle {
                                    id: volThumb
                                    width: 18
                                    height: 18
                                    radius: 9
                                    color: themeColors.primary
                                    border.width: 2
                                    border.color: "#FFFFFF"
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: {
                                        var val = (typeof backend !== "undefined" && backend) ? backend.volume : 80
                                        return Math.max(0, Math.min(volTrack.width - width, val / 100 * (volTrack.width - width)))
                                    }
                                    scale: volMouse.pressed ? 1.25 : 1.0
                                    Behavior on scale { SpringAnimation { spring: 4.0; damping: 0.28 } }
                                }

                                MouseArea {
                                    id: volMouse
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    preventStealing: true
                                    function updatePos(mx) {
                                        var frac = Math.max(0.0, Math.min(1.0, mx / width))
                                        var val = Math.round(frac * 100)
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setVolume(val)
                                        }
                                    }
                                    onPressed: (mouse) => updatePos(mouse.x)
                                    onPositionChanged: (mouse) => {
                                        if (pressed) updatePos(mouse.x)
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 2: 自訂提示音管理（4 個槽位：hit, feed, land, off）
                Rectangle {
                    width: parent.width
                    height: 290
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "個別提示音槽位管理（支援 mp3, wav, ogg）"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Repeater {
                            model: [
                                { key: "hit", name: "輕點 / 扣費提示音", fileProp: (typeof backend !== "undefined" && backend) ? backend.cueHitFile : "預設音效" },
                                { key: "feed", name: "餵食 / 充值提示音", fileProp: (typeof backend !== "undefined" && backend) ? backend.cueFeedFile : "預設音效" },
                                { key: "land", name: "鐵盆著陸提示音", fileProp: (typeof backend !== "undefined" && backend) ? backend.cueLandFile : "預設音效" },
                                { key: "off", name: "取下鐵盆提示音", fileProp: (typeof backend !== "undefined" && backend) ? backend.cueOffFile : "預設音效" }
                            ]
                            delegate: Rectangle {
                                width: colTab1.width - 32
                                height: 50
                                radius: 10
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border

                                Row {
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    spacing: 12

                                    Column {
                                        width: 320
                                        anchors.verticalCenter: parent.verticalCenter
                                        spacing: 2

                                        Text {
                                            text: modelData.name
                                            color: themeColors.text
                                            font.pixelSize: 13
                                            font.bold: true
                                            font.family: root.modernFontStack
                                            renderType: Text.NativeRendering
                                        }
                                        Text {
                                            text: "檔案: " + modelData.fileProp
                                            color: themeColors.textSub
                                            font.pixelSize: 11
                                            font.family: root.modernFontStack
                                            renderType: Text.NativeRendering
                                            elide: Text.ElideMiddle
                                            width: 320
                                        }
                                    }

                                    Item { width: Math.max(10, parent.width - 500); height: 1 }

                                    // 試聽
                                    Rectangle {
                                        width: 70
                                        height: 30
                                        radius: 6
                                        color: themeColors.surface
                                        border.width: 1
                                        border.color: themeColors.border
                                        anchors.verticalCenter: parent.verticalCenter
                                        Text {
                                            anchors.centerIn: parent
                                            text: "試聽"
                                            color: themeColors.text
                                            font.pixelSize: 12
                                            font.bold: true
                                            font.family: root.modernFontStack
                                            renderType: Text.NativeRendering
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (typeof backend !== "undefined" && backend) {
                                                    backend.playCue(modelData.key)
                                                }
                                            }
                                        }
                                    }

                                    // 更換
                                    Rectangle {
                                        width: 80
                                        height: 30
                                        radius: 6
                                        color: themeColors.primary
                                        anchors.verticalCenter: parent.verticalCenter
                                        Text {
                                            anchors.centerIn: parent
                                            text: "更換..."
                                            color: "#FFFFFF"
                                            font.pixelSize: 12
                                            font.bold: true
                                            font.family: root.modernFontStack
                                            renderType: Text.NativeRendering
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (typeof backend !== "undefined" && backend) {
                                                    backend.uploadCue(modelData.key)
                                                }
                                            }
                                        }
                                    }

                                    // 重設
                                    Rectangle {
                                        width: 80
                                        height: 30
                                        radius: 6
                                        color: themeColors.surface
                                        border.width: 1
                                        border.color: themeColors.border
                                        anchors.verticalCenter: parent.verticalCenter
                                        Text {
                                            anchors.centerIn: parent
                                            text: "恢復預設"
                                            color: themeColors.textSub
                                            font.pixelSize: 11
                                            font.family: root.modernFontStack
                                            renderType: Text.NativeRendering
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (typeof backend !== "undefined" && backend) {
                                                    backend.resetCue(modelData.key)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 3: Gemini Live 純語音即時模式與音色
                Rectangle {
                    width: parent.width
                    height: 160
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "Gemini Live 純語音即時模式與音色選擇"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Text {
                            text: "全語音即時雙向連線，不彈出任何文字對話框，隨說隨回覆。"
                            color: themeColors.textSub
                            font.pixelSize: 12
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Row {
                            spacing: 14
                            width: parent.width

                            Rectangle {
                                width: 170
                                height: 38
                                radius: 10
                                color: (typeof backend !== "undefined" && backend && backend.pureVoiceActive) ? themeColors.danger : themeColors.primary
                                scale: mouseLive.pressed ? 0.94 : (mouseLive.containsMouse ? 1.02 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.28 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: (typeof backend !== "undefined" && backend && backend.pureVoiceActive) ? "關閉純語音連線" : "啟動純語音模式"
                                    color: "#FFFFFF"
                                    font.pixelSize: 13
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }

                                MouseArea {
                                    id: mouseLive
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.togglePureVoice()
                                        }
                                    }
                                }
                            }

                            // 音色選擇
                            Row {
                                spacing: 8
                                anchors.verticalCenter: parent.verticalCenter
                                Text {
                                    text: "語音音色:"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Repeater {
                                    model: ["Kore", "Puck", "Charon", "Fenrir", "Aoede"]
                                    delegate: Rectangle {
                                        width: 68
                                        height: 32
                                        radius: 8
                                        color: (typeof backend !== "undefined" && backend && backend.geminiLiveVoice === modelData) ? themeColors.primaryContainer : (mVoice.containsMouse ? themeColors.surfaceHover : themeColors.surfaceVariant)
                                        border.width: (typeof backend !== "undefined" && backend && backend.geminiLiveVoice === modelData) ? 2 : 1
                                        border.color: (typeof backend !== "undefined" && backend && backend.geminiLiveVoice === modelData) ? themeColors.primary : themeColors.border

                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData
                                            color: (typeof backend !== "undefined" && backend && backend.geminiLiveVoice === modelData) ? themeColors.primary : themeColors.text
                                            font.pixelSize: 11
                                            font.bold: true
                                            font.family: root.modernFontStack
                                            renderType: Text.NativeRendering
                                        }
                                        MouseArea {
                                            id: mVoice
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (typeof backend !== "undefined" && backend) {
                                                    backend.setGeminiLiveVoice(modelData)
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ===================================================== 分頁 3【AI 與 API 金鑰】
        Flickable {
            id: viewTab2
            anchors.fill: parent
            contentHeight: colTab2.height + 24
            clip: true
            opacity: root.currentTab === 2 ? 1.0 : 0.0
            visible: opacity > 0
            y: root.currentTab === 2 ? 0 : 8
            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

            Column {
                id: colTab2
                width: parent.width
                spacing: 14

                // 卡片 1: 模型供應商切換
                Rectangle {
                    width: parent.width
                    height: colCardProv.implicitHeight + 32
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        id: colCardProv
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "AI 模型供應商選擇（支援 23 家雲端平台、聚合服務與本機私有模型）"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        // 熱門快速切換膠囊
                        Flow {
                            width: parent.width
                            spacing: 8

                            Repeater {
                                model: ["DeepSeek", "OpenAI", "Claude", "Google Gemini", "Groq", "Mistral", "xAI / Grok", "Ollama", "OpenRouter", "矽基流動 (SiliconFlow)"]
                                delegate: Rectangle {
                                    width: txtPill.implicitWidth + 24
                                    height: 32
                                    radius: 8
                                    color: (typeof backend !== "undefined" && backend && backend.apiProvider === modelData) ? themeColors.primaryContainer : (provMouse.containsMouse ? themeColors.surfaceHover : themeColors.surfaceVariant)
                                    border.width: (typeof backend !== "undefined" && backend && backend.apiProvider === modelData) ? 2 : 1
                                    border.color: (typeof backend !== "undefined" && backend && backend.apiProvider === modelData) ? themeColors.primary : themeColors.border

                                    Text {
                                        id: txtPill
                                        anchors.centerIn: parent
                                        text: modelData
                                        color: (typeof backend !== "undefined" && backend && backend.apiProvider === modelData) ? themeColors.primary : themeColors.text
                                        font.pixelSize: 12
                                        font.bold: true
                                        font.family: root.modernFontStack
                                        renderType: Text.NativeRendering
                                    }

                                    MouseArea {
                                        id: provMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof backend !== "undefined" && backend) {
                                                backend.setApiProvider(modelData)
                                                edApiKey.text = backend.apiKey
                                                edApiEndpoint.text = backend.apiEndpoint
                                                edChatModel.text = backend.chatModel
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // 全部廠商下拉選單
                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "或自全部支援清單中選取："
                                color: themeColors.textSub
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            ComboBox {
                                id: cmbAllProviders
                                width: 280
                                height: 34
                                model: (typeof backend !== "undefined" && backend && backend.apiProvidersList) ? backend.apiProvidersList : ["DeepSeek", "OpenAI", "Claude", "Google Gemini"]
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                                onActivated: {
                                    if (typeof backend !== "undefined" && backend) {
                                        backend.setApiProvider(currentText)
                                        edApiKey.text = backend.apiKey
                                        edApiEndpoint.text = backend.apiEndpoint
                                        edChatModel.text = backend.chatModel
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 2: API 金鑰配置與連線端點
                Rectangle {
                    width: parent.width
                    height: 250
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "API 金鑰與連線端點配置（" + ((typeof backend !== "undefined" && backend) ? backend.apiProvider : "當前廠商") + "）"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        // 金鑰輸入行
                        Row {
                            width: parent.width
                            spacing: 10

                            Rectangle {
                                width: parent.width - 200
                                height: 38
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border

                                TextInput {
                                    id: edApiKey
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    text: (typeof backend !== "undefined" && backend) ? backend.apiKey : ""
                                    echoMode: chkShowKey.checked ? TextInput.Normal : TextInput.Password
                                    color: themeColors.text
                                    font.pixelSize: 13
                                    font.family: "Consolas, monospace"
                                    selectByMouse: true
                                    clip: true
                                }
                            }

                            Rectangle {
                                width: 75
                                height: 38
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: chkShowKey.checked ? "隱藏" : "顯示"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                property bool checked: false
                                id: chkShowKey
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: chkShowKey.checked = !chkShowKey.checked
                                }
                            }

                            Rectangle {
                                width: 100
                                height: 38
                                radius: 8
                                color: themeColors.primary
                                Text {
                                    anchors.centerIn: parent
                                    text: "儲存金鑰"
                                    color: "#FFFFFF"
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.saveApiKey(backend.apiProvider, edApiKey.text)
                                        }
                                    }
                                }
                            }
                        }

                        // 自訂端點（Base URL）輸入行
                        Row {
                            width: parent.width
                            spacing: 10

                            Rectangle {
                                width: parent.width - 110
                                height: 38
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border

                                TextInput {
                                    id: edApiEndpoint
                                    anchors.fill: parent
                                    anchors.margins: 10
                                    text: (typeof backend !== "undefined" && backend) ? backend.apiEndpoint : ""
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.family: "Consolas, monospace"
                                    selectByMouse: true
                                    clip: true
                                }
                            }

                            Rectangle {
                                width: 100
                                height: 38
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "儲存端點"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.saveApiEndpoint(backend.apiProvider, edApiEndpoint.text)
                                        }
                                    }
                                }
                            }
                        }

                        // 安全開關：Windows DPAPI 與 PIN 認證
                        Row {
                            width: parent.width
                            spacing: 16

                            Row {
                                spacing: 10
                                Text {
                                    text: "Windows DPAPI 原生密文加密保護"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Item {
                                    width: 44
                                    height: 24
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 12
                                        color: (typeof backend !== "undefined" && backend && backend.dpapiEnabled) ? themeColors.primary : themeColors.surfaceVariant
                                        Rectangle {
                                            width: 18
                                            height: 18
                                            radius: 9
                                            y: 3
                                            color: "#FFFFFF"
                                            x: (typeof backend !== "undefined" && backend && backend.dpapiEnabled) ? 23 : 3
                                            Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof backend !== "undefined" && backend) {
                                                backend.setDpapiEnabled(!backend.dpapiEnabled)
                                            }
                                        }
                                    }
                                }
                            }

                            Item { width: 20; height: 1 }

                            Row {
                                spacing: 10
                                Text {
                                    text: "Windows PIN / 身分驗證保護"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Item {
                                    width: 44
                                    height: 24
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 12
                                        color: (typeof backend !== "undefined" && backend && backend.pinAuthEnabled) ? themeColors.primary : themeColors.surfaceVariant
                                        Rectangle {
                                            width: 18
                                            height: 18
                                            radius: 9
                                            y: 3
                                            color: "#FFFFFF"
                                            x: (typeof backend !== "undefined" && backend && backend.pinAuthEnabled) ? 23 : 3
                                            Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof backend !== "undefined" && backend) {
                                                backend.setPinAuthEnabled(!backend.pinAuthEnabled)
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 3: 對話模型選取與線上探索
                Rectangle {
                    width: parent.width
                    height: 175
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "對話模型配置與線上探索"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Row {
                            width: parent.width
                            spacing: 12

                            Rectangle {
                                width: 180
                                height: 36
                                radius: 8
                                color: themeColors.primary
                                Text {
                                    anchors.centerIn: parent
                                    text: "線上獲取最新模型列表"
                                    color: "#FFFFFF"
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.fetchRemoteModels(backend.apiProvider)
                                        }
                                    }
                                }
                            }

                            Text {
                                text: (typeof backend !== "undefined" && backend) ? backend.remoteModelStatus : "請點擊按鈕獲取清單"
                                color: themeColors.textSub
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                                width: 450
                                elide: Text.ElideRight
                            }
                        }

                        Row {
                            width: parent.width
                            spacing: 12

                            ComboBox {
                                id: cmbModels
                                width: 280
                                height: 36
                                model: (typeof backend !== "undefined" && backend && backend.remoteModels.length > 0) ? backend.remoteModels : ["deepseek-chat"]
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                                onActivated: {
                                    edChatModel.text = currentText
                                }
                            }

                            Rectangle {
                                width: 200
                                height: 36
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border

                                TextInput {
                                    id: edChatModel
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    text: (typeof backend !== "undefined" && backend) ? backend.chatModel : ""
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.family: "Consolas, monospace"
                                    selectByMouse: true
                                    clip: true
                                }
                            }

                            Rectangle {
                                width: 140
                                height: 36
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.primary
                                Text {
                                    anchors.centerIn: parent
                                    text: "套用對話模型"
                                    color: themeColors.primary
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setChatModel(edChatModel.text || cmbModels.currentText)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 4: AI 對話行為與系統提示詞
                Rectangle {
                    width: parent.width
                    height: colCardChatBehavior.implicitHeight + 32
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        id: colCardChatBehavior
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "AI 對話行為與系統提示詞 (System Prompt)"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        // 對話模式選擇
                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "對話模式："
                                color: themeColors.textSub
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Repeater {
                                model: [
                                    { "id": "standard", "label": "標準陪伴對話" },
                                    { "id": "reasoner", "label": "深度思考 (Reasoner)" },
                                    { "id": "agent", "label": "系統助手 (Agent)" }
                                ]
                                delegate: Rectangle {
                                    width: txtMode.implicitWidth + 24
                                    height: 32
                                    radius: 8
                                    color: (typeof backend !== "undefined" && backend && backend.aiMode === modelData.id) ? themeColors.primaryContainer : themeColors.surfaceVariant
                                    border.width: (typeof backend !== "undefined" && backend && backend.aiMode === modelData.id) ? 2 : 1
                                    border.color: (typeof backend !== "undefined" && backend && backend.aiMode === modelData.id) ? themeColors.primary : themeColors.border

                                    Text {
                                        id: txtMode
                                        anchors.centerIn: parent
                                        text: modelData.label
                                        color: (typeof backend !== "undefined" && backend && backend.aiMode === modelData.id) ? themeColors.primary : themeColors.text
                                        font.pixelSize: 12
                                        font.bold: true
                                        font.family: root.modernFontStack
                                        renderType: Text.NativeRendering
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof backend !== "undefined" && backend) {
                                                backend.setAiMode(modelData.id)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // 系統提示詞輸入框
                        Column {
                            width: parent.width
                            spacing: 6

                            Text {
                                text: "自訂系統提示詞 (System Prompt)："
                                color: themeColors.textSub
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                            }

                            Row {
                                width: parent.width
                                spacing: 10

                                Rectangle {
                                    width: parent.width - 120
                                    height: 60
                                    radius: 8
                                    color: themeColors.surfaceVariant
                                    border.width: 1
                                    border.color: themeColors.border

                                    Flickable {
                                        anchors.fill: parent
                                        anchors.margins: 8
                                        contentWidth: parent.width - 16
                                        contentHeight: edSysPrompt.implicitHeight
                                        clip: true

                                        TextEdit {
                                            id: edSysPrompt
                                            width: parent.width
                                            text: (typeof backend !== "undefined" && backend) ? backend.systemPrompt : ""
                                            color: themeColors.text
                                            font.pixelSize: 12
                                            font.family: root.modernFontStack
                                            wrapMode: TextEdit.Wrap
                                            selectByMouse: true
                                        }
                                    }
                                }

                                Rectangle {
                                    width: 110
                                    height: 38
                                    radius: 8
                                    color: themeColors.primary
                                    anchors.verticalCenter: parent.verticalCenter
                                    Text {
                                        anchors.centerIn: parent
                                        text: "儲存提示詞"
                                        color: "#FFFFFF"
                                        font.pixelSize: 12
                                        font.bold: true
                                        font.family: root.modernFontStack
                                        renderType: Text.NativeRendering
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof backend !== "undefined" && backend) {
                                                backend.setSystemPrompt(edSysPrompt.text)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // 溫度滑桿與隱私優先模式
                        Row {
                            width: parent.width
                            spacing: 24

                            Row {
                                spacing: 10
                                anchors.verticalCenter: parent.verticalCenter
                                Text {
                                    text: "溫度 (創造力): " + ((typeof backend !== "undefined" && backend) ? backend.temperature.toFixed(2) : "0.70")
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Slider {
                                    id: sldTemp
                                    from: 0.0
                                    to: 1.5
                                    stepSize: 0.05
                                    value: (typeof backend !== "undefined" && backend) ? backend.temperature : 0.70
                                    onMoved: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.setTemperature(value)
                                        }
                                    }
                                }
                            }

                            Row {
                                spacing: 10
                                anchors.verticalCenter: parent.verticalCenter
                                Text {
                                    text: "隱私優先脫敏模式"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                    anchors.verticalCenter: parent.verticalCenter
                                }
                                Item {
                                    width: 44
                                    height: 24
                                    Rectangle {
                                        anchors.fill: parent
                                        radius: 12
                                        color: (typeof backend !== "undefined" && backend && backend.privacyMode) ? themeColors.primary : themeColors.surfaceVariant
                                        Rectangle {
                                            width: 18
                                            height: 18
                                            radius: 9
                                            y: 3
                                            color: "#FFFFFF"
                                            x: (typeof backend !== "undefined" && backend && backend.privacyMode) ? 23 : 3
                                            Behavior on x { SpringAnimation { spring: 3.5; damping: 0.3 } }
                                        }
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (typeof backend !== "undefined" && backend) {
                                                backend.setPrivacyMode(!backend.privacyMode)
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        // 快捷按鈕列：打開對話視窗、進階設定檔
                        Row {
                            spacing: 12

                            Rectangle {
                                width: 140
                                height: 36
                                radius: 8
                                color: themeColors.primary
                                Text {
                                    anchors.centerIn: parent
                                    text: "開啟 AI 對話視窗"
                                    color: "#FFFFFF"
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openChatDialog()
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 180
                                height: 36
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "開啟進階 API 設定檔管理..."
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openApiProfileDialog()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ===================================================== 分頁 4【字體設定】
        Flickable {
            id: viewTab3
            anchors.fill: parent
            contentHeight: colTab3.height + 24
            clip: true
            opacity: root.currentTab === 3 ? 1.0 : 0.0
            visible: opacity > 0
            y: root.currentTab === 3 ? 0 : 8
            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

            Column {
                id: colTab3
                width: parent.width
                spacing: 14

                // 卡片 1: 系統字型選取與字體檔案匯入
                Rectangle {
                    width: parent.width
                    height: 180
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "高品質現代字體排版系統 (Typography)"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Text {
                            text: "全域注入現代無襯線字體堆疊，啟用文字抗鋸齒與次像素渲染，徹底告別粗糙字體感。"
                            color: themeColors.textSub
                            font.pixelSize: 12
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: "系統字型清單:"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.bold: true
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            ComboBox {
                                id: cmbSysFonts
                                width: 280
                                height: 36
                                model: (typeof backend !== "undefined" && backend) ? backend.systemFonts : ["Segoe UI Variable Text", "Microsoft JhengHei UI", "PingFang TC"]
                                currentIndex: {
                                    if (typeof backend !== "undefined" && backend) {
                                        var idx = model.indexOf(backend.currentFontFamily)
                                        return idx >= 0 ? idx : 0
                                    }
                                    return 0
                                }
                                onActivated: (index) => {
                                    if (typeof backend !== "undefined" && backend) {
                                        backend.selectSystemFont(currentText)
                                    }
                                }
                                font.pixelSize: 12
                                font.family: root.modernFontStack
                            }

                            Rectangle {
                                width: 170
                                height: 36
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                anchors.verticalCenter: parent.verticalCenter
                                Text {
                                    anchors.centerIn: parent
                                    text: "匯入自訂字體檔 (.ttf/.otf)..."
                                    color: themeColors.text
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.browseCustomFont()
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            text: "目前字型路徑 / 字族: " + ((typeof backend !== "undefined" && backend && backend.customFontPath) ? backend.customFontPath : ((typeof backend !== "undefined" && backend) ? backend.currentFontFamily : "系統預設"))
                            color: themeColors.textSub
                            font.pixelSize: 11
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                            elide: Text.ElideMiddle
                            width: parent.width
                        }
                    }
                }

                // 卡片 2: 即時中文排版效果預覽
                Rectangle {
                    width: parent.width
                    height: 230
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "即時中文排版效果預覽"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Rectangle {
                            width: parent.width
                            height: 100
                            radius: 10
                            color: themeColors.surfaceVariant
                            border.width: 1
                            border.color: themeColors.border
                            clip: true

                            Column {
                                anchors.fill: parent
                                anchors.margins: 14
                                spacing: 8

                                Text {
                                    text: "繁體中文排版預覽：永遠熱愛生活，桌面寵物陪伴你的每一天。"
                                    color: themeColors.text
                                    font.pixelSize: 15
                                    font.bold: true
                                    font.family: (typeof backend !== "undefined" && backend) ? backend.currentFontFamily : root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                Text {
                                    text: "數位時鐘與英數符號展示：0123456789 ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz"
                                    color: themeColors.textSub
                                    font.pixelSize: 12
                                    font.family: (typeof backend !== "undefined" && backend) ? backend.currentFontFamily : root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                            }
                        }

                        Row {
                            spacing: 12

                            Rectangle {
                                width: 140
                                height: 36
                                radius: 8
                                color: themeColors.primary
                                Text {
                                    anchors.centerIn: parent
                                    text: "套用選定字體"
                                    color: "#FFFFFF"
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.applyFont(backend.currentFontFamily)
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 150
                                height: 36
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "重設為推薦字體"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.resetDefaultFont()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ===================================================== 分頁 5【關於與日誌】
        Flickable {
            id: viewTab4
            anchors.fill: parent
            contentHeight: colTab4.height + 24
            clip: true
            opacity: root.currentTab === 4 ? 1.0 : 0.0
            visible: opacity > 0
            y: root.currentTab === 4 ? 0 : 8
            Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
            Behavior on y { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

            Column {
                id: colTab4
                width: parent.width
                spacing: 14

                // 卡片 1: 系統狀態摘要膠囊與快捷
                Rectangle {
                    width: parent.width
                    height: 98
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        Row {
                            width: parent.width
                            spacing: 12

                            Text {
                                text: (typeof backend !== "undefined" && backend) ? backend.statusSummary : "狀態：就緒"
                                color: themeColors.text
                                font.pixelSize: 13
                                font.bold: true
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            Item { width: Math.max(10, parent.width - 300); height: 1 }

                            Rectangle {
                                width: 90
                                height: 30
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "重新整理"
                                    color: themeColors.text
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.refreshLogs(logLevelCmb.currentText, edLogSearch.text)
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 90
                                height: 30
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "清空緩存"
                                    color: themeColors.text
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.clearLogs()
                                        }
                                    }
                                }
                            }
                        }

                        Row {
                            spacing: 12
                            Rectangle {
                                width: 130
                                height: 28
                                radius: 6
                                color: themeColors.primaryContainer
                                Text {
                                    anchors.centerIn: parent
                                    text: "開啟 AI 對話視窗"
                                    color: themeColors.primaryText
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openChatDialog()
                                        }
                                    }
                                }
                            }
                            Rectangle {
                                width: 130
                                height: 28
                                radius: 6
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "開啟 Web 儀表板"
                                    color: themeColors.text
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openWebUi()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 2: 即時 Console 日誌檢視器
                Rectangle {
                    width: parent.width
                    height: 260
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 10

                        Row {
                            width: parent.width
                            spacing: 10

                            Text {
                                text: "日誌等級過濾:"
                                color: themeColors.text
                                font.pixelSize: 12
                                font.bold: true
                                font.family: root.modernFontStack
                                renderType: Text.NativeRendering
                                anchors.verticalCenter: parent.verticalCenter
                            }

                            ComboBox {
                                id: logLevelCmb
                                width: 110
                                height: 30
                                model: ["全部 (ALL)", "INFO", "WARNING", "ERROR"]
                                font.pixelSize: 11
                                onActivated: (idx) => {
                                    if (typeof backend !== "undefined" && backend) {
                                        backend.refreshLogs(currentText, edLogSearch.text)
                                    }
                                }
                            }

                            Rectangle {
                                width: 220
                                height: 30
                                radius: 6
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border

                                TextInput {
                                    id: edLogSearch
                                    anchors.fill: parent
                                    anchors.margins: 6
                                    color: themeColors.text
                                    font.pixelSize: 11
                                    font.family: root.modernFontStack
                                    selectByMouse: true
                                    clip: true
                                    onTextChanged: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.refreshLogs(logLevelCmb.currentText, text)
                                        }
                                    }
                                }
                                Text {
                                    anchors.left: parent.left
                                    anchors.leftMargin: 8
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "搜尋關鍵字..."
                                    color: themeColors.textSub
                                    font.pixelSize: 11
                                    font.family: root.modernFontStack
                                    visible: !edLogSearch.text
                                }
                            }
                        }

                        // 日誌終端視圖
                        Rectangle {
                            width: parent.width
                            height: 170
                            radius: 10
                            color: themeColors.currentTheme === "dark" ? "#0A0D14" : "#1E293B"
                            border.width: 1
                            border.color: themeColors.border
                            clip: true

                            Flickable {
                                id: flickLogs
                                anchors.fill: parent
                                anchors.margins: 10
                                contentWidth: textLogs.paintedWidth
                                contentHeight: textLogs.paintedHeight
                                clip: true

                                TextEdit {
                                    id: textLogs
                                    text: (typeof backend !== "undefined" && backend) ? backend.logsSnippet : "尚無即時日誌紀錄。"
                                    color: "#E2E8F0"
                                    font.pixelSize: 11
                                    font.family: "Consolas, 'Cascadia Code', monospace"
                                    readOnly: true
                                    selectByMouse: true
                                }
                            }
                        }
                    }
                }

                // 卡片 3: GitHub 更新與官方專案倉庫
                Rectangle {
                    width: parent.width
                    height: 130
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        Text {
                            text: "版本更新與官方倉庫"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Row {
                            spacing: 12

                            Rectangle {
                                width: 160
                                height: 34
                                radius: 8
                                color: themeColors.primary
                                Text {
                                    anchors.centerIn: parent
                                    text: "檢查 GitHub 最新版本"
                                    color: "#FFFFFF"
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.checkForUpdates()
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 140
                                height: 34
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "開啟官方 GitHub 專案"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openRepoUrl()
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 120
                                height: 34
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "提交 Issue 回報"
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openIssuesUrl()
                                        }
                                    }
                                }
                            }
                        }

                        Text {
                            text: (typeof backend !== "undefined" && backend) ? backend.updateStatus : "點擊按鈕檢查更新"
                            color: themeColors.textSub
                            font.pixelSize: 11
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }
                    }
                }

                // 卡片 4: 開源協議與本機目錄
                Rectangle {
                    width: parent.width
                    height: 160
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        Text {
                            text: "開源授權與本機目錄"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Text {
                            text: "本專案採用 MIT License 開源許可協議發布；圖示採用 Google Material Symbols (Apache 2.0)。\n角色立繪與音訊素材著作權歸原創作者所有，使用者可於本機目錄中自由管理自訂素材。"
                            color: themeColors.textSub
                            font.pixelSize: 11
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Row {
                            spacing: 12

                            Rectangle {
                                width: 130
                                height: 30
                                radius: 6
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "開啟本機立繪目錄"
                                    color: themeColors.text
                                    font.pixelSize: 11
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openCustomCharsDir()
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 130
                                height: 30
                                radius: 6
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "開啟本機音效目錄"
                                    color: themeColors.text
                                    font.pixelSize: 11
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openCustomSoundsDir()
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 130
                                height: 30
                                radius: 6
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                Text {
                                    anchors.centerIn: parent
                                    text: "開啟本機日誌目錄"
                                    color: themeColors.text
                                    font.pixelSize: 11
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openLogsDir()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 5: 開源專案與依賴清單
                Rectangle {
                    width: parent.width
                    height: colCardThanks.implicitHeight + 32
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        id: colCardThanks
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Text {
                            text: "開源專案與依賴清單"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Text {
                            text: "• VK-1 (DSH Balance Pet)：原型倉庫（本專案為其衍生分支）\n• YuYue_Encryption：備份資料加密模組\n• PySide6 / Qt 6：介面與 QML 渲染框架 (LGPLv3)\n• Google Material Symbols：向量圖示庫 (Apache 2.0)\n• Python 標準庫 & Windows MCI：系統核心與本機音訊"
                            color: themeColors.textSub
                            font.pixelSize: 11
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                            lineHeight: 1.4
                        }

                        Row {
                            spacing: 12

                            Rectangle {
                                width: 130
                                height: 30
                                radius: 6
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.primary

                                Text {
                                    anchors.centerIn: parent
                                    text: "造訪 VK-1 倉庫"
                                    color: themeColors.primary
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openVk1Repo()
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 180
                                height: 30
                                radius: 6
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.primary

                                Text {
                                    anchors.centerIn: parent
                                    text: "造訪 YuYue_Encryption 倉庫"
                                    color: themeColors.primary
                                    font.pixelSize: 11
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.openYuYueRepo()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 卡片 6: 全設定與資料安全備份管理
                Rectangle {
                    width: parent.width
                    height: 140
                    radius: 14
                    color: themeColors.surface
                    border.width: 1
                    border.color: themeColors.border

                    Column {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 10

                        Text {
                            text: "全設定與資料安全備份"
                            color: themeColors.text
                            font.pixelSize: 14
                            font.bold: true
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Text {
                            text: "完整備份寵物配置、鬧鐘與自訂角色；整合 YuYue 8 層複合高強度加密防護與 API 金鑰脫敏防護。"
                            color: themeColors.textSub
                            font.pixelSize: 11
                            font.family: root.modernFontStack
                            renderType: Text.NativeRendering
                        }

                        Row {
                            spacing: 12

                            Rectangle {
                                width: 175
                                height: 34
                                radius: 8
                                color: themeColors.primary
                                scale: mExportBtn.pressed ? 0.95 : (mExportBtn.containsMouse ? 1.02 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.28 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: "匯出所有設定與資料..."
                                    color: "#FFFFFF"
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }

                                MouseArea {
                                    id: mExportBtn
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.exportSettingsData()
                                        }
                                    }
                                }
                            }

                            Rectangle {
                                width: 130
                                height: 34
                                radius: 8
                                color: themeColors.surfaceVariant
                                border.width: 1
                                border.color: themeColors.border
                                scale: mImportBtn.pressed ? 0.95 : (mImportBtn.containsMouse ? 1.02 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.28 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: "匯入設定..."
                                    color: themeColors.text
                                    font.pixelSize: 12
                                    font.bold: true
                                    font.family: root.modernFontStack
                                    renderType: Text.NativeRendering
                                }

                                MouseArea {
                                    id: mImportBtn
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (typeof backend !== "undefined" && backend) {
                                            backend.importSettingsData()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
