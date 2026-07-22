import { Order, ItineraryItem, itineraryMapUrl, itineraryBookingUrl } from "../lib/agentClient";

function formatAmount(order: Order): string {
  if (typeof order.total_amount === "number") {
    return `${order.currency ?? "USD"} ${order.total_amount.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  }
  return "";
}

export function SidePanel({
  itinerary,
  orders,
  onAddCard,
  cardOnFile,
  vicEnabled,
}: {
  itinerary: ItineraryItem[];
  orders: Order[];
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
        {itinerary.map((it, i) => {
          const mapUrl = itineraryMapUrl(it);
          const bookingUrl = itineraryBookingUrl(it);
          return (
            <div className="panel-card" key={i}>
              <strong>{it.title ?? it.type}</strong>
              {it.location && <div className="muted">{it.location}</div>}
              {it.date && <div className="muted">{it.date}</div>}
              {it.price && <div className="price">{it.price}</div>}
              {mapUrl && (
                <a className="map-link" href={mapUrl} target="_blank" rel="noreferrer">
                  📍 View on Bing Maps
                </a>
              )}
              {bookingUrl && (
                <a className="map-link" href={bookingUrl} target="_blank" rel="noreferrer">
                  ✈️ Book this flight
                </a>
              )}
            </div>
          );
        })}
      </section>

      <section>
        <h4>🧾 Past Orders</h4>
        {orders.length === 0 && <p className="empty">No orders yet.</p>}
        {orders.map((o, i) => (
          <div className="panel-card" key={o.order_id ?? i}>
            <strong>{o.order_id ?? "Order"}</strong>
            {formatAmount(o) && <div className="price">{formatAmount(o)}</div>}
            {typeof o.items_count === "number" && (
              <div className="muted">
                {o.items_count} item{o.items_count === 1 ? "" : "s"}
                {o.status ? ` · ${o.status}` : ""}
              </div>
            )}
            {o.payment_method && <div className="muted">{o.payment_method}</div>}
            {o.createdAt && (
              <div className="muted">{new Date(o.createdAt).toLocaleString()}</div>
            )}
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
