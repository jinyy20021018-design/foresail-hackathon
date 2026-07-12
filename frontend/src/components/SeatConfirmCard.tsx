import { useState } from "react";
import type { TradeCase, TradePerspective } from "../api/client";

type Props = {
  tradeCase: TradeCase;
  basis?: string;
  onSetSeat: (perspective: TradePerspective) => Promise<void>;
};

export function SeatConfirmCard({ tradeCase, basis, onSetSeat }: Props) {
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const detected = (tradeCase.trade_perspective ?? "SELLER") as TradePerspective;
  const detectedLabel = detected === "SELLER" ? "Seller" : "Buyer";
  const oppositeLabel = detected === "SELLER" ? "Buyer" : "Seller";
  const opposite: TradePerspective = detected === "SELLER" ? "BUYER" : "SELLER";
  const confirmed = tradeCase.perspective_source === "MANUAL";
  const basisText = basis || tradeCase.perspective_basis || "";

  async function run(perspective: TradePerspective) {
    setError(null);
    setIsBusy(true);
    try {
      await onSetSeat(perspective);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update our role.");
    } finally {
      setIsBusy(false);
    }
  }

  if (confirmed) {
    return (
      <div className="panel seat-confirm confirmed">
        <span className="fchip on">Our role confirmed: {detectedLabel}</span>
        {basisText && <span className="seat-basis">{basisText}</span>}
      </div>
    );
  }

  return (
    <div className="panel seat-confirm">
      <div className="seat-confirm-copy">
        <span className="section-kicker">Our role in this trade</span>
        <strong>We detected your company as the {detectedLabel}.</strong>
        {basisText && <p className="seat-basis">{basisText}</p>}
        <p className="seat-confirm-q">Is this correct?</p>
      </div>
      <div className="seat-confirm-actions">
        <button className="primary-action" type="button" disabled={isBusy} onClick={() => run(detected)}>
          {isBusy ? "Saving…" : `Yes, we are the ${detectedLabel}`}
        </button>
        <button className="secondary-action" type="button" disabled={isBusy} onClick={() => run(opposite)}>
          No, we are the {oppositeLabel}
        </button>
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  );
}
