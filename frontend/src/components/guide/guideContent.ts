// Guided-tour content for the case workspace.
// Each tab gets its own first-visit walkthrough; tours chain tab -> tab so a
// first-time user is walked through the whole flow one page at a time.
// Copy is plain-language for non-experts: what you see / what to do / where next.

export type GuideTabKey =
  | "overview"
  | "documents"
  | "conflicts"
  | "agent"
  | "events"
  | "risks"
  | "actions"
  | "treatment"
  | "audit";

export type GuidePlacement = "top" | "bottom" | "left" | "right" | "center";

export interface GuideStep {
  // CSS selector to spotlight. Empty string (or a missing element) renders a
  // centered card instead — used for page-intro steps and as a safe fallback.
  selector: string;
  title: string;
  body: string;
  placement?: GuidePlacement;
  // When true, clicking the highlighted element advances the tour — so an
  // action step (Accept all / Confirm / Run) is driven by doing it, not by a
  // separate "Next". Disabled targets can't be clicked, which naturally gates
  // the order (Run only fires after facts are confirmed).
  advanceOnClick?: boolean;
}

// Order the tabs are chained in — matches the 8-step trade workflow.
export const GUIDE_ORDER: GuideTabKey[] = [
  "overview",
  "documents",
  "conflicts",
  "agent",
  "events",
  "risks",
  "actions",
  "treatment",
  "audit",
];

export const TAB_LABELS: Record<GuideTabKey, string> = {
  overview: "Overview",
  documents: "Documents & Evidence",
  conflicts: "Conflicts",
  agent: "Agent Runs",
  events: "External Events",
  risks: "Risks & Obligations",
  actions: "Actions",
  treatment: "Treatment Plans",
  audit: "Audit",
};

export function nextTabOf(tab: GuideTabKey): GuideTabKey | null {
  const idx = GUIDE_ORDER.indexOf(tab);
  return idx >= 0 && idx < GUIDE_ORDER.length - 1 ? GUIDE_ORDER[idx + 1] : null;
}

export function prevTabOf(tab: GuideTabKey): GuideTabKey | null {
  const idx = GUIDE_ORDER.indexOf(tab);
  return idx > 0 ? GUIDE_ORDER[idx - 1] : null;
}

// Intake walkthrough — runs on the Create New Case page, where the user
// actually uploads their documents (the real start of the flow).
export const INTAKE_STEPS: GuideStep[] = [
  {
    selector: "",
    title: "Let's set up your first shipment",
    body: "ForeSail works off your real trade documents — it reads the facts straight out of them. So we start by uploading yours.",
    placement: "center",
  },
  {
    selector: ".document-slot-grid",
    title: "Upload your documents",
    body: "Drop your contract, LC, booking, and B/L into these slots. The contract is the key one — the more you add, the better the matching.",
    placement: "top",
  },
  {
    selector: "[data-guide='intake-sample']",
    title: "No documents on hand?",
    body: "Just trying ForeSail out? Click here to load a ready-made sample document set, then run the flow exactly as you would with your own files.",
    placement: "bottom",
  },
  {
    selector: "[data-guide='intake-extract']",
    title: "Extract the facts",
    body: "With your documents in, click here. The system pulls out the transaction facts and flags anything that conflicts across documents.",
    placement: "top",
  },
  {
    selector: "",
    title: "Then review & confirm",
    body: "Click Extract now. When it finishes, the drafted case facts appear below — I'll point you to the next step.",
    placement: "center",
  },
];

// Shown after extraction finishes: the "Continue to Review" button is far down
// the page, so we scroll to it and spotlight it.
export const INTAKE_CONTINUE_STEPS: GuideStep[] = [
  {
    selector: "[data-guide='intake-continue']",
    title: "Facts extracted — continue",
    body: "The system read the facts and drafted the case. Review the auto-filled details above if you like, then click “Continue to Review” to move into the case workspace.",
    placement: "top",
    advanceOnClick: true,
  },
];

