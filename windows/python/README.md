# Python Desktop Pet v4

PowerShell / C# 桌寵的 PySide6 重構版。主視窗使用透明、無邊框、可拖曳的桌面視窗；角色圖一律以 Pillow 等比例縮放到 **1536×1024 RGBA 完整畫布**，不裁切，不改變比例，因此新匯入的尾巴、頭髮與畫布邊界都會保留。

## 功能

- 1536×1024 完整比例角色畫布；舊版 1024×1024 素材會以 contain 方式相容顯示。
- 透明桌面視窗、最上層、固定左下角、透明度與尺寸調整、滑鼠拖曳。
- 滑鼠穿透切換；開啟後可由托盤選單再次恢復。
- 自訂角色匯入：PNG/JPG/WEBP，Pillow 等比例縮放置中，不裁切。
- 內建角色選擇：藍色大肥魚、GPT 龍娘、大小姐 Claude、北美貓娘 Gemini，以及 DeepSeek 離線抱盆狀態。
- 右鍵「開啟控制面板」：角色預覽、視窗外觀、位置、火控／飯盆、模擬模式與 API 模式集中管理。
- 右鍵快捷操作仍保留：立即掉飯盆、清除飯盆、滑鼠穿透、回到左下角與退出。
- 模擬模式可設定初始餘額、事件間隔、扣款／充值上下限與自動模擬開關。
- API Key 管理和「切換模擬／API 模式」是兩個分開的右鍵功能；儲存 Key 不會自動切換模式。
- 右鍵選單會依目前狀態反向顯示操作：目前是模擬模式時顯示「切換到 API 餘額模式」，目前是 API 模式時顯示「切換到模擬模式」；API Key 與模擬控制也會使用「開啟／修改」等狀態文字。
- 最多可同時新增 4 個額外角色，加上主角色共 5 個；額外角色會以獨立透明視窗水平行走。自動貼邊預設開啟，可在「同時角色」右鍵子選單或控制面板關閉。
- 自動火控 / 飯盆：可設定間隔，提供關閉選項；飯盆 45 秒自動清除，也可右鍵立即清除。
- Windows 啟動：`start_pet.bat`、`start_pet_debug.bat`。
- PyInstaller 打包：`build_windows.bat`，產出 `dist\PythonPetV4\PythonPetV4.exe`，目標電腦不需安裝 Python。

## Windows 使用方式

開發模式需要 Python 3.10+：

```bat
py -m pip install -r requirements.txt
start_pet_debug.bat
```

產生免安裝版本：

```bat
build_windows.bat
```

將整個 `dist\PythonPetV4` 資料夾複製到其他 Windows 電腦，雙擊其中的 `PythonPetV4.exe` 即可。若要保留自訂角色，請一併保留 `custom_characters` 資料夾。

## 1536×1024 角色圖

把完整透明角色圖放入 `assets\sprite_full.png`。程式不會裁切它，只會在視窗內使用 `Qt.KeepAspectRatio` 縮放。若透過右鍵「匯入自訂角色」，程式會產生新的 `custom_characters\角色名.png`。

內建角色資產取自 [VK-1 macOS Resources](https://github.com/VKmich16/VK-1/tree/main/dsh-balance-pet-macos/Resources)，其中 `sprite.png`、`sprite-gpt.png`、`sprite-claude.png`、`sprite-gemini.png` 與 `sprite-deepseek-offline.png` 都是 1536×1024 RGBA 圖。這些原圖保留了完整頭髮、尾巴與透明邊界，不再使用先前 1024×1024 裁切版作為預設。

若使用者沒有放入新資產，程式才會退回舊版 `reference/windows/sprite.png` 並建立相容 fallback；這不會重新生成舊素材缺失的像素。

使用者提供的 `377.webp` 與 `916.webp` 已保存為 `assets/reference_multi.webp`、`assets/reference_thinking.webp`，並透過邊界連通背景移除產生 `reference_multi_clean.png` 與 `reference_thinking_clean.png`。它們仍是候選參考圖：第一張包含多個角色與原始版面，並非逐角色 walking sprite，所以程式不會把整張預覽圖直接冒充成單一走路角色。

另外加入使用者提供的正常／黑化 DeepSeek 三方向圖：`064.webp` 與 `065.webp`。原圖保留在 `deepseek_directions.webp`、`deepseek_dark_directions.webp`，清理版會移除 `#d2d2d2` 背景及右下角純背景上的「知乎 @阿落」，並輸出 `deepseek_{front,side,back}.png` 與 `deepseek_dark_{front,side,back}.png`。右鍵「同時角色」可新增這兩種三方向走動角色；行走時使用側面，到達邊緣轉向時短暫切換前／後面。

## 專案結構

- `main.py`：PySide6 主程式
- `assets/sprite_full.png`：預設完整畫布
- `custom_characters/`：使用者匯入的角色
- `build_windows.bat`：PyInstaller 打包
- `start_pet.bat`：一般啟動
- `start_pet_debug.bat`：保留主控台的除錯啟動
