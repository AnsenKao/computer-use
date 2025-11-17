

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import base64
import asyncio
from typing import Optional, List, Set
from playwright.async_api import async_playwright, TimeoutError
from openai import OpenAI
import time
import json
import os
import threading

# Lazy import pyautogui to avoid X display connection at import time
pyautogui = None

def _ensure_pyautogui():
    """Lazy load pyautogui when needed."""
    global pyautogui
    if pyautogui is None:
        import pyautogui as _pyautogui
        _pyautogui.FAILSAFE = True
        _pyautogui.PAUSE = 0.1
        pyautogui = _pyautogui
    return pyautogui

# Azure AI Configuration
AZURE_ENDPOINT = "https://abscgpt01.cognitiveservices.azure.com/openai/v1/"
AZURE_API_KEY = os.getenv("AZURE_API_KEY", "your-azure-api-key-here")
MODEL_DEPLOYMENT = "computer-use-preview"

# Display settings - 從環境變數讀取或使用預設值
DISPLAY_WIDTH = int(os.getenv("SCREEN_WIDTH", "1920"))
DISPLAY_HEIGHT = int(os.getenv("SCREEN_HEIGHT", "1080"))
INITIAL_URL = os.getenv("INITIAL_URL", "about:blank")
MAX_AI_ITERATIONS = 10

# Browser window offset - auto-calibrated at startup
# Accounts for window manager title bar and browser chrome
BROWSER_OFFSET_X = 0
BROWSER_OFFSET_Y = 0

# Global browser instances
playwright = None
browser = None
context = None
page = None
openai_client = None

# Global state for AI/Human arbitration
state = {
    "mode": "idle",       # idle / ai / human
    "last_human": 0,      # last human action timestamp
    "task": None,         # current AI task
    "ai_running": False,  # is AI currently executing
    "current_response_id": None,  # current AI response ID
    "iteration_count": 0,  # current iteration
    "last_screenshot": None,  # cache last successful screenshot
    "history": [],  # action history
}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.streaming_task: Optional[asyncio.Task] = None
        self.streaming = False

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        # Start streaming if not already started
        if not self.streaming and not self.streaming_task:
            self.streaming_task = asyncio.create_task(self.stream_screenshots())

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        # Stop streaming if no connections
        if not self.active_connections and self.streaming_task:
            self.streaming = False

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            self.active_connections.discard(conn)

    async def stream_screenshots(self):
        """Background task to continuously stream screenshots."""
        self.streaming = True
        print(f"🎬 WebSocket 串流已啟動（{len(self.active_connections)} 個連接）")
        
        frame_count = 0
        while self.streaming and self.active_connections:
            try:
                # Take screenshot
                screenshot_b64 = await take_screenshot_safe()
                
                # Broadcast to all connected clients
                await self.broadcast({
                    "type": "screenshot",
                    "image": screenshot_b64,
                    "width": DISPLAY_WIDTH,
                    "height": DISPLAY_HEIGHT,
                    "url": page.url if page else None,
                    "mode": state["mode"],
                    "timestamp": time.time()
                })
                
                frame_count += 1
                
                # 每 300 幀（約 10 秒）報告一次狀態
                if frame_count % 300 == 0:
                    print(f"📊 串流狀態: {frame_count} 幀已發送，{len(self.active_connections)} 個連接")
                
                # Adjust FPS (30 FPS = ~33ms delay)
                await asyncio.sleep(0.033)
                
            except Exception as e:
                print(f"❌ Screenshot streaming error: {e}")
                await asyncio.sleep(0.1)
        
        self.streaming = False
        self.streaming_task = None
        print(f"⏹ WebSocket 串流已停止（共發送 {frame_count} 幀）")

manager = ConnectionManager()

# Key mapping for special keys in Playwright
KEY_MAPPING = {
    "/": "Slash", "\\": "Backslash", "alt": "Alt", "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft", "arrowright": "ArrowRight", "arrowup": "ArrowUp",
    "backspace": "Backspace", "ctrl": "Control", "delete": "Delete", 
    "enter": "Enter", "esc": "Escape", "shift": "Shift", "space": " ",
    "tab": "Tab", "win": "Meta", "cmd": "Meta", "super": "Meta", "option": "Alt"
}

