import { useCallback, useEffect, useState } from "react";
import { Chat } from "./components/Chat";
import { SidePanel } from "./components/SidePanel";
import { ItinerarySwitcher } from "./components/ItinerarySwitcher";
import { VicCardModal } from "./components/VicCardModal";
import { config, DEMO_USER_ID } from "./lib/config";
import {
  getCart,
  getItinerary,
  listItineraries,
  createItinerary,
  deleteItinerary,
  CartItem,
  ItineraryItem,
  ItinerarySummary,
} from "./lib/agentClient";

export default function App({ userId, userName }: { userId?: string; userName?: string }) {
  const uid = userId ?? DEMO_USER_ID;
  const [itineraries, setItineraries] = useState<ItinerarySummary[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [itinerary, setItinerary] = useState<ItineraryItem[]>([]);
  const [showCard, setShowCard] = useState(false);
  const [cardOnFile, setCardOnFile] = useState<string | null>(null);

  // Load (and if necessary seed) the user's itineraries once.
  useEffect(() => {
    let active = true;
    (async () => {
      let list = await listItineraries(uid).catch(() => [] as ItinerarySummary[]);
      if (list.length === 0) {
        const created = await createItinerary(uid, "My Trip").catch(() => null);
        if (created) list = [created];
      }
      if (!active) return;
      setItineraries(list);
      setCurrentId((prev) => prev ?? list[0]?.id ?? null);
    })();
    return () => {
      active = false;
    };
  }, [uid]);

  const refresh = useCallback(() => {
    getCart(uid).then(setCart).catch(() => {});
    if (currentId) {
      getItinerary(uid, currentId).then(setItinerary).catch(() => {});
    } else {
      setItinerary([]);
    }
    listItineraries(uid).then(setItineraries).catch(() => {});
  }, [uid, currentId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleCreate = useCallback(async () => {
    const name = window.prompt("Name your new itinerary:", "New Trip");
    if (name === null) return;
    const created = await createItinerary(uid, name.trim() || "New Trip").catch(() => null);
    if (created) {
      setItineraries((prev) => [...prev, created]);
      setCurrentId(created.id);
    }
  }, [uid]);

  const handleDelete = useCallback(
    async (id: string) => {
      if (!window.confirm("Delete this itinerary and its conversation? This can't be undone.")) return;
      await deleteItinerary(uid, id).catch(() => {});
      const remaining = itineraries.filter((it) => it.id !== id);
      setItineraries(remaining);
      if (currentId === id) setCurrentId(remaining[0]?.id ?? null);
    },
    [uid, itineraries, currentId],
  );

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">✈️ Travel Concierge</div>
        <ItinerarySwitcher
          itineraries={itineraries}
          currentId={currentId}
          onSelect={setCurrentId}
          onCreate={handleCreate}
          onDelete={handleDelete}
        />
        <div className="user">
          {userName ?? "Demo Traveler"}
          <span className="badge">Azure AI Foundry</span>
        </div>
      </header>
      <div className="layout">
        {currentId ? (
          <Chat key={currentId} userId={uid} sessionId={currentId} onTurnComplete={refresh} />
        ) : (
          <div className="chat">
            <div className="welcome">
              <h2>Create an itinerary to get started</h2>
            </div>
          </div>
        )}
        <SidePanel
          itinerary={itinerary}
          cart={cart}
          cardOnFile={cardOnFile}
          vicEnabled={config.enableVic}
          onAddCard={() => setShowCard(true)}
        />
      </div>
      {showCard && (
        <VicCardModal
          userId={uid}
          onClose={() => setShowCard(false)}
          onSuccess={(last4) => {
            setCardOnFile(last4);
            setShowCard(false);
          }}
        />
      )}
    </div>
  );
}
