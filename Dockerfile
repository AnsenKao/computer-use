# 使用 Python 3.11 作為基礎映像
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 安裝系統依賴 (用於 Playwright 和 GUI 操作)
RUN apt-get update && apt-get install -y \
    # Playwright 瀏覽器依賴
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    # PyAutoGUI 依賴
    python3-tk \
    python3-dev \
    scrot \
    xvfb \
    x11vnc \
    fluxbox \
    x11-utils \
    # 清理
    && rm -rf /var/lib/apt/lists/*

# 設定顯示環境變數
ENV DISPLAY=:99
ENV SCREEN_WIDTH=1920
ENV SCREEN_HEIGHT=1080
ENV SCREEN_DEPTH=24

# 複製 requirements
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 安裝 Microsoft Edge (使用新的 GPG 金鑰方法)
RUN wget -q https://packages.microsoft.com/keys/microsoft.asc -O /tmp/microsoft.asc \
    && gpg --dearmor < /tmp/microsoft.asc > /usr/share/keyrings/microsoft-edge.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft-edge.gpg] https://packages.microsoft.com/repos/edge stable main" > /etc/apt/sources.list.d/microsoft-edge.list \
    && apt-get update \
    && apt-get install -y microsoft-edge-stable \
    && rm -rf /var/lib/apt/lists/* /tmp/microsoft.asc

# 安裝 Playwright 瀏覽器（msedge channel）
RUN playwright install msedge
RUN playwright install-deps msedge

# 複製應用程式碼
COPY . .

# 創建啟動腳本
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# 清理舊的 X server lock\n\
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99\n\
\n\
# 創建 .Xauthority 檔案（使用 -ac 選項禁用訪問控制，因此不需要 xauth）\n\
touch ~/.Xauthority\n\
chmod 600 ~/.Xauthority\n\
\n\
# 啟動虛擬顯示器（-ac 禁用訪問控制）\n\
echo "Starting Xvfb..."\n\
Xvfb :99 -screen 0 ${SCREEN_WIDTH}x${SCREEN_HEIGHT}x${SCREEN_DEPTH} -ac +extension GLX +render -noreset &\n\
XVFB_PID=$!\n\
\n\
# 等待 X server 啟動並確認可用\n\
echo "Waiting for X server..."\n\
for i in {1..30}; do\n\
    if xdpyinfo -display :99 >/dev/null 2>&1; then\n\
        echo "X server is ready!"\n\
        break\n\
    fi\n\
    if [ $i -eq 30 ]; then\n\
        echo "Failed to start X server"\n\
        exit 1\n\
    fi\n\
    sleep 0.5\n\
done\n\
\n\
# 啟動視窗管理器\n\
echo "Starting window manager..."\n\
fluxbox &\n\
sleep 1\n\
\n\
# (可選) 啟動 VNC 伺服器\n\
# x11vnc -display :99 -forever -nopw -quiet -rfbport 5900 &\n\
\n\
# 啟動 FastAPI 應用\n\
echo "Starting FastAPI application..."\n\
exec python computer_use_backend.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# 暴露端口
EXPOSE 8000
# EXPOSE 5900  # VNC port (如果需要的話)

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/status')" || exit 1

# 啟動應用
CMD ["/app/start.sh"]
