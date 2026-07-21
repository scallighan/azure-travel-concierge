import { ItinerarySummary } from "../lib/agentClient";

export function ItinerarySwitcher({
  itineraries,
  currentId,
  onSelect,
  onCreate,
  onDelete,
}: {
  itineraries: ItinerarySummary[];
  currentId: string | null;
  onSelect: (id: string) => void;
  onCreate: () => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="itin-switcher">
      <select
        className="itin-select"
        value={currentId ?? ""}
        onChange={(e) => onSelect(e.target.value)}
        aria-label="Select itinerary"
      >
        {itineraries.length === 0 && <option value="">No itineraries</option>}
        {itineraries.map((it) => (
          <option key={it.id} value={it.id}>
            {it.name} ({it.itemCount})
          </option>
        ))}
      </select>
      <button className="btn-secondary" onClick={onCreate} title="New itinerary">
        ＋ New
      </button>
      {currentId && (
        <button
          className="btn-link"
          onClick={() => onDelete(currentId)}
          title="Delete this itinerary"
        >
          Delete
        </button>
      )}
    </div>
  );
}
