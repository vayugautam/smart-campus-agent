import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt
from langchain_groq import ChatGroq
from dotenv import load_dotenv

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from app.tools.availability_checker import check_availability
from app.tools.booking import create_booking
from app.tools.registration import check_registration_open, create_registration
from app.tools.retrieval import (
    EVENTS_PATH,
    FACILITIES_PATH,
    get_event_store,
    get_facility_store,
    search_events,
    search_facilities,
)

load_dotenv()

# ==============================================================================
# 1. State Definition
# ==============================================================================
class AgentState(TypedDict):
    """The unified state for the Campus Agent graph."""
    messages: Annotated[list[BaseMessage], add_messages]
    intent: Literal["event_query", "facility_query", "booking_query", "unclear"] | None
    retrieved_context: dict[str, Any] | None
    availability_result: dict[str, Any] | None
    requires_confirmation: bool
    confirmed: bool
    booking_result: dict[str, Any] | None
    pending_clarification: dict[str, Any] | None
    clarified_facility: dict[str, Any] | None
    registration_check: dict[str, Any] | None
    registration_result: dict[str, Any] | None


class IntentClassification(BaseModel):
    intent: Literal["event_query", "facility_query", "booking_query", "unclear"] = Field(
        description="The classified intent of the user's message."
    )


def classify_intent_locally(message: str) -> Literal["event_query", "facility_query", "booking_query", "unclear"]:
    """Fallback classifier used when Groq is not configured or unavailable."""
    text = message.lower()

    booking_terms = ["book", "booking", "reserve", "reservation", "available", "availability", "free"]
    event_terms = [
        "event",
        "events",
        "hackathon",
        "seminar",
        "workshop",
        "festival",
        "festivals",
        "cultural",
        "happening",
    ]
    facility_terms = ["room", "lab", "library", "auditorium", "facility", "facilities", "equipment"]

    if any(term in text for term in booking_terms):
        return "booking_query"
    if any(term in text for term in event_terms):
        return "event_query"
    if any(term in text for term in facility_terms):
        return "facility_query"
    return "unclear"


def has_real_groq_key() -> bool:
    key = os.getenv("GROQ_API_KEY", "").strip()
    return bool(key and key != "gsk_your_key_here")


