# Desktop Pet（deskop-pet）

桌面寵物程式，使用 Python + PySide6 製作。本倉庫是 **VK-1** 的 fork，分支名稱為 `deskop-pet`。

## 功能

- **桌面角色**：透明無邊框、置頂、可拖曳、可調透明度與大小、自動貼邊、滑鼠穿透。
- **內建角色**：藍色大肥魚（DeepSeek，含黑化版與專屬表情）、GPT 龍娘、大小姐 Claude、北美貓娘 Gemini；可匯入自訂圖片角色。
- **額外行走角色**：最多 4 個 DeepSeek 三方向（正面／側面／背面）角色在桌面巡邏。
- **模擬模式**：隨機扣款／充值事件，充值時掉落飯盆，拖到角色身上即餵食。
- **API 模式**：DeepSeek 餘額查詢（`/user/balance`）。
- **AI 對話**：透過 LiteLLM 支援 DeepSeek、OpenAI、Google Gemini、Anthropic、Mistral、xAI、Groq、OpenRouter、Ollama、z.ai／GLM 與任意 OpenAI 相容端點；多組 API 設定檔、遠端模型列表查詢。
- **記憶**：短期記憶（預設最近 20 次對話）與長期記憶（手動編輯，不自動淘汰）。
- **語音**：Vosk 本機中文辨識、AI 語音辨識、pyttsx3／AI TTS、Gemini Live 純語音模式。
- **介面**：淺色／深色主題、系統匣選單、控制中心。

## 系統需求

- Windows 10/11
- Python 3.11 以上 3.14 以下 (核心依賴 PySide6 目前不支持 3.14)
- 麥克風（僅語音功能需要）

## 快速開始

```bat
cd windows\python
setup_venv.bat      :: 建立 .venv 並安裝依賴
start_pet.bat       :: 啟動（除錯用 start_pet_debug.bat）
```

使用 `traditional` 語音輸入前，先下載本機中文模型：

```bat
download_voice_model.bat
```

## 使用方式

- **右鍵角色**或使用系統匣圖示開啟選單。
- **控制中心**：角色與表情、外觀、模擬與事件紀錄、API 與對話。
- **API 設定檔**：填入供應商、Key、端點與模型 ID；可按「刷新模型列表」取得清單，也可手動輸入。
- **AI 對話**：需在選單開啟「AI 對話模式」，且設定檔有 Key（Ollama 除外）；否則改用隨機文句。
- **純語音（Gemini Live）**：使用 Google Gemini 設定檔的 Key；模型與聲音可在「語音與 TTS 設定」修改。

## 打包

```bat
build_windows.bat        :: 輸出 dist\PythonPetV4\PythonPetV4.exe
package_portable.bat     :: 另外壓縮成 release\PythonPetV4-portable.zip
```

## 專案結構

```
windows/python/
├─ main.py                  主程式（視窗、對話、語音、設定）
├─ model_catalog.py         各供應商模型列表查詢
├─ requirements.txt         依賴
├─ assets/                  角色圖片、圖示、音效
├─ docs/GEMINI_LIVE.md      Gemini Live 實作說明
└─ *.bat                    安裝、啟動、打包腳本
```

執行後會在程式目錄產生：`pet_config.json`（設定）、`voice_cache/`（錄音與語音輸出）、`custom_characters/`（匯入角色）。

## 注意事項

- `pet_config.json` 以**明文**儲存 API Key 與對話記憶，請勿提交或分享（已列入 `.gitignore`）。
- Gemini Live 預設模型名稱與各供應商預設模型可能隨時間下架，若報錯請在設定中改成目前可用的模型 ID。
- 餘額查詢目前僅支援 DeepSeek。
- Claude／Gemini／GPT 角色沒有行走用圖片，不支援額外行走角色。

## 授權與來源

本專案 fork 自 VK-1，授權條款請參照原專案與本倉庫的 LICENSE 檔案。
