import { HttpAgent } from "@ag-ui/client";
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

export interface ItinerarySummary {
  id: string;
  name: string;
  itemCount: number;
  createdAt?: string;
  updatedAt?: string;
}

const base = config.agentUrl.replace(/\/$/, "");

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

// Stream the agent's response over the AG-UI protocol, invoking onDelta for each
// text chunk. A fresh HttpAgent is created per turn carrying only the new user
// message; the server (CosmosHistoryProvider, keyed by threadId) owns history, so
// we never resend the transcript. The (user_id, itinerary_id) travel in
// forwardedProps and as the thread id "user_id:itinerary_id".
export async function streamChat(
  prompt: string,
  userId: string,
  itineraryId: string,
  onDelta: (text: string) => void,
): Promise<void> {
  const agent = new HttpAgent({
    url: `${base}/agui`,
    threadId: `${userId}:${itineraryId}`,
    initialMessages: [{ id: newId(), role: "user", content: prompt }],
  });

  let runError: string | null = null;
  await agent.runAgent(
    { forwardedProps: { user_id: userId, itinerary_id: itineraryId } },
    {
      onTextMessageContentEvent: ({ event }) => onDelta(event.delta),
      onRunErrorEvent: ({ event }) => {
        runError = event.message ?? "Agent run failed";
      },
    },
  );
  if (runError) throw new Error(runError);
}

export async function getCart(userId: string): Promise<CartItem[]> {
  const r = await fetch(`${base}/api/cart/${userId}`);
  const data = await r.json();
  return (data.items as CartItem[]) ?? [];
}

export async function getItinerary(userId: string, itineraryId: string): Promise<ItineraryItem[]> {
  const r = await fetch(`${base}/api/itinerary/${userId}/${itineraryId}`);
  const data = await r.json();
  return (data.items as ItineraryItem[]) ?? [];
}

export async function listItineraries(userId: string): Promise<ItinerarySummary[]> {
  const r = await fetch(`${base}/api/itineraries/${userId}`);
  const data = await r.json();
  return (data.itineraries as ItinerarySummary[]) ?? [];
}

export async function createItinerary(userId: string, name: string): Promise<ItinerarySummary | null> {
  const r = await fetch(`${base}/api/itineraries/${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const data = await r.json();
  return (data.itinerary as ItinerarySummary) ?? null;
}

export async function renameItinerary(userId: string, itineraryId: string, name: string): Promise<boolean> {
  const r = await fetch(`${base}/api/itinerary/${userId}/${itineraryId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const data = await r.json();
  return Boolean(data.renamed);
}

export async function deleteItinerary(userId: string, itineraryId: string): Promise<boolean> {
  const r = await fetch(`${base}/api/itinerary/${userId}/${itineraryId}`, { method: "DELETE" });
  const data = await r.json();
  return Boolean(data.deleted);
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
