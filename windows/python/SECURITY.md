# Python TLS 安全更新

本專案針對 2026 年 10 月 eMudhra／emSign 中間 CA 私鑰外洩事件設定安全基線。Python 官方公告指出，舊版 pip 會繼續使用自身 vendored certifi CA bundle；只更新 Windows 系統信任庫不足以修復風險。

目前安全下限：

- `pip >= 26.2.2`
- `certifi >= 2026.10.19`

目前驗證到的 PyPI 版本為 `pip 26.2.2` 與 `certifi 2026.10.23`。依賴檔使用 `>=`，讓之後重新安裝時取得當時最新版本。

Windows 使用者請先執行：

```bat
update_python_security.bat
```

再執行：

```bat
build_windows.bat
```

`update_python_security.bat` 會先使用 Python 官方公告提供的 SHA-256 鎖定 pip wheel，再更新 certifi；打包程式啟動時也會把 Python HTTPS 的 `SSL_CERT_FILE`／`REQUESTS_CA_BUNDLE` 指向 certifi CA bundle。

這不能取代 Windows Update。請同時維持 Windows 根憑證、Python 本身與瀏覽器更新；若系統仍使用受影響的 CA 憑證，請不要忽略作業系統安全更新。
