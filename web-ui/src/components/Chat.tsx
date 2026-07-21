import { useEffect, useRef, useState } from "react";
import { Message, ChatMessage } from "./Message";
import { streamChat } from "../lib/agentClient";

const SUGGESTIONS = [
  "Plan a 3-day trip to Tokyo",
  "What are the visa requirements for Japan?",
  "Find me hotels in Kyoto under $200",
  "Add the Tokyo flight to my cart",
];

export function Chat({
  userId,
  sessionId,
  onTurnComplete,
}: {
  userId: string;
  sessionId: string;
  onTurnComplete: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  async function send(text: string) {
    if (!text.trim() || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    try {
      await streamChat(text, userId, sessionId, (delta) => {
        setMessages((m) => {
          const copy = [...m];
          copy[copy.length - 1] = {
            role: "assistant",
            content: copy[copy.length - 1].content + delta,
          };
          return copy;
        });
      });
    } catch (e) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: `⚠️ ${String(e)}` };
        return copy;
      });
    } finally {
      setBusy(false);
      onTurnComplete();
    }
  }

  return (
    <div className="chat">
      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="welcome">
            <h2>👋 Your AI Travel Concierge</h2>
            <p>Plan trips, check visa requirements, and book with a card on file.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <Message key={i} msg={m} />
        ))}
      </div>
      <div className="chat-input">
        <input
          value={input}
          placeholder="Ask about destinations, visas, hotels…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          disabled={busy}
        />
        <button className="btn-primary" onClick={() => send(input)} disabled={busy}>
          {busy ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
