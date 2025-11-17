# 🤖 AI Computer Use - 完整版

## 📋 功能特色

✅ **遠端瀏覽器控制** - 透過 Canvas 實時顯示並操作遠端瀏覽器  
✅ **人類操作** - 點擊、鍵盤、滾動，完全控制  
✅ **AI 助手** - 透過自然語言指令讓 AI 自動操作瀏覽器  
✅ **WebSocket 串流** - 30 FPS 高品質截圖串流  
✅ **單一服務** - 只需運行一個 FastAPI 服務  
✅ **純 HTML 前端** - 無需框架，簡單高效  
✅ **Docker 支援** - 一鍵部署，包含完整瀏覽器環境  

---

## 🚀 快速開始

### 方式一：Docker 部署 (推薦)

這是最簡單的方式，包含完整的瀏覽器環境。

#### 1. 設定環境變數

```bash
# 複製環境變數範本
cp .env.example .env

# 編輯 .env 檔案，填入你的 Azure API Key
nano .env  # 或使用其他編輯器
```

#### 2. 構建 Docker 映像

```bash
./build.sh
```

#### 3. 啟動服務

```bash
# 方式 A：使用 Docker Compose (推薦)
docker-compose up -d

# 方式 B：使用啟動腳本
./run.sh

# 方式 C：手動運行
docker run -d \
  --name ai-computer-use \
  -p 8000:8000 \
  --shm-size=2g \
  -e AZURE_API_KEY=your-key-here \
  ai-computer-use:latest
```

#### 4. 查看日誌

```bash
# Docker Compose
docker-compose logs -f

# Docker 直接運行
docker logs -f ai-computer-use
```

#### 5. 停止服務

```bash
# Docker Compose
docker-compose down

# Docker 直接運行
docker stop ai-computer-use
docker rm ai-computer-use
```

### 方式二：本地開發

適合開發和測試。

#### 1. 安裝依賴

```bash
# 安裝 Python 套件
pip install -r requirements.txt

# 安裝 Playwright 瀏覽器
playwright install chromium
```

#### 2. 設定環境變數

```bash
export AZURE_API_KEY=your-azure-api-key-here
```

#### 3. 啟動服務

```bash
# 方式一：使用啟動腳本
./start.sh

# 方式二：直接運行
python computer_use_backend.py
```

#### 4. 打開瀏覽器

訪問：**http://localhost:8000**

---

## 🐳 Docker 詳細說明

### 映像特點

- **基於 Python 3.11**
- **包含 Chromium 瀏覽器** - 完整的 Playwright Chromium 安裝
- **虛擬顯示器** - 使用 Xvfb 提供 X11 顯示環境
- **視窗管理器** - 使用 Fluxbox 輕量級視窗管理器
- **PyAutoGUI 支援** - 完整的 GUI 自動化功能
- **健康檢查** - 自動監控服務狀態

### 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `AZURE_API_KEY` | Azure OpenAI API Key | (必填) |
| `AZURE_ENDPOINT` | Azure OpenAI 端點 | `https://abscgpt01...` |
| `MODEL_DEPLOYMENT` | 模型部署名稱 | `computer-use-preview` |
| `SCREEN_WIDTH` | 虛擬螢幕寬度 | `1920` |
| `SCREEN_HEIGHT` | 虛擬螢幕高度 | `1080` |
| `SCREEN_DEPTH` | 色彩深度 | `24` |

### 資源需求

- **CPU**: 建議 2 核心以上
- **記憶體**: 建議 4GB 以上
- **磁碟空間**: 約 2GB (映像大小)
- **共享記憶體**: 2GB (Chromium 需要)

### 埠號

- `8000` - FastAPI Web 服務
- `5900` - VNC 埠 (可選，用於遠端查看瀏覽器畫面)

---

## 🎮 使用方式

### 人類控制模式

- **滑鼠點擊** → 直接點擊 Canvas 上的任何位置
- **鍵盤輸入** → 在 Canvas 上按任意鍵
- **滾動** → 在 Canvas 上使用滾輪

### AI 控制模式

1. 在右下角的 **AI 助手面板** 輸入指令
2. 點擊「發送」或按 Enter
3. AI 會自動執行任務，你可以看到：
   - 實時截圖更新
   - AI 執行的動作
   - AI 的思考過程
4. 點擊「停止」可隨時中斷

### AI 指令範例

```
在 Google 搜尋 "FastAPI 教學"
打開 GitHub 並搜尋 "computer use"
填寫這個表單並送出
幫我在這個網站上找到聯絡資訊
```

---

## 📡 API 端點

### REST API

- `GET /` - 前端頁面
- `GET /api/status` - 服務狀態
- `GET /screenshot` - 獲取當前截圖
- `GET /state` - 獲取系統狀態
- `POST /ai/start` - 啟動 AI 任務
- `POST /ai/stop` - 停止 AI 任務
- `GET /history` - 獲取操作歷史
- `POST /history/clear` - 清除歷史

### WebSocket

- `ws://localhost:8000/ws/screenshot` - 即時截圖串流和互動

完整 API 文檔：http://localhost:8000/docs

---

## 🔧 進階配置

### 啟用 VNC 遠端查看

如果你想要直接查看 Docker 容器內的瀏覽器畫面：

