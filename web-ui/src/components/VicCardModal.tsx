import { useState } from "react";
import { onboardCard } from "../lib/agentClient";

interface Props {
  userId: string;
  onClose: () => void;
  onSuccess: (last4: string, brand: string) => void;
}

// Mock card capture. Card data is POSTed directly to the agent's REST endpoint,
// which forwards it to the mock VIC tokenization tool — it never reaches the LLM.
export function VicCardModal({ userId, onClose, onSuccess }: Props) {
  const [cardNumber, setCardNumber] = useState("4111 1111 1111 1111");
  const [expiration, setExpiration] = useState("12/28");
  const [cvv, setCvv] = useState("123");
  const [name, setName] = useState("Demo Traveler");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setBusy(true);
    setError("");
    try {
      const res = await onboardCard({
        user_id: userId,
        card_number: cardNumber.replace(/\s+/g, ""),
        expiration_date: expiration,
        cvv,
        cardholder_name: name,
      });
      if (res.success && res.card) {
        onSuccess(res.card.last4, res.card.card_brand);
      } else {
        setError(res.error ?? "Card onboarding failed");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Add Payment Card</h3>
        <p className="modal-note">
          🔒 Mock VIC tokenization — demo data only. Card details bypass the AI model.
        </p>
        <label>Cardholder Name</label>
        <input value={name} onChange={(e) => setName(e.target.value)} />
        <label>Card Number</label>
        <input value={cardNumber} onChange={(e) => setCardNumber(e.target.value)} />
        <div className="modal-row">
          <div>
            <label>Expiration</label>
            <input value={expiration} onChange={(e) => setExpiration(e.target.value)} />
          </div>
          <div>
            <label>CVV</label>
            <input value={cvv} onChange={(e) => setCvv(e.target.value)} />
          </div>
        </div>
        {error && <div className="modal-error">{error}</div>}
        <div className="modal-actions">
          <button className="btn-secondary" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn-primary" onClick={submit} disabled={busy}>
            {busy ? "Tokenizing…" : "Save Card"}
          </button>
        </div>
      </div>
    </div>
  );
}
