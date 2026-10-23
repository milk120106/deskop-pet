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

## 多模型、Ollama 與自訂端點

「API 設定檔／多模型管理」可以新增多組設定，每組包含名稱、供應商、API Key、端點 URL 與模型名稱。聊天框會在送出訊息前提供設定檔／模型選擇器。支援：

- DeepSeek、OpenAI、Anthropic 原生端點。
- Ollama：預設 `http://localhost:11434/v1`，可不填 API Key，例如模型 `llama3.2`。
- OpenAI-compatible 自訂端點：可接公司內網 gateway、LocalAI、vLLM 或其他相容服務。

目前沒有強制使用 LiteLLM。程式內建的 provider adapter 只處理聊天所需的少量差異，直接使用 `urllib.request`，因此打包檔較小、Ollama 不需要 Key，也能保留自訂端點。若未來需要路由、fallback、重試、token budget、更多供應商統一管理，再考慮加入 LiteLLM；目前加入它反而會增加依賴與 PyInstaller 收集複雜度。

## 角色對話

右鍵選單選擇「與角色對話」會開啟貼近角色的聊天框。送出訊息後：

1. 角色頭頂顯示「思考中…」的視覺泡泡；這只是 UI 狀態，不代表 API 思考鏈，也不會顯示或儲存模型的 hidden reasoning。
2. 回覆完成後，思考泡泡會換成角色對話泡泡；聊天記錄仍保留在聊天框內。
3. 沒有 API Key，或 API Key 存在但「AI 對話模式」未啟用時，只使用內建隨機文句，不會發出網路請求。

## AI API 呼叫方式

API Key 只存於本機 `pet_config.json`，程式使用 Python 標準庫 `urllib.request`，在背景 QThread 中發送 HTTPS 請求，避免卡住 GUI：

- **DeepSeek**：`POST https://api.deepseek.com/chat/completions`，Bearer API Key，模型 `deepseek-chat`。
- **OpenAI**：`POST https://api.openai.com/v1/chat/completions`，Bearer API Key，模型 `gpt-4o-mini`。
- **Anthropic**：`POST https://api.anthropic.com/v1/messages`，使用 `x-api-key` 與 `anthropic-version: 2023-06-01`，模型 `claude-3-5-haiku-latest`。

送出的內容是角色提示詞加上使用者訊息，要求模型以繁體中文簡短回覆，並明確要求不要輸出思考過程。程式只取回覆文字顯示在泡泡中，不會把 API Key 寫入事件紀錄。

餘額查詢與聊天是兩條獨立流程：DeepSeek 餘額使用官方 `GET https://api.deepseek.com/user/balance`；聊天使用上述 chat endpoint。OpenAI 組織成本查詢需要 Admin API Key；Anthropic 成本查詢需要組織管理權限，因此目前聊天可用，但餘額頁會提示權限限制。

## 資產目錄

- `assets/sprite*.png`：完整 1536×1024 角色圖。
- `assets/deepseek_{front,side,back}.png`：正常 DeepSeek walking sprite。
- `assets/deepseek_dark_{front,side,back}.png`：黑化 DeepSeek walking sprite。
- `assets/legacy_chars/{claude,gemini,gpt}/sprites/`：舊表情差分。
- `custom_characters/`：匯入的自訂角色。
