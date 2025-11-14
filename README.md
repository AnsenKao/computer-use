# 🤖 AI Computer Use - 完整版

## 📋 功能特色

✅ **遠端瀏覽器控制** - 透過 Canvas 實時顯示並操作遠端瀏覽器  
✅ **人類操作** - 點擊、鍵盤、滾動，完全控制  
✅ **AI 助手** - 透過自然語言指令讓 AI 自動操作瀏覽器  
✅ **WebSocket 串流** - 30 FPS 高品質截圖串流  
✅ **單一服務** - 只需運行一個 FastAPI 服務  
✅ **純 HTML 前端** - 無需框架，簡單高效  

---

## 🚀 快速開始

### 1. 啟動服務

```bash
# 方式一：使用啟動腳本
./start.sh

# 方式二：直接運行
python computer_use_backend.py
```

### 2. 打開瀏覽器

訪問：**http://localhost:8000**

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
