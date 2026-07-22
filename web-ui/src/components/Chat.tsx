import { useEffect, useRef, useState } from "react";
import { Message, ChatMessage } from "./Message";
import { streamChat, resumeChat, AgentInterrupt } from "../lib/agentClient";

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
  const [pending, setPending] = useState<AgentInterrupt[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages, pending]);

  function appendDelta(delta: string) {
    setMessages((m) => {
      const copy = [...m];
      copy[copy.length - 1] = {
        role: "assistant",
        content: copy[copy.length - 1].content + delta,
      };
      return copy;
    });
  }

  async function send(text: string) {
    if (!text.trim() || busy || pending.length) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", content: text }, { role: "assistant", content: "" }]);
    try {
      const interrupts = await streamChat(text, userId, sessionId, appendDelta);
      setPending(interrupts);
      if (!interrupts.length) onTurnComplete();
    } catch (e) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: `⚠️ ${String(e)}` };
        return copy;
      });
    } finally {
      setBusy(false);
    }
  }

  // Answer the current approval request(s). Resolving one may surface the next,
  // so loop until the agent finishes with no further interrupts.
  async function decide(accepted: boolean) {
    if (busy || !pending.length) return;
    setBusy(true);
    // Ensure there is an assistant bubble for continued output.
    setMessages((m) =>
      m.length && m[m.length - 1].role === "assistant" ? m : [...m, { role: "assistant", content: "" }],
    );
    let queue = pending;
    setPending([]);
    try {
      while (queue.length) {
        const next = await resumeChat(
          userId,
          sessionId,
          queue.map((i) => i.id),
          accepted,
          appendDelta,
        );
        queue = next;
      }
      setPending([]);
      onTurnComplete();
    } catch (e) {
      setMessages((m) => {
        const copy = [...m];
        copy[copy.length - 1] = { role: "assistant", content: `⚠️ ${String(e)}` };
        return copy;
      });
    } finally {
      setBusy(false);
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
        {pending.length > 0 && (
          <div className="approval-card">
            <div className="approval-title">Approval needed</div>
            <ul className="approval-list">
              {pending.map((p) => (
                <li key={p.id}>
                  <code>{p.toolName}</code>
                  {Object.keys(p.toolArgs).length > 0 && (
                    <span className="approval-args"> ({Object.values(p.toolArgs).join(", ")})</span>
                  )}
                </li>
              ))}
            </ul>
            <div className="approval-actions">
              <button className="btn-primary" onClick={() => decide(true)} disabled={busy}>
                {busy ? "…" : "Approve"}
              </button>
              <button className="btn-secondary" onClick={() => decide(false)} disabled={busy}>
                Reject
              </button>
            </div>
          </div>
        )}
      </div>
      <div className="chat-input">
        <input
          value={input}
          placeholder={pending.length ? "Approve or reject the pending action…" : "Ask about destinations, visas, hotels…"}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send(input)}
          disabled={busy || pending.length > 0}
        />
        <button className="btn-primary" onClick={() => send(input)} disabled={busy || pending.length > 0}>
          {busy ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}
