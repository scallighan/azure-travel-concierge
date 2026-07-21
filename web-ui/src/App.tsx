import { useCallback, useEffect, useMemo, useState } from "react";
import { Chat } from "./components/Chat";
import { SidePanel } from "./components/SidePanel";
import { VicCardModal } from "./components/VicCardModal";
import { config, DEMO_USER_ID } from "./lib/config";
import { getCart, getItinerary, CartItem, ItineraryItem } from "./lib/agentClient";

export default function App({ userId, userName }: { userId?: string; userName?: string }) {
  const uid = userId ?? DEMO_USER_ID;
  const sessionId = useMemo(() => `sess-${Date.now()}`, []);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [itinerary, setItinerary] = useState<ItineraryItem[]>([]);
  const [showCard, setShowCard] = useState(false);
  const [cardOnFile, setCardOnFile] = useState<string | null>(null);

  const refresh = useCallback(() => {
    getCart(uid).then(setCart).catch(() => {});
    getItinerary(uid).then(setItinerary).catch(() => {});
  }, [uid]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">✈️ Travel Concierge</div>
        <div className="user">
          {userName ?? "Demo Traveler"}
          <span className="badge">Azure AI Foundry</span>
        </div>
      </header>
      <div className="layout">
        <Chat userId={uid} sessionId={sessionId} onTurnComplete={refresh} />
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
