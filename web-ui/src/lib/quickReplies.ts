// Parse an assistant message for a machine-readable quick-reply block so the UI
// can render clickable option buttons. The agent emits choices as a fenced code
// block tagged `options`, one option per line:
//
//   ```options
//   Exact dates: Oct 20–25
//   Flexible a few days around Oct 20
//   ```
//
// We strip that block from the rendered text and return the options separately.

export interface ParsedMessage {
  text: string;
  options: string[];
}

// Matches a complete ```options ... ``` fenced block (case-insensitive tag).
const OPTIONS_BLOCK = /```[ \t]*options[ \t]*\r?\n([\s\S]*?)```/i;
// Matches an unclosed trailing block while the message is still streaming in.
const OPTIONS_BLOCK_OPEN = /```[ \t]*options[ \t]*\r?\n([\s\S]*)$/i;

function toOptions(body: string): string[] {
  return body
    .split(/\r?\n/)
    .map((l) => l.replace(/^\s*(?:[-*•]|\d+[.)])\s*/, "").trim())
    .filter((l) => l.length > 0);
}

export function parseMessage(content: string): ParsedMessage {
  const closed = content.match(OPTIONS_BLOCK);
  if (closed) {
    return {
      text: content.replace(OPTIONS_BLOCK, "").trim(),
      options: toOptions(closed[1]),
    };
  }
  // Hide a partially-streamed (unclosed) options block; don't render it as buttons yet.
  const open = content.match(OPTIONS_BLOCK_OPEN);
  if (open) {
    return { text: content.replace(OPTIONS_BLOCK_OPEN, "").trim(), options: [] };
  }
  return { text: content, options: [] };
}
