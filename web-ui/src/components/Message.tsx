import ReactMarkdown from "react-markdown";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function Message({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === "user";
  return (
    <div className={`msg ${isUser ? "msg-user" : "msg-assistant"}`}>
      <div className="msg-avatar">{isUser ? "You" : "AI"}</div>
      <div className="msg-body">
        {isUser ? (
          <span>{msg.content}</span>
        ) : (
          <ReactMarkdown>{msg.content || "…"}</ReactMarkdown>
        )}
      </div>
    </div>
  );
}
