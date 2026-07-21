import { config } from "./config";

export interface CartItem {
  item_type?: string;
  title?: string;
  price?: string;
  [k: string]: unknown;
}

export interface ItineraryItem {
  type?: string;
  title?: string;
  location?: string;
  price?: string;
  date?: string;
  day?: number;
  description?: string;
}

const base = config.agentUrl.replace(/\/$/, "");

// Stream the agent's SSE response, invoking onDelta for each text chunk.
export async function streamChat(
  prompt: string,
  userId: string,
  sessionId: string,
  onDelta: (text: string) => void,
): Promise<void> {
  const resp = await fetch(`${base}/invocations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, user_id: userId, session_id: sessionId }),
  });
  if (!resp.body) throw new Error("No response body");

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const evt of events) {
      const line = evt.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      try {
        const data = JSON.parse(line.slice(5).trim());
        if (data.delta) onDelta(data.delta);
        if (data.error) throw new Error(data.error);
      } catch {
        /* ignore keep-alive / partial */
      }
    }
  }
}

export async function getCart(userId: string): Promise<CartItem[]> {
  const r = await fetch(`${base}/api/cart/${userId}`);
  const data = await r.json();
  return (data.items as CartItem[]) ?? [];
}

export async function getItinerary(userId: string): Promise<ItineraryItem[]> {
  const r = await fetch(`${base}/api/itinerary/${userId}`);
  const data = await r.json();
  return (data.items as ItineraryItem[]) ?? [];
}

export async function clearItinerary(userId: string): Promise<number> {
  const r = await fetch(`${base}/api/itinerary/${userId}`, { method: "DELETE" });
  const data = await r.json();
  return (data.removed as number) ?? 0;
}

export async function onboardCard(payload: {
  user_id: string;
  card_number: string;
  expiration_date: string;
  cvv: string;
  cardholder_name: string;
}): Promise<{ success: boolean; card?: { last4: string; card_brand: string }; error?: string }> {
  const r = await fetch(`${base}/api/vic/onboard-card`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return r.json();
}
