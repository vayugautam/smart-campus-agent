"""
facility_info.py – Facility Information Tool.

A LangChain tool that performs FAISS-based RAG or structured lookup
over campus facility records.  Supports queries by name, type, building,
capacity, or free-text description.
"""

from __future__ import annotations


def build_facility_vectorstore():
    """Build (or load) a FAISS vector store from facilities.json.

    Steps:
        1. Load facilities from mock_db.
        2. Convert each facility into a LangChain Document.
        3. Embed documents using the configured embedding model.
        4. Create and return a FAISS vectorstore.

    Returns:
        A FAISS vectorstore instance ready for similarity search.
    """
    pass


def search_facilities(query: str, k: int = 3) -> list[dict]:
    """Retrieve the top-k facilities most relevant to the user query.

    Args:
        query: Natural-language search string from the user.
        k: Number of results to return (default 3).

    Returns:
        A list of facility dicts ranked by relevance.
    """
    pass


def facility_info_tool(query: str) -> str:
    """LangChain-compatible tool function for facility information retrieval.

    This is the callable registered with the LangGraph ToolNode.
    Wraps `search_facilities` and formats output for the LLM.

    Args:
        query: The user's facility-related question.

    Returns:
        A formatted string describing matching facilities.
    """
    pass
