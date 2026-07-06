"""
event_info.py – Event Information Tool.

A LangChain tool that performs FAISS-based RAG over the campus event
documents.  Given a natural-language query, it retrieves the most
relevant events and returns structured summaries.
"""

from __future__ import annotations


def build_event_vectorstore():
    """Build (or load) a FAISS vector store from events.json.

    Steps:
        1. Load events from mock_db.
        2. Convert each event into a LangChain Document.
        3. Embed documents using the configured embedding model.
        4. Create and return a FAISS vectorstore.

    Returns:
        A FAISS vectorstore instance ready for similarity search.
    """
    pass


def search_events(query: str, k: int = 3) -> list[dict]:
    """Retrieve the top-k events most relevant to the user query.

    Args:
        query: Natural-language search string from the user.
        k: Number of results to return (default 3).

    Returns:
        A list of event dicts ranked by relevance.
    """
    pass


def event_info_tool(query: str) -> str:
    """LangChain-compatible tool function for event information retrieval.

    This is the callable that will be registered with the LangGraph
    ToolNode.  It wraps `search_events` and formats the output as a
    human-readable string for the LLM response-generation node.

    Args:
        query: The user's event-related question.

    Returns:
        A formatted string describing matching events.
    """
    pass
