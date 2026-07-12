import type { ScoreFactor, RelevanceResult } from "../api/client";
import "../styles/viz.css";

const CLASS_TONE: Record<string, string> = { Relevant: "red", Watch: "amber", Irrelevant: "faint" };

export function ScoreWaterfall({ result }: { result: RelevanceResult }) {
  const factors: ScoreFactor[] = result.factor_breakdown ?? [];
  if (factors.length === 0) return null;

  // Scale bars against the largest absolute contribution so the biggest driver fills the row.
  const maxAbs = Math.max(1, ...factors.map((f) => Math.abs(f.delta)));
  const tone = CLASS_TONE[result.classification] ?? "faint";

  return (
    <div className="waterfall">
      <div className="waterfall-head">
        <span className="viz-kicker">Why this scored {result.display_score ?? result.score}</span>
        <span className={`waterfall-verdict ${tone}`}>{result.classification}</span>
      </div>
      <div className="waterfall-rows">
        {factors.map((f, i) => {
          const positive = f.delta > 0;
          const zero = f.delta === 0;
          const widthPct = zero ? 0 : Math.max(6, Math.round((Math.abs(f.delta) / maxAbs) * 100));
          const kindTag = f.kind === "scale" ? "×conf" : f.kind === "cap" ? "cap" : f.kind === "flag" ? "rule" : "";
          return (
            <div className="wf-row" key={`${f.factor}-${i}`}>
              <span className="wf-label" title={f.label}>{f.label}</span>
              <div className="wf-track">
                <span className="wf-axis" />
                {!zero && (
                  <div
                    className={`wf-bar ${positive ? "pos" : "neg"}`}
                    style={positive ? { left: "50%", width: `${widthPct / 2}%` } : { right: "50%", width: `${widthPct / 2}%` }}
                  />
                )}
              </div>
              <span className={`wf-delta ${zero ? "zero" : positive ? "pos" : "neg"}`}>
                {zero ? (kindTag || "0") : `${positive ? "+" : ""}${f.delta}`}
              </span>
            </div>
          );
        })}
      </div>
      <div className="wf-total">
        <span>Relevance score</span>
        <strong className={tone}>{result.display_score ?? result.score}</strong>
      </div>
    </div>
  );
}
