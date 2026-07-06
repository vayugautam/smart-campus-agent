"""
retrieval.py — FAISS-backed semantic search tools for events and facilities.

Uses HuggingFace sentence-transformers (all-MiniLM-L6-v2) for embeddings
so no external API calls are needed.  FAISS indices are cached to disk
under ``app/data/.faiss_cache/`` and only rebuilt when the cache is missing.

Usage inside the LangGraph agent::

    from app.tools.retrieval import search_events, search_facilities

Both are decorated with ``@tool`` so they can be passed directly to a
LangGraph ToolNode.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_huggingface import HuggingFaceEmbeddings

# ── constants ────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CACHE_DIR = DATA_DIR / ".faiss_cache"

EVENTS_PATH = DATA_DIR / "events.json"
FACILITIES_PATH = DATA_DIR / "facilities.json"

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

# Number of results returned by default
DEFAULT_K = 3

# ── lazy singletons ──────────────────────────────────────────────────────
# Initialised on first call, then reused for the lifetime of the process.

_embeddings: HuggingFaceEmbeddings | None = None
_event_store: FAISS | None = None
_facility_store: FAISS | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Return (and lazily create) the shared embedding model instance."""
    global _embeddings
    if _embeddings is None:
        logger.info("Loading embedding model '%s' ...", EMBEDDING_MODEL_NAME)
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL_NAME,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


# ── document builders ────────────────────────────────────────────────────