# Request/Response models
class AITaskRequest(BaseModel):
    task: str
    max_iterations: Optional[int] = MAX_AI_ITERATIONS


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    global playwright, browser, context, page, openai_client
    
    # Startup
    # Initialize OpenAI client
    openai_client = OpenAI(
        base_url=AZURE_ENDPOINT,
        api_key=AZURE_API_KEY
    )
    print("OpenAI client initialized")

    # Initialize Playwright
    playwright = await async_playwright().start()

    # Launch browser in fullscreen
    try:
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--start-fullscreen",
                "--kiosk",
                f"--window-size={DISPLAY_WIDTH},{DISPLAY_HEIGHT}",
                f"--window-position=0,0",
                "--disable-extensions",
                "--disable-infobars",
                "--no-default-browser-check",
                "--disable-popup-blocking"
            ]
        )
    except Exception as e:
        print(f"Failed to launch default browser: {e}")
        print("Trying with executable path...")
        browser = await playwright.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=False,
            args=[
                "--start-fullscreen",
                "--kiosk",
                f"--window-size={DISPLAY_WIDTH},{DISPLAY_HEIGHT}",
                f"--window-position=0,0",
                "--disable-extensions",
                "--disable-infobars",
                "--no-default-browser-check",
                "--disable-popup-blocking"
            ]
        )

    context = await browser.new_context(
        viewport={"width": DISPLAY_WIDTH, "height": DISPLAY_HEIGHT},
        accept_downloads=True,
        no_viewport=True  # 不限制 viewport，使用全螢幕
    )

    page = await context.new_page()
    await page.goto(INITIAL_URL)
    
    # Auto-calibrate coordinate offset between Playwright and PyAutoGUI
    try:
        # Get viewport information
        viewport_info = await page.evaluate("""
            () => {
                const rect = document.documentElement.getBoundingClientRect();
                return {
                    // Window position on screen
                    screenX: window.screenX || 0,
                    screenY: window.screenY || 0,
                    
                    // Window dimensions
                    outerWidth: window.outerWidth,
                    outerHeight: window.outerHeight,
                    innerWidth: window.innerWidth,
                    innerHeight: window.innerHeight,
                    
                    // Viewport offset within the window
                    viewportOffsetX: window.pageXOffset || 0,
                    viewportOffsetY: window.pageYOffset || 0,
                    
                    // Document element position
                    docLeft: rect.left,
                    docTop: rect.top
                };
            }
        """)
        
        print(f"📐 Viewport info: {viewport_info}")
        
        global BROWSER_OFFSET_X, BROWSER_OFFSET_Y
        
        # Initial values from JavaScript (usually 0 in Docker kiosk mode)
        BROWSER_OFFSET_X = viewport_info.get('screenX', 0)
        BROWSER_OFFSET_Y = viewport_info.get('screenY', 0)
        
        print(f"📍 Browser offset (from JS): X={BROWSER_OFFSET_X}px, Y={BROWSER_OFFSET_Y}px")
        print(f"📏 Viewport size: {viewport_info.get('innerWidth')}x{viewport_info.get('innerHeight')}")
        print(f"🖥  Window position: ({viewport_info.get('screenX')}, {viewport_info.get('screenY')})")
        print(f"🔍 Window dimensions: outer={viewport_info.get('outerWidth')}x{viewport_info.get('outerHeight')}, inner={viewport_info.get('innerWidth')}x{viewport_info.get('innerHeight')}")
        
        # Auto-calibrate offset by testing actual click position
        print("🔧 Auto-calibrating browser offset...")
        try:
            # Add a visible marker at page coordinate (100, 100)
            await page.evaluate("""
                () => {
                    const marker = document.createElement('div');
                    marker.id = 'calibration-marker';
                    marker.style.cssText = `
                        position: fixed;
                        left: 100px;
                        top: 100px;
                        width: 20px;
                        height: 20px;
                        background: red;
                        border: 2px solid yellow;
                        z-index: 999999;
                        pointer-events: none;
                    `;
                    document.body.appendChild(marker);
                }
            """)
            
            # Use Playwright to click at page coordinate (100, 100)
            await page.mouse.click(100, 100)
            
            # Wait a moment
            import asyncio
            await asyncio.sleep(0.3)
            
            # Get the actual click position detected by the browser
            click_result = await page.evaluate("""
                () => {
                    return new Promise(resolve => {
                        let detected = null;
                        const handler = (e) => {
                            detected = { x: e.clientX, y: e.clientY };
                        };
                        document.addEventListener('click', handler, { once: true });
                        
                        // Trigger click at (100, 100) from pyautogui
                        setTimeout(() => {
                            document.removeEventListener('click', handler);
                            resolve(detected);
                        }, 2000);
                    });
                }
            """)
            
            # Now use pyautogui to click at screen coordinate (100, 100)
            pg = _ensure_pyautogui()
            print("🖱  Testing pyautogui click at screen (100, 100)...")
            execute_pyautogui_action(lambda: pg.click(100, 100))
            
            # Wait for the click to be detected
            await asyncio.sleep(0.5)
            
            # Check where the click landed in page coordinates
            click_result = await page.evaluate("""
                () => {
                    const clicks = window.__lastClick;
                    return clicks || null;
                }
            """)
            
            # Set up click tracking
            await page.evaluate("""
                () => {
                    window.__lastClick = null;
                    document.addEventListener('click', (e) => {
                        window.__lastClick = { x: e.clientX, y: e.clientY };
                    });
                }
            """)
            
            # Click with pyautogui at screen (100, 100)
            execute_pyautogui_action(lambda: pg.click(100, 100))
            await asyncio.sleep(0.3)
            
            # Get where it landed in page coordinates
            click_result = await page.evaluate("() => window.__lastClick")
            
            if click_result:
                page_x = click_result['x']
                page_y = click_result['y']
                
                # Calculate offset: screen_pos - page_pos = offset
                measured_offset_x = 100 - page_x
                measured_offset_y = 100 - page_y
                
                print("📏 Calibration result:")
                print("   PyAutoGUI clicked at screen: (100, 100)")
                print(f"   Browser detected click at page: ({page_x}, {page_y})")
                print(f"   Calculated offset: X={measured_offset_x}px, Y={measured_offset_y}px")
                
                # Use measured offset if reasonable
                if -200 <= measured_offset_x <= 200 and -200 <= measured_offset_y <= 200:
                    BROWSER_OFFSET_X = int(measured_offset_x)
                    BROWSER_OFFSET_Y = int(measured_offset_y)
                    print(f"✅ Applied calibrated offset: X={BROWSER_OFFSET_X}px, Y={BROWSER_OFFSET_Y}px")
                else:
                    print("⚠️  Measured offset seems unreasonable, using default (0, 0)")
            else:
                print("⚠️  Could not detect calibration click")
            
            # Remove calibration marker
            await page.evaluate("() => document.getElementById('calibration-marker')?.remove()")
            
        except Exception as calib_error:
            print(f"⚠️  Auto-calibration failed: {calib_error}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Failed to get viewport info: {e}")
        import traceback
        traceback.print_exc()
        BROWSER_OFFSET_X = 0
        BROWSER_OFFSET_Y = 0  # Default to no offset
        print(f"⚠️  Using default offset: X={BROWSER_OFFSET_X}, Y={BROWSER_OFFSET_Y}")
    
    print(f"✅ Browser initialized at {page.url}")
    print(f"🖼  Screen size: {DISPLAY_WIDTH}x{DISPLAY_HEIGHT}")
    print(f"🎯 Final browser offset: X={BROWSER_OFFSET_X}px, Y={BROWSER_OFFSET_Y}px")
    
    yield
    
    # Shutdown
    if context:
        await context.close()
    if browser:
        await browser.close()
    if playwright:
        await playwright.stop()
    print("Browser and playwright closed")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Azure AI Computer Use Backend",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory (for serving index.html)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
    
