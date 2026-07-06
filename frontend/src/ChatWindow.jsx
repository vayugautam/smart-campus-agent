import React, { useState, useEffect, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { sendMessage, confirmBooking } from './api';

export default function ChatWindow({ prefillMessage = '', onAgentMessage = null }) {
  const [threadId, setThreadId] = useState('');
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // When a pre-filled message arrives (from Register / Check Availability buttons),
  // drop it into the input box — the user still reviews and sends it manually.
  useEffect(() => {
    if (prefillMessage) {
      setInputValue(prefillMessage);
    }
  }, [prefillMessage]);

  useEffect(() => {
    let storedThreadId = localStorage.getItem('campus_agent_thread_id');
    if (!storedThreadId) {
      storedThreadId = uuidv4();
      localStorage.setItem('campus_agent_thread_id', storedThreadId);
    }
    setThreadId(storedThreadId);
    
    // Initial welcome message
    setMessages([
      {
        id: uuidv4(),
        sender: 'agent',
        text: 'Hello! I am the Smart Campus Agent. I can help you with campus events, facility information, and booking requests. How can I assist you today?'
      }
    ]);
  }, []);

  const handleNewConversation = () => {
    const newThreadId = uuidv4();
    localStorage.setItem('campus_agent_thread_id', newThreadId);
    setThreadId(newThreadId);
    setMessages([
      {
        id: uuidv4(),
        sender: 'agent',
        text: 'Hello! I am the Smart Campus Agent. I can help you with campus events, facility information, and booking requests. How can I assist you today?'
      }
    ]);
    setInputValue('');
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (text) => {
    if (!text.trim() || isLoading) return;

    const userMessage = { id: uuidv4(), sender: 'user', text: text.trim() };
    setMessages((prev) => 
      prev.map(msg => 
        msg.isConfirmationRequest || (msg.clarificationCandidates && msg.clarificationCandidates.length > 0)
          ? { ...msg, isConfirmationRequest: false, clarificationCandidates: [] } 
          : msg
      ).concat(userMessage)
    );
    setInputValue('');
    setIsLoading(true);

    try {
      const data = await sendMessage(threadId, text.trim());
      const agentMessage = {
        id: uuidv4(),
        sender: 'agent',
        text: data.reply,
        intent: data.intent,
        isConfirmationRequest: data.waiting_on_confirmation,
        clarificationCandidates: data.clarification_candidates || []
      };
      setMessages((prev) => [...prev, agentMessage]);
      onAgentMessage?.();
    } catch (error) {
      setMessages((prev) => [...prev, {
        id: uuidv4(),
        sender: 'agent',
        text: '⚠️ Cannot connect to the server. Please ensure the FastAPI backend is running at http://localhost:8000.'
      }]);
      onAgentMessage?.();
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = async (confirmed) => {
    setIsLoading(true);
    
    // Add user's explicit reply to the chat
    const userMessage = { id: uuidv4(), sender: 'user', text: confirmed ? 'Yes, confirm' : 'No, cancel' };
    setMessages((prev) => [...prev, userMessage]);

    // Mark the previous confirmation request as resolved so buttons disappear (turn into normal message visually)
    setMessages((prev) => 
      prev.map(msg => 
        msg.isConfirmationRequest || (msg.clarificationCandidates && msg.clarificationCandidates.length > 0)
          ? { ...msg, isConfirmationRequest: false, clarificationCandidates: [] } 
          : msg
      )
    );

    try {
      const data = await confirmBooking(threadId, confirmed);
      const agentMessage = {
        id: uuidv4(),
        sender: 'agent',
        text: data.reply,
        intent: data.intent,
        isConfirmationRequest: data.waiting_on_confirmation,
        clarificationCandidates: data.clarification_candidates || []
      };
      setMessages((prev) => [...prev, agentMessage]);
      onAgentMessage?.();
    } catch (error) {
       setMessages((prev) => [...prev, {
        id: uuidv4(),
        sender: 'agent',
        text: '⚠️ Cannot connect to the server. Please ensure the FastAPI backend is running at http://localhost:8000.'
      }]);
      onAgentMessage?.();
    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="h-full p-4 flex flex-col bg-white border border-gray-200 rounded-2xl overflow-hidden">
      <div className="border-b border-gray-100 pb-4 mb-4 flex items-center justify-between">
        <div>
            <h2 className="text-xl font-semibold text-gray-800 tracking-tight">Smart Campus Agent</h2>
            <p className="text-xs text-gray-400 font-mono mt-1">Session: {threadId.split('-')[0]}</p>
        </div>
        <div className="flex items-center gap-4">
            <button 
              onClick={handleNewConversation}
              className="text-sm text-blue-600 hover:bg-blue-50 px-3 py-1.5 rounded-lg transition-colors font-medium border border-transparent hover:border-blue-100 flex items-center gap-1.5"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><line x1="9" x2="15" y1="10" y2="10"/><line x1="12" x2="12" y1="7" y2="13"/></svg>
              New Chat
            </button>
            <div className="flex items-center gap-2">
                <span className="relative flex h-3 w-3">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
                <span className="text-sm text-gray-500 font-medium">Online</span>
            </div>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto mb-4 space-y-6 pr-2 scrollbar-thin scrollbar-thumb-gray-200 scrollbar-track-transparent">
        {messages.map((msg) => {
          const isUser = msg.sender === 'user';
          return (
            <div key={msg.id} className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
              {!isUser && msg.intent && msg.intent !== "unclear" && (
                <div className="mb-1 ml-1">
                  <span className="text-[10px] uppercase font-bold tracking-wider px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-500">
                    {msg.intent.replace('_', ' ')}
                  </span>
                </div>
              )}
              
              {msg.isConfirmationRequest ? (
                <div className="bg-amber-50 border border-amber-200 rounded-2xl p-5 max-w-[85%] shadow-sm mt-1">
                  <div className="flex items-start gap-3">
                    <div className="text-amber-500 mt-0.5">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
                    </div>
                    <div>
                        <p className="text-amber-900 mb-4 font-medium leading-relaxed">{msg.text}</p>
                        <div className="flex gap-3">
                          <button 
                            onClick={() => handleConfirm(true)}
                            disabled={isLoading}
                            className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white font-medium py-2.5 px-4 rounded-xl transition-all shadow-sm active:scale-95 disabled:opacity-50"
                          >
                            Yes, Confirm
                          </button>
                          <button 
                            onClick={() => handleConfirm(false)}
                            disabled={isLoading}
                            className="flex-1 bg-white border border-gray-300 hover:bg-gray-50 text-gray-700 font-medium py-2.5 px-4 rounded-xl transition-all active:scale-95 disabled:opacity-50"
                          >
                            Cancel
                          </button>
                        </div>
                    </div>
                  </div>
                </div>
              ) : (msg.clarificationCandidates && msg.clarificationCandidates.length > 0) ? (
                <div className="bg-blue-50 border border-blue-200 rounded-2xl p-5 max-w-[85%] shadow-sm mt-1">
                  <div className="flex items-start gap-3">
                    <div className="text-blue-500 mt-0.5">
                        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>
                    </div>
                    <div>
                        <p className="text-blue-900 mb-4 font-medium leading-relaxed">{msg.text}</p>
                        <div className="flex flex-wrap gap-2">
                          {msg.clarificationCandidates.map(candidate => (
                            <button 
                              key={candidate}
                              onClick={() => handleSend(candidate)}
                              disabled={isLoading}
                              className="bg-white border border-blue-300 hover:bg-blue-50 text-blue-700 font-medium py-1.5 px-3 rounded-full transition-all active:scale-95 disabled:opacity-50 text-sm"
                            >
                              {candidate}
                            </button>
                          ))}
                        </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className={`px-5 py-3.5 rounded-2xl max-w-[80%] shadow-sm ${
                  isUser 
                    ? 'bg-blue-600 text-white rounded-tr-sm' 
                    : 'bg-gray-50 border border-gray-100 text-gray-800 rounded-tl-sm'
                }`}>
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                </div>
              )}
            </div>
          );
        })}
        {isLoading && (
          <div className="flex flex-col items-start">
             <div className="bg-gray-50 border border-gray-100 px-5 py-4 rounded-2xl rounded-tl-sm text-gray-500 flex gap-1.5 items-center shadow-sm">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
             </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <div className="pt-4 border-t border-gray-100">
        <form 
          className="flex gap-3 relative"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(inputValue);
          }}
        >
          <input 
            type="text" 
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Type your message..." 
            className="flex-1 bg-gray-50 border border-gray-200 focus:bg-white p-4 rounded-xl outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all text-gray-800 disabled:opacity-60 disabled:cursor-not-allowed"
            disabled={isLoading}
          />
          <button 
            type="submit"
            className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-8 py-4 rounded-xl transition-all shadow-sm active:scale-95 disabled:opacity-50 disabled:active:scale-100 disabled:cursor-not-allowed flex items-center gap-2" 
            disabled={isLoading || !inputValue.trim()}
          >
            <span>Send</span>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
          </button>
        </form>
      </div>
    </div>
  );
}
