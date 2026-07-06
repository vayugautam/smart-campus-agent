import pytest
from app.graph.graph import classify_intent
from langchain_core.messages import HumanMessage

@pytest.mark.asyncio
async def test_classify_intent():
    # We must have the GROQ_API_KEY environment variable set to run this test.
    # Otherwise, ChatGroq initialization or invocation will fail.
    
    # 6 example queries covering all 4 categories
    queries = [
        # event_query
        ("When is the next hackathon happening?", "event_query"),
        ("Are there any cultural festivals this weekend?", "event_query"),
        # facility_query
        ("Does the robotics lab have 3D printers?", "facility_query"),
        # booking_query
        ("I need to book study room A for tomorrow at 10 AM.", "booking_query"),
        ("Can I reserve the main auditorium?", "booking_query"),
        # unclear
        ("Hello, how are you?", "unclear"),
    ]
    
    for message_text, expected_intent in queries:
        state = {"messages": [HumanMessage(content=message_text)]}
        result = classify_intent(state)
        assert result["intent"] == expected_intent, f"Failed for query: '{message_text}'. Expected {expected_intent}, got {result['intent']}"
