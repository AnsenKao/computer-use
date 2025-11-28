# AI Computer Use with Browser-Use Integration

集成了 Azure Computer Use 和 Browser-Use 的智能瀏覽器自動化平台，提供兩種不同的 AI agent 選擇。

## ✨ 特色功能

- **雙 AI Agent 支持**: Computer Use (精確像素控制) + Browser-Use (智能網頁自動化)
- **共享瀏覽器實例**: 兩個 agent 使用同一個 Chromium 瀏覽器進程
- **即時 WebSocket 通信**: 實時查看 AI 執行過程
- **Web 界面**: 直觀的控制面板和狀態監控
- **Docker 部署**: 一鍵部署，包含所有依賴

## 🤖 AI Agent 比較

| 特性 | Computer Use | Browser-Use |
|------|-------------|-------------|
| 控制方式 | 像素級精確控制 | 高級瀏覽器 API |
| 適用場景 | 複雜視覺任務、非標準界面 | 標準網頁自動化、表單填寫 |
| 執行速度 | 較慢（需要截圖分析） | 較快（直接 DOM 操作） |
| 準確性 | 極高（視覺確認） | 高（元素定位） |
| 模型支持 | Azure Computer Use | OpenAI GPT-4o, Claude 等 |

## 🚀 快速開始

### Docker 部署 (推薦)

```bash
# 1. 克隆項目
git clone <your-repo-url>
cd computer-use

# 2. 設定環境變數
cp .env.example .env
# 編輯 .env 填入 API Keys:
# - AZURE_API_KEY (必需，用於 Computer Use)  
# - OPENAI_API_KEY (可選，用於 Browser-Use)

# 3. 構建並啟動服務
docker-compose up -d

# 4. 訪問應用
# WebUI: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### 本地開發

```bash
# 1. 創建虛擬環境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. 安裝依賴
pip install -r requirements.txt
playwright install chromium --with-deps

# 3. 設定環境變數
export AZURE_API_KEY=your-azure-key-here
export OPENAI_API_KEY=your-openai-key-here  # 可選

# 4. 啟動服務
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
