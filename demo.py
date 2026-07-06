import uuid
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.types import Command
from app.graph.graph import build_graph

def run_demo():
    print("Initializing Campus Agent...")
    agent_graph = build_graph()
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    print("Agent is ready! (Type 'quit' or 'exit' to stop)\n")
    
    while True:
        try:
            user_input = input("User: ")
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
            
        if user_input.strip().lower() in ["quit", "exit"]:
            break
            
        # Check if the graph is currently interrupted
        graph_state = agent_graph.get_state(config)
        is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
        
        try:
            if is_interrupted:
                # We are providing a confirmation resume value
                state = agent_graph.invoke(Command(resume=user_input), config=config)
            else:
                inputs = {"messages": [HumanMessage(content=user_input)]}
                state = agent_graph.invoke(inputs, config=config)
                
            # Check if graph is interrupted AFTER the invoke
            graph_state = agent_graph.get_state(config)
            is_interrupted = len(graph_state.tasks) > 0 and any(task.interrupts for task in graph_state.tasks)
            
            if is_interrupted:
                interrupt_val = graph_state.tasks[0].interrupts[0].value
                print(f"\nAgent (Interrupt): {interrupt_val}")
            else:
                messages = state.get("messages", [])
                for msg in reversed(messages):
                    if isinstance(msg, AIMessage):
                        print(f"\nAgent: {msg.content}")
                        break
            print("-" * 50)
            
        except Exception as e:
            print(f"\n[Error executing graph]: {e}")
            print("-" * 50)

if __name__ == "__main__":
    run_demo()
