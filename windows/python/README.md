# Python Desktop Pet v4

Windows Python 版本使用 PySide6 + Pillow，主角色採用 1536×1024 完整透明畫布，等比例縮放、不裁切尾巴與頭髮。

## 已整合功能

- Claude、Gemini、GPT 的舊 `expression_11/12/21/22.png` 差分已接入控制面板「表情差分」頁。
- 最多 4 個額外角色，主角色合計 5 個；獨立透明視窗、可拖曳、碰撞避讓。
- 只有存在完整 `front/side/back` walking sprite 的角色才會啟動自動行走。目前正常／黑化 DeepSeek 可行走；Claude、Gemini、GPT 沒有 walking sprite 時會在選單中明確禁止，不會讓整張立繪自行滑動。
- 主角色與額外角色都支援滑鼠拖曳；角色互相碰撞時會抬高避讓。
- 模擬模式：可設定餘額、扣款／充值範圍、間隔、開關；控制面板顯示最近事件與最多 100 筆事件紀錄。
- API 模式：DeepSeek 使用官方 `GET https://api.deepseek.com/user/balance`；OpenAI 使用 organization costs（需要 Admin API Key）；Anthropic 會提示需要組織管理權限與官方 cost report 權限。
- 飯盆可拖曳；拖到主角色透明視窗範圍會餵食並播放 `feed.mp3`；扣款／充值事件播放對應音效。
- 沒有 API Key，或有 Key 但沒有啟用 AI 對話模式時，角色對話使用內建隨機文句；只有兩者同時成立才呼叫聊天 API。
- Windows DPI：啟用 Qt High DPI 與 `PassThrough` rounding，避免高 DPI 螢幕上的尺寸跳動。
- PyInstaller onedir 打包，會收集 Qt Multimedia，目標電腦不需要 Python。

## 執行

```bat
py -m pip install -r requirements.txt
start_pet_debug.bat
```

一般啟動使用 `start_pet.bat`。設定檔會寫在程式目錄的 `pet_config.json`，請勿將它與 API Key 一起提交到 Git。

## 打包

```bat
build_windows.bat
```

完成後執行 `dist\PythonPetV4\PythonPetV4.exe`。發佈時請複製整個 `dist\PythonPetV4` 資料夾。

## 資產目錄

- `assets/sprite*.png`：完整 1536×1024 角色圖。
- `assets/deepseek_{front,side,back}.png`：正常 DeepSeek walking sprite。
- `assets/deepseek_dark_{front,side,back}.png`：黑化 DeepSeek walking sprite。
- `assets/legacy_chars/{claude,gemini,gpt}/sprites/`：舊表情差分。
- `custom_characters/`：匯入的自訂角色。