export const GUIDE_STEPS: Record<GuideTabKey, GuideStep[]> = {
  overview: [
    {
      selector: "",
      title: "1 · Overview",
      body: "A 20-second read on whether this shipment is in trouble right now. Follow the blue highlights and you'll know your way around.",
      placement: "center",
    },
    {
      selector: "[data-guide='ov-alerts']",
      title: "Route alerts",
      body: "Every risk that hits this shipment is listed here. Click any card and the map on the right jumps to where it's happening.",
      placement: "bottom",
    },
    {
      selector: "[data-guide='ov-map']",
      title: "Route risk map",
      body: "Your whole route is drawn here, with risks coloured by severity. Click a risk to see why it affects you (the attribution note).",
      placement: "left",
    },
    {
      selector: "[data-guide='ov-shipment']",
      title: "The shipment facts",
      body: "Vessel, ports, Incoterm, payment terms — all auto-extracted from the documents you upload. This is the case in a nutshell.",
      placement: "left",
    },
    {
      selector: "[data-guide='ov-exposure']",
      title: "Your exposure flags",
      body: "Red = an exposure to watch, green = already covered. A quick read on where your gaps are.",
      placement: "left",
    },
    {
      selector: "[data-guide='run-agent']",
      title: "Run a monitoring cycle",
      body: "Click here and the system pulls the latest external events, scores them against this case, and drafts recommended actions. This is the engine of the whole flow.",
      placement: "bottom",
    },
    {
      selector: "",
      title: "Next: build the case",
      body: "That's the overview. Next, head to Documents & Evidence to see where those facts come from and how to confirm them.",
      placement: "center",
    },
  ],
  documents: [
    {
      selector: "",
      title: "2 · Documents & Evidence",
      body: "Step one is always intake: upload documents → the system extracts the facts → you review and confirm. That's this page.",
      placement: "center",
    },
    {
      selector: ".seat-confirm",
      title: "Confirm your seat first",
      body: "The system reads the parties on your documents to tell whether you're the seller or buyer (e.g. LC beneficiary = seller). Confirm it — every later analysis is framed from your side.",
      placement: "bottom",
    },
    {
      selector: "[data-guide='doc-accept-all']",
      title: "Approve the extracted facts",
      body: "These are the facts pulled from your documents. Skim them (click a field to see its source), then click “Accept all” to approve them.",
      placement: "bottom",
      advanceOnClick: true,
    },
    {
      selector: "[data-guide='doc-confirm']",
      title: "Confirm the facts",
      body: "Approved — now click “Confirm Fields” to lock them in as this case's confirmed facts.",
      placement: "top",
      advanceOnClick: true,
    },
    {
      selector: "[data-guide='run-agent']",
      title: "Run your first monitoring cycle",
      body: "Facts are locked in, so this button up here just unlocked. Click it — the agent pulls external events, scores them against this case, and surfaces the risks.",
      placement: "bottom",
      advanceOnClick: true,
    },
    {
      selector: "",
      title: "Monitoring is running",
      body: "Nice — that's the core loop. Risks will show up across the tabs. Next, let's look at how the system handles conflicting facts.",
      placement: "center",
    },
  ],
  conflicts: [
    {
      selector: "",
      title: "3 · Conflicts",
      body: "When a fact disagrees across documents (say the contract says CIF but the invoice says FOB), the system won't guess — it surfaces the conflict here for you to decide.",
      placement: "center",
    },
    {
      selector: ".conflicts-panel",
      title: "Settle each one",
      body: "Each conflict shows both sources and their evidence; you pick which to trust. High-severity conflicts must be resolved before you can confirm facts or run monitoring.",
      placement: "top",
    },
    {
      selector: "",
      title: "Next: monitoring runs",
      body: "With conflicts cleared, every monitoring run is logged. Head to Agent Runs to see that trail.",
      placement: "center",
    },
  ],
  agent: [
    {
      selector: "",
      title: "4 · Agent Runs",
      body: "Every time you run monitoring, the system records exactly what it did and what changed — fully traceable and reviewable.",
      placement: "center",
    },
    {
      selector: ".run-delta",
      title: "What changed this run",
      body: "Versus the last run: which risks were added, escalated, or resolved. So you only look at what actually moved, not the whole board again.",
      placement: "bottom",
    },
    {
      selector: ".run-history-panel",
      title: "Every past run",
      body: "Each monitoring run is archived here — open one to replay its full execution trace.",
      placement: "top",
    },
    {
      selector: "",
      title: "Next: external events",
      body: "Want to know where these risks come from? Head to External Events for the raw signals the system pulled in.",
      placement: "center",
    },
  ],
  events: [
    {
      selector: "",
      title: "5 · External Events",
      body: "The risks aren't guesses — they come from real external signals: news, geopolitical events, weather. This page shows those raw signals.",
      placement: "center",
    },
    {
      selector: ".corridor-board",
      title: "Corridor status",
      body: "Live status (green / amber / red) for the world's major shipping corridors. The ones on your route are highlighted, so you see where it's jammed.",
      placement: "bottom",
    },
    {
      selector: ".action-row",
      title: "Pull real events",
      body: "Click Search Real External Events — the system builds queries from this case and pulls live from GDELT / news / weather sources, then normalizes them.",
      placement: "bottom",
    },
    {
      selector: ".wide-data-table",
      title: "Event detail",
      body: "Every event it pulled: source, type, severity, confidence, and the ports / vessels it hit — all listed, with the original source one click away.",
      placement: "top",
    },
    {
      selector: "",
      title: "Next: risks & obligations",
      body: "How do events become risks to you? Head to Risks & Obligations for the scoring and who carries the risk.",
      placement: "center",
    },
  ],
  risks: [
    {
      selector: "",
      title: "6 · Risks & Obligations",
      body: "This page translates external events into what they mean for your shipment: which deadlines are closing in, and why each risk lands on you.",
      placement: "center",
    },
    {
      selector: ".deadline-matrix",
      title: "Deadline countdown",
      body: "Countdowns to your key deadlines — latest shipment date, LC expiry, and more. The redder and further left, the more urgent.",
      placement: "bottom",
    },
    {
      selector: ".relevance-panel",
      title: "Scoring & attribution",
      body: "How each risk's relevance score is built (vessel / port / time-window hits…), and whether the risk falls on buyer or seller under CIF.",
      placement: "top",
    },
    {
      selector: "",
      title: "Next: recommended actions",
      body: "Now that you know the risks, what should you do? Head to Actions to have the system draft recommendations.",
      placement: "center",
    },
  ],
  actions: [
    {
      selector: "",
      title: "7 · Actions",
      body: "Based on the current risks, the system drafts concrete actions you can take (amend the LC, reroute, chase a deadline…). You pick and edit them.",
      placement: "center",
    },
    {
      selector: ".action-grid",
      title: "Pick and confirm actions",
      body: "Click Generate Actions for candidates, tick the ones you'll take, edit the wording if needed, then confirm. Confirmed actions feed the treatment plan.",
      placement: "top",
    },
    {
      selector: "",
      title: "Next: treatment plans",
      body: "With actions set, head to Treatment Plans to organize them into an executable, approvable plan.",
      placement: "center",
    },
  ],
  treatment: [
    {
      selector: "",
      title: "8 · Treatment Plans",
      body: "Package the confirmed actions into a full treatment plan: who does what, by when, and what needs approval. This is where the flow lands.",
      placement: "center",
    },
    {
      selector: ".prerequisite-panel",
      title: "Generate & approve",
      body: "Generate a plan from the confirmed actions, edit it, and build an approval package to route to the relevant parties for sign-off.",
      placement: "top",
    },
    {
      selector: "",
      title: "Last stop: the audit trail",
      body: "Every decision should be traceable. Head to Audit for this case's full timeline, from intake to treatment.",
      placement: "center",
    },
  ],
  audit: [
    {
      selector: "",
      title: "9 · Audit",
      body: "This case's whole journey — intake, confirmation, every monitoring run, and treatment — is logged on a timeline you can trace and review any time.",
      placement: "center",
    },
    {
      selector: ".audit-grid",
      title: "The full timeline",
      body: "Left is the status-change timeline, right is every monitoring run. That's the full loop — you now know how to use ForeSail. 🎉",
      placement: "top",
    },
  ],
};

