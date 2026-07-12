interface Props {
  onStart: () => void;
  onSkip: () => void;
}

const PHASES = [
  {
    tag: "Intake",
    icon: "📄",
    text: "Upload documents → the system extracts the key facts → you confirm",
  },
  {
    tag: "Monitor",
    icon: "📡",
    text: "Run the agent → pull real external events → surface risks that hit this shipment",
  },
  {
    tag: "Treat",
    icon: "✅",
    text: "Draft recommended actions → you confirm → package into an approvable plan",
  },
];

export function GuideWelcome({ onStart, onSkip }: Props) {
  return (
    <div className="guide-layer welcome" role="dialog" aria-label="Welcome to ForeSail">
      <div className="guide-welcome-backdrop" />
      <div className="guide-welcome-card">
        <span className="guide-welcome-kicker">Getting started</span>
        <h2>👋 Welcome to ForeSail</h2>
        <p className="guide-welcome-lead">
          ForeSail watches the risk on a single cross-border shipment. The whole thing is just three
          phases — get these and you're set:
        </p>

        <div className="guide-phases">
          {PHASES.map((phase, i) => (
            <div className="guide-phase" key={phase.tag}>
              <span className="guide-phase-icon">{phase.icon}</span>
              <div>
                <strong>{phase.tag}</strong>
                <span>{phase.text}</span>
              </div>
              {i < PHASES.length - 1 && <span className="guide-phase-arrow">→</span>}
            </div>
          ))}
        </div>

        <p className="guide-welcome-note">
          I'll walk you through it — starting by setting up your first shipment, then guiding you page by
          page. You can replay this any time from the "?" in the top bar.
        </p>

        <div className="guide-welcome-actions">
          <button className="guide-skip-btn" type="button" onClick={onSkip}>
            Explore on my own
          </button>
          <button className="guide-start-btn" type="button" onClick={onStart}>
            Set up my first case →
          </button>
        </div>
      </div>
    </div>
  );
}
