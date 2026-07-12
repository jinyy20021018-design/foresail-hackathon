import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import type { GuideStep } from "./guideContent";

type GuideExit = "next" | "prev" | "done" | "skip";

interface Props {
  steps: GuideStep[];
  // Label for the final button when there is a next tab to jump to.
  // null => final step just closes ("Done").
  nextLabel: string | null;
  // Label for the previous tab, shown as a "Back" on the first step so the
  // user can retreat through the guided flow. null => no cross-tab back.
  prevLabel?: string | null;
  onClose: (dir: GuideExit) => void;
}

const PAD = 8;
const TOOLTIP_W = 340;
const TOOLTIP_H = 180;

export function GuideTour({ steps, nextLabel, prevLabel = null, onClose }: Props) {
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<DOMRect | null>(null);

  const current = steps[step];
  const isLast = step === steps.length - 1;

  const measure = useCallback(() => {
    const target = current?.selector ? document.querySelector(current.selector) : null;
    if (target) {
      // Instant scroll so the measured rect is final immediately; the ring's
      // own CSS transition animates it smoothly into place.
      target.scrollIntoView({ block: "center", behavior: "auto" });
      requestAnimationFrame(() => setRect(target.getBoundingClientRect()));
    } else {
      setRect(null); // centered card (page intro or missing anchor)
    }
  }, [current]);

  useLayoutEffect(() => {
    measure();
  }, [measure]);

  useEffect(() => {
    const handler = () => measure();
    window.addEventListener("resize", handler);
    window.addEventListener("scroll", handler, true);
    return () => {
      window.removeEventListener("resize", handler);
      window.removeEventListener("scroll", handler, true);
    };
  }, [measure]);

  // Action steps advance when the user actually clicks the highlighted control
  // (Accept all / Confirm / Run). Disabled controls don't fire click, which
  // keeps the order honest.
  useEffect(() => {
    if (!current?.advanceOnClick || !current.selector) return;
    const target = document.querySelector(current.selector);
    if (!target) return;
    const onTargetClick = () => setStep((s) => Math.min(s + 1, steps.length - 1));
    target.addEventListener("click", onTargetClick, { once: true });
    return () => target.removeEventListener("click", onTargetClick);
  }, [current, step, steps.length]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose("skip");
      else if (e.key === "ArrowRight" || e.key === "Enter") advance();
      else if (e.key === "ArrowLeft") back();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, isLast, nextLabel, prevLabel]);

  if (!current) return null;

  function advance() {
    if (isLast) onClose(nextLabel ? "next" : "done");
    else setStep((s) => s + 1);
  }
  function back() {
    if (step > 0) setStep((s) => s - 1);
    else if (prevLabel) onClose("prev");
  }

  const centered = !rect;
  const placement = current.placement ?? "bottom";

  const tooltipStyle: React.CSSProperties = centered
    ? { top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: TOOLTIP_W }
    : positionTooltip(rect as DOMRect, placement);

  const finalLabel = isLast ? (nextLabel ? `Next: ${nextLabel} →` : "Done ✓") : "Next";

  return (
    <div className="guide-layer" role="dialog" aria-label="新手引导">
      {/* Dimmed backdrop with a spotlight hole over the target */}
      <svg className="guide-mask" aria-hidden="true">
        <defs>
          <mask id="guide-hole">
            <rect x="0" y="0" width="100%" height="100%" fill="white" />
            {rect && (
              <rect
                x={rect.left - PAD}
                y={rect.top - PAD}
                width={rect.width + PAD * 2}
                height={rect.height + PAD * 2}
                rx="14"
                fill="black"
              />
            )}
          </mask>
        </defs>
        <rect x="0" y="0" width="100%" height="100%" fill="rgba(20,26,38,0.55)" mask="url(#guide-hole)" />
      </svg>

      {/* Highlight ring */}
      {rect && (
        <div
          className="guide-ring"
          style={{
            top: rect.top - PAD,
            left: rect.left - PAD,
            width: rect.width + PAD * 2,
            height: rect.height + PAD * 2,
          }}
        />
      )}

      {/* Tooltip / intro card */}
      <div className={`guide-tip${centered ? " centered" : ""}`} style={tooltipStyle}>
        <button className="guide-skip" type="button" onClick={() => onClose("skip")}>
          Skip
        </button>
        <h3>{current.title}</h3>
        <p>{current.body}</p>
        {current.advanceOnClick && <p className="guide-hint">↑ Click the highlighted button to continue.</p>}

        <div className="guide-foot">
          <div className="guide-dots" aria-hidden="true">
            {steps.map((_, i) => (
              <span key={i} className={i === step ? "on" : i < step ? "done" : ""} />
            ))}
          </div>
          <div className="guide-btns">
            {(step > 0 || prevLabel) && (
              <button className="guide-prev" type="button" onClick={back}>
                {step > 0 ? "Back" : `← ${prevLabel}`}
              </button>
            )}
            {!current.advanceOnClick && (
              <button className="guide-next" type="button" onClick={advance}>
                {finalLabel}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function positionTooltip(rect: DOMRect, preferred: GuideStep["placement"]): React.CSSProperties {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const gap = PAD + 10;
  let pos = preferred ?? "bottom";

  if (pos === "center") {
    return { top: "50%", left: "50%", transform: "translate(-50%, -50%)", width: TOOLTIP_W };
  }
  // Auto-flip when there is not enough room.
  if (pos === "bottom" && rect.bottom + gap + TOOLTIP_H > vh) pos = "top";
  if (pos === "top" && rect.top - gap - TOOLTIP_H < 0) pos = "bottom";
  if (pos === "right" && rect.right + gap + TOOLTIP_W > vw) pos = "left";
  if (pos === "left" && rect.left - gap - TOOLTIP_W < 0) pos = "right";

  const clampLeft = Math.min(Math.max(12, rect.left + rect.width / 2 - TOOLTIP_W / 2), vw - TOOLTIP_W - 12);
  const clampTop = Math.min(Math.max(12, rect.top + rect.height / 2 - TOOLTIP_H / 2), vh - TOOLTIP_H - 12);

  switch (pos) {
    case "top":
      return { top: Math.max(12, rect.top - gap - TOOLTIP_H), left: clampLeft, width: TOOLTIP_W };
    case "right":
      return { top: clampTop, left: rect.right + gap, width: TOOLTIP_W };
    case "left":
      return { top: clampTop, left: Math.max(12, rect.left - gap - TOOLTIP_W), width: TOOLTIP_W };
    case "bottom":
    default:
      return { top: rect.bottom + gap, left: clampLeft, width: TOOLTIP_W };
  }
}