1. 取消註解 `Dockerfile` 中的 VNC 相關行
2. 在 `docker-compose.yml` 中暴露 5900 埠
3. 使用 VNC 客戶端連接 `localhost:5900`

```bash
# 在 Dockerfile 中取消註解這一行
# x11vnc -display :99 -forever -nopw -quiet -rfbport 5900 &
```

### 自訂螢幕解析度

在 `.env` 或 `docker-compose.yml` 中修改：

```env
SCREEN_WIDTH=2560
SCREEN_HEIGHT=1440
```

### 資源限制

在 `docker-compose.yml` 中調整：

```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
```

---

## 🛠 開發

### 專案結構

```
computer-use/
├── computer_use_backend.py   # FastAPI 後端服務
├── requirements.txt           # Python 依賴
├── static/
│   └── index.html            # 前端 HTML
├── Dockerfile                # Docker 映像定義
├── docker-compose.yml        # Docker Compose 配置
├── .dockerignore             # Docker 忽略檔案
├── .env.example              # 環境變數範本
├── build.sh                  # 構建腳本
├── run.sh                    # 運行腳本
└── README.md                 # 說明文件
```

### 重新構建映像

```bash
# 清理舊映像
docker-compose down
docker rmi ai-computer-use:latest

# 重新構建
./build.sh

# 啟動
docker-compose up -d
```

---

## ⚠️ 注意事項

1. **Azure API Key** - 請確保已設定有效的 Azure OpenAI API Key
2. **安全性** - 此服務允許 AI 控制瀏覽器，請在受信任的環境中使用
3. **資源消耗** - 瀏覽器和 AI 模型會消耗較多資源
4. **網路存取** - 確保容器可以訪問 Azure OpenAI 端點
5. **共享記憶體** - Chromium 需要足夠的共享記憶體 (`--shm-size=2g`)

---

## 📄 授權

MIT License

---

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

---

## 📞 支援

如有問題，請在 GitHub 上開 Issue。

```
搜尋台灣天氣
打開 GitHub 並登入
在 Google 搜尋 Python 教學
填寫表單並提交
```

---

## 📁 專案結構

```
.
├── computer_use_backend.py   # FastAPI 後端（所有邏輯）
├── static/
│   └── index.html             # 前端 UI（單一 HTML）
├── start.sh                   # 啟動腳本
└── README_FULL.md             # 本文件
```

---

## 🔧 技術架構

### 後端 (FastAPI)
- **Playwright** - 瀏覽器自動化
- **OpenAI Computer Use** - Azure AI 模型
- **WebSocket** - 實時雙向通信
- **Python asyncio** - 異步處理

### 前端 (純 HTML)
- **Canvas API** - 顯示截圖
- **WebSocket API** - 與後端通信
- **原生 JavaScript** - 無框架依賴

---

## 🎯 優勢

### vs Flask 版本
- ✅ 少一層中間層（Flask）
- ✅ 延遲更低
- ✅ 架構更簡潔
- ✅ 只需運行一個服務
- ✅ 部署更容易

### vs 框架版本
- ✅ 無需 React/Vue
- ✅ 代碼更少
- ✅ 加載更快
- ✅ 維護成本低

---

## 📊 WebSocket 訊息格式

### 前端 → 後端

```javascript
// 點擊
{ "type": "click", "x": 100, "y": 200 }

// 按鍵
{ "type": "keypress", "key": "a", "ctrl": false, "shift": false, "alt": false }

// 滾動
{ "type": "scroll", "deltaY": 100 }

// 啟動 AI
{ "type": "ai_start", "task": "搜尋台灣天氣" }

// 停止 AI
{ "type": "ai_stop" }
```

### 後端 → 前端

```javascript
// 截圖
{ "type": "screenshot", "image": "base64...", "width": 1280, "height": 900, "url": "..." }

// AI 狀態
{ "type": "ai_status", "status": "starting|stopped" }

// AI 訊息
{ "type": "ai_message", "message": "..." }

// AI 動作
{ "type": "ai_action", "action": "click", "iteration": 1 }
```

---

## 🔐 安全提示

⚠️ **本項目包含 API 密鑰，僅供開發測試使用**

生產環境請：
1. 將 API 密鑰移至環境變數
2. 添加身份驗證
3. 限制 CORS
4. 使用 HTTPS

---

## 🐛 常見問題

### Q: 無法連接 WebSocket？
A: 確保 FastAPI 服務正在運行，檢查瀏覽器控制台錯誤

### Q: AI 沒有反應？
A: 檢查 Azure API 密鑰是否有效，查看後端日誌

### Q: Canvas 沒有顯示？
A: 檢查 WebSocket 連接狀態，確認截圖串流正常

---

## 📝 開發提示

### 修改前端
編輯 `static/index.html` 即可，無需重啟服務（刷新瀏覽器）

### 修改後端
編輯 `computer_use_backend.py`，FastAPI 會自動重載

### 調整截圖 FPS
修改 `computer_use_backend.py` 第 103 行：
```python
await asyncio.sleep(0.033)  # 30 FPS
```

---

## 🎨 自定義

### 修改 Canvas 大小
修改 `computer_use_backend.py` 第 19-20 行：
```python
DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 900
```

### 修改 AI Panel 位置
編輯 `static/index.html` CSS `#ai-panel` 部分

---

## 📄 授權

本專案僅供學習和研究使用。

---

**享受 AI 控制瀏覽器的樂趣！** 🚀
