import { useEffect, useRef, useState } from "react";
import { Message, ChatMessage } from "./Message";
import { streamChat, resumeChat, AgentInterrupt } from "../lib/agentClient";

const SUGGESTIONS = [
  "Plan a 5-day trip: Chicago → Tokyo, ~Oct 20, 2 travelers, mid-range",
  "Find flights from SFO to Paris, Sept 10–17, 1 traveler",
  "Find me mid-range hotels in Kyoto for 3 nights under $200/night",
  "Add a day of things to do in Rome to my itinerary",
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
            <p>
              I plan and mock-book <strong>flights &amp; hotels</strong>, and add
              food &amp; activities to your itinerary. To start fast, tell me your{" "}
              <strong>origin, destination, dates, travelers</strong> and{" "}
              <strong>budget</strong>.
            </p>
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
          <Message
            key={i}
            msg={m}
            interactive={
              m.role === "assistant" &&
              i === messages.length - 1 &&
              !busy &&
              pending.length === 0
            }
            onSelectOption={send}
          />
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
          placeholder={pending.length ? "Approve or reject the pending action…" : "e.g. Chicago → Tokyo, ~Oct 20, 2 travelers, mid-range…"}
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