def _load_json(path: Path) -> list[dict[str, Any]]:
    """Read and parse a JSON file, returning a list of dicts."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _events_to_documents(events: list[dict[str, Any]]) -> list[Document]:
    """Convert raw event dicts into LangChain Documents.

    The ``page_content`` is a rich text blob that gives the embedding
    model enough signal to match natural-language queries.  The full
    original dict is kept in ``metadata`` so the tool can return
    structured data.
    """
    docs: list[Document] = []
    for evt in events:
        text = (
            f"{evt['name']}\n"
            f"{evt['description']}\n"
            f"Category: {evt['category']}\n"
            f"Date: {evt['date']} at {evt['time']}\n"
            f"Venue: {evt['venue']}\n"
            f"Registration required: {'yes' if evt.get('registration_required') else 'no'}"
        )
        docs.append(Document(page_content=text, metadata=evt))
    return docs


def _facilities_to_documents(facilities: list[dict[str, Any]]) -> list[Document]:
    """Convert raw facility dicts into LangChain Documents."""
    docs: list[Document] = []
    for fac in facilities:
        equipment_str = ", ".join(fac.get("equipment", []))
        text = (
            f"{fac['name']}\n"
            f"Type: {fac['type']}\n"
            f"Capacity: {fac['capacity']} people\n"
            f"Location: {fac['location']}\n"
            f"Equipment: {equipment_str}\n"
            f"Bookable: {'yes' if fac.get('bookable') else 'no'}"
        )
        docs.append(Document(page_content=text, metadata=fac))
    return docs


# ── index management ────────────────────────────────────────────────────

def _load_or_build_index(
    cache_name: str,
    json_path: Path,
    doc_builder,
) -> FAISS:
    """Load a cached FAISS index from disk, or build + cache it.

    Args:
        cache_name: Sub-directory name under ``.faiss_cache/``.
        json_path:  Path to the source JSON file.
        doc_builder: Callable that turns ``list[dict]`` → ``list[Document]``.

    Returns:
        A ready-to-query FAISS vectorstore.
    """
    embeddings = _get_embeddings()
    cache_path = CACHE_DIR / cache_name

    if cache_path.exists():
        logger.info("Loading cached FAISS index from %s", cache_path)
        return FAISS.load_local(
            str(cache_path),
            embeddings,
            allow_dangerous_deserialization=True,
        )

    logger.info("Building FAISS index for '%s' ...", cache_name)
    raw_data = _load_json(json_path)
    docs = doc_builder(raw_data)
    store = FAISS.from_documents(docs, embeddings)

    # Persist to disk so subsequent runs skip the embedding step.
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(cache_path))
    logger.info("Saved FAISS index to %s", cache_path)

    return store


def get_event_store() -> FAISS:
    """Return (and lazily build/load) the events FAISS vectorstore."""
    global _event_store
    if _event_store is None:
        _event_store = _load_or_build_index(
            cache_name="events",
            json_path=EVENTS_PATH,
            doc_builder=_events_to_documents,
        )
    return _event_store


def get_facility_store() -> FAISS:
    """Return (and lazily build/load) the facilities FAISS vectorstore."""
    global _facility_store
    if _facility_store is None:
        _facility_store = _load_or_build_index(
            cache_name="facilities",
            json_path=FACILITIES_PATH,
            doc_builder=_facilities_to_documents,
        )
    return _facility_store


# ── formatting helpers ───────────────────────────────────────────────────

def _format_event(meta: dict[str, Any]) -> str:
    """Format a single event metadata dict into a readable block."""
    reg = "Yes" if meta.get("registration_required") else "No"
    return (
        f"- **{meta['name']}**\n"
        f"  Date: {meta['date']} at {meta['time']}\n"
        f"  Venue: {meta['venue']}\n"
        f"  Category: {meta['category']}\n"
        f"  Registration required: {reg}\n"
        f"  {meta['description']}"
    )


def _format_facility(meta: dict[str, Any]) -> str:
    """Format a single facility metadata dict into a readable block."""
    equip = ", ".join(meta.get("equipment", []))
    return (
        f"- **{meta['name']}** ({meta['type']})\n"
        f"  Capacity: {meta['capacity']} | Location: {meta['location']}\n"
        f"  Equipment: {equip}"
    )


# ── LangChain tools ─────────────────────────────────────────────────────

@tool
def search_events(query: str) -> str:
    """Search upcoming campus events by natural-language query.

    Use this tool when the user asks about events, workshops, fests,
    lectures, tournaments, or anything happening on campus.

    Args:
        query: A natural-language description of the events the user
               is looking for (e.g. "any tech workshops this month?").

    Returns:
        A formatted string listing the most relevant upcoming events
        with dates, venues, and descriptions.
    """
    store = get_event_store()
    results = store.similarity_search_with_score(query, k=DEFAULT_K)

    if not results:
        return "No matching events found."

    lines = [f"Found {len(results)} relevant event(s):\n"]
    for doc, score in results:
        lines.append(_format_event(doc.metadata))
        lines.append(f"  (relevance score: {score:.4f})\n")

    return "\n".join(lines)


@tool
def search_facilities(query: str) -> str:
    """Search campus facilities, rooms, and labs by natural-language query.

    Use this tool when the user asks about rooms, labs, auditoriums,
    studios, sports venues, or any bookable campus facility.

    Args:
        query: A natural-language description of the facility the user
               is looking for (e.g. "room with a projector for 30 people").

    Returns:
        A formatted string listing the most relevant facilities with
        capacity, location, and equipment details.
    """
    store = get_facility_store()
    results = store.similarity_search_with_score(query, k=DEFAULT_K)

    if not results:
        return "No matching facilities found."

    lines = [f"Found {len(results)} relevant facility(ies):\n"]
    for doc, score in results:
        lines.append(_format_facility(doc.metadata))
        lines.append(f"  (relevance score: {score:.4f})\n")

    return "\n".join(lines)


# ── manual rebuild helper ───────────────────────────────────────────────

def rebuild_indices() -> None:
    """Force-rebuild both FAISS indices from the source JSON files.

    Useful after updating events.json or facilities.json.  Deletes the
    existing cache and rebuilds from scratch.
    """
    import shutil

    global _event_store, _facility_store

    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        logger.info("Cleared FAISS cache at %s", CACHE_DIR)

    _event_store = None
    _facility_store = None

    # Trigger rebuild
    get_event_store()
    get_facility_store()

    logger.info("Both FAISS indices rebuilt and cached.")


if __name__ == "__main__":
    # Quick smoke test — run with: python -m app.tools.retrieval
    logging.basicConfig(level=logging.INFO)

    print("=== Event search: 'tech workshop' ===")
    print(search_events.invoke("tech workshop"))
    print()
    print("=== Facility search: 'room with projector for 30 people' ===")
    print(search_facilities.invoke("room with projector for 30 people"))
