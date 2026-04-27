// Photo Inbox — every photo capture path lands here, owner approves with a swipe,
// customer gets notified automatically. The single most important habit-formation
// surface: the easier we make sending a photo, the more we get.
//
// Five capture paths, one inbox:
//   1. Tablet drop target (active clocked-in job)
//   2. MMS to shop number  → twilio webhook → inbox
//   3. build@brothersfab.ca → mail parser → inbox
//   4. Trello attachment   → poll diff → inbox
//   5. Mobile web upload   → /upload?job=BF-2041 short link
//
// Three states: inbox · pending-review · published (or internal-only)
// Approve = swipe right (publish + notify customer)
// Internal = swipe left (visible to owner/crew, not customer)

const { useState: useSPI, useMemo: useMPI, useEffect: useEPI, useRef: useRPI } = React;

// Sample inbox — a realistic mix of recent arrivals
const INBOX_SEED = [
  { id: 'p101', src: 'mms',    from: 'Tyler · 587-***-2841',  jobId: 'BF-2041', received: '08:14', cap: '', stage: 'frame', state: 'pending', exif: { gps: 'shop · bay 2', cam: 'iPhone 13' } },
  { id: 'p102', src: 'mms',    from: 'Tyler · 587-***-2841',  jobId: 'BF-2041', received: '08:14', cap: '', stage: 'frame', state: 'pending', exif: { gps: 'shop · bay 2', cam: 'iPhone 13' } },
  { id: 'p103', src: 'email',  from: 'jesse@brothersfab.ca',  jobId: 'BF-2039', received: '07:52', cap: 'gas line pressure test ✓', stage: 'plumbing', state: 'pending', exif: { gps: 'shop · bay 1', cam: 'iPhone 12' } },
  { id: 'p104', src: 'email',  from: 'jesse@brothersfab.ca',  jobId: 'BF-2039', received: '07:53', cap: 'gas regulator install', stage: 'plumbing', state: 'pending', exif: { gps: 'shop · bay 1', cam: 'iPhone 12' } },
  { id: 'p105', src: 'tablet', from: 'Andrew · clocked-in',   jobId: 'BF-2042', received: '07:31', cap: '', stage: 'electrical', state: 'inbox', exif: { gps: 'shop · bay 3', cam: 'tablet' } },
  { id: 'p106', src: 'trello', from: 'Chris · card attach',   jobId: 'BF-2038', received: 'yest 17:22', cap: 'final stainless before delivery', stage: 'delivered', state: 'published', exif: { gps: '—', cam: '—' } },
  { id: 'p107', src: 'mms',    from: 'unknown · 403-***-9912', jobId: null,      received: 'yest 16:48', cap: '', stage: null, state: 'unmatched', exif: { gps: '—', cam: '—' } },
  { id: 'p108', src: 'tablet', from: 'Tyler · clocked-in',    jobId: 'BF-2041', received: 'yest 14:02', cap: 'frame complete · ready for paint', stage: 'frame', state: 'published', exif: { gps: 'shop · bay 2', cam: 'tablet' } },
];

const SRC_META = {
  mms:    { ic: 'phone', label: 'MMS',     color: 'oklch(0.70 0.12 220)' },
  email:  { ic: 'mail',  label: 'Email',   color: 'oklch(0.68 0.10 280)' },
  tablet: { ic: 'tablet',label: 'Tablet',  color: 'oklch(0.65 0.11 155)' },
  trello: { ic: 'check', label: 'Trello',  color: 'oklch(0.70 0.10 100)' },
  web:    { ic: 'send',  label: 'Web link',color: 'oklch(0.70 0.14 35)' },
};

