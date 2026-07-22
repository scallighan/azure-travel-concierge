import { config } from "./config";

export interface OrderItem {
  type?: string;
  title?: string;
  location?: string;
  price?: string;
  date?: string;
}

export interface Order {
  order_id?: string;
  itinerary_id?: string;
  status?: string;
  total_amount?: number;
  currency?: string;
  items_count?: number;
  items?: OrderItem[];
  payment_method?: string | null;
  transaction_reference?: string | null;
  createdAt?: string;
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
  map_url?: string;
  booking_url?: string;
}

/**
 * Bing Maps link for an itinerary place. Uses the agent-provided `map_url` when
 * present, otherwise derives a maps search from the title/location. Flights are
 * routes, not places, so they never get a link.
 */
export function itineraryMapUrl(it: ItineraryItem): string | null {
  if (it.type && it.type.toLowerCase().includes("flight")) return null;
  if (it.map_url) return it.map_url;
  const q = [it.title, it.location].filter(Boolean).join(", ").trim();
  if (!q) return null;
  return `https://www.bing.com/maps?q=${encodeURIComponent(q)}`;
}

/**
 * Booking link for a flight itinerary item. Uses the agent-provided `booking_url`
 * when present. Only flights carry a booking link; other item types return null.
 */
export function itineraryBookingUrl(it: ItineraryItem): string | null {
  const isFlight = it.type ? it.type.toLowerCase().includes("flight") : false;
  if (!isFlight) return null;
  const url = it.booking_url?.trim();
  if (!url || !/^https?:\/\//i.test(url)) return null;
  return url;
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

// A pending human-in-the-loop approval request surfaced by the harness. The
// agent pauses (plan/execute mode + tool approval) and waits for the user to
// approve or reject running a tool such as load_skill.
export interface AgentInterrupt {
  id: string;
  message: string;
  toolName: string;
  toolArgs: Record<string, unknown>;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toInterrupts(raw: any[]): AgentInterrupt[] {
  return (raw ?? []).map((it) => {
    const fc = it?.metadata?.agent_framework?.function_call ?? {};
    return {
      id: String(it?.id ?? it?.toolCallId ?? ""),
      message: it?.message ?? "Approve this action?",
      toolName: fc?.name ?? "action",
      toolArgs: (fc?.arguments as Record<string, unknown>) ?? {},
    };
  });
}

// Minimal AG-UI SSE client. We POST a RunAgentInput to /agui and parse the
// Server-Sent Events stream ourselves rather than using @ag-ui/client's
// HttpAgent. The MAF resume stream is not self-contained -- on resume it emits
// TOOL_CALL_END / TOOL_CALL_RESULT events for tool calls whose TOOL_CALL_START
// was in the previous (interrupted) run. @ag-ui/client's strict per-run event
// verifier rejects those with "No active tool call found", so we read the raw
// stream and only act on the text, interrupt, and error events we care about.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function postAgui(payload: Record<string, unknown>, onEvent: (ev: any) => void): Promise<void> {
  const resp = await fetch(`${base}/agui`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok || !resp.body) throw new Error(`Agent request failed (${resp.status})`);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";

  const emitFrame = (frame: string) => {
    const data = frame
      .split("\n")
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).replace(/^ /, ""))
      .join("\n");
    if (!data) return;
    try {
      onEvent(JSON.parse(data));
    } catch {
      /* ignore keepalive comments / partial frames */
    }
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const frames = buf.split("\n\n");
    buf = frames.pop() ?? "";
    for (const frame of frames) emitFrame(frame);
  }
  if (buf.trim()) emitFrame(buf);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function run(payload: Record<string, unknown>, onDelta: (text: string) => void): Promise<AgentInterrupt[]> {
  let interrupts: AgentInterrupt[] = [];
  let runError: string | null = null;
  await postAgui(payload, (ev) => {
    switch (ev?.type) {
      case "TEXT_MESSAGE_CONTENT":
        if (typeof ev.delta === "string") onDelta(ev.delta);
        break;
      case "RUN_FINISHED":
        if (ev.outcome?.type === "interrupt") interrupts = toInterrupts(ev.outcome.interrupts ?? []);
        break;
      case "RUN_ERROR":
        runError = ev.message ?? "Agent run failed";
        break;
    }
  });
  if (runError) throw new Error(runError);
  return interrupts;
}

// Stream the agent's response over the AG-UI protocol, invoking onDelta for each
// text chunk. Each turn carries only the new user message; the server
// (CosmosHistoryProvider, keyed by threadId) owns history, so we never resend the
// transcript. The (user_id, itinerary_id) travel in forwardedProps and as the
// thread id "user_id:itinerary_id".
//
// Returns any human-in-the-loop approval requests the run paused on. When the
// returned array is non-empty, the UI must collect the user's decision and call
// resumeChat to continue. The server holds the pending approval in-process
// (keyed by threadId), so the agent runs as a single replica.
export async function streamChat(
  prompt: string,
  userId: string,
  itineraryId: string,
  onDelta: (text: string) => void,
): Promise<AgentInterrupt[]> {
  return run(
    {
      threadId: `${userId}:${itineraryId}`,
      runId: newId(),
      messages: [{ id: newId(), role: "user", content: prompt }],
      forwardedProps: { user_id: userId, itinerary_id: itineraryId },
    },
    onDelta,
  );
}

// Resume a paused run by answering every open approval request with the same
// decision (accepted). Resolving one approval may surface the next one, so the
// UI keeps calling resumeChat until it returns an empty array.
export async function resumeChat(
  userId: string,
  itineraryId: string,
  interruptIds: string[],
  accepted: boolean,
  onDelta: (text: string) => void,
): Promise<AgentInterrupt[]> {
  return run(
    {
      threadId: `${userId}:${itineraryId}`,
      runId: newId(),
      messages: [],
      forwardedProps: { user_id: userId, itinerary_id: itineraryId },
      resume: interruptIds.map((id) => ({ interruptId: id, status: "resolved", payload: { accepted } })),
    },
    onDelta,
  );
}

export async function getOrders(userId: string): Promise<Order[]> {
  const r = await fetch(`${base}/api/orders/${userId}`);
  const data = await r.json();
  return (data.orders as Order[]) ?? [];
}

export async function getItinerary(userId: string, itineraryId: string): Promise<ItineraryItem[]> {
  const r = await fetch(`${base}/api/itinerary/${userId}/${itineraryId}`);
  const data = await r.json();
  return (data.items as ItineraryItem[]) ?? [];
}

/**
 * The persisted chat transcript for an itinerary. Used to restore the visible
 * conversation when switching itineraries or reloading — the agent already keeps
 * this history server-side (Cosmos), keyed by `userId:itineraryId`.
 */
export async function getHistory(
  userId: string,
  itineraryId: string,
): Promise<{ role: "user" | "assistant"; content: string }[]> {
  const r = await fetch(`${base}/api/history/${encodeURIComponent(userId)}/${encodeURIComponent(itineraryId)}`);
  if (!r.ok) return [];
  const data = await r.json();
  const msgs = Array.isArray(data.messages) ? data.messages : [];
  return msgs
    .filter(
      (m: unknown): m is { role: "user" | "assistant"; content: string } =>
        !!m &&
        ((m as { role?: string }).role === "user" || (m as { role?: string }).role === "assistant") &&
        typeof (m as { content?: unknown }).content === "string",
    )
    .map((m: { role: "user" | "assistant"; content: string }) => ({ role: m.role, content: m.content }));
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

export async function getCardStatus(
  userId: string,
): Promise<{ enabled: boolean; has_card?: boolean; last4?: string; brand?: string }> {
  const r = await fetch(`${base}/api/vic/card-status/${encodeURIComponent(userId)}`);
  if (!r.ok) return { enabled: false };
  return r.json();
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
