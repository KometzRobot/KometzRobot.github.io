// Journey — the framework view.
// One job, three lanes (Customer / Owner / Crew), eight milestones across the lifecycle.
// Each touchpoint is tagged with the integration level (L0–L4) that delivers it
// and which surface the action lives on. This is the glue diagram for the whole system.

const { useState: useSJ, useMemo: useMJ } = React;

// ─── Milestones: the spine of every job ──────────────────────────────────────
const MILESTONES = [
  { id: 'm-lead',     label: 'Lead arrives',         day: -28, stage: 'quote',      ic: 'inbox' },
  { id: 'm-quote',    label: 'Quote sent',           day: -21, stage: 'quote',      ic: 'mail' },
  { id: 'm-deposit',  label: 'Deposit · approved',   day:   0, stage: 'approved',   ic: 'check' },
  { id: 'm-design',   label: 'Design signed off',    day:  10, stage: 'design',     ic: 'layout' },
  { id: 'm-frame',    label: 'Frame complete',       day:  35, stage: 'frame',      ic: 'truck' },
  { id: 'm-mech',     label: 'Mechanicals tested',   day:  55, stage: 'plumbing',   ic: 'spark' },
  { id: 'm-final',    label: 'Final inspection',     day:  72, stage: 'electrical', ic: 'eye' },
  { id: 'm-deliver',  label: 'Delivered · keys',     day:  82, stage: 'delivered',  ic: 'send' },
];

// ─── Touchpoints: who feels what at each milestone, and which level builds it
// Lanes: customer · owner · crew
// Levels: 0 (mirror) · 1 (reflect) · 2 (notice) · 3 (augment) · 4 (replace)
// surface: which screen in the prototype delivers it
const TOUCHPOINTS = [
  // m-lead
  { m: 'm-lead', lane: 'customer', level: 0, surface: 'website',  text: 'Submits quote form on brothersfab.ca' },
  { m: 'm-lead', lane: 'owner',    level: 0, surface: 'pipeline', text: 'Lead lands in Pipeline · auto-classified by job type' },
  { m: 'm-lead', lane: 'owner',    level: 2, surface: 'ai',       text: 'AI drafts a first-touch reply with similar-job pricing band' },

  // m-quote
  { m: 'm-quote',  lane: 'owner',    level: 2, surface: 'ai',       text: 'AI assembles quote from past jobs of this type · Chris reviews' },
  { m: 'm-quote',  lane: 'customer', level: 0, surface: 'portal',   text: 'Receives quote PDF · clicks through to portal preview' },
  { m: 'm-quote',  lane: 'owner',    level: 1, surface: 'pipeline', text: 'Email replies thread under the lead automatically' },

  // m-deposit
  { m: 'm-deposit', lane: 'customer', level: 0, surface: 'portal',   text: 'Pays deposit · portal unlocks · welcome screen' },
  { m: 'm-deposit', lane: 'owner',    level: 0, surface: 'admin',    text: 'Job created in Trello · mirrors to admin dashboard' },
  { m: 'm-deposit', lane: 'crew',     level: 0, surface: 'tablet',   text: 'Job appears on shop tablet rail · no action required' },

  // m-design
  { m: 'm-design', lane: 'owner',    level: 2, surface: 'admin',    text: 'AI flags design vs. AHS code conflicts before sign-off' },
  { m: 'm-design', lane: 'customer', level: 0, surface: 'portal',   text: 'Reviews & approves layout from portal · one tap' },
  { m: 'm-design', lane: 'crew',     level: 3, surface: 'tablet',   text: 'Tablet asks once: "Tyler, are you welding the frame?" · tap face' },

  // m-frame
  { m: 'm-frame', lane: 'crew',     level: 1, surface: 'photo',    text: 'Crew text 4 build photos to build@brothersfab.ca · auto-tagged' },
  { m: 'm-frame', lane: 'owner',    level: 2, surface: 'admin',    text: 'AI: "Frame at 58% spent / 35% time. Flag?" · one tap' },
  { m: 'm-frame', lane: 'customer', level: 1, surface: 'portal',   text: 'Approved photos appear in feed with caption + crew name' },
  { m: 'm-frame', lane: 'crew',     level: 4, surface: 'tablet',   text: 'Punch-list ticked from tablet — Trello updates back' },

  // m-mech
  { m: 'm-mech', lane: 'owner',    level: 2, surface: 'inv',      text: 'AI: "Argon below reorder · 3 jobs need it. Draft Russel PO?"' },
  { m: 'm-mech', lane: 'crew',     level: 3, surface: 'tablet',   text: 'Andrew taps "gas pressure test ✓" while standing at the truck' },
  { m: 'm-mech', lane: 'customer', level: 1, surface: 'portal',   text: 'Notification: "mechanicals tested · everything passed"' },

  // m-final
  { m: 'm-final', lane: 'owner',    level: 2, surface: 'admin',    text: 'AI books AHS inspection slot from saved auditor calendar' },
  { m: 'm-final', lane: 'crew',     level: 0, surface: 'tablet',   text: 'Inspection date shown on job hero · countdown' },
  { m: 'm-final', lane: 'customer', level: 0, surface: 'portal',   text: 'Sees inspection date · gets walkthrough invite' },

  // m-deliver
  { m: 'm-deliver', lane: 'crew',     level: 1, surface: 'photo',    text: 'Hand-off photo MMSed in · auto-tagged "delivered"' },
  { m: 'm-deliver', lane: 'customer', level: 0, surface: 'portal',   text: 'Final invoice + warranty packet + how-to videos · all in portal' },
  { m: 'm-deliver', lane: 'owner',    level: 2, surface: 'ai',       text: 'AI drafts a 30/60/90 follow-up sequence · Chris approves once' },
];

