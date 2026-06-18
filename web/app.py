import os
import json
import queue
import threading
from typing import Dict, Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

from agent.core import run_agent, AgentEventHandler

load_dotenv()

app = FastAPI(title="ReAct AI Agent Dashboard")

# Templates setup
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Active SSE session tracking for HITL responses
class WebAgentEventHandler(AgentEventHandler):
    """Event handler that pushes execution events to a thread-safe queue for SSE delivery."""
    def __init__(self, sse_queue: queue.Queue):
        self.sse_queue = sse_queue
        self.hitl_event = threading.Event()
        self.hitl_approved = False
        
    def _send(self, event: str, data: dict):
        self.sse_queue.put({"event": event, "data": data})

    def on_plan_created(self, plan: str):
        self._send("plan", {"plan": plan})

    def on_step_start(self, step: int, max_steps: int):
        self._send("step_start", {"step": step, "max_steps": max_steps})

    def on_thought(self, step: int, thought: str):
        self._send("thought", {"step": step, "thought": thought})

    def on_action(self, step: int, tool_name: str, tool_input: dict):
        self._send("action", {"step": step, "tool_name": tool_name, "tool_input": tool_input})

    def on_hitl_request(self, tool_name: str, tool_input: dict) -> bool:
        self.hitl_event.clear()
        self._send("hitl_request", {"tool_name": tool_name, "tool_input": tool_input})
        # Wait until client calls the approve endpoint
        self.hitl_event.wait()
        return self.hitl_approved

    def on_observation(self, step: int, observation: str):
        self._send("observation", {"step": step, "observation": observation})

    def on_complete(self, final_answer: str):
        self._send("complete", {"final_answer": final_answer})
        self.sse_queue.put(None)  # Sentinel to close connection

    def on_timeout(self, max_steps: int):
        self._send("timeout", {"max_steps": max_steps})
        self.sse_queue.put(None)

    def on_error(self, error_msg: str):
        self._send("error", {"error_msg": error_msg})
        self.sse_queue.put(None)


# Dictionary mapping run sessions to event handlers
active_sessions: Dict[str, WebAgentEventHandler] = {}
session_lock = threading.Lock()

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Serves the dashboard home page."""
    # Check what providers have keys configured to display status on the UI
    has_gemini = bool(os.getenv("GEMINI_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    default_provider = os.getenv("LLM_PROVIDER", "gemini")
    
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "has_gemini": has_gemini,
            "has_openai": has_openai,
            "default_provider": default_provider
        }
    )

@app.get("/api/run")
def run_agent_api(
    task: str,
    max_steps: int = 10,
    enable_planning: bool = True,
    provider: str = "gemini"
):
    """API endpoint that runs the agent loop and returns an SSE stream of results."""
    if not task:
        raise HTTPException(status_code=400, detail="Task query cannot be empty.")

    # Override LLM provider for this execution thread
    os.environ["LLM_PROVIDER"] = provider
    
    sse_queue = queue.Queue()
    handler = WebAgentEventHandler(sse_queue)
    
    # For simplicity, we use a single key since it's running locally, 
    # but we support scaling by assigning a session ID
    session_id = "default_session"
    with session_lock:
        active_sessions[session_id] = handler

    # Start the core run_agent in a separate thread
    def run_worker():
        run_agent(
            task=task,
            max_steps=max_steps,
            enable_planning=enable_planning,
            event_handler=handler
        )
        # Ensure lock cleanup after run
        with session_lock:
            active_sessions.pop(session_id, None)

    thread = threading.Thread(target=run_worker)
    thread.start()

    def sse_generator():
        while True:
            try:
                # Wait for next update with timeout to keep connection alive
                item = sse_queue.get(timeout=30)
                if item is None:
                    break
                yield f"event: {item['event']}\ndata: {json.dumps(item['data'])}\n\n"
            except queue.Empty:
                # Heartbeat to keep connection alive
                yield "event: heartbeat\ndata: {}\n\n"
            except Exception:
                break

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@app.post("/api/approve")
def approve_action(payload: dict):
    """API endpoint to receive HITL confirmations from the Web interface."""
    session_id = "default_session"
    approved = payload.get("approved", False)
    
    with session_lock:
        handler = active_sessions.get(session_id)
        
    if not handler:
        raise HTTPException(status_code=400, detail="No active agent session is waiting for approval.")

    handler.hitl_approved = approved
    handler.hitl_event.set()
    return {"status": "success", "approved": approved}
