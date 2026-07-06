import uuid
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from app.graph.graph import build_graph
import sqlite3
import os

def test_booking_e2e():
    print("Testing baseline booking...")
    
    # Check DB state before booking
    db_path = "app/data/availability.db"
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # Find a completely free slot
    row = cur.execute("SELECT facility_id, date, start_time, end_time FROM slots WHERE is_booked=0 LIMIT 1").fetchone()
    
    if not row:
        print("No free slots found in the DB. Run python -m app.data.seed first.")
        return
        
    fac_id, book_date, stime, etime = row
    print(f"Found free slot: {fac_id} on {book_date} from {stime} to {etime}")
    
    agent_graph = build_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # We will simulate a booking intent query
    # To bypass LLM flakiness in testing, our previous hardcoded test used "tomorrow at 2 pm" vs "tomorrow at 10 am"
    # But wait, execute_booking has a stubbed facility_id right now in our test setup!
    # Ah! In graph.py, the previous session wrote a complex NLP extraction:
    # "resolved = resolve_facility_id(response_text...)"
    # That means the agent actually handles entity extraction!
    # Let me just run a generic request.
    
    inputs = {"messages": [HumanMessage(content=f"Book {fac_id} on {book_date} at 8 AM")]}
    print(f"Sending input: '{inputs['messages'][0].content}'")
    
    state = agent_graph.invoke(inputs, config=config)
    print("Intent:", state["intent"])
    
    # Check interrupt
    graph_state = agent_graph.get_state(config)
    is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
    
    print("Interrupted:", is_interrupted)
    if is_interrupted:
        interrupt_val = graph_state.tasks[0].interrupts[0].value
        print("Interrupt Message:", interrupt_val)
        print("Resuming with 'yes'...")
        
        state = agent_graph.invoke(Command(resume="yes"), config=config)
        print("Final message from agent:")
        print(state["messages"][-1].content)
        
        print("Booking Result Object:", state.get("booking_result"))
        
        # Verify in DB
        check_row = cur.execute("SELECT is_booked FROM slots WHERE facility_id=? AND date=? AND start_time=?", (fac_id, book_date, stime)).fetchone()
        print(f"DB is_booked value for this slot: {check_row[0]}")
    else:
        print("Agent did not interrupt for confirmation. Last message:")
        if state.get("messages"):
            print(state["messages"][-1].content)

if __name__ == "__main__":
    test_booking_e2e()