const LANES = [
  { id: 'customer', label: 'Customer',     who: 'Luis · Mendez Tacos',   surface: 'portal' },
  { id: 'owner',    label: 'Owner / Admin', who: 'Chris · Michelle',      surface: 'admin' },
  { id: 'crew',     label: 'Crew',          who: 'Tyler · Jesse · Andrew', surface: 'tablet' },
];

const LEVEL_META = {
  0: { label: 'L0 · Mirror',  desc: 'Free signal — Trello, photos crew already take',     color: 'oklch(0.72 0.10 220)' },
  1: { label: 'L1 · Reflect', desc: 'Capture habits — email/MMS dropbox, label automation', color: 'oklch(0.72 0.13 100)' },
  2: { label: 'L2 · Notice',  desc: 'AI speaks first — single-tap approvals only',          color: 'oklch(0.70 0.14 35)' },
  3: { label: 'L3 · Augment', desc: 'New data, but only when it pays off',                  color: 'oklch(0.68 0.13 280)' },
  4: { label: 'L4 · Replace', desc: 'Tablet becomes source of truth · Trello fades',        color: 'oklch(0.65 0.11 155)' },
};

const SURFACE_LABEL = {
  website:  'Website',
  portal:   'Portal',
  pipeline: 'Pipeline',
  admin:    'Admin',
  tablet:   'Tablet',
  inv:      'Inventory',
  ai:       'Brothers AI',
  photo:    'Photo dropbox',
};