// ---- localStorage gating -------------------------------------------------

const WELCOME_KEY = "foresail_guide_welcome";
const SKIP_KEY = "foresail_guide_skipped";
const INTAKE_KEY = "foresail_guide_intake";
const tabKey = (tab: GuideTabKey) => `foresail_guide_tab_${tab}`;

export const guideStore = {
  welcomeSeen: () => localStorage.getItem(WELCOME_KEY) === "1",
  markWelcomeSeen: () => localStorage.setItem(WELCOME_KEY, "1"),
  skipped: () => localStorage.getItem(SKIP_KEY) === "1",
  setSkipped: () => localStorage.setItem(SKIP_KEY, "1"),
  intakeSeen: () => localStorage.getItem(INTAKE_KEY) === "1",
  markIntakeSeen: () => localStorage.setItem(INTAKE_KEY, "1"),
  tabSeen: (tab: GuideTabKey) => localStorage.getItem(tabKey(tab)) === "1",
  markTabSeen: (tab: GuideTabKey) => localStorage.setItem(tabKey(tab), "1"),
  reset: () => {
    Object.keys(localStorage)
      .filter((k) => k.startsWith("foresail_guide_"))
      .forEach((k) => localStorage.removeItem(k));
  },
};

export const GUIDE_RESTART_EVENT = "foresail:guide-restart";
