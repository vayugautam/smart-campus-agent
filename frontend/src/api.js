const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export async function sendMessage(threadId, message) {
    const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, message })
    });
    if (!response.ok) {
        throw new Error("Network response was not ok");
    }
    return response.json();
}

export async function confirmBooking(threadId, confirmed) {
    const response = await fetch(`${API_BASE}/chat/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, confirmed })
    });
    if (!response.ok) {
        throw new Error("Network response was not ok");
    }
    return response.json();
}

export async function getEvents() {
    const response = await fetch(`${API_BASE}/events`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

export async function getFacilities() {
    const response = await fetch(`${API_BASE}/facilities`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}
