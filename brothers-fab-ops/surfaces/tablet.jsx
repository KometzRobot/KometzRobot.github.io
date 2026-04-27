// Shop Tablet — kanban + job detail + worker actions
// Designed for landscape 10-11" Android tablet, kiosk-mounted.
// Big tap targets, high contrast, gloves-friendly.

const { useState, useMemo, useEffect, useRef } = React;

function StageDot({ stage }) {
  const s = window.BF_STAGES.find(x => x.id === stage);
  return <span className="stage-dot" style={{ background: s?.color || 'var(--ink-3)' }} />;
}

function StageChip({ stage }) {
  const s = window.BF_STAGES.find(x => x.id === stage);
  if (!s) return null;
  return <span className="stage"><span className="stage-dot" style={{ background: s.color }} />{s.label}</span>;
}

function Avatar({ id, size=24 }) {
  const m = window.BF_TEAM.find(t => t.id === id);
  if (!m) return null;
  const initials = m.name.split(' ').map(s => s[0]).join('').slice(0, 2);
  return (
    <span title={m.name} style={{
      width: size, height: size, borderRadius: '50%',
      background: m.color, color: 'white',
      display: 'inline-grid', placeItems: 'center',
      fontSize: size * 0.42, fontWeight: 600,
      letterSpacing: '0.02em', flexShrink: 0,
      border: '1.5px solid var(--bg-elev)',
    }}>{initials}</span>
  );
}

function AvatarStack({ ids, size=24, max=4 }) {
  const shown = ids.slice(0, max);
  const more = ids.length - shown.length;
  return (
    <span style={{ display: 'inline-flex' }}>
      {shown.map((id, i) => (
        <span key={id} style={{ marginLeft: i === 0 ? 0 : -6 }}><Avatar id={id} size={size} /></span>
      ))}
      {more > 0 && (
        <span style={{
          width: size, height: size, borderRadius: '50%',
          background: 'var(--bg-sunk)', color: 'var(--ink-2)',
          border: '1.5px solid var(--bg-elev)',
          display: 'inline-grid', placeItems: 'center',
          fontSize: size * 0.38, fontWeight: 600, marginLeft: -6,
        }}>+{more}</span>
      )}
    </span>
  );
}