def latest_user_message(state: AgentState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


def load_json_list(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def significant_words(text: str) -> set[str]:
    stop = {"the", "a", "an", "and", "of", "for", "room", "facility"}
    return {word for word in normalize_text(text).split() if len(word) > 1 and word not in stop}


def structured_search(kind: Literal["events", "facilities"], query: str, k: int = 3) -> dict[str, Any]:
    """Run the retrieval tool and return structured metadata, with a JSON fallback."""
    tool = search_events if kind == "events" else search_facilities
    store_getter = get_event_store if kind == "events" else get_facility_store
    json_path = EVENTS_PATH if kind == "events" else FACILITIES_PATH

    formatted_summary = ""
    matches: list[dict[str, Any]] = []
    can_use_faiss = os.getenv("ENABLE_FAISS_RETRIEVAL") == "1"

    try:
        if not can_use_faiss:
            raise RuntimeError("FAISS semantic search skipped because the embedding model is not cached locally.")
        formatted_summary = tool.invoke(query)
        matches = [
            {**doc.metadata, "relevance_score": float(score)}
            for doc, score in store_getter().similarity_search_with_score(query, k=k)
        ]
    except Exception as exc:
        raw_items = load_json_list(json_path)
        query_words = significant_words(query)

        def score_item(item: dict[str, Any]) -> int:
            blob = " ".join(str(value) for value in item.values())
            return len(query_words & significant_words(blob))

        ranked = sorted(raw_items, key=score_item, reverse=True)
        matches = [item for item in ranked[:k] if score_item(item) > 0] or ranked[:k]
        formatted_summary = f"Retrieved {len(matches)} {kind} from local JSON fallback. Semantic search unavailable: {exc}"

    return {"type": kind, "query": query, "matches": matches, "formatted_summary": formatted_summary}


def resolve_facility_id(message: str, retrieved_context: dict[str, Any] | None) -> dict[str, Any]:
    facilities = load_json_list(FACILITIES_PATH)
    message_norm = normalize_text(message)
    exact_matches = []
    direct_matches = []

    for facility in facilities:
        name_norm = normalize_text(facility["name"])
        id_norm = normalize_text(facility["id"])
        name_words = significant_words(facility["name"])
        if name_norm in message_norm or id_norm in message_norm:
            direct_matches.append(facility)
        elif name_words.issubset(significant_words(message)):
            exact_matches.append(facility)

    if len(direct_matches) == 1:
        return {"facility": direct_matches[0], "needs_clarification": False, "reason": None}
    if len(direct_matches) > 1:
        return {
            "facility": None,
            "needs_clarification": True,
            "reason": "Multiple facilities matched that request.",
            "candidates": direct_matches,
        }

    if len(exact_matches) == 1:
        return {"facility": exact_matches[0], "needs_clarification": False, "reason": None}
    if len(exact_matches) > 1:
        return {
            "facility": None,
            "needs_clarification": True,
            "reason": "Multiple facilities matched that request.",
            "candidates": exact_matches,
        }

    candidates = []
    if retrieved_context and retrieved_context.get("type") == "facilities":
        candidates = retrieved_context.get("matches", [])[:3]

    return {
        "facility": None,
        "needs_clarification": True,
        "reason": "I could not resolve a specific facility name without guessing.",
        "candidates": candidates,
    }


def db_date_bounds() -> tuple[date | None, date | None]:
    db_path = Path(__file__).resolve().parent.parent / "data" / "availability.db"
    if not db_path.exists():
        return None, None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT MIN(date), MAX(date) FROM slots").fetchone()
    finally:
        conn.close()
    if not row or not row[0] or not row[1]:
        return None, None
    return date.fromisoformat(row[0]), date.fromisoformat(row[1])


def resolve_date(message: str) -> str | None:
    explicit = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", message)
    if explicit:
        return explicit.group(1)

    min_db_date, max_db_date = db_date_bounds()
    anchor = date.today()
    if min_db_date and max_db_date and not (min_db_date <= anchor <= max_db_date):
        anchor = min_db_date

    text = message.lower()
    if "tomorrow" in text:
        return (anchor + timedelta(days=1)).isoformat()
    if "today" in text:
        return anchor.isoformat()
    return None


def resolve_time_window(message: str) -> tuple[str, str] | tuple[None, None]:
    text = message.lower()
    # Ensure we don't match parts of a date like 2026-07-20 by ignoring digits around dashes
    match = re.search(r"(?<!-)\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b(?!-)", text)
    if not match:
        # Fallback for 24-hr time like 08:00 or 14:00 without am/pm
        match = re.search(r"(?<!-)\b(\d{1,2}):(\d{2})\b(?!-)", text)
        if not match:
            return None, None

    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    meridiem = match.group(3) if match.lastindex >= 3 else None

    if meridiem == "pm" and hour != 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0

    if hour < 8 or hour >= 20:
        return None, None

    slot_start_hour = 8 + ((hour - 8) // 2) * 2
    if minute == 0 and hour in range(8, 20, 2):
        slot_start_hour = hour

    return f"{slot_start_hour:02d}:00", f"{slot_start_hour + 2:02d}:00"


def previous_available_slot(state: AgentState) -> dict[str, Any] | None:
    availability = state.get("availability_result") or {}
    slot = availability.get("requested_slot")
    if availability.get("available") is True and slot:
        return slot
    return None


def asks_to_book(message: str) -> bool:
    return bool(re.search(r"\b(book|booking|reserve|reservation)\b", message.lower()))

def asks_to_register(message: str) -> bool:
    return bool(re.search(r"\b(register|registration|enroll|sign up|join|attend)\b", message.lower()))

def resolve_event_id(message: str, retrieved_context: dict[str, Any] | None) -> dict[str, Any]:
    events = load_json_list(EVENTS_PATH)
    message_norm = normalize_text(message)
    exact_matches = []
    direct_matches = []

    for event in events:
        name_norm = normalize_text(event["name"])
        id_norm = normalize_text(event["id"])
        name_words = significant_words(event["name"])
        if name_norm in message_norm or id_norm in message_norm:
            direct_matches.append(event)
        elif name_words.issubset(significant_words(message)):
            exact_matches.append(event)

    if len(direct_matches) == 1:
        return {"event": direct_matches[0], "needs_clarification": False, "reason": None}
    if len(direct_matches) > 1:
        return {
            "event": None,
            "needs_clarification": True,
            "reason": "Multiple events matched that request.",
            "candidates": direct_matches,
        }

    if len(exact_matches) == 1:
        return {"event": exact_matches[0], "needs_clarification": False, "reason": None}
    if len(exact_matches) > 1:
        return {
            "event": None,
            "needs_clarification": True,
            "reason": "Multiple events matched that request.",
            "candidates": exact_matches,
        }

    candidates = []
    if retrieved_context and retrieved_context.get("type") == "events":
        candidates = retrieved_context.get("matches", [])[:3]

    return {
        "event": None,
        "needs_clarification": True,
        "reason": "I could not resolve a specific event name without guessing.",
        "candidates": candidates,
    }


def build_pending_clarification(
    *,
    intent: Literal["event_query", "facility_query", "booking_query", "unclear"] | None,
    query: str,
    candidates: list[dict[str, Any]],
    target: Literal["generate_response", "check_constraints"],
    date: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    source: Literal["retrieve_info", "check_constraints"] = "retrieve_info",
) -> dict[str, Any]:
    return {
        "source": source,
        "target": target,
        "intent": intent,
        "query": query,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "candidates": candidates,
    }


def clarification_prompt(pending: dict[str, Any]) -> str:
    candidates = pending.get("candidates") or []
    if candidates:
        candidate_lines = []
        for candidate in candidates[:5]:
            name = candidate.get("name", candidate.get("id", "Unknown facility"))
            location = candidate.get("location")
            if location:
                candidate_lines.append(f"- {name} ({location})")
            else:
                candidate_lines.append(f"- {name}")
        candidates_text = "\n".join(candidate_lines)
    else:
        candidates_text = "- No close matches were found. Please reply with the exact facility name."

    context_bits = []
    if pending.get("date"):
        context_bits.append(f"date {pending['date']}")
    if pending.get("start_time") and pending.get("end_time"):
        context_bits.append(f"time {pending['start_time']} to {pending['end_time']}")
    context_text = f" for {' and '.join(context_bits)}" if context_bits else ""

    return (
        "I need one exact facility name before I can continue" + context_text + ".\n"
        "Please reply with just the facility name.\n"
        "Possible matches:\n"
        f"{candidates_text}"
    )

def clarification_response_text(user_response: Any) -> str:
    def extract_resume(text: str) -> str:
        match = re.search(r"resume=['\"](.+?)['\"]", text)
        if match:
            return match.group(1).strip()
        return text.strip()

    if isinstance(user_response, str):
        return extract_resume(user_response)
    if isinstance(user_response, dict):
        for key in ("resume", "response", "message", "content", "text"):
            value = user_response.get(key)
            if value is not None:
                return extract_resume(str(value))
    for attribute in ("resume", "response", "message", "content", "text"):
        if hasattr(user_response, attribute):
            value = getattr(user_response, attribute)
            if value is not None:
                return extract_resume(str(value))
    return extract_resume(str(user_response))


def resolve_clarification_from_text(state: AgentState, response_text: str) -> dict[str, Any]:
    pending = state.get("pending_clarification") or {}
    resolution_context = {"type": "facilities", "matches": pending.get("candidates", [])}
    resolved = resolve_facility_id(response_text, resolution_context)

    if resolved.get("needs_clarification"):
        return {
            "pending_clarification": build_pending_clarification(
                intent=pending.get("intent", state.get("intent")),
                query=pending.get("query", latest_user_message(state)),
                candidates=resolved.get("candidates", pending.get("candidates", [])),
                target=pending.get("target", "generate_response"),
                date=pending.get("date"),
                start_time=pending.get("start_time"),
                end_time=pending.get("end_time"),
                source=pending.get("source", "retrieve_info"),
            ),
            "clarified_facility": None,
            "retrieved_context": {
                "type": "facilities",
                "query": pending.get("query", response_text or latest_user_message(state)),
                "matches": resolved.get("candidates", pending.get("candidates", [])),
                "needs_clarification": True,
                "reason": resolved.get("reason"),
            },
        }

    facility = resolved["facility"]
    return {
        "clarified_facility": facility,
        "retrieved_context": {
            "type": "facilities",
            "query": pending.get("query", response_text or latest_user_message(state)),
            "matches": [facility],
            "formatted_summary": f"Resolved facility clarification to {facility['name']}.",
        },
    }


# ==============================================================================
# 2. Nodes
# ==============================================================================
def classify_intent(state: AgentState) -> dict:
    """Classifies the intent of the user message."""
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "unclear"}
    
    latest_message = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
    
    if not has_real_groq_key():
        return {"intent": classify_intent_locally(latest_message)}
    
    prompt = f"""You are an intent classification assistant for a college campus agent.
Classify the user's latest message into exactly one of the following categories:
- 'event_query': Asking about upcoming events, hackathons, seminars, or what is happening on campus.
- 'facility_query': Asking about rooms, labs, library, equipment, or general campus facilities (without explicitly trying to book them).
- 'booking_query': Trying to book a facility, check availability for a specific time, or reserve a room.
- 'unclear': Anything else, greeting, or if the user's request is ambiguous.

User message: "{latest_message}"
"""
    try:
        llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
        structured_llm = llm.with_structured_output(IntentClassification)
        result = structured_llm.invoke(prompt)
        return {"intent": result.intent}
    except Exception:
        return {"intent": classify_intent_locally(latest_message)}

def retrieve_info(state: AgentState) -> dict:
    """Retrieves context from FAISS via event or facility tools based on intent."""
    query = latest_user_message(state)
    intent = state.get("intent")

    if intent == "event_query":
        return {"retrieved_context": structured_search("events", query)}
    if intent in {"facility_query", "booking_query"}:
        previous_slot = previous_available_slot(state)
        if intent == "booking_query" and previous_slot and re.search(r"\b(it|that|same)\b", query, re.I):
            return {
                "retrieved_context": {
                    "type": "facilities",
                    "query": query,
                    "matches": [previous_slot["facility"]],
                    "formatted_summary": "Reusing the facility from the previous availability check.",
                }
            }
        retrieval = structured_search("facilities", query)
        facility_resolution = resolve_facility_id(query, retrieval)
        if facility_resolution.get("needs_clarification"):
            booking_date = resolve_date(query)
            start_time, end_time = resolve_time_window(query)
            target = "check_constraints" if intent == "booking_query" else "generate_response"
            return {
                "retrieved_context": {
                    **retrieval,
                    "needs_clarification": True,
                    "reason": facility_resolution.get("reason"),
                    "candidates": facility_resolution.get("candidates", retrieval.get("matches", [])),
                },
                "pending_clarification": build_pending_clarification(
                    intent=intent,
                    query=query,
                    candidates=facility_resolution.get("candidates", retrieval.get("matches", [])),
                    target=target,
                    date=booking_date,
                    start_time=start_time,
                    end_time=end_time,
                    source="retrieve_info",
                ),
            }
        return {"retrieved_context": retrieval}

    return {"retrieved_context": {"type": "none", "query": query, "matches": []}}


def resume_clarification(state: AgentState) -> dict:
    """Resolve a pending clarification from the user's next turn without re-classifying."""
    response_text = latest_user_message(state)
    return resolve_clarification_from_text(state, response_text)

def check_constraints(state: AgentState) -> dict:
    """Checks the database to see if the requested facility is free."""
    pending = state.get("pending_clarification") or {}
    message = pending.get("query") or latest_user_message(state)

    clarified_facility = state.get("clarified_facility")
    if clarified_facility is not None:
        facility = clarified_facility
    else:
        facility_resolution = resolve_facility_id(message, state.get("retrieved_context"))
        if facility_resolution.get("needs_clarification"):
            parsed_start, parsed_end = resolve_time_window(message)
            return {
                "availability_result": {
                    "available": False,
                    "needs_clarification": True,
                    "reason": facility_resolution["reason"],
                    "conflicts": [],
                    "alternatives": [],
                    "candidates": facility_resolution.get("candidates", []),
                },
                "pending_clarification": build_pending_clarification(
                    intent=state.get("intent"),
                    query=message,
                    candidates=facility_resolution.get("candidates", []),
                    target="check_constraints",
                    date=pending.get("date") or resolve_date(message),
                    start_time=pending.get("start_time") or parsed_start,
                    end_time=pending.get("end_time") or parsed_end,
                    source="check_constraints",
                ),
                "requires_confirmation": False,
            }
        facility = facility_resolution["facility"]

    if previous_slot := previous_available_slot(state):
        if re.search(r"\b(it|that|same)\b", message, re.I) and not resolve_date(message):
            result = check_availability(
                previous_slot["facility_id"],
                previous_slot["date"],
                previous_slot["start_time"],
                previous_slot["end_time"],
            )
            result["requested_slot"] = previous_slot
            return {
                "availability_result": result,
                "requires_confirmation": state.get("intent") == "booking_query",
                "pending_clarification": None,
                "clarified_facility": None,
            }

    booking_date = pending.get("date") or resolve_date(message)
    start_time = pending.get("start_time")
    end_time = pending.get("end_time")
    if not start_time or not end_time:
        parsed_start, parsed_end = resolve_time_window(message)
        start_time = start_time or parsed_start
        end_time = end_time or parsed_end
    if not booking_date or not start_time or not end_time:
        return {
            "availability_result": {
                "available": False,
                "needs_clarification": True,
                "reason": "Please provide a date and time for the booking.",
                "conflicts": [],
                "alternatives": [],
            },
            "requires_confirmation": False,
            "pending_clarification": None,
            "clarified_facility": None,
        }

    result = check_availability(facility["id"], booking_date, start_time, end_time)
    result["requested_slot"] = {
        "facility_id": facility["id"],
        "facility": facility,
        "date": booking_date,
        "start_time": start_time,
        "end_time": end_time,
    }
    return {
        "availability_result": result,
        "requires_confirmation": state.get("intent") == "booking_query",
        "pending_clarification": None,
        "clarified_facility": None,
    }


def check_registration(state: AgentState) -> dict:
    """Checks the registration open status and capacity for the requested event."""
    message = latest_user_message(state)
    event_resolution = resolve_event_id(message, state.get("retrieved_context"))
    
    if event_resolution.get("needs_clarification"):
        return {
            "registration_check": {
                "open": False,
                "needs_clarification": True,
                "reason": event_resolution["reason"],
                "candidates": event_resolution.get("candidates", [])
            },
            "requires_confirmation": False
        }
        
    event = event_resolution["event"]
    result = check_registration_open(event["id"])
    result["event"] = event
    
    return {
        "registration_check": result,
        "requires_confirmation": result.get("open") is True
    }


def execute_registration(state: AgentState) -> dict:
    """Invokes the registration tool to sign up the user."""
    reg_check = state.get("registration_check") or {}
    event = reg_check.get("event")
    
    if not event or reg_check.get("open") is not True:
        return {"registration_result": {"success": False, "error": "Event is not open for registration."}}
        
    result = create_registration(event["id"], "demo_user")
    return {"registration_result": result}


def request_clarification(state: AgentState) -> dict:
    """Interrupt the graph and wait for a facility-name clarification."""
    pending = state.get("pending_clarification") or {}
    prompt = clarification_prompt(pending)
    user_response = interrupt(prompt)
    response_text = clarification_response_text(user_response)

    resolution_context = {"type": "facilities", "matches": pending.get("candidates", [])}
    resolved = resolve_facility_id(response_text, resolution_context)

    if resolved.get("needs_clarification"):
        return {
            "pending_clarification": build_pending_clarification(
                intent=pending.get("intent", state.get("intent")),
                query=pending.get("query", latest_user_message(state)),
                candidates=resolved.get("candidates", pending.get("candidates", [])),
                target=pending.get("target", "generate_response"),
                date=pending.get("date"),
                start_time=pending.get("start_time"),
                end_time=pending.get("end_time"),
                source=pending.get("source", "retrieve_info"),
            ),
            "clarified_facility": None,
            "retrieved_context": {
                "type": "facilities",
                "query": pending.get("query", latest_user_message(state)),
                "matches": resolved.get("candidates", pending.get("candidates", [])),
                "needs_clarification": True,
                "reason": resolved.get("reason"),
            },
        }

    facility = resolved["facility"]
    return {
        "clarified_facility": facility,
        "retrieved_context": {
            "type": "facilities",
            "query": pending.get("query", latest_user_message(state)),
            "matches": [facility],
            "formatted_summary": f"Resolved facility clarification to {facility['name']}.",
        },
    }

def request_confirmation(state: AgentState) -> dict:
    """
    Uses LangGraph's interrupt() to pause execution and request user approval.
    """
    reg_check = state.get("registration_check") or {}
    if reg_check:
        event_name = reg_check.get("event", {}).get("name", "that event")
        confirmation_prompt = f"Registration for {event_name} is open. Please explicitly confirm you want to register (Yes/No)."
    else:
        availability = state.get("availability_result") or {}
        slot = availability.get("requested_slot") or {}
        facility_name = slot.get("facility", {}).get("name", slot.get("facility_id", "that facility"))
        date_text = slot.get("date", "the requested date")
        start_time = slot.get("start_time", "the requested start time")
        end_time = slot.get("end_time", "the requested end time")
        confirmation_prompt = (
            f"{facility_name} is available on {date_text} from {start_time} to {end_time}. "
            "Please explicitly confirm this booking (Yes/No)."
        )

    # LangGraph's interrupt pauses execution and sends this payload to the client.
    # The graph won't proceed until the client resumes it with a user response.
    user_response = interrupt(confirmation_prompt)
    
    # Process the user's response once resumed
    user_resp_str = str(user_response).strip().lower()
    is_confirmed = user_resp_str in ["yes", "y", "confirm", "approve", "ok"]
    
    return {"confirmed": is_confirmed}

def execute_booking(state: AgentState) -> dict:
    """Invokes the booking tool to mark the slot as booked."""
    availability = state.get("availability_result") or {}
    slot = availability.get("requested_slot")
    if availability.get("available") is not True or not slot:
        return {"booking_result": {"success": False, "error": "No available slot is ready to book."}}

    from app.tools.booking import create_booking
    booking = create_booking(
        facility_id=slot["facility_id"],
        date=slot["date"],
        start_time=slot["start_time"],
        end_time=slot["end_time"],
        user_name="demo_user",
    )
    return {"booking_result": booking}

def generate_response(state: AgentState) -> dict:
    """Synthesizes the final AI response to the user using the LLM."""
    pending = state.get("pending_clarification") or {}
    if pending and state.get("clarified_facility") is None:
        response_text = latest_user_message(state)
        resolved = resolve_facility_id(response_text, {"type": "facilities", "matches": pending.get("candidates", [])})
        if not resolved.get("needs_clarification"):
            facility = resolved["facility"]
            if pending.get("target") == "check_constraints":
                booking_date = pending.get("date") or resolve_date(pending.get("query", response_text))
                start_time = pending.get("start_time")
                end_time = pending.get("end_time")
                if not start_time or not end_time:
                    parsed_start, parsed_end = resolve_time_window(pending.get("query", response_text))
                    start_time = start_time or parsed_start
                    end_time = end_time or parsed_end

                if booking_date and start_time and end_time:
                    result = check_availability(facility["id"], booking_date, start_time, end_time)
                    result["requested_slot"] = {
                        "facility_id": facility["id"],
                        "facility": facility,
                        "date": booking_date,
                        "start_time": start_time,
                        "end_time": end_time,
                    }
                    if result.get("available"):
                        reply = (
                            f"{facility['name']} is available on {booking_date} from {start_time} to {end_time}. "
                            "Please explicitly confirm this booking with Yes or No."
                        )
                    else:
                        alternatives = result.get("alternatives") or []
                        alt_text = ""
                        if alternatives:
                            alt_text = " Alternatives: " + ", ".join(
                                f"{alt['start_time']} to {alt['end_time']}" for alt in alternatives
                            ) + "."
                        reply = (
                            f"{facility['name']} is not available on {booking_date} from {start_time} to {end_time}. "
                            f"{result.get('reason') or 'The slot is unavailable.'}{alt_text}"
                        )
                    return {
                        "messages": [AIMessage(content=reply)],
                        "availability_result": result,
                        "requires_confirmation": result.get("available") is True and state.get("intent") == "booking_query",
                        "pending_clarification": None,
                        "clarified_facility": None,
                    }

            facilities = [facility]
            lines = ["Here are the most relevant facilities I found:"]
            for item in facilities:
                equipment = ", ".join(item.get("equipment", [])[:3])
                lines.append(f"- {item['name']} ({item['location']}), capacity {item['capacity']}. Equipment: {equipment}.")
            return {
                "messages": [AIMessage(content="\n".join(lines))],
                "retrieved_context": {
                    "type": "facilities",
                    "query": pending.get("query", response_text),
                    "matches": facilities,
                    "formatted_summary": f"Resolved facility clarification to {facility['name']}.",
                },
                "pending_clarification": None,
                "clarified_facility": None,
            }

        return {
            "messages": [AIMessage(content=clarification_prompt(pending))],
            "pending_clarification": pending,
            "clarified_facility": None,
        }

    prompt = f"""You are a concise campus assistant. Use only the supplied state data.

Conversation:
{[getattr(msg, "content", str(msg)) for msg in state.get("messages", [])]}

Intent: {state.get("intent")}
Retrieved context: {state.get("retrieved_context")}
Availability result: {state.get("availability_result")}
Booking result: {state.get("booking_result")}
Registration check: {state.get("registration_check")}
Registration result: {state.get("registration_result")}

Write a natural response that names real events, facilities, availability, alternatives,
or booking/registration IDs when present. Ask for clarification when the state says clarification is needed.
"""
    if has_real_groq_key():
        try:
            llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.2)
            return {"messages": [AIMessage(content=llm.invoke(prompt).content)]}
        except Exception:
            pass

    intent = state.get("intent")
    retrieved = state.get("retrieved_context") or {}
    availability = state.get("availability_result") or {}
    booking = state.get("booking_result") or {}
    reg_check = state.get("registration_check") or {}
    reg_result = state.get("registration_result") or {}

    if reg_result:
        if reg_result.get("success"):
            event_name = (reg_check.get("event") or {}).get("name", "the event")
            return {
                "messages": [AIMessage(content=f"Successfully registered for {event_name}. Your registration ID is {reg_result['registration_id']}.")],
                "pending_clarification": None,
                "clarified_facility": None,
            }
        return {
            "messages": [AIMessage(content=f"I could not complete the registration: {reg_result.get('error', 'unknown error')}.")],
            "pending_clarification": None,
            "clarified_facility": None,
        }

    if reg_check and not reg_check.get("open"):
        return {
            "messages": [AIMessage(content=reg_check.get("reason", "Registration is currently closed or full for this event."))],
            "pending_clarification": None,
            "clarified_facility": None,
        }

    if booking:
        if booking.get("success"):
            facility_name = (availability.get("requested_slot") or {}).get("facility", {}).get("name", booking["facility_id"])
            return {
                "messages": [AIMessage(content=(
                    f"Booked {facility_name} on {booking['date']} from {booking['start_time']} to "
                    f"{booking['end_time']}. Your booking ID is {booking['booking_id']}."
                ))],
                "pending_clarification": None,
                "clarified_facility": None,
            }
        return {
            "messages": [AIMessage(content=f"I could not complete the booking: {booking.get('error', 'unknown error')}.")],
            "pending_clarification": None,
            "clarified_facility": None,
        }

    if availability:
        if availability.get("needs_clarification"):
            candidates = availability.get("candidates") or []
            names = ", ".join(candidate.get("name", candidate.get("id", "")) for candidate in candidates[:3])
            suffix = f" Possible matches: {names}." if names else ""
            return {
                "messages": [AIMessage(content=f"{availability.get('reason')}{suffix}")],
                "pending_clarification": state.get("pending_clarification"),
                "clarified_facility": state.get("clarified_facility"),
            }

        slot = availability.get("requested_slot") or {}
        facility_name = slot.get("facility", {}).get("name", slot.get("facility_id", "that facility"))
        date_text = slot.get("date", "that date")
        window = f"{slot.get('start_time')} to {slot.get('end_time')}"
        if availability.get("available"):
            next_step = (
                "Please explicitly confirm this booking with Yes or No."
                if state.get("requires_confirmation")
                else "Say \"book it\" if you want me to reserve it."
            )
            return {
                "messages": [AIMessage(content=(
                    f"{facility_name} is available on {date_text} from {window}. "
                    f"{next_step}"
                ))],
                "pending_clarification": None,
                "clarified_facility": None,
            }

        alternatives = availability.get("alternatives") or []
        alt_text = ""
        if alternatives:
            alt_text = " Alternatives: " + ", ".join(
                f"{alt['start_time']} to {alt['end_time']}" for alt in alternatives
            ) + "."
        return {
            "messages": [AIMessage(content=(
                f"{facility_name} is not available on {date_text} from {window}. "
                f"{availability.get('reason') or 'The slot is unavailable.'}{alt_text}"
            ))],
            "pending_clarification": None,
            "clarified_facility": None,
        }

    if intent == "event_query":
        events = retrieved.get("matches", [])
        if not events:
            return {
                "messages": [AIMessage(content="I could not find matching events.")],
                "pending_clarification": None,
                "clarified_facility": None,
            }
        lines = ["Here are the most relevant events I found:"]
        for event in events:
            lines.append(f"- {event['name']} on {event['date']} at {event['time']} in {event['venue']}.")
        return {
            "messages": [AIMessage(content="\n".join(lines))],
            "pending_clarification": None,
            "clarified_facility": None,
        }

    if intent == "facility_query":
        facilities = retrieved.get("matches", [])
        if not facilities:
            return {
                "messages": [AIMessage(content="I could not find matching facilities.")],
                "pending_clarification": None,
                "clarified_facility": None,
            }
        lines = ["Here are the most relevant facilities I found:"]
        for facility in facilities:
            equipment = ", ".join(facility.get("equipment", [])[:3])
            lines.append(f"- {facility['name']} ({facility['location']}), capacity {facility['capacity']}. Equipment: {equipment}.")
        return {
            "messages": [AIMessage(content="\n".join(lines))],
            "pending_clarification": None,
            "clarified_facility": None,
        }

    return {
        "messages": [AIMessage(content="Could you clarify whether you need event information, facility details, or a booking?")],
        "pending_clarification": None,
        "clarified_facility": None,
    }

# ==============================================================================
# 3. Conditional Edges
# ==============================================================================
def route_to_tool(state: AgentState) -> str:
    """
    Decision Point: Routes execution based on the user's classified intent.
    Problem Statement Requirement: The agent must decide which system to consult.
    If the user asks about events/facilities/bookings, we must retrieve relevant data.
    If it's unclear, we skip tools and go straight to response generation to ask for clarification.
    """
    intent = state.get("intent")
    if intent in ["event_query", "facility_query", "booking_query"]:
        return "retrieve_info"
    return "generate_response"


def route_from_start(state: AgentState) -> str:
    if state.get("pending_clarification"):
        return "resume_clarification"
    return "classify_intent"

def route_after_retrieval(state: AgentState) -> str:
    """
    Decision Point: What to do after gathering basic context.
    """
    retrieved = state.get("retrieved_context") or {}
    if retrieved.get("needs_clarification"):
        return "generate_response"
        
    intent = state.get("intent")
    message = latest_user_message(state)
    
    if intent == "booking_query":
        return "check_constraints"
        
    if intent == "event_query" and asks_to_register(message):
        return "check_registration"
        
    return "generate_response"

def route_after_registration_check(state: AgentState) -> str:
    reg_check = state.get("registration_check") or {}
    if reg_check.get("needs_clarification"):
        return "generate_response"
    if reg_check.get("open") is True:
        return "request_confirmation"
    return "generate_response"

def route_after_constraints(state: AgentState) -> str:
    """
    Decision Point: Should we prompt for confirmation?
    Problem Statement Requirement: The agent must determine if a booking is possible. 
    If the slot is free, we MUST mandate explicit user confirmation before booking.
    If the slot is not free, we abort the booking flow and go to generation to suggest alternatives.
    """
    avail = state.get("availability_result", {})
    if avail.get("needs_clarification"):
        return "generate_response"
    if avail.get("available") is True and state.get("requires_confirmation") is True:
        return "request_confirmation"
    else:
        # Slot is booked or invalid; respond to the user with reasons/alternatives.
        return "generate_response"


def route_after_clarification(state: AgentState) -> str:
    pending = state.get("pending_clarification") or {}
    if state.get("clarified_facility") is None:
        return "generate_response"
    return pending.get("target", "generate_response")

def route_after_confirmation(state: AgentState) -> str:
    """
    Decision Point: Did the user approve the action?
    """
    if state.get("confirmed") is True:
        if state.get("registration_check"):
            return "execute_registration"
        return "execute_booking"
    return "generate_response"

# ==============================================================================
# 4. Compile the Graph
# ==============================================================================
def build_graph() -> StateGraph:
    """
    Constructs and compiles the unified Campus Agent StateGraph.
    Uses a MemorySaver checkpointer to persist conversation state across turns
    using a thread_id, enabling multi-turn capabilities.
    """
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("resume_clarification", resume_clarification)
    workflow.add_node("classify_intent", classify_intent)
    workflow.add_node("retrieve_info", retrieve_info)
    workflow.add_node("check_constraints", check_constraints)
    workflow.add_node("check_registration", check_registration)
    workflow.add_node("request_clarification", request_clarification)
    workflow.add_node("request_confirmation", request_confirmation)
    workflow.add_node("execute_booking", execute_booking)
    workflow.add_node("execute_registration", execute_registration)
    workflow.add_node("generate_response", generate_response)
    
    # Add edges
    workflow.add_conditional_edges(START, route_from_start)
    
    workflow.add_conditional_edges("classify_intent", route_to_tool)
    workflow.add_conditional_edges("resume_clarification", route_after_clarification)
    workflow.add_conditional_edges("retrieve_info", route_after_retrieval)
    workflow.add_conditional_edges("check_constraints", route_after_constraints)
    workflow.add_conditional_edges("check_registration", route_after_registration_check)
    workflow.add_conditional_edges("request_clarification", route_after_clarification)
    workflow.add_conditional_edges("request_confirmation", route_after_confirmation)
    
    # Post-execution paths
    workflow.add_edge("execute_booking", "generate_response")
    workflow.add_edge("execute_registration", "generate_response")
    workflow.add_edge("generate_response", END)
    
    # Compile with MemorySaver to ensure conversation persistence and enable interrupt capability.
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)
    
    return app
