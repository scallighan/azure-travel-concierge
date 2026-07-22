import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { parseMessage } from "../lib/quickReplies";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function Message({
  msg,
  interactive = false,
  onSelectOption,
}: {
  msg: ChatMessage;
  interactive?: boolean;
  onSelectOption?: (option: string) => void;
}) {
  const isUser = msg.role === "user";
  const { text, options } = isUser
    ? { text: msg.content, options: [] as string[] }
    : parseMessage(msg.content);

  return (
    <div className={`msg ${isUser ? "msg-user" : "msg-assistant"}`}>
      <div className="msg-avatar">{isUser ? "You" : "AI"}</div>
      <div className="msg-body">
        {isUser ? (
          <span>{text}</span>
        ) : (
          <>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{text || "…"}</ReactMarkdown>
            {options.length > 0 && (
              <div className="quick-replies">
                {options.map((opt) => (
                  <button
                    key={opt}
                    className="quick-reply"
                    disabled={!interactive}
                    onClick={() => interactive && onSelectOption?.(opt)}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