# Serve static files
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the main HTML frontend."""
    static_file = os.path.join(static_dir, "index.html")
    if os.path.exists(static_file):
        with open(static_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Frontend not found. Please create static/index.html</h1>", status_code=404)


def validate_coordinates(x: int, y: int) -> tuple:
    """Ensure coordinates are within display bounds."""
    return max(0, min(x, DISPLAY_WIDTH)), max(0, min(y, DISPLAY_HEIGHT))


async def take_screenshot_safe():
    """Take a screenshot with caching for failures."""
    global state
    
    try:
        png = await page.screenshot(type="png", full_page=False)
        state["last_screenshot"] = base64.b64encode(png).decode("utf-8")
        return state["last_screenshot"]
    except Exception as e:
        # 只在真正失敗且沒有緩存時才 log
        if not state["last_screenshot"]:
            print(f"❌ Screenshot failed: {e}")
        if state["last_screenshot"]:
            return state["last_screenshot"]
        raise


async def run_ai_task_background(task: str):
    """Run AI task in background and broadcast progress via WebSocket."""
    try:
        # Take initial screenshot
        screenshot_b64 = await take_screenshot_safe()
        
        # Initial request to AI model
        response = openai_client.responses.create(
            model=MODEL_DEPLOYMENT,
            tools=[{
                "type": "computer_use_preview",
                "display_width": DISPLAY_WIDTH,
                "display_height": DISPLAY_HEIGHT,
                "environment": "browser"
            }],
            instructions="You are an AI agent with the ability to control a browser. You can control the keyboard and mouse. You take a screenshot after each action to check if your action was successful. Once you have completed the requested task you should stop running and pass back control to your human operator.",
            input=[{
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": task
                }, {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{screenshot_b64}"
                }]
            }],
            reasoning={"generate_summary": "concise"},
            truncation="auto"
        )
        
        state["current_response_id"] = response.id
        
        # Execute AI task loop
        for iteration in range(MAX_AI_ITERATIONS):
            if not state["ai_running"]:
                break
                
            state["iteration_count"] = iteration + 1
            
            # Get current response
            response = openai_client.responses.retrieve(response_id=state["current_response_id"])
            
            # Check if there's output
            if not hasattr(response, 'output') or not response.output:
                await manager.broadcast({
                    "type": "ai_message",
                    "message": "✅ AI 任務完成",
                    "status": "completed"
                })
                break
            
            # Extract text and reasoning
            text_messages = []
            for item in response.output:
                if hasattr(item, 'type') and item.type == "text":
                    text_messages.append(item.text)
            
            # Broadcast AI messages
            if text_messages:
                await manager.broadcast({
                    "type": "ai_message",
                    "message": "\n".join(text_messages),
                    "iteration": state["iteration_count"]
                })
            
            # Extract computer calls
            computer_calls = [item for item in response.output 
                             if hasattr(item, 'type') and item.type == "computer_call"]
            
            if not computer_calls:
                await manager.broadcast({
                    "type": "ai_message",
                    "message": "✅ AI 任務完成",
                    "status": "completed"
                })
                break
            
            computer_call = computer_calls[0]
            if not hasattr(computer_call, 'call_id') or not hasattr(computer_call, 'action'):
                break
            
            call_id = computer_call.call_id
            action = computer_call.action
            
            # Broadcast action info
            await manager.broadcast({
                "type": "ai_action",
                "action": action.type,
                "iteration": state["iteration_count"]
            })
            
            # Execute the action
            await page.bring_to_front()
            await handle_ai_action(action)
            
            # Handle new tabs/pages
            if action.type in ["click"]:
                await asyncio.sleep(1.5)
                all_pages = page.context.pages
                if len(all_pages) > 1:
                    newest_page = all_pages[-1]
                    if newest_page != page and newest_page.url not in ["about:blank", ""]:
                        globals()['page'] = newest_page
            elif action.type != "wait":
                await asyncio.sleep(0.5)
            
            # Take screenshot after action
            screenshot_b64 = await take_screenshot_safe()
            
            # Check for safety checks
            acknowledged_checks = []
            if hasattr(computer_call, 'pending_safety_checks') and computer_call.pending_safety_checks:
                acknowledged_checks = computer_call.pending_safety_checks
            
            # Prepare input for next request
            input_content = [{
                "type": "computer_call_output",
                "call_id": call_id,
                "output": {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{screenshot_b64}"
                }
            }]
            
            if acknowledged_checks:
                input_content[0]["acknowledged_safety_checks"] = [
                    {"id": c.id, "code": c.code, "message": c.message}
                    for c in acknowledged_checks
                ]
            
            # Send screenshot back for next step
            next_response = openai_client.responses.create(
                model=MODEL_DEPLOYMENT,
                previous_response_id=response.id,
                tools=[{
                    "type": "computer_use_preview",
                    "display_width": DISPLAY_WIDTH,
                    "display_height": DISPLAY_HEIGHT,
                    "environment": "browser"
                }],
                input=input_content,
                truncation="auto"
            )
            
            state["current_response_id"] = next_response.id
            
    except Exception as e:
        print(f"❌ AI task error: {e}")
        await manager.broadcast({
            "type": "ai_message",
            "message": f"❌ 錯誤: {str(e)}",
            "status": "error"
        })
    finally:
        state["ai_running"] = False
        state["mode"] = "idle"
        await manager.broadcast({
            "type": "ai_status",
            "status": "stopped"
        })


def execute_pyautogui_action(func):
    """在新執行緒中執行 pyautogui 動作以避免阻塞"""
    _ensure_pyautogui()  # Ensure pyautogui is loaded
    thread = threading.Thread(target=func)
    thread.start()
    thread.join()

async def handle_ai_action(action):
    """Handle different action types from the AI model using pyautogui."""
    action_type = action.type
    pg = _ensure_pyautogui()  # Ensure pyautogui is loaded
    
    if action_type == "drag":
        print("Drag action not supported yet")
        return
        
    elif action_type == "click":
        button = getattr(action, "button", "left")
        x_raw, y_raw = action.x, action.y
        
        # Add browser window offset (same logic as user clicks)
        x = x_raw + BROWSER_OFFSET_X
        y = y_raw + BROWSER_OFFSET_Y
        
        x, y = validate_coordinates(x, y)
        
        print(f"  AI 點擊: 截圖座標=({x_raw}, {y_raw}), 螢幕座標=({x}, {y}), button='{button}'")
        
        if button == "back":
            await page.go_back()
        elif button == "forward":
            await page.go_forward()
        elif button == "wheel":
            # 滾輪操作
            execute_pyautogui_action(lambda: pg.scroll(-100, x, y))
        else:
            # 使用 pyautogui 進行點擊
            button_map = {"left": "left", "right": "right", "middle": "middle"}
            pyautogui_button = button_map.get(button, "left")
            execute_pyautogui_action(lambda: pg.click(x, y, button=pyautogui_button))
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=3000)
            except TimeoutError:
                pass
        
    elif action_type == "double_click":
        x_raw, y_raw = action.x, action.y
        
        # Add browser window offset
        x = x_raw + BROWSER_OFFSET_X
        y = y_raw + BROWSER_OFFSET_Y
        
        x, y = validate_coordinates(x, y)
        print(f"  AI 雙擊: 截圖座標=({x_raw}, {y_raw}), 螢幕座標=({x}, {y})")
        execute_pyautogui_action(lambda: pg.doubleClick(x, y))
        
    elif action_type == "scroll":
        scroll_x = getattr(action, "scroll_x", 0)
        scroll_y = getattr(action, "scroll_y", 0)
        x_raw, y_raw = action.x, action.y
        
        # Add browser window offset
        x = x_raw + BROWSER_OFFSET_X
        y = y_raw + BROWSER_OFFSET_Y
        
        x, y = validate_coordinates(x, y)
        
        print(f"  AI 滾動: 截圖座標=({x_raw}, {y_raw}), 螢幕座標=({x}, {y}), offset=({scroll_x}, {scroll_y})")
        # 移動滑鼠到指定位置再滾動
        execute_pyautogui_action(lambda: pg.moveTo(x, y, duration=0.1))
        # pyautogui.scroll 的參數是滾動的「刻度」，負數向下
        scroll_amount = int(-scroll_y / 10)  # 轉換為滾動刻度
        execute_pyautogui_action(lambda: pg.scroll(scroll_amount))
        
    elif action_type == "keypress":
        keys = getattr(action, "keys", [])
        print(f"  AI Action: keypress {keys}")
        
        # PyAutoGUI 按鍵映射
        pyautogui_key_map = {
            "ctrl": "ctrl", "control": "ctrl", "shift": "shift", "alt": "alt",
            "cmd": "command", "super": "command", "win": "command", "meta": "command",
            "enter": "enter", "return": "enter", "backspace": "backspace",
            "tab": "tab", "esc": "escape", "escape": "escape",
            "space": "space", " ": "space",
            "arrowup": "up", "arrowdown": "down", "arrowleft": "left", "arrowright": "right",
            "delete": "delete", "home": "home", "end": "end",
            "pageup": "pageup", "pagedown": "pagedown"
        }
        
        mapped_keys = [pyautogui_key_map.get(key.lower(), key.lower()) for key in keys]
        
        if len(mapped_keys) > 1:
            # 組合鍵
            execute_pyautogui_action(lambda: pg.hotkey(*mapped_keys))
        else:
            # 單一按鍵
            execute_pyautogui_action(lambda: pg.press(mapped_keys[0]))
                
    elif action_type == "type":
        text = getattr(action, "text", "")
        print(f"  AI Action: type text: {text[:50]}...")
        # 使用 pyautogui 輸入文字
        execute_pyautogui_action(lambda: pg.write(text, interval=0.02))
        
    elif action_type == "wait":
        ms = getattr(action, "ms", 1000)
        print(f"  AI Action: wait {ms}ms")
        await asyncio.sleep(ms / 1000)
        
    elif action_type == "screenshot":
        print("  AI Action: screenshot")
        
    else:
        print(f"  Unrecognized action: {action_type}")
    
    # Record action in history
    state["history"].append({
        "type": action_type,
        "timestamp": time.time(),
        "mode": "ai"
    })


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/status")
async def api_status():
    """API status and info."""
    return {
        "status": "running",
        "version": "1.0.0",
        "mode": state["mode"],
        "ai_running": state["ai_running"],
        "current_task": state["task"]
    }


@app.get("/screenshot")
async def screenshot():
    """Get current browser screenshot."""
    screenshot_b64 = await take_screenshot_safe()
    return {
        "image": screenshot_b64,
        "width": DISPLAY_WIDTH,
        "height": DISPLAY_HEIGHT,
        "url": page.url if page else None,
        "mode": state["mode"]
    }


@app.websocket("/ws/screenshot")
async def websocket_screenshot(websocket: WebSocket):
    """
    WebSocket endpoint for streaming screenshots and handling user interactions.
    Continuously sends screenshots to connected clients at ~30 FPS.
    Also handles incoming user actions (click, keypress, scroll, AI commands).
    """
    client_id = id(websocket)
    print(f"🔌 WebSocket 客戶端連接: {client_id}")
    
    await manager.connect(websocket)
    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive any messages (e.g., control commands, user actions)
                data = await websocket.receive_text()
                message = json.loads(data)
                message_type = message.get("type")
                
                # Handle control messages
                if message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    
                elif message_type == "get_state":
                    await websocket.send_json({
                        "type": "state",
                        "mode": state["mode"],
                        "ai_running": state["ai_running"],
                        "connections": len(manager.active_connections)
                    })
                
                # Handle user interactions
                elif message_type == "click":
                    state["mode"] = "human"
                    state["last_human"] = time.time()
                    x_raw, y_raw = message.get("x", 0), message.get("y", 0)
                    
                    # 調整點擊座標
                    # Playwright screenshot 只截取頁面內容 (innerWidth x innerHeight)
                    # 但 pyautogui 點擊是相對於螢幕，需要加上瀏覽器視窗的偏移量
                    x = x_raw + BROWSER_OFFSET_X
                    y = y_raw + BROWSER_OFFSET_Y
                    
                    x, y = validate_coordinates(x, y)
                    print(f"👆 點擊: 截圖座標=({x_raw}, {y_raw}), 螢幕座標=({x}, {y}), 偏移=({BROWSER_OFFSET_X}, {BROWSER_OFFSET_Y})")
                    try:
                        pg = _ensure_pyautogui()
                        execute_pyautogui_action(lambda: pg.click(x, y))
                        print("   點擊執行完成")
                    except Exception as e:
                        print(f"   ❌ 點擊執行錯誤: {e}")
                        import traceback
                        traceback.print_exc()
                    
                elif message_type == "keypress":
                    state["mode"] = "human"
                    state["last_human"] = time.time()
                    key = message.get("key", "")
                    ctrl = message.get("ctrl", False)
                    shift = message.get("shift", False)
                    alt = message.get("alt", False)
                    
                    # Type text or press keys using pyautogui
                    pg = _ensure_pyautogui()
                    if len(key) == 1 and key.isprintable() and not ctrl and not alt:
                        execute_pyautogui_action(lambda: pg.write(key, interval=0.02))
                    else:
                        keys = []
                        if ctrl:
                            keys.append('ctrl')
                        if shift:
                            keys.append('shift')
                        if alt:
                            keys.append('alt')
                        
                        # PyAutoGUI 按鍵映射
                        pyautogui_key_map = {
                            'Enter': 'enter', 'Backspace': 'backspace', 'Tab': 'tab',
                            'Escape': 'escape', 'ArrowUp': 'up', 'ArrowDown': 'down',
                            'ArrowLeft': 'left', 'ArrowRight': 'right',
                            'Delete': 'delete', ' ': 'space'
                        }
                        
                        mapped_key = pyautogui_key_map.get(key, key.lower() if len(key) == 1 else None)
                        if mapped_key:
                            keys.append(mapped_key)
                        
                        if keys:
                            if len(keys) > 1:
                                execute_pyautogui_action(lambda: pg.hotkey(*keys))
                            else:
                                execute_pyautogui_action(lambda: pg.press(keys[0]))
                    
                elif message_type == "scroll":
                    state["mode"] = "human"
                    state["last_human"] = time.time()
                    delta_y = message.get("deltaY", 0)
                    await page.evaluate(f"window.scrollBy(0, {delta_y});")
                
                # Handle AI commands
                elif message_type == "ai_start":
                    task = message.get("task", "")
                    if task and not state["ai_running"]:
                        # Start AI task
                        state["mode"] = "ai"
                        state["task"] = task
                        state["ai_running"] = True
                        state["iteration_count"] = 0
                        
                        # Broadcast AI status
                        await manager.broadcast({
                            "type": "ai_status",
                            "status": "starting",
                            "task": task
                        })
                        
                        # Start AI task in background
                        asyncio.create_task(run_ai_task_background(task))
                        
                elif message_type == "ai_stop":
                    if state["ai_running"]:
                        state["ai_running"] = False
                        state["mode"] = "idle"
                        await manager.broadcast({
                            "type": "ai_status",
                            "status": "stopped"
                        })
                
                # Handle navigation commands
                elif message_type == "navigate":
                    url = message.get("url", "")
                    if url:
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=10000)
                            print(f"🌐 Navigated to: {url}")
                        except Exception as e:
                            print(f"❌ Navigation error: {e}")
                
                elif message_type == "back":
                    try:
                        await page.go_back(wait_until="domcontentloaded", timeout=5000)
                        print("◀ Go back")
                    except Exception as e:
                        print(f"❌ Back navigation error: {e}")
                
                elif message_type == "forward":
                    try:
                        await page.go_forward(wait_until="domcontentloaded", timeout=5000)
                        print("▶ Go forward")
                    except Exception as e:
                        print(f"❌ Forward navigation error: {e}")
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                # 只 log 非正常斷線的錯誤
                if "disconnect" not in str(e).lower():
                    print(f"❌ WebSocket error: {e}")
                break
                
    finally:
        manager.disconnect(websocket)
        print(f"🔌 WebSocket 客戶端斷線: {client_id}，剩餘 {len(manager.active_connections)} 個連接")


@app.get("/state")
async def get_state():
    """Get current system state."""
    return {
        "mode": state["mode"],
        "ai_running": state["ai_running"],
        "task": state["task"],
        "iteration_count": state["iteration_count"],
        "history_length": len(state["history"]),
        "current_url": page.url if page else None,
        "browser_offset": {
            "x": BROWSER_OFFSET_X,
            "y": BROWSER_OFFSET_Y
        }
    }


@app.post("/ai/start")
async def ai_start(request: AITaskRequest):
    """
    Start an AI task with Azure Computer Use model.
    This initializes the task and returns immediately.
    Use /ai/tick to step through execution.
    """
    if state["ai_running"]:
        return {
            "status": "error",
            "message": "AI task already running. Stop it first with /ai/stop"
        }
    
    # Reset state
    state["mode"] = "ai"
    state["task"] = request.task
    state["ai_running"] = True
    state["iteration_count"] = 0
    state["current_response_id"] = None
    
    # Take initial screenshot
    screenshot_b64 = await take_screenshot_safe()
    
    # Initial request to AI model
    try:
        response = openai_client.responses.create(
            model=MODEL_DEPLOYMENT,
            tools=[{
                "type": "computer_use_preview",
                "display_width": DISPLAY_WIDTH,
                "display_height": DISPLAY_HEIGHT,
                "environment": "browser"
            }],
            instructions="You are an AI agent with the ability to control a browser. You can control the keyboard and mouse. You take a screenshot after each action to check if your action was successful. Once you have completed the requested task you should stop running and pass back control to your human operator.",
            input=[{
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": request.task
                }, {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{screenshot_b64}"
                }]
            }],
            reasoning={"generate_summary": "concise"},
            truncation="auto"
        )
        
        state["current_response_id"] = response.id
        
        return {
            "status": "started",
            "task": request.task,
            "response_id": response.id,
            "max_iterations": request.max_iterations,
            "message": "AI task started. Use /ai/tick to execute steps."
        }
        
    except Exception as e:
        state["ai_running"] = False
        state["mode"] = "idle"
        return {
            "status": "error",
            "message": f"Failed to start AI task: {str(e)}"
        }


@app.post("/ai/stop")
async def ai_stop():
    """Stop the currently running AI task."""
    was_running = state["ai_running"]
    
    state["ai_running"] = False
    state["mode"] = "idle"
    state["current_response_id"] = None
    
    return {
        "status": "stopped",
        "was_running": was_running,
        "iterations_completed": state["iteration_count"],
        "task": state["task"]
    }


@app.get("/history")
async def get_history(limit: int = 50):
    """Get action history."""
    return {
        "history": state["history"][-limit:],
        "total": len(state["history"])
    }


@app.post("/history/clear")
async def clear_history():
    """Clear action history."""
    count = len(state["history"])
    state["history"] = []
    return {
        "status": "cleared",
        "items_removed": count
    }


if __name__ == "__main__":
    import uvicorn
    
    print("="*60)
    print("  Azure AI Computer Use Backend")
    print("="*60)
    print()
    print("Starting server...")
    print("  API: http://localhost:8000")
    print("  Docs: http://localhost:8000/docs")
    print("  ReDoc: http://localhost:8000/redoc")
    print()
    print("Press Ctrl+C to stop")
    print("="*60)
    print()
    
    uvicorn.run(
        "computer_use_backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )