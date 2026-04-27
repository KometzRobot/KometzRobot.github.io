// Admin Dashboard, Customer Portal, Inventory, Quote Pipeline, Brothers AI

const { useState: useS2, useMemo: useM2, useEffect: useE2, useRef: useR2 } = React;

// ─────────────────────────────────────────────────────────────────────────────
// ADMIN DASHBOARD
// ─────────────────────────────────────────────────────────────────────────────
function AdminDashboard() {
  const [tab, setTab] = useS2('overview');
  const [filter, setFilter] = useS2('all');

  return (
    <div className="admin">
      <header className="admin-header">
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em' }}>Good morning, Chris.</h1>
          <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>Saturday, April 25 · 5 active jobs · 38.5h logged this week</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <div className="search-input">
            <Ic.search size={14} />
            <input placeholder="Jobs, clients, materials… (⌘K)" />
          </div>
          <button className="btn"><Ic.filter size={14} /> Filter</button>
          <button className="btn primary"><Ic.plus size={14} /> New job</button>
        </div>
      </header>

      <nav className="admin-tabs">
        {['overview', 'jobs', 'calendar', 'approvals', 'budgets'].map(t => (
          <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>
            {t === 'approvals' && window.BF_APPROVALS.length > 0 && <span className="tab-badge">{window.BF_APPROVALS.length}</span>}
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </nav>

      <div className="admin-body scroll">
        {tab === 'overview' && <AdminOverview />}
        {tab === 'jobs' && <AdminJobs />}
        {tab === 'calendar' && <AdminCalendar />}
        {tab === 'approvals' && <AdminApprovals />}
        {tab === 'budgets' && <AdminBudgets />}
      </div>
    </div>
  );
}

function AdminOverview() {
  const jobs = window.BF_JOBS;
  const active = jobs.filter(j => j.stage !== 'quote' && j.stage !== 'delivered');
  const overBudget = jobs.filter(j => j.spent / j.quote > 0.8 && j.spent / j.quote < 1.5);
  const blockers = jobs.filter(j => j.blockers > 0);

  return (
    <div className="ov-grid">
      <AdoptionLevels currentLevel={1}/>

      <div className="kpi-row">
        <Kpi label="Active jobs" value={active.length} sub="2 in build, 1 sourcing, 1 design, 1 elec" />
        <Kpi label="Pipeline value" value="$606K" sub="across active jobs" trend="+8.4%" />
        <Kpi label="This week's hours" value="186h" sub="across 6 crew" trend="+12h vs avg" />
        <Kpi label="Approvals waiting" value={window.BF_APPROVALS.length} sub="for your review" warn />
      </div>

      <div className="ov-cols">
        <section className="card">
          <header className="job-col-head">
            <div>
              <div className="section-label">Today on the floor</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>Live activity from tablet · Synced with Trello</div>
            </div>
            <span className="chip"><span className="dot live-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)' }} /> Live</span>
          </header>
          <div>
            {window.BF_ACTIVITY.slice().reverse().map(a => {
              const job = window.BF_JOBS.find(j => j.id === a.jobId);
              return (
                <div key={a.id} className="activity-row">
                  <div className="activity-time mono muted">{a.t}</div>
                  <ActivityIcon kind={a.kind} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="activity-title">{a.title}</div>
                    <div className="muted" style={{ fontSize: 12 }}>
                      <span className="mono" style={{ color: job?.color }}>●</span> {job?.name} · {a.body}
                    </div>
                  </div>
                  <Avatar id={a.who} size={22} />
                </div>
              );
            })}
          </div>
        </section>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <section className="card">
            <header className="job-col-head">
              <div className="section-label">Heat map · this week</div>
            </header>
            <Heatmap />
          </section>

          <section className="card">
            <header className="job-col-head">
              <div>
                <div className="section-label">Brothers AI suggests</div>
                <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>Based on shop data · updated 12 min ago</div>
              </div>
              <Ic.spark size={16} />
            </header>
            <div className="ai-list">
              <div className="ai-card">
                <div className="ai-tag">Budget</div>
                <div className="ai-text">Mendez Tacos at 67.7% spend, 58% complete — trending +6%. Likely cause: stainless waste during interior fit (Russel pricing rose 4% this month).</div>
                <div className="ai-actions">
                  <button className="btn sm">View job</button>
                  <button className="btn sm ghost">Dismiss</button>
                </div>
              </div>
              <div className="ai-card">
                <div className="ai-tag">Schedule</div>
                <div className="ai-text">Glycol pressure test on Tinta clashes with Aria AHS inspection (both Mon AM). Suggest moving Aria to Tue — Loris is free.</div>
                <div className="ai-actions">
                  <button className="btn sm">Reschedule</button>
                  <button className="btn sm ghost">Dismiss</button>
                </div>
              </div>
              <div className="ai-card">
                <div className="ai-tag">Inventory</div>
                <div className="ai-text">PEX-A 3/4" hits reorder by Wed at current pace. Andrew already requested 300ft — approve to send to Wolseley.</div>
                <div className="ai-actions">
                  <button className="btn sm primary">Approve · $495</button>
                  <button className="btn sm ghost">Edit qty</button>
                </div>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function Kpi({ label, value, sub, trend, warn }) {
  return (
    <div className={`kpi ${warn ? 'kpi-warn' : ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-val">{value}</div>
      <div className="kpi-sub">
        {trend && <span className="kpi-trend">{trend}</span>}
        {sub}
      </div>
    </div>
  );
}

function Heatmap() {
  const days = ['Mon','Tue','Wed','Thu','Fri','Sat'];
  const rows = window.BF_JOBS.filter(j => j.stage !== 'quote' && j.stage !== 'delivered').slice(0, 5);
  const intensity = (j, d) => {
    const seed = (j.id.charCodeAt(j.id.length-1) + d) % 5;
    return seed; // 0..4
  };
  return (
    <div className="heatmap">
      <div className="heatmap-grid">
        <div></div>
        {days.map(d => <div key={d} className="heatmap-h">{d}</div>)}
        {rows.map(j => (
          <React.Fragment key={j.id}>
            <div className="heatmap-row-label">
              <span className="mono" style={{ color: j.color }}>●</span> {j.name}
            </div>
            {days.map((d, i) => {
              const v = intensity(j, i);
              return <div key={d} className="heatmap-cell" style={{ background: v === 0 ? 'var(--bg-sunk)' : `oklch(0.92 ${0.02 + v*0.025} 60 / ${0.4 + v*0.15})`, borderColor: v >= 3 ? 'var(--accent)' : 'transparent' }} title={`${j.name} · ${d} · ${v*2}h`}></div>;
            })}
          </React.Fragment>
        ))}
      </div>
      <div className="heatmap-legend">
        <span className="muted" style={{ fontSize: 11 }}>Less</span>
        {[0,1,2,3,4].map(v => <span key={v} className="heatmap-legend-cell" style={{ background: v === 0 ? 'var(--bg-sunk)' : `oklch(0.92 ${0.02 + v*0.025} 60 / ${0.4 + v*0.15})` }}></span>)}
        <span className="muted" style={{ fontSize: 11 }}>More</span>
      </div>
    </div>
  );
}

function AdminJobs() {
  const stages = window.BF_STAGES;
  return (
    <div className="kanban scroll-x">
      {stages.map(s => {
        const cards = window.BF_JOBS.filter(j => j.stage === s.id);
        return (
          <div key={s.id} className="kanban-col">
            <header className="kanban-head">
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.color }}/>
                <span style={{ fontWeight: 600, fontSize: 12.5 }}>{s.label}</span>
                <span className="mono muted" style={{ fontSize: 11 }}>{cards.length}</span>
              </div>
              <button className="btn sm ghost"><Ic.plus size={12} /></button>
            </header>
            <div className="kanban-body">
              {cards.map(j => (
                <div key={j.id} className="kanban-card">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <span className="mono muted" style={{ fontSize: 10.5 }}>{j.id}</span>
                    {j.blockers > 0 && <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--danger)' }}/>}
                  </div>
                  <div style={{ fontWeight: 600, fontSize: 13, margin: '4px 0' }}>{j.name}</div>
                  <div className="muted" style={{ fontSize: 11, marginBottom: 8 }}>{j.type}</div>
                  <div className="progress" style={{ height: 3 }}><i style={{ width: `${j.progress*100}%`, background: j.color }} /></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                    <AvatarStack ids={j.crew} size={20} />
                    <span className="mono muted" style={{ fontSize: 10.5 }}><Money n={j.quote} /></span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AdminCalendar() {
  const days = Array.from({length: 35}, (_, i) => i + 1 - 2); // start with a couple days from prev month
  const today = 25;
  const events = [
    { day: 26, jobId: 'BF-2036', label: 'Glycol pressure test', color: 'oklch(0.66 0.16 25)' },
    { day: 27, jobId: 'BF-2043', label: 'Order acrylic', color: 'oklch(0.66 0.13 90)' },
    { day: 28, jobId: 'BF-2038', label: 'AHS gas inspection', color: 'oklch(0.66 0.10 260)' },
    { day: 29, jobId: 'BF-2039', label: 'Layout approval', color: 'oklch(0.72 0.13 250)' },
    { day: 30, jobId: 'BF-2042', label: '304 SS delivery', color: 'oklch(0.70 0.10 170)' },
    { day: 30, jobId: 'BF-2045', label: 'Site visit', color: 'oklch(0.74 0.10 200)' },
    { day: 2, jobId: 'BF-2041', label: 'Plumbing rough-in', color: 'oklch(0.70 0.14 30)' },
    { day: 5, jobId: 'BF-2038', label: 'Aria delivery', color: 'oklch(0.66 0.10 260)' },
    { day: 12, jobId: 'BF-2041', label: 'Mendez delivery 🚚', color: 'oklch(0.70 0.14 30)' },
    { day: 20, jobId: 'BF-2036', label: 'Tinta delivery', color: 'oklch(0.66 0.16 25)' },
  ];

  return (
    <div className="cal">
      <header className="cal-head">
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>April – May 2026</h2>
          <div className="muted" style={{ fontSize: 12 }}>Auto-synced with job ETAs · drag to reschedule</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn sm"><Ic.chev size={14} style={{ transform: 'rotate(180deg)' }}/></button>
          <button className="btn sm">Today</button>
          <button className="btn sm"><Ic.chev size={14} /></button>
          <div style={{ width: 1, background: 'var(--line)', margin: '0 4px' }}/>
          <div className="seg" style={{ padding: 2 }}>
            <button className="on">Month</button>
            <button>Week</button>
            <button>Crew</button>
          </div>
        </div>
      </header>
      <div className="cal-grid">
        {['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(d => <div key={d} className="cal-dow">{d}</div>)}
        {days.map((d, i) => {
          const inMonth = d >= 1 && d <= 30;
          const isToday = d === today && i < 28;
          const dayEvents = events.filter(e => e.day === d).slice(0, 3);
          return (
            <div key={i} className={`cal-cell ${!inMonth ? 'out' : ''} ${isToday ? 'today' : ''}`}>
              <div className="cal-num">{d > 30 ? d - 30 : (d < 1 ? 30 + d : d)}</div>
              {dayEvents.map((e, j) => (
                <div key={j} className="cal-event" style={{ background: `color-mix(in oklch, ${e.color}, white 78%)`, color: `color-mix(in oklch, ${e.color}, black 50%)` }}>
                  <span style={{ width: 4, borderRadius: 2, background: e.color, alignSelf: 'stretch' }}/>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.label}</span>
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AdminApprovals() {
  const [approved, setApproved] = useS2(new Set());
  return (
    <div className="appr-list">
      <div className="appr-intro">
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>Approvals queue</h2>
          <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>Anything that goes to a customer or affects budget waits here for your nod.</div>
        </div>
        <div className="seg">
          <button className="on">All ({window.BF_APPROVALS.length})</button>
          <button>Photos</button>
          <button>Budget</button>
          <button>Customer</button>
        </div>
      </div>

      {window.BF_APPROVALS.map(a => {
        const job = window.BF_JOBS.find(j => j.id === a.jobId);
        const isApproved = approved.has(a.id);
        return (
          <div key={a.id} className={`appr-card ${isApproved ? 'done' : ''}`}>
            <div className="appr-kind">{a.kind}</div>
            <div className="appr-body">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span className="mono muted" style={{ fontSize: 11 }}>{job?.id} · {job?.name}</span>
              </div>
              <div className="appr-title">{a.title}</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>Requested by {a.requested}</div>
              {a.detail && <div className="appr-detail">{a.detail}</div>}
              {a.kind === 'photo' && (
                <div className="appr-photo" style={{ backgroundImage: `url(${window.stockPhoto({ jobId: a.jobId, idx: a.id.charCodeAt(2) || 0, w: 320, h: 220 })})`, backgroundSize: 'cover', backgroundPosition: 'center' }} />
              )}
            </div>
            <div className="appr-actions">
              {!isApproved ? (
                <>
                  <button className="btn"><Ic.x size={14}/> Reject</button>
                  <button className="btn primary" onClick={() => setApproved(prev => new Set(prev).add(a.id))}><Ic.check size={14}/> Approve</button>
                </>
              ) : (
                <span className="chip" style={{ background: 'var(--success-soft)', color: 'var(--success-ink)', borderColor: 'transparent' }}><Ic.check size={12} /> Approved</span>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AdminBudgets() {
  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div className="kpi-row">
        <Kpi label="On budget" value={window.BF_JOBS.filter(j => j.spent/j.quote < 0.8 && j.stage !== 'quote' && j.stage !== 'delivered').length} sub="of 5 active" />
        <Kpi label="Watch list" value={window.BF_JOBS.filter(j => j.spent/j.quote >= 0.8 && j.spent/j.quote < 1).length} sub="80–99% spent" warn />
        <Kpi label="Over budget" value={window.BF_JOBS.filter(j => j.spent/j.quote >= 1).length} sub="0 right now" />
        <Kpi label="Total spent" value="$240K" sub="across active jobs" />
      </div>
      <section className="card">
        <header className="job-col-head">
          <div className="section-label">Per-job budget</div>
        </header>
        <div>
          {window.BF_JOBS.filter(j => j.stage !== 'quote' && j.stage !== 'delivered').map(j => {
            const pct = j.spent/j.quote;
            const tone = pct > 0.95 ? 'danger' : pct > 0.80 ? 'warn' : 'success';
            return (
              <div key={j.id} className="bud-row">
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>{j.name}</div>
                  <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>{j.id} · {j.progress*100|0}% complete · {j.hoursLogged}h / {j.hoursBudget}h logged</div>
                </div>
                <div style={{ width: 280 }}>
                  <div className={`progress ${tone}`}><i style={{ width: `${pct*100}%` }}/></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 11.5 }}>
                    <span className="mono"><Money n={j.spent}/></span>
                    <span className="mono muted">/ <Money n={j.quote}/></span>
                  </div>
                </div>
                <div style={{ width: 80, textAlign: 'right' }} className="mono">{(pct*100).toFixed(0)}%</div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// CUSTOMER PORTAL
// ─────────────────────────────────────────────────────────────────────────────
function CustomerPortal() {
  const job = window.BF_JOBS.find(j => j.id === 'BF-2041'); // Mendez Tacos
  const timeline = window.BF_TIMELINE_MENDEZ;

  return (
    <div className="cp scroll">
      <header className="cp-header">
        <div className="cp-brand">
          <div className="cp-mark"><span className="mono">BF</span></div>
          <div>
            <div style={{ fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--ink-3)' }}>Brothers Fabrication</div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Build Portal</div>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, fontSize: 12 }}>
          <span className="muted">Signed in as</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 24, height: 24, borderRadius: '50%', background: 'oklch(0.74 0.10 50)', color: 'white', display: 'grid', placeItems: 'center', fontSize: 11, fontWeight: 600 }}>LM</span>
            Luis Mendez
          </span>
        </div>
      </header>

      <div className="cp-hero">
        <div>
          <div className="cp-eyebrow">Your build · BF-2041</div>
          <h1 className="cp-title">Mendez Tacos</h1>
          <div className="cp-meta">
            <StageChip stage={job.stage}/>
            <span className="chip"><Ic.cal size={12}/> Delivery <strong>June 12, 2026</strong></span>
            <span className="chip" style={{ background: 'var(--success-soft)', color: 'var(--success-ink)', borderColor: 'transparent' }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)' }} className="live-dot"/> On schedule
            </span>
          </div>
          <p className="cp-desc">{job.description}</p>
        </div>
        <div className="cp-prog">
          <CircularProgress value={job.progress}/>
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <div className="muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Build progress</div>
            <div style={{ fontSize: 22, fontWeight: 600, marginTop: 2 }}>{Math.round(job.progress*100)}%</div>
          </div>
        </div>
      </div>

      <div className="cp-grid">
        {/* Live feed */}
        <section className="card">
          <header className="job-col-head">
            <div>
              <div className="section-label">Live build feed</div>
              <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>Photos & updates from the shop, curated daily</div>
            </div>
            <span className="chip"><span className="dot live-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)' }}/> 47 photos</span>
          </header>
          <div className="cp-feed">
            {[
              { t: 'Today, 2:40 PM', who: 'Jesse', body: 'Passenger-side framing complete after weld. Looking square.', tag: 'Frame · Build', photos: 2 },
              { t: 'Today, 8:14 AM', who: 'Jesse', body: 'Front cab corner, port side. Stainless interior next week.', tag: 'Frame · Build', photos: 1 },
              { t: 'Apr 23', who: 'Chris K', body: 'Equipment dry-fit — your range, fryers, prep tables. Adjusted clearance for the 8-burner.', tag: 'Equipment', photos: 4 },
              { t: 'Apr 18', who: 'Chris K', body: 'Stainless interior walls in. Easier to clean = AHS happy.', tag: 'Interior', photos: 5 },
            ].map((p, i) => (
              <div key={i} className="feed-card">
                <div className="feed-photos">
                  {Array.from({length: p.photos}).map((_, j) => (
                    <div key={j} style={{ aspectRatio: '4/3', borderRadius: 10, backgroundImage: `url(${window.stockPhoto({ jobId: 'BF-2041', idx: i*4 + j, stage: i === 0 || i === 1 ? 'frame' : i === 2 ? 'sourcing' : 'frame', type: 'food truck', kind: i === 3 ? 'interior' : undefined, w: 480, h: 360 })})`, backgroundSize: 'cover', backgroundPosition: 'center' }} />
                  ))}
                </div>
                <div className="feed-meta">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="chip" style={{ fontSize: 10.5 }}>{p.tag}</span>
                    <span className="muted" style={{ fontSize: 11 }}>{p.t} · {p.who}</span>
                  </div>
                  <div style={{ marginTop: 6 }}>{p.body}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Right column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Decisions needed */}
          <section className="card cp-decisions">
            <header className="job-col-head">
              <div className="section-label">Decisions needed from you</div>
              <span className="chip" style={{ background: 'var(--warn-soft)', color: 'var(--warn-ink)', borderColor: 'transparent' }}>2</span>
            </header>
            <div>
              <div className="cp-decision">
                <div style={{ fontWeight: 600, fontSize: 13.5 }}>Approve interior layout</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>We finalized prep table positions. Confirm or send notes — locks for plumbing rough-in.</div>
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button className="btn sm primary"><Ic.check size={12}/> Approve</button>
                  <button className="btn sm">Request changes</button>
                </div>
              </div>
              <div className="cp-decision">
                <div style={{ fontWeight: 600, fontSize: 13.5 }}>Choose exterior wrap finish</div>
                <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>Matte vs satin laminate. Affects price by ±$420.</div>
                <div className="cp-options">
                  <label className="cp-opt"><input type="radio" name="wrap" defaultChecked/><span>Matte (+$0)</span></label>
                  <label className="cp-opt"><input type="radio" name="wrap"/><span>Satin (+$420)</span></label>
                </div>
              </div>
            </div>
          </section>

          {/* Timeline */}
          <section className="card">
            <header className="job-col-head">
              <div className="section-label">Build timeline</div>
              <span className="muted" style={{ fontSize: 11 }}>10 milestones</span>
            </header>
            <div className="cp-tl">
              {timeline.map((m, i) => (
                <div key={i} className={`cp-tl-row ${m.done ? 'done' : ''} ${m.current ? 'current' : ''}`}>
                  <div className="cp-tl-dot">{m.done && <Ic.check size={10}/>}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                      <span style={{ fontSize: 13, fontWeight: m.current ? 600 : 500 }}>{m.title}</span>
                      <span className="mono muted" style={{ fontSize: 11 }}>{new Date(m.date).toLocaleDateString('en-CA', { month: 'short', day: 'numeric' })}</span>
                    </div>
                    <div className="muted" style={{ fontSize: 11.5, marginTop: 2 }}>{m.body}</div>
                  </div>
                  {i < timeline.length - 1 && <div className="cp-tl-line"/>}
                </div>
              ))}
            </div>
          </section>

          {/* Invoice */}
          <section className="card">
            <header className="job-col-head">
              <div className="section-label">Invoices</div>
            </header>
            <div className="cp-invoices">
              <div className="cp-inv done"><Ic.check size={14}/> <div style={{ flex: 1 }}><div>Deposit (30%)</div><div className="muted mono" style={{ fontSize: 11 }}>$42,750 · paid Feb 15</div></div></div>
              <div className="cp-inv done"><Ic.check size={14}/> <div style={{ flex: 1 }}><div>Frame milestone (30%)</div><div className="muted mono" style={{ fontSize: 11 }}>$42,750 · paid Mar 28</div></div></div>
              <div className="cp-inv pending"><div className="cp-inv-dot"/> <div style={{ flex: 1 }}><div>Pre-electrical (25%)</div><div className="muted mono" style={{ fontSize: 11 }}>$35,625 · due May 18</div></div><button className="btn sm primary">Pay</button></div>
              <div className="cp-inv future"><div className="cp-inv-dot"/> <div style={{ flex: 1 }}><div>Final (15%)</div><div className="muted mono" style={{ fontSize: 11 }}>$21,375 · due on delivery</div></div></div>
            </div>
          </section>

          {/* Message thread */}
          <section className="card cp-msgs">
            <header className="job-col-head">
              <div className="section-label">Messages with the shop</div>
            </header>
            <div className="cp-msg-list">
              <div className="cp-msg shop"><strong>Chris K</strong> — wrap install starts May 30, takes 3 days. We'll have the truck under cover overnight.<div className="muted" style={{ fontSize: 10.5, marginTop: 4 }}>Today, 2:12 PM</div></div>
              <div className="cp-msg you">Sounds good. Will I be able to come by during the wrap?<div className="muted" style={{ fontSize: 10.5, marginTop: 4 }}>Today, 2:18 PM</div></div>
              <div className="cp-msg shop"><strong>Chris K</strong> — yep, day 2 is the best look. I'll text you a window.<div className="muted" style={{ fontSize: 10.5, marginTop: 4 }}>Today, 2:21 PM</div></div>
            </div>
            <div className="cp-msg-input">
              <input placeholder="Reply to the shop…"/>
              <button className="btn primary"><Ic.send size={14}/></button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function CircularProgress({ value }) {
  const r = 54;
  const c = 2 * Math.PI * r;
  const off = c * (1 - value);
  return (
    <svg width="140" height="140" viewBox="0 0 140 140">
      <circle cx="70" cy="70" r={r} fill="none" stroke="var(--bg-sunk)" strokeWidth="8"/>
      <circle cx="70" cy="70" r={r} fill="none" stroke="var(--ink)" strokeWidth="8" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={off} transform="rotate(-90 70 70)"
        style={{ transition: 'stroke-dashoffset 600ms cubic-bezier(.2,.7,.2,1)' }}
      />
    </svg>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// INVENTORY
// ─────────────────────────────────────────────────────────────────────────────
function Inventory() {
  const mats = window.BF_MATERIALS;
  return (
    <div className="inv scroll">
      <header className="admin-header">
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em' }}>Inventory & Materials</h1>
          <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>Auto-deducts from worker logs · pulls budgets from quotes · AI suggests reorders</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn"><Ic.filter size={14}/> Filter</button>
          <button className="btn primary"><Ic.plus size={14}/> Add SKU</button>
        </div>
      </header>

      <div className="kpi-row">
        <Kpi label="SKUs tracked" value={mats.length} sub="across 4 vendors"/>
        <Kpi label="Below reorder" value={mats.filter(m => m.stock <= m.reorder).length} sub="auto-drafted requests" warn/>
        <Kpi label="Trending up (30d)" value={mats.filter(m => m.trend === 'up').length} sub="usage rising — watch budgets"/>
        <Kpi label="Inventory value" value="$28.4K" sub="at last vendor pricing"/>
      </div>

      <section className="card">
        <header className="job-col-head">
          <div className="section-label">All materials</div>
          <div style={{ display: 'flex', gap: 6 }}>
            <div className="search-input"><Ic.search size={12}/><input placeholder="Search SKU or name…"/></div>
            <div className="seg" style={{ padding: 2 }}>
              <button className="on">All</button>
              <button>Steel</button>
              <button>Plumbing</button>
              <button>Electrical</button>
              <button>Gas</button>
            </div>
          </div>
        </header>
        <div className="inv-table">
          <div className="inv-head">
            <div>SKU / Material</div>
            <div>Stock</div>
            <div>Reorder at</div>
            <div>30d usage</div>
            <div>Vendor</div>
            <div>Last cost</div>
            <div></div>
          </div>
          {mats.map(m => {
            const ratio = m.stock / m.reorder;
            const tone = ratio < 1 ? 'danger' : ratio < 1.3 ? 'warn' : 'success';
            return (
              <div key={m.sku} className="inv-row">
                <div>
                  <div style={{ fontWeight: 500, fontSize: 13.5 }}>{m.name}</div>
                  <div className="mono muted" style={{ fontSize: 11 }}>{m.sku}</div>
                </div>
                <div className="mono" style={{ fontWeight: 600 }}>{m.stock} <span className="muted" style={{ fontWeight: 400 }}>{m.unit}</span></div>
                <div className="mono muted">{m.reorder} {m.unit}</div>
                <div>
                  <div className="mono" style={{ fontSize: 12.5 }}>{m.usage30} {m.unit}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                    {m.trend === 'up' && <Ic.trend size={10} style={{ color: 'var(--warn)' }}/>}
                    <span className="muted" style={{ fontSize: 10.5 }}>{m.trend}</span>
                  </div>
                </div>
                <div className="muted" style={{ fontSize: 12 }}>{m.vendor} <span className="mono" style={{ fontSize: 10.5 }}>· {m.lead}</span></div>
                <div className="mono">${m.cost.toFixed(2)} <span className="muted">/{m.unit}</span></div>
                <div>
                  {tone === 'danger' && <button className="btn sm primary">Reorder</button>}
                  {tone === 'warn' && <button className="btn sm">Reorder?</button>}
                  {tone === 'success' && <button className="btn sm ghost"><Ic.more size={14}/></button>}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="card" style={{ marginTop: 12 }}>
        <header className="job-col-head">
          <div>
            <div className="section-label">Predictive · Brothers AI</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>Synthesized from quotes, jobs in progress, and vendor lead times</div>
          </div>
          <Ic.spark size={16}/>
        </header>
        <div style={{ padding: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div className="ai-card">
            <div className="ai-tag">Forecast</div>
            <div className="ai-text">2mm 316 SS will run out in <strong>~9 days</strong> at current pace. Patel build dry-fit starts May 6 and uses 80 ft². Order 100 ft² now to keep buffer.</div>
            <div className="ai-actions"><button className="btn sm primary">Order 100 ft² · $2,610</button></div>
          </div>
          <div className="ai-card">
            <div className="ai-tag">Mitigation</div>
            <div className="ai-text">Mendez stainless usage is +12% over quote. Last 3 truck builds averaged +8%. <strong>Recommend</strong>: bake 10% into future quotes; absorb on Mendez (still 22% margin).</div>
            <div className="ai-actions"><button className="btn sm">Update quote template</button><button className="btn sm ghost">Dismiss</button></div>
          </div>
          <div className="ai-card">
            <div className="ai-tag">Vendor</div>
            <div className="ai-text">Russel Metals raised 304 SS pricing 4% this month. Metal Supermarket has 304 in stock at last week's price — switching saves <strong>~$780</strong> on Patel.</div>
            <div className="ai-actions"><button className="btn sm">Compare quotes</button></div>
          </div>
          <div className="ai-card">
            <div className="ai-tag">Argon</div>
            <div className="ai-text">3 tanks left, reorder at 4. Praxair next-day. With 4 active welding jobs, <strong>order 4 tanks</strong>.</div>
            <div className="ai-actions"><button className="btn sm primary">Approve · $352</button></div>
          </div>
        </div>
      </section>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// QUOTE PIPELINE
// ─────────────────────────────────────────────────────────────────────────────
function Pipeline() {
  return (
    <div className="pipe scroll">
      <header className="admin-header">
        <div>
          <h1 style={{ margin: 0, fontSize: 22, fontWeight: 600, letterSpacing: '-0.02em' }}>Lead → Job pipeline</h1>
          <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>Incoming quotes from website, social, and phone — convert with one tap</div>
        </div>
        <button className="btn primary"><Ic.plus size={14}/> Add lead</button>
      </header>

      <div className="kpi-row">
        <Kpi label="New leads (7d)" value="12" sub="+4 vs last week" trend="+50%"/>
        <Kpi label="Avg quote" value="$92K" sub="across food trucks"/>
        <Kpi label="Conversion" value="34%" sub="lead → signed"/>
        <Kpi label="Pipeline value" value="$1.2M" sub="open quotes"/>
      </div>

      <div className="pipe-table card">
        <div className="pipe-head">
          <div>Lead</div>
          <div>Service</div>
          <div>Source</div>
          <div>Heat</div>
          <div>Estimate</div>
          <div>Status</div>
          <div></div>
        </div>
        {window.BF_QUOTES.map(q => (
          <div key={q.id} className="pipe-row">
            <div>
              <div style={{ fontWeight: 600, fontSize: 13.5 }}>{q.name}</div>
              <div className="mono muted" style={{ fontSize: 11 }}>{q.id} · {q.received}</div>
            </div>
            <div style={{ fontSize: 13 }}>{q.service}</div>
            <div className="muted" style={{ fontSize: 12 }}>{q.source}</div>
            <div>
              <span className={`heat heat-${q.heat}`}>{q.heat}</span>
            </div>
            <div className="mono">{q.est}</div>
            <div>
              <span className="chip" style={{ fontSize: 10.5 }}>{q.status}</span>
            </div>
            <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
              <button className="btn sm">Quote</button>
              <button className="btn sm primary">Convert</button>
            </div>
          </div>
        ))}
      </div>

      <section className="card" style={{ marginTop: 12 }}>
        <header className="job-col-head">
          <div>
            <div className="section-label">Brothers AI · auto-draft</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>Pulled from website form · ready for Chris's review</div>
          </div>
        </header>
        <div style={{ padding: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <div className="section-label">Lead — YYC Donuts (Hannah Lee)</div>
            <div className="muted" style={{ fontSize: 12, margin: '8px 0' }}>"Hi! I'm starting a small donut truck. 18 ft, single fryer, glaze table. Hoping to be on the road by September."</div>
            <div className="quote-pre">
              <div className="quote-line"><span>18-ft truck (basic spec)</span><span className="mono">$72,000</span></div>
              <div className="quote-line"><span>Single fryer system + glaze table</span><span className="mono">$4,400</span></div>
              <div className="quote-line"><span>Customer-facing window + shelf</span><span className="mono">$1,800</span></div>
              <div className="quote-line"><span>AHS compliance package</span><span className="mono">$2,200</span></div>
              <div className="quote-line"><span>Standard wrap (matte)</span><span className="mono">$3,800</span></div>
              <div className="quote-line total"><span>Estimated total</span><span className="mono">$84,200</span></div>
            </div>
          </div>
          <div>
            <div className="section-label">Auto-drafted reply</div>
            <div className="quote-reply">
              <p>Hi Hannah —</p>
              <p>Thanks for reaching out. An 18-ft donut truck like you're describing typically lands in our <strong>Basic / Standard</strong> tier, around <strong>$84K</strong> turnkey, depending on finishes and equipment specs.</p>
              <p>To deliver by September we'd need to start within ~6 weeks. Let's chat next week — I've got a couple of slots open Tuesday afternoon.</p>
              <p>— Chris K, Brothers Fabrication</p>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button className="btn primary"><Ic.send size={14}/> Send reply</button>
              <button className="btn">Edit</button>
              <button className="btn ghost">Discard</button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// BROTHERS AI
// ─────────────────────────────────────────────────────────────────────────────
function BrothersAI() {
  const [tab, setTab] = useS2('chat');
  return (
    <div className="ai-surface">
      <aside className="ai-sidebar">
        <div className="ai-sidebar-head">
          <div className="tablet-mark">AI</div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Brothers AI</div>
            <div className="muted" style={{ fontSize: 11 }}>Local · 7B model · 12ms</div>
          </div>
        </div>
        <button className={`ai-nav ${tab==='chat'?'on':''}`} onClick={() => setTab('chat')}><Ic.msg size={16}/> Chat</button>
        <button className={`ai-nav ${tab==='daily'?'on':''}`} onClick={() => setTab('daily')}><Ic.mail size={16}/> Daily email composer</button>
        <button className={`ai-nav ${tab==='voice'?'on':''}`} onClick={() => setTab('voice')}><Ic.mic size={16}/> Voice on tablet</button>
        <button className={`ai-nav ${tab==='docs'?'on':''}`} onClick={() => setTab('docs')}><Ic.box size={16}/> Knowledge base</button>
        <div style={{ marginTop: 'auto', padding: 12, borderTop: '1px solid var(--line)' }}>
          <div className="muted" style={{ fontSize: 11, marginBottom: 4 }}>Indexed</div>
          <div style={{ fontSize: 12 }}>284 docs · 8 jobs · 12 SKUs</div>
        </div>
      </aside>

      <main className="ai-main scroll">
        {tab === 'chat' && <AIChat/>}
        {tab === 'daily' && <AIDaily/>}
        {tab === 'voice' && <AIVoice/>}
        {tab === 'docs' && <AIDocs/>}
      </main>
    </div>
  );
}

function AIChat() {
  const [messages, setMessages] = useS2([
    { role: 'user', text: "What's the status of the Mendez job?" },
    { role: 'ai', text: "Mendez Tacos (BF-2041) is in Frame / Build, 58% complete. Spent $96.4K of $142.5K (67.7%). Next milestone: plumbing rough-in May 2. Two photos pending your approval. ETA June 12 — confidence high.", sources: ['BF-2041', 'punchlist', 'today\'s activity'] },
    { role: 'user', text: 'Why is it tracking high on budget?' },
    { role: 'ai', text: "Stainless usage is +12% vs quote — interior wall fit took more 304 SS than estimated. Russel also raised pricing 4% this month. Margin still healthy at ~22%. Want me to draft a revised material spec for the Patel build to bake this in?", sources: ['materials log', 'BF-2041 quote', 'vendor pricing'] },
  ]);
  const [draft, setDraft] = useS2('');

  return (
    <div className="ai-chat">
      <div className="ai-chat-list">
        {messages.map((m, i) => (
          <div key={i} className={`ai-msg ai-msg-${m.role}`}>
            {m.role === 'ai' && <div className="ai-msg-avatar"><Ic.spark size={14}/></div>}
            <div className="ai-msg-body">
              <div>{m.text}</div>
              {m.sources && (
                <div className="ai-sources">
                  {m.sources.map(s => <span key={s} className="chip" style={{ fontSize: 10.5 }}><Ic.link size={10}/> {s}</span>)}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="ai-chat-suggest">
        {[
          'Show jobs over budget',
          'What was used on Mendez today?',
          "Forecast next week's stainless usage",
          'Reorder anything we need',
        ].map(s => <button key={s} className="chip" onClick={() => setDraft(s)}>{s}</button>)}
      </div>

      <div className="ai-chat-input">
        <input value={draft} onChange={e => setDraft(e.target.value)} placeholder="Ask about jobs, materials, schedule, budgets…"/>
        <button className="tablet-icon-btn"><Ic.mic size={18}/></button>
        <button className="btn primary"><Ic.send size={14}/></button>
      </div>
    </div>
  );
}

function AIDaily() {
  const r = window.BF_DAILY;
  return (
    <div className="ai-daily">
      <div className="ai-daily-head">
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>Daily summary email — for Chris</h2>
          <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>Auto-drafted at 6:00 AM each morning · review and send</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn">Customize sections</button>
          <button className="btn primary"><Ic.send size={14}/> Send to Chris</button>
        </div>
      </div>

      <div className="ai-email card">
        <div className="ai-email-head">
          <div><strong>To:</strong> chris@brothersfabrication.ca</div>
          <div><strong>Subject:</strong> Brothers Fab — Saturday, April 25 · daily rollup</div>
        </div>
        <div className="ai-email-body">
          <p>Morning Chris — here's where the shop is at as of 6 AM.</p>

          <h3>By the numbers</h3>
          <ul>
            <li><strong>{r.hoursLogged}h</strong> logged yesterday across {r.jobsTouched} jobs</li>
            <li><strong>{r.photos}</strong> new photos · 2 awaiting your approval before going to customers</li>
            <li>{r.weather}</li>
          </ul>

          <h3>Blockers ({r.blockers.length})</h3>
          {r.blockers.map((b, i) => <div key={i} className="ai-email-blocker"><span className="mono">{b.jobId}</span> — {b.text}</div>)}

          <h3>Budget watch ({r.budgetFlags.length})</h3>
          {r.budgetFlags.map((b, i) => <div key={i} className="ai-email-flag"><span className="mono">{b.jobId}</span> — {b.text}</div>)}

          <h3>Tomorrow</h3>
          <ul>{r.tomorrow.map((t, i) => <li key={i}>{t}</li>)}</ul>

          <p style={{ marginTop: 16 }}>Approvals queue: <strong>5 items</strong>. Nothing urgent. Photos are mostly milestone shots from the Mendez frame. Open the dashboard to review.</p>

          <p style={{ marginTop: 8 }}>— Brothers AI</p>
        </div>
      </div>
    </div>
  );
}

function AIVoice() {
  const WAKE_OPTIONS = [
    { id: 'computer', label: 'Computer',    sub: 'Star Trek classic. Universally legible.' },
    { id: 'shop',     label: 'Shop',        sub: 'Short. Lives where it works.' },
    { id: 'cinder',   label: 'Cinder',      sub: 'Welder\'s nickname. A little personality.' },
    { id: 'brofab',   label: 'BroFab',      sub: 'On-brand. Two syllables, easy over noise.' },
    { id: 'custom',   label: 'Type your own', sub: 'Anything goes. Test it against grinder noise first.' },
    { id: 'self',     label: 'Ask to name self', sub: 'Let it pick. It\'ll suggest three options on first boot.' },
  ];
  const [picked, setPicked] = useS2(() => localStorage.getItem('bf-wake-id') || 'computer');
  const [custom, setCustom] = useS2(() => localStorage.getItem('bf-wake-custom') || '');
  const [selfName, setSelfName] = useS2(null);
  const selfPool = ['Bayliss', 'Forge', 'Junior', 'Argon', 'Punch', 'Tig', 'Ember'];

  const choose = (id) => {
    setPicked(id);
    localStorage.setItem('bf-wake-id', id);
    if (id === 'self') {
      // Pick a name on the spot — feels like the AI introducing itself
      const n = selfPool[Math.floor(Math.random() * selfPool.length)];
      setSelfName(n);
      localStorage.setItem('bf-wake-self', n);
    }
  };

  const activeWord = picked === 'custom' ? (custom || '—')
                   : picked === 'self'   ? (selfName || localStorage.getItem('bf-wake-self') || '—')
                   : WAKE_OPTIONS.find(o => o.id === picked)?.label;

  return (
    <div style={{ padding: 24, display: 'grid', gap: 16, maxWidth: 720 }}>
      <div>
        <h2 style={{ margin: 0, fontSize: 18 }}>Voice on the tablet</h2>
        <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>Hands-free shop floor commands. Activates with <strong>"Hey {activeWord}"</strong> or the mic button on the tablet.</div>
      </div>
      <section className="card" style={{ padding: 18 }}>
        <div className="section-label" style={{ marginBottom: 10 }}>What it can do</div>
        <div style={{ display: 'grid', gap: 10 }}>
          {[
            ['Log materials',  `"Hey ${activeWord}, log 6 ft of half-inch PEX to the Tinta job."`],
            ['Punch in/out',   `"Hey ${activeWord}, punch me in to Mendez."`],
            ['Status checks',  `"Hey ${activeWord}, what's the status of the Aria kitchen?"`],
            ['Flag blockers',  `"Hey ${activeWord}, flag a blocker — argon is running low."`],
            ['Photo capture',  `"Hey ${activeWord}, take a photo and tag it to today's milestone."`],
          ].map(([k, v]) => (
            <div key={k} className="ai-voice-row">
              <div><Ic.mic size={14}/> <strong>{k}</strong></div>
              <div className="mono muted" style={{ fontSize: 12 }}>{v}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="card" style={{ padding: 18 }}>
        <div className="section-label" style={{ marginBottom: 10 }}>Wake word</div>
        <div className="muted" style={{ fontSize: 12, marginBottom: 14 }}>Pick what the tablet listens for. Goes in front of every command.</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
          {WAKE_OPTIONS.map(o => (
            <button
              key={o.id}
              onClick={() => choose(o.id)}
              className={`wake-pick ${picked === o.id ? 'on' : ''}`}
            >
              <div className="wake-pick-head">
                <span className="wake-pick-radio">{picked === o.id && <span/>}</span>
                <span className="wake-pick-label">"Hey {o.id === 'custom' ? (custom || '___') : o.id === 'self' ? (selfName || '?') : o.label}"</span>
              </div>
              <div className="wake-pick-sub">{o.sub}</div>
            </button>
          ))}
        </div>

        {picked === 'custom' && (
          <label className="sheet-field" style={{ marginTop: 14 }}>
            <span>Your wake word</span>
            <input
              type="text"
              value={custom}
              onChange={e => { setCustom(e.target.value); localStorage.setItem('bf-wake-custom', e.target.value); }}
              placeholder="e.g. Sparky, Boss, Mom…"
              style={{ width: '100%', padding: '12px 14px', border: '1px solid var(--line)', borderRadius: 'var(--r-md)', fontSize: 14 }}
              autoFocus
            />
            <div className="muted" style={{ fontSize: 11.5, marginTop: 6, fontStyle: 'italic' }}>2–3 syllables works best. Avoid words that sound like common shop chatter.</div>
          </label>
        )}

        {picked === 'self' && (
          <div className="self-name-card">
            <div className="self-name-bubble">
              <Ic.spark size={14}/> "How about <strong>{selfName || localStorage.getItem('bf-wake-self') || '…'}</strong>? It came up in a quote you wrote last spring."
            </div>
            <button className="btn sm" onClick={() => choose('self')}>Suggest another</button>
          </div>
        )}
      </section>

      <section className="card" style={{ padding: 18 }}>
        <div className="section-label" style={{ marginBottom: 10 }}>Language</div>
        <label className="sheet-field"><span>Recognition language</span><select><option>English (Canadian)</option><option>English (US)</option><option>Spanish</option></select></label>
      </section>
    </div>
  );
}

function AIDocs() {
  const docs = [
    ['BF-2041_quote.pdf', 'Job quote', '14d ago'],
    ['BF-2041_spec.pdf', 'Job spec', '12d ago'],
    ['AHS_food_truck_compliance.pdf', 'Compliance ref', '6mo ago'],
    ['shop_safety_protocols.md', 'Safety', '3mo ago'],
    ['vendor_pricelist_russel.csv', 'Vendor', '4d ago'],
    ['vendor_pricelist_wolseley.csv', 'Vendor', '4d ago'],
    ['piaggio_ape_conversion_notes.md', 'Build notes', '2mo ago'],
    ['ahs_inspection_checklist.pdf', 'Compliance', '1y ago'],
  ];
  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ margin: '0 0 4px', fontSize: 18 }}>Knowledge base</h2>
      <div className="muted" style={{ fontSize: 13 }}>Documents Brothers AI can pull from. Add specs, quotes, vendor sheets — answers cite their source.</div>
      <div className="card" style={{ marginTop: 16 }}>
        <header className="job-col-head">
          <div className="section-label">{docs.length} documents · 284 chunks</div>
          <button className="btn sm"><Ic.plus size={12}/> Upload</button>
        </header>
        <div>
          {docs.map(([n, k, t]) => (
            <div key={n} className="row">
              <Ic.box size={14}/>
              <div style={{ flex: 1 }}>
                <div className="mono" style={{ fontSize: 12.5 }}>{n}</div>
                <div className="muted" style={{ fontSize: 11 }}>{k} · indexed {t}</div>
              </div>
              <button className="btn sm ghost"><Ic.more size={14}/></button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

if (typeof window !== 'undefined') {
  Object.assign(window, { AdminDashboard, CustomerPortal, Inventory, Pipeline, BrothersAI });
}
