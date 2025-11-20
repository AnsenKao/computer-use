# AI Computer Use

## 🚀 快速開始

### Docker 部署

```bash
# 1. 設定環境變數
cp .env.example .env
# 編輯 .env 填入 Azure API Key

# 2. 構建映像
./build.sh

# 3. 啟動服務
docker-compose up -d

# 訪問: http://localhost:8000
```

### 本地開發

```bash
# 1. 安裝依賴
pip install -r requirements.txt
playwright install chromium

# 2. 設定環境變數
export AZURE_API_KEY=your-key-here

# 3. 啟動服務
python computer_use_backend.py
```

---

## 🏗 專案結構

```
computer-use/
├── computer_use_backend.py   # FastAPI 後端服務
├── requirements.txt           # Python 依賴
├── static/
│   └── index.html            # 前端 UI
├── Dockerfile                # Docker 映像定義
├── docker-compose.yml        # Docker Compose 配置
└── README.md                 # 說明文件
```

---

## 🔧 技術架構

### 後端 (FastAPI)
- **Playwright** - 瀏覽器自動化
- **pyautoGUI** - 模擬鍵鼠操作
- **Azure OpenAI** - Computer Use API
- **WebSocket** - 實時雙向通信
- **asyncio** - 異步處理

### 前端 (純 HTML)
- **Canvas API** - 顯示截圖
- **WebSocket API** - 與後端通信
- **原生 JavaScript** - 無框架依賴

### Docker 環境
- **Python 3.11** 基礎映像
- **Chromium** - Playwright 瀏覽器
- **Xvfb** - 虛擬顯示器
- **Fluxbox** - 輕量級視窗管理器

---

## 🐳 Docker 配置

### 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `AZURE_API_KEY` | Azure OpenAI API Key | (必填) |
| `AZURE_ENDPOINT` | Azure OpenAI 端點 | - |
| `MODEL_DEPLOYMENT` | 模型部署名稱 | `computer-use-preview` |
| `SCREEN_WIDTH` | 虛擬螢幕寬度 | `1920` |
| `SCREEN_HEIGHT` | 虛擬螢幕高度 | `1080` |

---

## 📡 API 架構

### REST Endpoints
- `GET /` - 前端頁面
- `GET /api/status` - 服務狀態
- `GET /screenshot` - 當前截圖
- `POST /ai/start` - 啟動 AI 任務
- `POST /ai/stop` - 停止 AI 任務

### WebSocket
- `ws://localhost:8000/ws/screenshot` - 即時截圖串流和互動

### 訊息格式

```javascript
// 前端 → 後端
{ "type": "click", "x": 100, "y": 200 }
{ "type": "keypress", "key": "a" }
{ "type": "ai_start", "task": "搜尋內容" }

// 後端 → 前端
{ "type": "screenshot", "image": "base64..." }
{ "type": "ai_status", "status": "starting" }
{ "type": "ai_action", "action": "click" }
```
