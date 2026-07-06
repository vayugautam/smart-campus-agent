import pytest
import uuid
from unittest.mock import patch
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from app.data.seed import seed
from app.graph.graph import build_graph

@pytest.fixture
def agent_graph():
    return build_graph()

@pytest.mark.asyncio
async def test_event_info_query(agent_graph):
    """Scenario 1: A pure event info query (no booking flow triggered)"""
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    inputs = {"messages": [HumanMessage(content="When is the next hackathon?")]}
    
    state = agent_graph.invoke(inputs, config=config)
    
    # Verify intent
    assert state["intent"] == "event_query"
    # Verify we visited the retrieval node
    assert state.get("retrieved_context") is not None
    
    # Verify we are NOT interrupted
    graph_state = agent_graph.get_state(config)
    is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
    assert not is_interrupted

@pytest.mark.asyncio
async def test_booking_available_and_confirm(agent_graph):
    """Scenario 2: A booking query where the slot is available and the user confirms"""
    seed()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    inputs = {"messages": [HumanMessage(content="Book the Main Auditorium for tomorrow at 8 AM.")]}
    
    # Run the graph against a real seeded slot.
    state = agent_graph.invoke(inputs, config=config)
    
    assert state["intent"] == "booking_query"
    
    # Verify we are interrupted
    graph_state = agent_graph.get_state(config)
    is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
    assert is_interrupted
    
    # Resume with confirmation
    state = agent_graph.invoke(Command(resume="yes"), config=config)
    
    # Verify execution finished and booking was executed
    assert state["confirmed"] is True
    assert state.get("booking_result") is not None
    assert state["booking_result"]["success"] is True
    
    # Ensure it's no longer interrupted
    graph_state_after = agent_graph.get_state(config)
    is_interrupted_after = len(graph_state_after.tasks) > 0 and any(task.interrupts for task in graph_state_after.tasks)
    assert not is_interrupted_after

@pytest.mark.asyncio
async def test_booking_unavailable():
    """Scenario 3: A booking query where the slot is unavailable and alternatives are suggested"""
    # We patch check_constraints to return available=False before building the graph
    with patch("app.graph.graph.check_constraints", return_value={"availability_result": {"available": False, "conflicts": []}}):
        agent_graph = build_graph()
        
        config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        inputs = {"messages": [HumanMessage(content="Book the main auditorium for tomorrow at 2 PM.")]}
        
        state = agent_graph.invoke(inputs, config=config)
        
        assert state["intent"] == "booking_query"
        assert state["availability_result"]["available"] is False
        
        # Verify it went straight to generation and did NOT interrupt
        graph_state = agent_graph.get_state(config)
        is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
        assert not is_interrupted


@pytest.mark.asyncio
async def test_booking_clarification_resume_uses_stored_context(agent_graph):
    """Scenario 4: A booking query that needs facility clarification resumes from stored date/time context."""
    seed()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    inputs = {"messages": [HumanMessage(content="Book the lab for tomorrow at 8 AM.")]}

    state = agent_graph.invoke(inputs, config=config)
    assert state["intent"] == "booking_query"
    assert state["pending_clarification"]["target"] == "check_constraints"

    state = agent_graph.invoke({"messages": [HumanMessage(content="Computer Lab 1")]}, config=config)

    assert state["intent"] == "booking_query"
    assert state["availability_result"]["requested_slot"]["facility"]["name"] == "Computer Lab 1"


@pytest.mark.asyncio
async def test_facility_clarification_resume_uses_stored_context(agent_graph):
    """Scenario 5: A facility info query resumes from the clarification interrupt without re-classifying."""
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    inputs = {"messages": [HumanMessage(content="Tell me about the lab.")]}

    state = agent_graph.invoke(inputs, config=config)
    assert state["intent"] == "facility_query"
    assert state["pending_clarification"]["target"] == "generate_response"

    state = agent_graph.invoke({"messages": [HumanMessage(content="Computer Lab 1")]}, config=config)

    assert state["intent"] == "facility_query"
    assert state["retrieved_context"]["matches"][0]["name"] == "Computer Lab 1"