function Money({ n }) {
  if (n == null) return <span className="mono muted">--</span>;
  return <span className="mono">${(n/1000).toFixed(1)}K</span>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Tablet — left rail jobs, center detail, right action drawer
// ─────────────────────────────────────────────────────────────────────────────

function ShopTablet({ workerMode = true }) {
  const activeJobs = window.BF_JOBS.filter(j => j.stage !== 'quote' && j.stage !== 'delivered');
  const [activeId, setActiveId] = useState(activeJobs[0]?.id);
  const [punchedJob, setPunchedJob] = useState('BF-2041');
  const [punchStart] = useState(Date.now() - 1000 * 60 * 60 * 4 - 1000 * 60 * 12);
  const [now, setNow] = useState(Date.now());
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [logged, setLogged] = useState([]); // recently logged actions for confirmation
  const [activeAction, setActiveAction] = useState(null); // 'photo' | 'material' | 'punchlist' | 'blocker' | 'reorder' | null

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const job = window.BF_JOBS.find(j => j.id === activeId);
  const punchedFor = punchedJob ? Math.floor((now - punchStart) / 1000) : 0;
  const fmtTime = (s) => `${Math.floor(s/3600)}h ${String(Math.floor((s%3600)/60)).padStart(2,'0')}m`;

  const showLog = (msg) => {
    const id = Date.now();
    setLogged(prev => [...prev, { id, msg }]);
    setTimeout(() => setLogged(prev => prev.filter(l => l.id !== id)), 3200);
  };

  return (
    <div className="tablet-frame">
      {/* Tablet bezel — visual context that this is wall-mounted */}
      <div className="tablet-bezel">
        <div className="tablet-screen">
          {/* Header */}
          <div className="tablet-header">
            <div className="tablet-header-left">
              <div className="tablet-mark" title="Brothers Fab — est. 2019">
                <span>BF</span>
                <span className="tablet-mark-stamp">.19</span>
              </div>
              <div>
                <div className="tablet-title">Bay 2 — the back shop</div>
                <div className="tablet-subtitle">3633 16 St SE · −7°C, blowing snow · doors stay shut</div>
              </div>
            </div>
            <div className="tablet-header-mid">
              <div className="punch-indicator">
                {punchedJob ? (
                  <>
                    <span className="live-dot" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--success)' }} />
                    <span className="muted" style={{ fontSize: 12 }}>Punched in to</span>
                    <strong>{window.BF_JOBS.find(j => j.id === punchedJob)?.name}</strong>
                    <span className="mono" style={{ color: 'var(--ink-2)' }}>{fmtTime(punchedFor)}</span>
                  </>
                ) : (
                  <span className="muted">Not clocked in</span>
                )}
              </div>
            </div>
            <div className="tablet-header-right">
              <button className="tablet-icon-btn" title="Notifications">
                <Ic.bell size={20} />
                <span className="tablet-badge">3</span>
              </button>
              <button className={`tablet-icon-btn ${voiceOpen ? 'on' : ''}`} onClick={() => setVoiceOpen(v => !v)} title="Brothers AI voice">
                <Ic.mic size={20} />
              </button>
              <div className="tablet-worker">
                <Avatar id="jesse" size={32} />
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>Jesse</div>
                  <div className="muted" style={{ fontSize: 11 }}>welds, fab, general havoc</div>
                </div>
              </div>
            </div>
          </div>

          {/* Read-only banner — sets honest expectations for v1 */}
          {workerMode && (
            <div className="tablet-readonly-banner">
              <Ic.eye size={14} /> Mirroring Chris's Trello — if it's wrong here, it's wrong there. Tap a card to nudge him.
              <span className="tablet-readonly-spacer" />
              <span className="mono" style={{ opacity: 0.7 }}>synced 11s ago</span>
            </div>
          )}

          {/* Main grid */}
          <div className="tablet-main">
            {/* Job rail */}
            <aside className="tablet-rail scroll">
              <div className="tablet-rail-head">
                <span className="section-label">On the floor</span>
                <span className="muted mono" style={{ fontSize: 11 }}>{activeJobs.length} live</span>
              </div>
              {activeJobs.map(j => (
                <button
                  key={j.id}
                  className={`tablet-rail-item ${j.id === activeId ? 'active' : ''}`}
                  onClick={() => setActiveId(j.id)}
                >
                  <div className="tablet-rail-strip" style={{ background: j.color }} />
                  <div className="tablet-rail-body">
                    <div className="tablet-rail-name">{j.name}</div>
                    <div className="tablet-rail-meta">
                      <StageChip stage={j.stage} />
                      {j.blockers > 0 && <span className="chip" style={{ background: 'var(--danger-soft)', color: 'var(--danger-ink)', borderColor: 'transparent' }}>blocker</span>}
                    </div>
                    <div className="tablet-rail-prog">
                      <div className="progress"><i style={{ width: `${j.progress*100}%` }} /></div>
                      <span className="mono muted" style={{ fontSize: 10 }}>{Math.round(j.progress*100)}%</span>
                    </div>
                  </div>
                </button>
              ))}
              <button className="tablet-rail-add">
                <Ic.plus size={16} /> Shop task / fixing the shop itself
              </button>
            </aside>

            {/* Job detail */}
            <main className="tablet-detail scroll">
              {job && <JobDetail job={job} punchedJob={punchedJob} setPunchedJob={setPunchedJob} setActiveAction={setActiveAction} showLog={showLog} />}
            </main>

            {/* Action drawer — Level 3+. Hidden by default; revealed under owner mode. */}
            {!workerMode && (
            <aside className="tablet-actions">
              <div className="section-label" style={{ padding: '0 4px 8px' }}>
                Owner controls <span className="chip" style={{ marginLeft: 6, fontSize: 9, padding: '1px 6px' }}>Level 3+</span>
              </div>

              <button className="tap-action" onClick={() => setActiveAction('photo')}>
                <div className="tap-action-ic" style={{ background: 'oklch(0.95 0.03 250)', color: 'oklch(0.40 0.15 250)' }}><Ic.cam size={26} /></div>
                <div>
                  <div className="tap-action-title">Snap photo</div>
                  <div className="tap-action-sub">Auto-tags to {job?.name}</div>
                </div>
              </button>

              <button className="tap-action" onClick={() => setActiveAction('material')}>
                <div className="tap-action-ic" style={{ background: 'oklch(0.95 0.04 60)', color: 'oklch(0.42 0.16 50)' }}><Ic.box size={26} /></div>
                <div>
                  <div className="tap-action-title">Log material used</div>
                  <div className="tap-action-sub">Deducts from inventory</div>
                </div>
              </button>

              <button className="tap-action" onClick={() => setActiveAction('punchlist')}>
                <div className="tap-action-ic" style={{ background: 'oklch(0.95 0.04 155)', color: 'oklch(0.36 0.10 155)' }}><Ic.check size={26} /></div>
                <div>
                  <div className="tap-action-title">Mark task done</div>
                  <div className="tap-action-sub">{job?.name} punch-list</div>
                </div>
              </button>

              <button className="tap-action" onClick={() => setActiveAction('blocker')}>
                <div className="tap-action-ic" style={{ background: 'oklch(0.96 0.04 25)', color: 'oklch(0.42 0.16 25)' }}><Ic.flag size={26} /></div>
                <div>
                  <div className="tap-action-title">Flag a blocker</div>
                  <div className="tap-action-sub">Notifies Chris</div>
                </div>
              </button>

              <button className="tap-action" onClick={() => setActiveAction('reorder')}>
                <div className="tap-action-ic" style={{ background: 'oklch(0.95 0.04 280)', color: 'oklch(0.40 0.13 280)' }}><Ic.inbox size={26} /></div>
                <div>
                  <div className="tap-action-title">Request reorder</div>
                  <div className="tap-action-sub">Material running low</div>
                </div>
              </button>

              <div className="divider" />

              <div className="punch-card">
                {punchedJob === activeId ? (
                  <>
                    <div className="muted" style={{ fontSize: 12 }}>Clocked in to this job</div>
                    <div className="mono" style={{ fontSize: 22, fontWeight: 600 }}>{fmtTime(punchedFor)}</div>
                    <button className="btn tap" style={{ width: '100%', background: 'var(--danger)', borderColor: 'var(--danger)', color: 'white' }} onClick={() => { setPunchedJob(null); showLog('Punched out'); }}>
                      Punch out
                    </button>
                  </>
                ) : (
                  <>
                    <div className="muted" style={{ fontSize: 12 }}>Switch jobs?</div>
                    <button className="btn tap primary" style={{ width: '100%' }} onClick={() => { setPunchedJob(activeId); showLog(`Punched in to ${job?.name}`); }}>
                      <Ic.clock size={18} /> Punch in to {job?.name}
                    </button>
                  </>
                )}
              </div>
            </aside>
            )}
          </div>

          {/* Voice overlay */}
          {voiceOpen && <VoiceOverlay onClose={() => setVoiceOpen(false)} onLog={(msg) => { showLog(msg); setVoiceOpen(false); }} />}

          {/* Action sheet */}
          {activeAction && (
            <ActionSheet
              kind={activeAction}
              job={job}
              onClose={() => setActiveAction(null)}
              onComplete={(msg) => { showLog(msg); setActiveAction(null); }}
            />
          )}

          {/* Toast log */}
          <div className="toast-stack">
            {logged.map(l => (
              <div key={l.id} className="toast anim-in">
                <Ic.check size={16} /> {l.msg}
              </div>
            ))}
          </div>
        </div>

        {/* Wall mount visual cue */}
        <div className="tablet-mount-tag">10.4" · Wall-mounted · Bay 2</div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
function JobDetail({ job, punchedJob, setPunchedJob, setActiveAction, showLog }) {
  const stage = window.BF_STAGES.find(s => s.id === job.stage);
  const stageIdx = window.BF_STAGES.findIndex(s => s.id === job.stage);
  const nextStage = window.BF_STAGES[stageIdx + 1];

  const punchlist = useMemo(() => [
    { id: 'p1', text: 'Square frame to chassis (front)', done: true, who: 'tyler' },
    { id: 'p2', text: 'Square frame to chassis (rear)', done: true, who: 'tyler' },
    { id: 'p3', text: 'Weld out service body corners', done: true, who: 'jesse' },
    { id: 'p4', text: 'Stainless wall — port side (done, ground flush)', done: true, who: 'jesse' },
    { id: 'p5', text: 'Stainless wall — starboard (in progress, careful w/ scratches)', done: false, who: 'jesse', current: true },
    { id: 'p6', text: 'Dry-fit range + fryers — confirm clearances', done: false, who: 'chrisk' },
    { id: 'p7', text: 'Frame service window opening (40×36 rough)', done: false, who: 'tyler' },
    { id: 'p8', text: 'Hand sink rough-in — wait for Andrew before you close it up', done: false, who: 'andrew' },
  ], [job.id]);

  const [items, setItems] = useState(punchlist);
  useEffect(() => setItems(punchlist), [punchlist]);

  const toggle = (id) => setItems(prev => prev.map(p => p.id === id ? { ...p, done: !p.done } : p));

  const recentForJob = window.BF_ACTIVITY.filter(a => a.jobId === job.id).slice(-4).reverse();

  return (
    <div>
      {/* Hero — name + the one number that matters: how close to done */}
      <div className="job-hero">
        <div className="job-hero-strip" style={{ background: job.color }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="job-hero-title">{job.name}</h1>
          <div className="job-hero-meta">
            <StageChip stage={job.stage} />
            <AvatarStack ids={job.crew} size={26} />
            <span className="hero-eta">
              <Ic.clock size={12} />
              out the door {new Date(job.eta).toLocaleDateString('en-CA', { month: 'short', day: 'numeric' })}
              <span className={`conf conf-${job.etaConfidence}`}>{job.etaConfidence === 'high' ? 'on track' : job.etaConfidence === 'medium' ? 'tight' : 'slipping'}</span>
            </span>
          </div>
        </div>
        <div className="job-hero-pct">
          <div className="job-hero-pct-num">{Math.round(job.progress*100)}<span>%</span></div>
          <div className="job-hero-pct-label">{job.progress > 0.85 ? 'almost there' : job.progress > 0.5 ? 'past halfway' : 'getting going'}</div>
        </div>
      </div>

      {/* Stage rail = the whole status story, no extra strips */}
      <StageRail current={job.stage} />

      {/* Two columns: what's next + what just happened. Nothing else. */}
      <div className="job-cols">
        <section className="card job-col">
          <header className="job-col-head">
            <div className="section-label">Up next today</div>
            <span className="muted mono" style={{ fontSize: 10.5 }}>handwritten by Chris · Tue 7:14am</span>
          </header>
          <div>
            {items.filter(i => !i.done).slice(0, 3).map(item => (
              <button
                key={item.id}
                onClick={() => toggle(item.id)}
                className={`punch-item ${item.current ? 'current' : ''}`}
              >
                <span className="check-box">
                  {item.done && <Ic.check size={14} />}
                </span>
                <div className="punch-text">
                  <div>{item.text}</div>
                </div>
                <Avatar id={item.who} size={22} />
              </button>
            ))}
            {items.filter(i => !i.done).length > 3 && (
              <button className="punch-more">+{items.filter(i => !i.done).length - 3} more</button>
            )}
          </div>
        </section>

        <section className="card job-col">
          <header className="job-col-head">
            <div className="section-label">Last few moves</div>
            <span className="muted mono" style={{ fontSize: 10.5 }}>↻ live</span>
          </header>
          <div>
            {recentForJob.length === 0 && <div className="muted" style={{ padding: 16 }}>Quiet so far today.</div>}
            {recentForJob.slice(0, 3).map(a => (
              <div key={a.id} className="activity-row">
                <div className="activity-time mono muted">{a.t}</div>
                <ActivityIcon kind={a.kind} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="activity-title">{a.title}</div>
                </div>
                <Avatar id={a.who} size={22} />
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Photo strip — taped to the corkboard */}
      <section className="card" style={{ marginTop: 14 }}>
        <header className="job-col-head">
          <div className="section-label">From the floor</div>
          <button className="btn sm" onClick={() => setActiveAction('photo')}><Ic.cam size={14} /> snap one</button>
        </header>
        <div className="photo-strip">
          {Array.from({ length: 6 }).map((_, i) => {
            const captions = ['frame square / chassis', 'jesse · port wall', 'chris approved', 'fryer dry-fit', 'service window rough', 'argon — last tank'];
            const tilt = [-1.2, 0.8, -0.4, 1.4, -0.9, 0.3][i];
            return (
              <div key={i} className="photo-tile polaroid" style={{ transform: `rotate(${tilt}deg)` }}>
                <div className="polaroid-tape" />
                <div className="polaroid-img" style={{ backgroundImage: `url(${window.stockPhoto({ jobId: job.id, idx: i, stage: job.stage, type: job.type, w: 320, h: 240 })})` }} />
                <div className="polaroid-cap">{captions[i]}</div>
                {i < 2 && <span className="photo-tag">awaiting Chris</span>}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
function StageRail({ current }) {
  const idx = window.BF_STAGES.findIndex(s => s.id === current);
  return (
    <div className="stage-rail">
      {window.BF_STAGES.map((s, i) => {
        const done = i < idx;
        const cur = i === idx;
        return (
          <div key={s.id} className={`stage-rail-step ${done ? 'done' : ''} ${cur ? 'cur' : ''}`}>
            <div className="stage-rail-mark" style={{ background: done || cur ? s.color : 'var(--bg-sunk)' }}>
              {done && <Ic.check size={12} />}
            </div>
            <div className="stage-rail-label">{s.label}</div>
            {i < window.BF_STAGES.length - 1 && <div className="stage-rail-line" />}
          </div>
        );
      })}
    </div>
  );
}

function ActivityIcon({ kind }) {
  const map = {
    photo: { ic: <Ic.cam size={14} />, c: 'oklch(0.40 0.15 250)', bg: 'oklch(0.95 0.03 250)' },
    material: { ic: <Ic.box size={14} />, c: 'oklch(0.42 0.16 50)', bg: 'oklch(0.95 0.04 60)' },
    blocker: { ic: <Ic.flag size={14} />, c: 'oklch(0.42 0.16 25)', bg: 'oklch(0.96 0.04 25)' },
    stage: { ic: <Ic.arrow size={14} />, c: 'oklch(0.36 0.10 155)', bg: 'oklch(0.95 0.04 155)' },
    punchin: { ic: <Ic.clock size={14} />, c: 'oklch(0.36 0.10 155)', bg: 'oklch(0.95 0.04 155)' },
    punch: { ic: <Ic.check size={14} />, c: 'oklch(0.36 0.10 155)', bg: 'oklch(0.95 0.04 155)' },
    message: { ic: <Ic.msg size={14} />, c: 'oklch(0.40 0.13 280)', bg: 'oklch(0.95 0.04 280)' },
    reorder: { ic: <Ic.inbox size={14} />, c: 'oklch(0.40 0.13 280)', bg: 'oklch(0.95 0.04 280)' },
  };
  const m = map[kind] || map.stage;
  return <span style={{ width: 26, height: 26, borderRadius: 6, background: m.bg, color: m.c, display: 'inline-grid', placeItems: 'center', flexShrink: 0 }}>{m.ic}</span>;
}

// ─────────────────────────────────────────────────────────────────────────────
function ActionSheet({ kind, job, onClose, onComplete }) {
  const titles = {
    photo: 'Snap photo',
    material: 'Log material used',
    punchlist: 'Mark task complete',
    blocker: 'Flag a blocker',
    reorder: 'Request material reorder',
  };

  const [qty, setQty] = useState(8);
  const [matIdx, setMatIdx] = useState(0);
  const [note, setNote] = useState('');

  const doComplete = () => {
    if (kind === 'photo') onComplete(`Photo logged to ${job.name} · pending Chris's approval`);
    else if (kind === 'material') {
      const m = window.BF_MATERIALS[matIdx];
      onComplete(`Logged ${qty} ${m.unit} of ${m.name} to ${job.name}`);
    }
    else if (kind === 'punchlist') onComplete(`Task marked complete on ${job.name}`);
    else if (kind === 'blocker') onComplete(`Blocker flagged on ${job.name} · Chris notified`);
    else if (kind === 'reorder') onComplete(`Reorder requested · sent to Wolseley`);
    else onClose();
  };

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet anim-in" onClick={e => e.stopPropagation()}>
        <header className="sheet-head">
          <div>
            <div className="muted mono" style={{ fontSize: 11 }}>{job.id} · {job.name}</div>
            <h2 style={{ margin: '4px 0 0' }}>{titles[kind]}</h2>
          </div>
          <button className="tablet-icon-btn" onClick={onClose}><Ic.x size={22} /></button>
        </header>

        <div className="sheet-body">
          {kind === 'photo' && (
            <div>
              <div className="photo-shoot" style={{ backgroundImage: `url(${window.stockPhoto({ jobId: 'shoot', idx: 0, kind: 'shop', w: 800, h: 500 })})`, backgroundSize: 'cover', backgroundPosition: 'center', position: 'relative' }}>
                <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.55)', display: 'grid', placeItems: 'center', color: 'white', textAlign: 'center', borderRadius: 12 }}>
                  <div>
                    <Ic.cam size={48} />
                    <div style={{ marginTop: 12 }}>Tap to capture · or drop photos here</div>
                  </div>
                </div>
              </div>
              <label className="sheet-field">
                <span>Caption</span>
                <input type="text" placeholder="e.g. Frame welds, port side" />
              </label>
              <label className="sheet-field">
                <span>Tag to milestone</span>
                <select defaultValue={job.nextMilestone}>
                  <option>{job.nextMilestone}</option>
                  <option>Frame complete</option>
                  <option>Other / no milestone</option>
                </select>
              </label>
              <div className="sheet-info">
                <Ic.alert size={14} /> Photo will be visible to {job.client ? job.client.name : 'the client'} after Chris approves it.
              </div>
            </div>
          )}

          {kind === 'material' && (
            <div>
              <label className="sheet-field">
                <span>Material</span>
                <select value={matIdx} onChange={e => setMatIdx(+e.target.value)}>
                  {window.BF_MATERIALS.map((m, i) => (
                    <option key={m.sku} value={i}>{m.name} · {m.stock} {m.unit} on hand</option>
                  ))}
                </select>
              </label>
              <label className="sheet-field">
                <span>Quantity used</span>
                <div className="qty-row">
                  <button className="qty-btn" onClick={() => setQty(q => Math.max(0, q - 1))}>−</button>
                  <input type="number" value={qty} onChange={e => setQty(+e.target.value)} className="mono qty-input" />
                  <span className="muted">{window.BF_MATERIALS[matIdx].unit}</span>
                  <button className="qty-btn" onClick={() => setQty(q => q + 1)}>+</button>
                </div>
              </label>
              <div className="sheet-summary">
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>After this log</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>{Math.max(0, window.BF_MATERIALS[matIdx].stock - qty)} {window.BF_MATERIALS[matIdx].unit} on hand</div>
                </div>
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>Cost charged to job</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>${(window.BF_MATERIALS[matIdx].cost * qty).toFixed(2)}</div>
                </div>
              </div>
              {Math.max(0, window.BF_MATERIALS[matIdx].stock - qty) < window.BF_MATERIALS[matIdx].reorder && (
                <div className="sheet-warn"><Ic.alert size={14} /> This will drop below reorder level. Auto-reorder request will be drafted.</div>
              )}
            </div>
          )}

          {kind === 'blocker' && (
            <div>
              <label className="sheet-field">
                <span>What's blocking?</span>
                <textarea rows={3} placeholder="e.g. 304 SS sheet pushed 2 days by Russel — need to reschedule wall install" value={note} onChange={e => setNote(e.target.value)} />
              </label>
              <label className="sheet-field">
                <span>Severity</span>
                <div className="seg">
                  {['Heads up', 'Slows the job', 'Stops the job'].map((s, i) => (
                    <button key={s} className={i === 1 ? 'on' : ''}>{s}</button>
                  ))}
                </div>
              </label>
              <div className="sheet-info"><Ic.bell size={14} /> Chris is notified instantly. ETA confidence on {job.name} drops to "medium" until cleared.</div>
            </div>
          )}

          {kind === 'punchlist' && (
            <div>
              <div className="muted" style={{ fontSize: 13, marginBottom: 12 }}>Pick a task to mark complete:</div>
              {[
                'Stainless interior wall — starboard',
                'Equipment dry-fit: range, fryers',
                'Service window framing',
              ].map(t => (
                <label key={t} className="punch-pick">
                  <span className="check-box on"><Ic.check size={14} /></span>
                  <span>{t}</span>
                </label>
              ))}
            </div>
          )}

          {kind === 'reorder' && (
            <div>
              <label className="sheet-field">
                <span>Material</span>
                <select defaultValue="PEX-A 3/4&quot; Blue">
                  {window.BF_MATERIALS.map(m => <option key={m.sku}>{m.name}</option>)}
                </select>
              </label>
              <div className="sheet-summary">
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>Current stock</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>140 ft</div>
                </div>
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>Reorder level</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600 }}>200 ft</div>
                </div>
                <div>
                  <div className="muted" style={{ fontSize: 12 }}>Suggested order</div>
                  <div className="mono" style={{ fontSize: 18, fontWeight: 600, color: 'var(--accent-strong)' }}>300 ft</div>
                </div>
              </div>
              <div className="sheet-info"><Ic.spark size={14} /> Brothers AI: 4 active jobs use this. 30-day usage trending up. 300 ft covers ~6 weeks.</div>
            </div>
          )}
        </div>

        <footer className="sheet-foot">
          <button className="btn tap" onClick={onClose}>Cancel</button>
          <button className="btn tap primary" onClick={doComplete}>
            {kind === 'photo' && 'Save photo'}
            {kind === 'material' && `Log ${qty} ${window.BF_MATERIALS[matIdx].unit}`}
            {kind === 'punchlist' && 'Mark complete'}
            {kind === 'blocker' && 'Flag blocker'}
            {kind === 'reorder' && 'Send to Chris for approval'}
          </button>
        </footer>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
function VoiceOverlay({ onClose, onLog }) {
  // Read the wake word the user picked in Brothers AI > Voice settings
  const wakeId = (typeof localStorage !== 'undefined' && localStorage.getItem('bf-wake-id')) || 'computer';
  const wakeWord = wakeId === 'custom' ? (localStorage.getItem('bf-wake-custom') || 'Boss')
                 : wakeId === 'self'   ? (localStorage.getItem('bf-wake-self') || 'Forge')
                 : { computer: 'Computer', shop: 'Shop', cinder: 'Cinder', brofab: 'BroFab' }[wakeId] || 'Computer';

  const phrases = [
    `Hey ${wakeWord}, log 6 feet of one half PEX to Tinta job`,
    `Hey ${wakeWord}, what's the status of the Mendez build?`,
    `Hey ${wakeWord}, punch me out`,
    `Hey ${wakeWord}, show me the punch list for Aria Tower`,
    `Hey ${wakeWord}, reorder argon — we're down to three tanks`,
  ];
  const [i, setI] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setI(p => (p + 1) % phrases.length), 1800);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="voice-overlay" onClick={onClose}>
      <div className="voice-card" onClick={e => e.stopPropagation()}>
        <div className="voice-pulse">
          <div className="voice-pulse-ring"></div>
          <div className="voice-pulse-ring"></div>
          <div className="voice-pulse-mid"><Ic.mic size={36} /></div>
        </div>
        <div className="voice-hint muted">Listening · try saying</div>
        <div className="voice-phrase mono">"{phrases[i]}"</div>
        <div className="voice-actions">
          <button className="btn tap" onClick={onClose}>Cancel</button>
          <button className="btn tap primary" onClick={() => onLog('Logged 6 ft of 1/2" PEX to Tinta Mobile Bar')}>Simulate result</button>
        </div>
      </div>
    </div>
  );
}

if (typeof window !== 'undefined') {
  window.ShopTablet = ShopTablet;
  window.Avatar = Avatar;
  window.AvatarStack = AvatarStack;
  window.StageChip = StageChip;
  window.Money = Money;
  window.ActivityIcon = ActivityIcon;
}