// ─────────────────────────────────────────────────────────────────────────────
function Journey() {
  const [filter, setFilter] = useSJ('all'); // 'all' | 'L0' | 'L1' | 'L2' | 'L3' | 'L4'
  const [hover, setHover]   = useSJ(null);  // milestone id

  const visible = useMJ(() => {
    if (filter === 'all') return TOUCHPOINTS;
    const lvl = +filter[1];
    return TOUCHPOINTS.filter(t => t.level === lvl);
  }, [filter]);

  return (
    <div className="journey">
      {/* Header — frames the artifact */}
      <header className="jr-header">
        <div>
          <div className="jr-eyebrow">The framework</div>
          <h1 className="jr-title">One job, end to end</h1>
          <p className="jr-sub">
            Mendez Tacos · BF-2041 · 24-ft custom truck. Every milestone, every lane, every level — laid out so the seams show.
            Each card is a real touchpoint built into the prototype today.
          </p>
        </div>
        <div className="jr-legend">
          <div className="jr-legend-row">
            {Object.entries(LEVEL_META).map(([k, v]) => (
              <button
                key={k}
                className={`jr-chip ${filter === 'L'+k ? 'on' : ''}`}
                onClick={() => setFilter(filter === 'L'+k ? 'all' : 'L'+k)}
                style={{ '--c': v.color }}
              >
                <span className="jr-chip-dot" style={{ background: v.color }} />
                {v.label}
              </button>
            ))}
            <button className={`jr-chip ${filter === 'all' ? 'on' : ''}`} onClick={() => setFilter('all')}>
              show all
            </button>
          </div>
        </div>
      </header>

      {/* Adoption arc — the through-line */}
      <div className="jr-arc">
        <div className="jr-arc-track">
          <div className="jr-arc-fill" style={{ width: '52%' }} />
          <div className="jr-arc-mark" style={{ left: '0%' }}>
            <div className="jr-arc-mark-dot" />
            <div className="jr-arc-mark-label">Day 1<br/><em>connect Trello</em></div>
          </div>
          <div className="jr-arc-mark" style={{ left: '18%' }}>
            <div className="jr-arc-mark-dot" />
            <div className="jr-arc-mark-label">Week 1<br/><em>portals lit up</em></div>
          </div>
          <div className="jr-arc-mark" style={{ left: '38%' }}>
            <div className="jr-arc-mark-dot" />
            <div className="jr-arc-mark-label">Week 2<br/><em>photo dropbox warm</em></div>
          </div>
          <div className="jr-arc-mark current" style={{ left: '52%' }}>
            <div className="jr-arc-mark-dot" />
            <div className="jr-arc-mark-label">Today<br/><em>L2 morning approvals</em></div>
          </div>
          <div className="jr-arc-mark" style={{ left: '74%' }}>
            <div className="jr-arc-mark-dot" />
            <div className="jr-arc-mark-label">Month 4<br/><em>crew taps once for assignment</em></div>
          </div>
          <div className="jr-arc-mark" style={{ left: '100%' }}>
            <div className="jr-arc-mark-dot" />
            <div className="jr-arc-mark-label">Month 6<br/><em>Chris hasn't opened Trello in a week</em></div>
          </div>
        </div>
      </div>

      {/* The grid: lanes × milestones */}
      <div className="jr-grid">
        {/* Top row: milestone headers */}
        <div className="jr-corner">
          <div className="jr-corner-title">Lifecycle</div>
          <div className="jr-corner-sub">~110 days, lead to delivery</div>
        </div>
        {MILESTONES.map(ms => (
          <div
            key={ms.id}
            className={`jr-ms ${hover === ms.id ? 'hover' : ''}`}
            onMouseEnter={() => setHover(ms.id)}
            onMouseLeave={() => setHover(null)}
          >
            <div className="jr-ms-day mono">{ms.day < 0 ? `pre · ${Math.abs(ms.day)}d` : ms.day === 0 ? 'day 0' : `day ${ms.day}`}</div>
            <div className="jr-ms-mark"><Ic[ms.ic] size={14} /></div>
            <div className="jr-ms-label">{ms.label}</div>
            <div className="jr-ms-stage">{window.BF_STAGES.find(s => s.id === ms.stage)?.label}</div>
          </div>
        ))}

        {/* Lane rows */}
        {LANES.map(lane => (
          <React.Fragment key={lane.id}>
            <div className={`jr-lane jr-lane-${lane.id}`}>
              <div className="jr-lane-label">{lane.label}</div>
              <div className="jr-lane-who muted">{lane.who}</div>
              <div className="jr-lane-surf">
                <Ic.eye size={11}/> opens in {SURFACE_LABEL[lane.surface]}
              </div>
            </div>
            {MILESTONES.map(ms => {
              const cells = visible.filter(t => t.m === ms.id && t.lane === lane.id);
              return (
                <div
                  key={ms.id + lane.id}
                  className={`jr-cell ${hover === ms.id ? 'hover' : ''}`}
                  onMouseEnter={() => setHover(ms.id)}
                  onMouseLeave={() => setHover(null)}
                >
                  {cells.map((t, i) => (
                    <div key={i} className="jr-card" style={{ '--c': LEVEL_META[t.level].color }}>
                      <div className="jr-card-head">
                        <span className="jr-card-lvl" style={{ background: LEVEL_META[t.level].color }}>L{t.level}</span>
                        <span className="jr-card-surf">{SURFACE_LABEL[t.surface]}</span>
                      </div>
                      <div className="jr-card-text">{t.text}</div>
                    </div>
                  ))}
                  {cells.length === 0 && <div className="jr-cell-empty">—</div>}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>

      {/* Level legend strip — the principle */}
      <section className="jr-principle">
        <div className="jr-principle-head">
          <div className="section-label">The promise of each level</div>
          <div className="muted" style={{ fontSize: 12 }}>Each one earns the next · no level ships until the previous is in passive use</div>
        </div>
        <div className="jr-principle-grid">
          {Object.entries(LEVEL_META).map(([k, v]) => (
            <div key={k} className="jr-principle-card" style={{ '--c': v.color }}>
              <div className="jr-principle-mark" style={{ background: v.color }}>L{k}</div>
              <div className="jr-principle-name">{v.label.split('·')[1].trim()}</div>
              <div className="jr-principle-desc">{v.desc}</div>
              <div className="jr-principle-meta">
                <span className="muted" style={{ fontSize: 11 }}>{TOUCHPOINTS.filter(t => t.level === +k).length} touchpoints in this prototype</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Cross-references: how surfaces talk to each other */}
      <section className="jr-flows">
        <div className="jr-principle-head">
          <div className="section-label">How the surfaces talk</div>
          <div className="muted" style={{ fontSize: 12 }}>Every arrow is a real wire in the prototype · no dead ends</div>
        </div>
        <div className="jr-flow-diagram">
          <div className="jr-node trello"><strong>Trello</strong><span>source of truth (today)</span></div>
          <div className="jr-arrows">
            <svg width="100%" height="120" viewBox="0 0 800 120" preserveAspectRatio="none">
              <defs>
                <marker id="jr-arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">
                  <path d="M0,0 L8,4 L0,8 z" fill="oklch(0.55 0.01 260)" />
                </marker>
              </defs>
              <path d="M 100 60 Q 200 20 350 60"  stroke="oklch(0.55 0.01 260)" strokeWidth="1.5" fill="none" strokeDasharray="4 3" markerEnd="url(#jr-arr)"/>
              <path d="M 100 60 Q 250 100 400 90" stroke="oklch(0.55 0.01 260)" strokeWidth="1.5" fill="none" strokeDasharray="4 3" markerEnd="url(#jr-arr)"/>
              <path d="M 100 60 L 250 60"          stroke="oklch(0.55 0.01 260)" strokeWidth="1.5" fill="none" strokeDasharray="4 3" markerEnd="url(#jr-arr)"/>
              <text x="180" y="35" fontSize="10" fill="oklch(0.50 0.01 260)" fontStyle="italic">read-only mirror</text>
              <text x="500" y="55" fontSize="10" fill="oklch(0.50 0.01 260)" fontStyle="italic">photos · checklists · stages (L4 writes back)</text>
            </svg>
          </div>
          <div className="jr-nodes">
            <div className="jr-node admin"><strong>Admin</strong><span>Chris · Michelle</span></div>
            <div className="jr-node tablet"><strong>Shop Tablet</strong><span>wall-mounted</span></div>
            <div className="jr-node portal"><strong>Customer Portal</strong><span>per-job link</span></div>
          </div>
          <div className="jr-side-rails">
            <div className="jr-side">
              <div className="jr-side-head"><Ic.mail size={13}/> Photo dropbox</div>
              <div className="jr-side-body">build@brothersfab.ca · MMS line · attaches photo to active job</div>
            </div>
            <div className="jr-side">
              <div className="jr-side-head"><Ic.spark size={13}/> Brothers AI</div>
              <div className="jr-side-body">Watches everything, surfaces single-tap suggestions in Admin / Inventory / Pipeline</div>
            </div>
            <div className="jr-side">
              <div className="jr-side-head"><Ic.dollar size={13}/> Vendor inbox</div>
              <div className="jr-side-body">bills@brothersfab.ca · OCR'd & attached to right job</div>
            </div>
          </div>
        </div>
      </section>

      {/* Honesty footer */}
      <section className="jr-honest">
        <div className="jr-honest-head"><Ic.alert size={14}/> What's <em>not</em> in this prototype yet</div>
        <ul className="jr-honest-list">
          <li><strong>Real Trello writes</strong> — connect screen + adapter exist; live writes (drag = move card) ship in Phase 2.</li>
          <li><strong>Geofence punch-in</strong> — passive presence requires shop wifi setup. Demo'd as one-tap toggle for now.</li>
          <li><strong>AHS code lookup</strong> — Brothers AI references it but the actual code-document RAG corpus needs uploading.</li>
          <li><strong>SMS dropbox</strong> — email path is wired, MMS-to-email gateway is a vendor decision pending.</li>
        </ul>
      </section>
    </div>
  );
}

if (typeof window !== 'undefined') {
  window.Journey = Journey;
  window.BF_MILESTONES = MILESTONES;
  window.BF_TOUCHPOINTS = TOUCHPOINTS;
  window.BF_LEVELS = LEVEL_META;
}
