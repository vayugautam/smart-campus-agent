from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Resolve the data directory relative to this file so the server works
# regardless of the working-directory it is launched from.
_DATA_DIR = Path(__file__).parent.parent / "data"

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from app.graph.graph import build_graph

# Initialize graph globally
agent_graph = build_graph()

app = FastAPI(
    title="Campus Agent API",
    description="LangGraph-powered campus assistant for events, facilities, and bookings.",
    version="0.1.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response schemas ───────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    thread_id: str
    waiting_on_confirmation: bool = False
    clarification_candidates: list = []


class ConfirmRequest(BaseModel):
    thread_id: str
    confirmed: bool
    is_clarification: bool = False
    clarification_text: str = ""


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Return a simple health-check response."""
    return {"status": "ok"}


@app.get("/events")
async def get_events():
    """
    Return the full list of campus events.

    Pure file-read — no LLM, no agent, no FAISS.
    Response shape (array of objects):
      [
        {
          "id": str,              # e.g. "evt-001"
          "name": str,
          "date": str,            # ISO-8601 date, e.g. "2026-07-20"
          "time": str,            # 24-hr "HH:MM"
          "venue": str,
          "description": str,
          "category": str,        # "academic" | "technology" | "cultural" |
                                  # "sports" | "networking" | "social"
          "registration_required": bool
        },
        ...
      ]
    """
    events = json.loads((_DATA_DIR / "events.json").read_text(encoding="utf-8"))
    return JSONResponse(content=events)


@app.get("/facilities")
async def get_facilities():
    """
    Return the full list of campus facilities.

    Pure file-read — no LLM, no agent, no FAISS.
    Response shape (array of objects):
      [
        {
          "id": str,              # e.g. "fac-001"
          "name": str,
          "type": str,            # "auditorium" | "seminar_hall" | "computer_lab" |
                                  # "science_lab" | "conference_room" |
                                  # "discussion_room" | "sports_facility" |
                                  # "amphitheatre" | "studio"
          "capacity": int,
          "location": str,
          "equipment": [str],     # list of equipment strings
          "bookable": bool
        },
        ...
      ]
    """
    facilities = json.loads((_DATA_DIR / "facilities.json").read_text(encoding="utf-8"))
    return JSONResponse(content=facilities)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle an incoming chat message."""
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    graph_state = await agent_graph.aget_state(config)
    is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
    
    if is_interrupted:
        state = await agent_graph.ainvoke(Command(resume=request.message), config=config)
    else:
        inputs = {"messages": [HumanMessage(content=request.message)]}
        state = await agent_graph.ainvoke(inputs, config=config)
    
    # Check if graph is interrupted
    graph_state = await agent_graph.aget_state(config)
    is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
    
    messages = state.get("messages", [])
    reply_text = ""
    
    # Try to find the latest AI message
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            reply_text = msg.content
            break
            
    candidates = []
    waiting_on_confirmation = False

    if is_interrupted:
        interrupts = graph_state.tasks[0].interrupts
        if interrupts:
            reply_text = str(interrupts[0].value)
            # Check if this interrupt is a clarification request (candidates attached to state)
            pending_clarification = state.get("pending_clarification")
            if pending_clarification and "Please clarify the facility name" in reply_text:
                candidates = [fac["name"] for fac in pending_clarification.get("candidates", [])]
            else:
                waiting_on_confirmation = True
    
    return ChatResponse(
        reply=reply_text,
        thread_id=thread_id,
        waiting_on_confirmation=waiting_on_confirmation,
        clarification_candidates=candidates
    )


@app.post("/chat/confirm", response_model=ChatResponse)
async def chat_confirm(request: ConfirmRequest):
    """Resumes an interrupted graph after user confirms/declines a booking."""
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # Resume the graph by passing the confirmation
    # Our graph expects "yes" or "no" or we can just pass the stringified bool
    # We pass the bool directly, which will be received by request_confirmation
    resume_val = "yes" if request.confirmed else "no"
    state = await agent_graph.ainvoke(Command(resume=resume_val), config=config)
    
    graph_state = await agent_graph.aget_state(config)
    is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
    
    messages = state.get("messages", [])
    reply_text = ""
    
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            reply_text = msg.content
            break
            
    if is_interrupted:
        interrupts = graph_state.tasks[0].interrupts
        if interrupts:
            reply_text = str(interrupts[0].value)
            
    return ChatResponse(
        reply=reply_text,
        thread_id=request.thread_id,
        waiting_on_confirmation=is_interrupted
    )
