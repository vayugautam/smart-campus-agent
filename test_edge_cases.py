import uuid
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from app.graph.graph import build_graph

def run_edge_cases():
    agent_graph = build_graph()
    
    # Test 1: Double-booking an already-booked slot
    print("\n--- Test 1: Double-booking ---")
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    # From previous tests, fac-001 at 08:00 on 2026-07-20 was booked or is booked by seed
    # Let's just ask to book a generic slot that we know is booked or will be rejected
    inputs = {"messages": [HumanMessage(content="Book the robotics lab for tomorrow at 2 PM")]}
    state = agent_graph.invoke(inputs, config=config)
    print("Intent:", state["intent"])
    print("Availability result:", state.get("availability_result"))
    print("Messages after double booking attempt:")
    print(state["messages"][-1].content if state.get("messages") else "No message")

    # Test 2: Unrelated query
    print("\n--- Test 2: Unrelated query ---")
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"messages": [HumanMessage(content="What's the weather like today?")]}
    state = agent_graph.invoke(inputs, config=config)
    print("Intent:", state["intent"])
    print("Messages for unrelated query:")
    print(state["messages"][-1].content if state.get("messages") else "No message")

    # Test 3: Decline a booking
    print("\n--- Test 3: Decline a booking ---")
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    # Let's trigger a valid booking request to get to the interrupt
    inputs = {"messages": [HumanMessage(content="Book the library for tomorrow at 10 AM.")]}
    state = agent_graph.invoke(inputs, config=config)
    
    graph_state = agent_graph.get_state(config)
    is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
    print("Is Interrupted (waiting for confirm):", is_interrupted)
    
    if is_interrupted:
        print("Interrupt message:", graph_state.tasks[0].interrupts[0].value)
        print("Sending 'No'...")
        state = agent_graph.invoke(Command(resume="no"), config=config)
        print("Confirmed:", state.get("confirmed"))
        print("Messages after decline:")
        print(state["messages"][-1].content if state.get("messages") else "No message")

if __name__ == "__main__":
    run_edge_cases()
