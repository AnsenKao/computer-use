

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

# Azure AI Configuration
AZURE_ENDPOINT = "https://abscgpt01.cognitiveservices.azure.com/openai/v1/"
AZURE_API_KEY = os.getenv("AZURE_API_KEY", "your-azure-api-key-here")
MODEL_DEPLOYMENT = "computer-use-preview"

# Display settings
DISPLAY_WIDTH = 1280
DISPLAY_HEIGHT = 900
MAX_AI_ITERATIONS = 10

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

# Request/Response models (kept for backward compatibility with HTTP API)
class NavigateRequest(BaseModel):
    url: str

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

    # Launch browser (macOS - using system Chrome/Chromium)
    try:
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                f"--window-size={DISPLAY_WIDTH},{DISPLAY_HEIGHT}",
                "--disable-extensions"
            ]
        )
    except Exception as e:
        print(f"Failed to launch default browser: {e}")
        print("Trying with executable path...")
        browser = await playwright.chromium.launch(
            executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            headless=False,
            args=[
                f"--window-size={DISPLAY_WIDTH},{DISPLAY_HEIGHT}",
                "--disable-extensions"
            ]
        )

    context = await browser.new_context(
        viewport={"width": DISPLAY_WIDTH, "height": DISPLAY_HEIGHT},
        accept_downloads=True
    )

    page = await context.new_page()
    await page.goto("https://www.google.com")
    print(f"Browser initialized at {page.url}")
    
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


async def handle_ai_action(action):
    """Handle different action types from the AI model."""
    action_type = action.type
    
    if action_type == "drag":
        print("Drag action not supported yet")
        return
        
    elif action_type == "click":
        button = getattr(action, "button", "left")
        x, y = validate_coordinates(action.x, action.y)
        
        print(f"  AI Action: click at ({x}, {y}) with button '{button}'")
        
        if button == "back":
            await page.go_back()
        elif button == "forward":
            await page.go_forward()
        elif button == "wheel":
            await page.mouse.wheel(x, y)
        else:
            button_type = {"left": "left", "right": "right", "middle": "middle"}.get(button, "left")
            await page.mouse.click(x, y, button=button_type)
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=3000)
            except TimeoutError:
                pass
        
    elif action_type == "double_click":
        x, y = validate_coordinates(action.x, action.y)
        print(f"  AI Action: double click at ({x}, {y})")
        await page.mouse.dblclick(x, y)
        
    elif action_type == "scroll":
        scroll_x = getattr(action, "scroll_x", 0)
        scroll_y = getattr(action, "scroll_y", 0)
        x, y = validate_coordinates(action.x, action.y)
        
        print(f"  AI Action: scroll at ({x}, {y}) with offsets ({scroll_x}, {scroll_y})")
        await page.mouse.move(x, y)
        await page.evaluate(f"window.scrollBy({{left: {scroll_x}, top: {scroll_y}, behavior: 'smooth'}});")
        
    elif action_type == "keypress":
        keys = getattr(action, "keys", [])
        print(f"  AI Action: keypress {keys}")
        mapped_keys = [KEY_MAPPING.get(key.lower(), key) for key in keys]
        
        if len(mapped_keys) > 1:
            for key in mapped_keys:
                await page.keyboard.down(key)
            await asyncio.sleep(0.1)
            for key in reversed(mapped_keys):
                await page.keyboard.up(key)
        else:
            for key in mapped_keys:
                await page.keyboard.press(key)
                
    elif action_type == "type":
        text = getattr(action, "text", "")
        print(f"  AI Action: type text: {text[:50]}...")
        await page.keyboard.type(text, delay=20)
        
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
                    x, y = validate_coordinates(message.get("x", 0), message.get("y", 0))
                    await page.mouse.click(x, y)
                    print(f"👆 Click at ({x}, {y})")
                    
                elif message_type == "keypress":
                    state["mode"] = "human"
                    state["last_human"] = time.time()
                    key = message.get("key", "")
                    ctrl = message.get("ctrl", False)
                    shift = message.get("shift", False)
                    alt = message.get("alt", False)
                    
                    # Map special keys
                    key_map = {
                        'Enter': 'enter', 'Backspace': 'backspace', 'Tab': 'tab',
                        'Escape': 'esc', 'ArrowUp': 'arrowup', 'ArrowDown': 'arrowdown',
                        'ArrowLeft': 'arrowleft', 'ArrowRight': 'arrowright',
                        'Delete': 'delete', ' ': 'space'
                    }
                    
                    # Type text or press keys
                    if len(key) == 1 and key.isprintable() and not ctrl and not alt:
                        await page.keyboard.type(key, delay=20)
                    else:
                        keys = []
                        if ctrl: keys.append('ctrl')
                        if shift: keys.append('shift')
                        if alt: keys.append('alt')
                        
                        mapped_key = key_map.get(key, key.lower() if len(key) == 1 else None)
                        if mapped_key:
                            keys.append(mapped_key)
                        
                        if keys:
                            mapped_keys = [KEY_MAPPING.get(k.lower(), k) for k in keys]
                            if len(mapped_keys) > 1:
                                for k in mapped_keys:
                                    await page.keyboard.down(k)
                                await asyncio.sleep(0.1)
                                for k in reversed(mapped_keys):
                                    await page.keyboard.up(k)
                            else:
                                for k in mapped_keys:
                                    await page.keyboard.press(k)
                    
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
        "current_url": page.url if page else None
    }


@app.post("/goto")
async def navigate(request: NavigateRequest):
    """Navigate to a URL."""
    try:
        await page.goto(request.url, wait_until="domcontentloaded", timeout=10000)
        state["history"].append({
            "type": "navigate",
            "url": request.url,
            "timestamp": time.time(),
            "mode": state["mode"]
        })
        return {
            "status": "ok",
            "url": page.url,
            "title": await page.title()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
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