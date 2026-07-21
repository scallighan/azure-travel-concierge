import { CartItem, ItineraryItem } from "../lib/agentClient";

export function SidePanel({
  itinerary,
  cart,
  onAddCard,
  cardOnFile,
  vicEnabled,
}: {
  itinerary: ItineraryItem[];
  cart: CartItem[];
  onAddCard: () => void;
  cardOnFile: string | null;
  vicEnabled: boolean;
}) {
  return (
    <aside className="side-panel">
      <section>
        <div className="section-head">
          <h4>🧭 Itinerary</h4>
        </div>
        {itinerary.length === 0 && <p className="empty">Nothing planned yet.</p>}
        {itinerary.map((it, i) => (
          <div className="panel-card" key={i}>
            <strong>{it.title ?? it.type}</strong>
            {it.location && <div className="muted">{it.location}</div>}
            {it.date && <div className="muted">{it.date}</div>}
            {it.price && <div className="price">{it.price}</div>}
          </div>
        ))}
      </section>

      <section>
        <h4>🛒 Cart</h4>
        {cart.length === 0 && <p className="empty">Cart is empty.</p>}
        {cart.map((it, i) => (
          <div className="panel-card" key={i}>
            <strong>{it.title ?? it.item_type}</strong>
            {it.price && <div className="price">{it.price}</div>}
          </div>
        ))}
      </section>

      {vicEnabled && (
        <section>
          <h4>💳 Payment</h4>
          {cardOnFile ? (
            <p className="muted">Card on file ending {cardOnFile}</p>
          ) : (
            <p className="empty">No card saved.</p>
          )}
          <button className="btn-secondary full" onClick={onAddCard}>
            {cardOnFile ? "Update Card" : "Add Card"}
          </button>
        </section>
      )}
    </aside>
  );
}
