# Python 安全依賴

因應 2026 年 10 月 eMudhra／emSign CA 事件，請先執行 `update_python_security.bat`，再執行 `build_windows.bat`。專案安全下限為 `pip>=26.2.2`、`certifi>=2026.10.19`；啟動時會使用 certifi CA bundle。詳見 [SECURITY.md](SECURITY.md)。

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

## 多模型、LiteLLM 與 API 供應商

聊天層使用 LiteLLM，將不同廠商統一成 `completion()` 呼叫；設定檔中的「模型」使用 LiteLLM provider prefix，而不是把所有廠商硬套成同一個 endpoint。聊天框仍可在多組設定檔之間切換。

目前供應商選單包含：

- DeepSeek、OpenAI、Google Gemini、Anthropic、Mistral。
- xAI / Grok、z.ai、GLM。
- Ollama、Ollama Cloud。
- OpenRouter、Cloudflare AI、Groq、Hugging Face。
- Kiwi、OpenCode、OpenAI-compatible 自訂端點。

常見模型設定例子：

| 服務 | LiteLLM model 範例 | API Key / 端點 |
| --- | --- | --- |
| Gemini | `gemini/gemini-2.5-flash` | Gemini API Key |
| OpenRouter | `openrouter/auto` 或 `openrouter/anthropic/claude-3.5-sonnet` | OpenRouter Key |
| Groq | `groq/llama-3.3-70b-versatile` | Groq Key |
| xAI / Grok | `xai/grok-3-mini` | xAI Key |
| Ollama | `ollama/llama3.2` | 通常不需要 Key，可填 `http://localhost:11434` |
| Ollama Cloud | `ollama_chat/llama3.2` | Ollama Cloud Key，可填官方 base URL |
| Cloudflare AI | `cloudflare/@cf/meta/llama-3.1-8b-instruct` | Cloudflare 憑證／端點依 LiteLLM 設定 |
| Hugging Face | `huggingface/meta-llama/Llama-3.1-8B-Instruct` | HF Token |

Kiwi、OpenCode 或任何 LiteLLM 尚未涵蓋的服務，請在模型欄填入對應 provider prefix；只有真正的 OpenAI-compatible 服務才填 `openai/模型名` 加自訂 `api_base`。這樣可以保留各家不同的認證、URL 與回應格式，不再假設所有服務都支援相同 API。

LiteLLM 已加入 `requirements.txt`，PyInstaller 會收集其 provider 子模組。餘額查詢仍由各家原生 endpoint 處理，因為 LiteLLM 統一的是模型呼叫，不是各平台的 billing／balance API。

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
