from __future__ import annotations

import uuid
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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


class ConfirmRequest(BaseModel):
    thread_id: str
    confirmed: bool


# ── Endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Return a simple health-check response."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle an incoming chat message."""
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    graph_state = agent_graph.get_state(config)
    is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
    interrupt_text = ""
    if is_interrupted:
        interrupts = graph_state.tasks[0].interrupts
        if interrupts:
            interrupt_text = str(interrupts[0].value)

    if is_interrupted and "facility name" not in interrupt_text.lower():
        state = agent_graph.invoke(Command(resume=request.message), config=config)
    else:
        inputs = {"messages": [HumanMessage(content=request.message)]}
        state = agent_graph.invoke(inputs, config=config)
    
    # Check if graph is interrupted
    graph_state = agent_graph.get_state(config)
    is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
    
    messages = state.get("messages", [])
    reply_text = ""
    
    # Try to find the latest AI message
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
        thread_id=thread_id,
        waiting_on_confirmation=is_interrupted
    )


@app.post("/chat/confirm", response_model=ChatResponse)
async def chat_confirm(request: ConfirmRequest):
    """Resumes an interrupted graph after user confirms/declines a booking."""
    config = {"configurable": {"thread_id": request.thread_id}}
    
    # Resume the graph by passing the confirmation
    # Our graph expects "yes" or "no" or we can just pass the stringified bool
    # We pass the bool directly, which will be received by request_confirmation
    resume_val = "yes" if request.confirmed else "no"
    state = agent_graph.invoke(Command(resume=resume_val), config=config)
    
    graph_state = agent_graph.get_state(config)
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
