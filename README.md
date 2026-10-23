# VK-1 桌面寵物

VK-1 是跨平台桌面寵物專案，包含 macOS 原生版本、Windows 舊版 PowerShell 實作、Windows 新版 Python + PySide6 實作，以及獨立網頁整合版本。

## 版本與目錄

| 版本 | 目錄 | 技術棧 | 狀態 |
| --- | --- | --- | --- |
| Windows Python v4 | [`windows/python/`](windows/python) | Python + PySide6 + Pillow | 目前主要開發版本 |
| Windows PowerShell | [`windows/powershell/`](windows/powershell) | PowerShell 5.1 + 內嵌 C# / WinForms | 舊版完整保留 |
| macOS | [`dsh-balance-pet-macos/`](dsh-balance-pet-macos) | Swift + AppKit | macOS 原生版本 |
| 網頁整合 | [`integration/`](integration) | JavaScript / 可選 Python 服務 | 網頁嵌入版本 |

## Windows Python v4

Python 版是目前建議的新 Windows 實作，使用透明 PySide6 桌面視窗，不依賴 PowerShell 的 `Add-Type` 或內嵌 C# 編譯流程。

功能包括：

- 1536×1024 RGBA 角色圖，等比例顯示，不裁切尾巴、頭髮或透明邊界。
- PySide6 控制面板：角色、外觀、位置、火控／飯盆、模擬模式與 API Key 管理。
- 右鍵快捷操作：控制面板、角色切換、模式切換、掉飯盆、清除飯盆、滑鼠穿透、回到左下角與退出。
- 模擬模式與 API 模式分開切換；模擬模式可設定餘額、扣款／充值範圍與事件間隔。
- 最多 5 個角色同時在場，額外角色以獨立透明視窗行走。
- 自動貼邊預設開啟，可以從右鍵選單或控制面板關閉。
- 正常與黑化 DeepSeek 三方向角色：前方、側面、後方；行走時使用側面，到達邊緣時切換視角。
- Pillow 自訂角色匯入，將圖片等比例置中到 1536×1024 透明畫布。
- PyInstaller Windows 打包，使用者不需要另外安裝 Python。

### 開發模式

Windows 上安裝 Python 3.10 或更新版本後，在 `windows/python/` 執行：

```bat
py -m pip install -r requirements.txt
start_pet_debug.bat
```

一般啟動可使用 `start_pet.bat`。除錯時使用 `start_pet_debug.bat` 查看主控台錯誤。

### 打包免安裝版本

```bat
build_windows.bat
```

完成後執行檔位於 `dist\PythonPetV4\PythonPetV4.exe`。請將整個 `dist\PythonPetV4` 資料夾一起複製到其他 Windows 電腦。

### Python 資產

- `windows/python/assets/sprite*.png`：1536×1024 內建角色圖。
- `windows/python/assets/deepseek_*_directions.webp`：正常／黑化 DeepSeek 原始三方向圖。
- `windows/python/assets/deepseek_{front,side,back}.png`：正常版透明三方向圖。
- `windows/python/assets/deepseek_dark_{front,side,back}.png`：黑化版透明三方向圖。
- `windows/python/assets/legacy_chars/`：從舊 Windows 資產提取的 Claude、Gemini、GPT 角色與表情圖片。
- `windows/python/custom_characters/`：使用者匯入的自訂角色，預設為空資料夾。

## Windows PowerShell 舊版

舊版沒有刪除，只是完整遷移到 [`windows/powershell/`](windows/powershell)。其中保留原有的 PowerShell、VBScript、音效、角色圖、說明文件與 sprites。若仍需要舊版行為，可直接進入該目錄使用原本的啟動腳本。

Python 版與 PowerShell 版互相獨立，設定檔與執行檔不共用。新功能優先在 Python 版維護，PowerShell 版作為相容與歷史保留版本。

## macOS 與網頁版本

macOS 原生版本位於 [`dsh-balance-pet-macos/`](dsh-balance-pet-macos)，使用 Swift + AppKit，包含角色切換、飯盆、鐵盆、火控雷達與摸頭互動。完整建置說明請查看 [`dsh-balance-pet-macos/README.md`](dsh-balance-pet-macos/README.md)。

網頁嵌入版本位於 [`integration/`](integration)，適合放入網站或本機監控面板；它不會像桌面版本一樣跨應用程式浮在系統桌面上。建置與部署方式請查看 [`integration/README.md`](integration/README.md)。

## 資產來源與授權注意

macOS Resources 與部分角色資產保留原專案的來源說明，請參閱 [`dsh-balance-pet-macos/Resources/README.md`](dsh-balance-pet-macos/Resources/README.md)。外部圖片與角色素材的授權狀態可能不同；若要重新發布或商用，請先確認各素材原作者的授權條款。
