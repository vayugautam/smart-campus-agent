import { useState } from 'react';
import Header from './Header';
import EventsGrid from './EventsGrid';
import FacilitiesGrid from './FacilitiesGrid';
import ChatWidget from './ChatWidget';

export default function App() {
  const [chatOpen, setChatOpen]           = useState(false);
  const [prefillMessage, setPrefillMessage] = useState('');
  const [hasUnread, setHasUnread]         = useState(false);

  // Open the chat and clear any unread dot in one place
  const openChat = () => {
    setChatOpen(true);
    setHasUnread(false);
  };

  // Toggle: opening clears unread; closing also clears (user just saw the messages)
  const handleToggle = () => {
    setHasUnread(false);
    setChatOpen((prev) => !prev);
  };

  // Called by EventCard's Register button
  const handleRegister = (eventName) => {
    setPrefillMessage(`I'd like to register for ${eventName}`);
    openChat();
  };

  // Called by FacilityCard's Ask Agent button (after user picks date/time)
  const handleCheckAvailability = (facilityName, date, time) => {
    // Format date → "6 August 2026"
    const formattedDate = new Date(date + 'T00:00:00').toLocaleDateString('en-IN', {
      day: 'numeric', month: 'long', year: 'numeric',
    });
    // Format time → "9:00 AM"
    const [h, m] = time.split(':').map(Number);
    const ampm = h >= 12 ? 'PM' : 'AM';
    const hour = h % 12 || 12;
    const formattedTime = `${hour}:${m.toString().padStart(2, '0')} ${ampm}`;
    setPrefillMessage(`Is ${facilityName} available on ${formattedDate} at ${formattedTime}?`);
    openChat();
  };

  // Called by ChatWindow whenever a new agent message lands.
  // Only marks unread when the widget is currently collapsed.
  const handleAgentMessage = () => {
    if (!chatOpen) setHasUnread(true);
  };

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* ── Sticky top nav ─────────────────────────────────────── */}
      <Header />

      {/* ── Main content ───────────────────────────────────────── */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-32">
        <EventsGrid onRegister={handleRegister} />
        <div className="border-t border-slate-200" />
        <FacilitiesGrid onCheckAvailability={handleCheckAvailability} />
      </main>

      {/* ── Floating chat widget (bottom-right) ────────────────── */}
      <ChatWidget
        isOpen={chatOpen}
        onToggle={handleToggle}
        prefillMessage={prefillMessage}
        hasUnread={hasUnread}
        onAgentMessage={handleAgentMessage}
      />
    </div>
  );
}