// ─────────────────────────────────────────────────────────────────────────────
function PhotoInbox() {
  const [photos, setPhotos] = useSPI(INBOX_SEED);
  const [filter, setFilter] = useSPI('all'); // all | pending | unmatched | published
  const [selected, setSelected] = useSPI(photos[0]?.id);
  const [draggingOver, setDraggingOver] = useSPI(false);
  const fileRef = useRPI(null);

  const counts = useMPI(() => ({
    all: photos.length,
    pending:    photos.filter(p => p.state === 'pending').length,
    inbox:      photos.filter(p => p.state === 'inbox').length,
    unmatched:  photos.filter(p => p.state === 'unmatched').length,
    published:  photos.filter(p => p.state === 'published').length,
  }), [photos]);

  const visible = useMPI(() => {
    if (filter === 'all') return photos;
    return photos.filter(p => p.state === filter);
  }, [filter, photos]);

  const sel = photos.find(p => p.id === selected) || visible[0];

  const setState = (id, state) => setPhotos(ps => ps.map(p => p.id === id ? { ...p, state } : p));
  const assign   = (id, jobId) => setPhotos(ps => ps.map(p => p.id === id ? { ...p, jobId, state: 'pending' } : p));

  const handleDrop = (e) => {
    e.preventDefault(); setDraggingOver(false);
    const files = [...(e.dataTransfer?.files || [])];
    if (!files.length) return;
    const newPhotos = files.map((f, i) => ({
      id: 'p' + Date.now() + i,
      src: 'web',
      from: 'You · drag drop',
      jobId: null,
      received: 'just now',
      cap: '',
      stage: null,
      state: 'unmatched',
      exif: { gps: '—', cam: f.name },
    }));
    setPhotos(ps => [...newPhotos, ...ps]);
  };

  return (
    <div className="pix">
      {/* ── Header / capture-path bar ──────────────────────────── */}
      <header className="pix-header">
        <div className="pix-head-l">
          <div className="section-label">Photo Inbox</div>
          <h1 className="pix-title">Five ways in. One place to land.</h1>
          <p className="pix-sub">Photos arrive from every direction — text, email, tablet, Trello, web. Approve with a swipe, customer is notified, ledger is updated.</p>
        </div>
        <div className="pix-head-r">
          <div className="pix-stat"><strong>{counts.pending + counts.unmatched}</strong><span>need you</span></div>
          <div className="pix-stat muted"><strong>{counts.published}</strong><span>published</span></div>
          <div className="pix-stat muted"><strong>{photos.length}</strong><span>this week</span></div>
        </div>
      </header>

      {/* The five send-paths — the literal address book */}
      <section className="pix-paths">
        <div className="pix-path">
          <div className="pix-path-mark" style={{ background: SRC_META.mms.color }}><Ic.phone size={16}/></div>
          <div>
            <div className="pix-path-name">Text a photo</div>
            <div className="pix-path-addr mono">587 · FAB · SHOP</div>
          </div>
          <div className="pix-path-tag">no app</div>
        </div>
        <div className="pix-path">
          <div className="pix-path-mark" style={{ background: SRC_META.email.color }}><Ic.mail size={16}/></div>
          <div>
            <div className="pix-path-name">Email a photo</div>
            <div className="pix-path-addr mono">build@brothersfab.ca</div>
          </div>
          <div className="pix-path-tag">subject = job</div>
        </div>
        <div className="pix-path">
          <div className="pix-path-mark" style={{ background: SRC_META.tablet.color }}><Ic.tablet size={16}/></div>
          <div>
            <div className="pix-path-name">Tablet drop</div>
            <div className="pix-path-addr">on the active clocked-in job</div>
          </div>
          <div className="pix-path-tag">auto-tagged</div>
        </div>
        <div className="pix-path">
          <div className="pix-path-mark" style={{ background: SRC_META.trello.color }}><Ic.check size={16}/></div>
          <div>
            <div className="pix-path-name">Trello attach</div>
            <div className="pix-path-addr">already-known cards</div>
          </div>
          <div className="pix-path-tag">if you must</div>
        </div>
        <div
          className={`pix-path drop ${draggingOver ? 'over' : ''}`}
          onDragOver={e => { e.preventDefault(); setDraggingOver(true); }}
          onDragLeave={() => setDraggingOver(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
          role="button"
        >
          <div className="pix-path-mark" style={{ background: SRC_META.web.color }}><Ic.send size={16}/></div>
          <div>
            <div className="pix-path-name">Drop here · or web link</div>
            <div className="pix-path-addr mono">brothersfab.ca/p/BF-2041</div>
          </div>
          <div className="pix-path-tag">qr on tablet</div>
          <input ref={fileRef} type="file" accept="image/*" multiple style={{ display:'none' }} onChange={e => handleDrop({ preventDefault(){}, dataTransfer: { files: e.target.files } })}/>
        </div>
      </section>

      {/* ── Filter rail ────────────────────────────────────────── */}
      <div className="pix-filters">
        {[
          ['all',       'Everything',    counts.all],
          ['pending',   'Need approval', counts.pending],
          ['inbox',     'Auto-published',counts.inbox],
          ['unmatched', 'No job · ?',    counts.unmatched],
          ['published', 'Published',     counts.published],
        ].map(([k, label, n]) => (
          <button key={k} className={`pix-filter ${filter === k ? 'on' : ''}`} onClick={() => setFilter(k)}>
            {label} <span className="pix-filter-n mono">{n}</span>
          </button>
        ))}
        <div className="pix-spacer"/>
        <div className="pix-policy">
          <Ic.eye size={11}/> Customer auto-notified on publish · <a href="#">edit policy</a>
        </div>
      </div>

      {/* ── Two-pane: grid + detail ────────────────────────────── */}
      <div className="pix-body">
        <div className="pix-grid">
          {visible.map(p => (
            <PhotoTile key={p.id} p={p} active={p.id === sel?.id} onClick={() => setSelected(p.id)} />
          ))}
          {visible.length === 0 && (
            <div className="pix-empty">
              <div className="muted">Nothing here.</div>
              <div className="muted" style={{ fontSize: 12 }}>Either nobody sent anything or you're caught up.</div>
            </div>
          )}
        </div>

        <aside className="pix-detail">
          {sel ? <PhotoDetail p={sel} setState={setState} assign={assign}/> : (
            <div className="muted" style={{ padding: 24 }}>Select a photo</div>
          )}
        </aside>
      </div>
    </div>
  );
}

// ── Tile ──────────────────────────────────────────────────────────────────
function PhotoTile({ p, active, onClick }) {
  const meta = SRC_META[p.src];
  const url = p.jobId
    ? window.stockPhoto({ jobId: p.jobId, idx: p.id.charCodeAt(2) || 0, stage: p.stage, w: 480, h: 360 })
    : window.stockPhoto({ jobId: 'unmatched', idx: p.id.charCodeAt(2) || 0, kind: 'shop', w: 480, h: 360 });

  return (
    <button className={`pix-tile ${active ? 'on' : ''} state-${p.state}`} onClick={onClick}>
      <div className="pix-tile-img" style={{ backgroundImage: `url(${url})` }}>
        <div className="pix-tile-state">
          {p.state === 'pending'   && <span className="badge warn">pending</span>}
          {p.state === 'inbox'     && <span className="badge ok">auto · OK</span>}
          {p.state === 'published' && <span className="badge ok">live</span>}
          {p.state === 'unmatched' && <span className="badge warn">no job?</span>}
        </div>
      </div>
      <div className="pix-tile-foot">
        <span className="pix-tile-src" style={{ color: meta.color }}>
          <Ic[meta.ic] size={11}/> {meta.label}
        </span>
        <span className="pix-tile-job mono">{p.jobId || '—'}</span>
        <span className="muted mono" style={{ fontSize: 10.5 }}>{p.received}</span>
      </div>
    </button>
  );
}

// ── Detail / approval ─────────────────────────────────────────────────────
function PhotoDetail({ p, setState, assign }) {
  const meta = SRC_META[p.src];
  const [caption, setCaption] = useSPI(p.cap || '');
  const url = p.jobId
    ? window.stockPhoto({ jobId: p.jobId, idx: p.id.charCodeAt(2) || 0, stage: p.stage, w: 1200, h: 900 })
    : window.stockPhoto({ jobId: 'unmatched', idx: p.id.charCodeAt(2) || 0, kind: 'shop', w: 1200, h: 900 });

  const job = (window.BF_JOBS || []).find(j => j.id === p.jobId);

  return (
    <div className="pix-d">
      <div className="pix-d-img" style={{ backgroundImage: `url(${url})` }}>
        <div className="pix-d-overlay">
          <span className="pix-d-src" style={{ background: meta.color }}>
            <Ic[meta.ic] size={12}/> {meta.label}
          </span>
          <span className="pix-d-time mono">{p.received}</span>
        </div>
      </div>

      <div className="pix-d-body">
        <div className="pix-d-meta">
          <div>
            <div className="muted" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>From</div>
            <div style={{ fontSize: 13, fontWeight: 500 }}>{p.from}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Where</div>
            <div style={{ fontSize: 13 }}>{p.exif.gps}</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Device</div>
            <div style={{ fontSize: 13 }}>{p.exif.cam}</div>
          </div>
        </div>

        {p.state === 'unmatched' ? (
          <div className="pix-d-block">
            <div className="pix-d-block-head"><Ic.alert size={13}/> Couldn't match a job</div>
            <p className="muted" style={{ fontSize: 12.5, lineHeight: 1.4, marginBottom: 10 }}>
              No clocked-in job and no number/email we recognize. Pick one:
            </p>
            <div className="pix-job-pick">
              {(window.BF_JOBS || []).slice(0, 5).map(j => (
                <button key={j.id} className="pix-job-pick-btn" onClick={() => assign(p.id, j.id)}>
                  <span className="mono" style={{ color: 'var(--ink-3)' }}>{j.id}</span>
                  <span>{j.name}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="pix-d-block">
            <div className="pix-d-block-head">
              <span className="mono" style={{ color: 'var(--ink-3)' }}>{p.jobId}</span>
              {job && <span> · {job.name}</span>}
              {p.stage && <span className="muted"> · {p.stage}</span>}
            </div>
            <label className="pix-d-cap-label muted" style={{ fontSize: 10.5, textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 600 }}>Caption · sent to customer</label>
            <textarea
              className="pix-d-cap"
              value={caption}
              onChange={e => setCaption(e.target.value)}
              placeholder='AI suggested: "Frame welds complete on the cab corner"'
              rows={2}
            />
            <div className="pix-d-aihint">
              <Ic.spark size={11}/> AI: looks like a frame weld at the cab corner. Suggest:
              <button className="pix-d-aibtn" onClick={() => setCaption('Frame welds complete on the cab corner')}>
                use this caption
              </button>
            </div>
          </div>
        )}

        {p.state !== 'unmatched' && (
          <div className="pix-d-actions">
            <button
              className="pix-d-act publish"
              disabled={p.state === 'published'}
              onClick={() => setState(p.id, 'published')}
            >
              <Ic.send size={14}/>
              {p.state === 'published' ? 'Published · customer notified' : 'Publish + notify customer'}
            </button>
            <button
              className="pix-d-act internal"
              onClick={() => setState(p.id, 'inbox')}
            >
              <Ic.eye size={14}/>
              Keep internal
            </button>
            <button className="pix-d-act ghost">
              <Ic.alert size={14}/> Reject
            </button>
          </div>
        )}

        <div className="pix-d-trail muted">
          <span>Where this goes when published:</span>
          <ul>
            <li><Ic.user size={11}/> Customer portal feed · push notification</li>
            <li><Ic.layout size={11}/> Job ledger · evidence under "{p.stage || 'general'}"</li>
            <li><Ic.check size={11}/> Trello card · attached + commented</li>
            <li><Ic.spark size={11}/> AI memory · referenced if anyone asks "show me the welds"</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

window.PhotoInbox = PhotoInbox;
