// Connect screen + stage-mapping designer for the Trello integration.
// No Trello branding by spec — we call it "Project source" everywhere visible
// to crew/customers. Owner-mode is where the connect surface lives.

const { useState: useStateConn, useEffect: useEffectConn } = React;

function ConnectScreen({ onConnect, error: incomingError, onCancel }) {
  const [step, setStep]     = useStateConn(1);
  // Pre-fill the BroFab API key so Chris doesn't have to hunt for it again.
  // Token still has to be authorized fresh per device. Both live in localStorage on connect, never in source.
  const [apiKey, setApiKey] = useStateConn(() => localStorage.getItem('bf-trello-key') || '');
  const [token, setToken]   = useStateConn(() => localStorage.getItem('bf-trello-token') || '');
  const [boardUrl, setBoardUrl] = useStateConn(() => localStorage.getItem('bf-trello-board-url') || '');
  const [busy, setBusy]     = useStateConn(false);
  const [err, setErr]       = useStateConn(null);

  useEffectConn(() => { if (incomingError) setErr(incomingError); }, [incomingError]);

  const boardId = parseBoardId(boardUrl);

  async function go() {
    setBusy(true); setErr(null);
    try {
      await onConnect({ key: apiKey.trim(), token: token.trim(), boardId, stageMap: {} });
    } catch (e) {
      setErr(e.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="connect-overlay">
      <div className="connect-card">
        <div className="connect-header">
          <div className="mark">BF</div>
          <div>
            <h2>Connect your project source</h2>
            <p className="muted">Brothers Fab Ops syncs jobs from your existing Trello board. Read &amp; write — moves, photos, comments, due dates and checklists flow both ways.</p>
          </div>
          {onCancel && <button className="x" onClick={onCancel} aria-label="Close">×</button>}
        </div>

        <ol className="connect-steps">
          <li className={step >= 1 ? 'on' : ''} onClick={() => setStep(1)}><span>1</span> API key</li>
          <li className={step >= 2 ? 'on' : ''} onClick={() => apiKey && setStep(2)}><span>2</span> Authorize</li>
          <li className={step >= 3 ? 'on' : ''} onClick={() => apiKey && token && setStep(3)}><span>3</span> Pick board</li>
        </ol>

        {step === 1 && (
          <div className="connect-step">
            <p>Your "BroFab" key is filled in below. Hit Next unless you want to use a different one — then grab a new key from <a href="https://trello.com/app-key" target="_blank" rel="noreferrer">trello.com/app-key</a>.</p>
            <input className="connect-input" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder="32-char API key" autoFocus/>
            <div className="connect-hint">Approved 19 Apr · read &amp; write on all boards &amp; workspaces · never expires</div>
            <div className="connect-actions">
              <button className="btn-primary" disabled={!apiKey.trim()} onClick={() => { localStorage.setItem('bf-trello-key', apiKey.trim()); setStep(2); }}>Next</button>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="connect-step">
            <p>Click <strong>Authorize</strong>, approve read/write access in Trello, copy the token, and paste it back here.</p>
            <a className="btn-secondary" href={window.bfTrello.buildAuthorizeUrl(apiKey)} target="_blank" rel="noreferrer">Authorize on Trello ↗</a>
            <input className="connect-input" value={token} onChange={e => setToken(e.target.value)} placeholder="Paste token from Trello" style={{ marginTop: 12 }}/>
            <div className="connect-actions">
              <button className="btn-ghost" onClick={() => setStep(1)}>Back</button>
              <button className="btn-primary" disabled={!token.trim()} onClick={() => setStep(3)}>Next</button>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="connect-step">
            <p>Paste the URL of the board you want connected. We'll auto-detect lists and let you map them to fab stages.</p>
            <input className="connect-input" value={boardUrl} onChange={e => setBoardUrl(e.target.value)} placeholder="https://trello.com/b/.../my-board"/>
            {boardId ? <div className="connect-hint ok">Board ID: <code>{boardId}</code></div>
                      : <div className="connect-hint">Paste a board URL or short ID</div>}
            {err && <div className="connect-hint err">{err}</div>}
            <div className="connect-actions">
              <button className="btn-ghost" onClick={() => setStep(2)}>Back</button>
              <button className="btn-primary" disabled={!boardId || busy} onClick={go}>
                {busy ? 'Connecting…' : 'Connect'}
              </button>
            </div>
          </div>
        )}

        <div className="connect-foot muted">
          Credentials stored locally on this device only · Trello stays the admin source of truth · No customer-facing Trello branding
        </div>
      </div>
    </div>
  );
}

function parseBoardId(url) {
  if (!url) return '';
  // Standard board URL: trello.com/b/<id>/<slug>
  let m = url.match(/trello\.com\/b\/([a-zA-Z0-9]+)/);
  if (m) return m[1];
  // Invite URL: trello.com/invite/b/<id>/...
  m = url.match(/trello\.com\/invite\/b\/([a-zA-Z0-9]+)/);
  if (m) return m[1];
  // Already an id?
  if (/^[a-f0-9]{24}$/i.test(url) || /^[a-zA-Z0-9]{8}$/.test(url)) return url;
  return '';
}

// ── Stage mapping panel — appears in Admin > Settings ───────────────────────
function StageMappingPanel({ trello }) {
  if (!trello.isConnected) return null;
  const { lists, ctx, setStageMapping, disconnect, board, lastSync, status } = trello;
  return (
    <div className="map-panel">
      <div className="map-head">
        <div>
          <h3>Project source · {board?.name || 'Connected'}</h3>
          <p className="muted">Map each list on your board to a fab stage. Crew see only fab stages — customers never see Trello.</p>
        </div>
        <div className="map-status">
          <span className={`dot ${status}`}/>
          <span className="muted">{status === 'live' ? `Synced ${timeAgo(lastSync)}` : status}</span>
          <button className="btn-ghost sm" onClick={disconnect}>Disconnect</button>
        </div>
      </div>
      <div className="map-grid">
        {lists.map(list => (
          <div key={list.id} className="map-row">
            <div className="map-list">
              <div className="map-list-name">{list.name}</div>
              <div className="muted xs">Trello list</div>
            </div>
            <div className="map-arrow">→</div>
            <select className="map-select" value={ctx.stageMap[list.id] || ''} onChange={e => setStageMapping(list.id, e.target.value)}>
              {window.bfTrello.FAB_STAGES.map(s => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
              <option value="ignore">— Ignore —</option>
            </select>
          </div>
        ))}
      </div>
    </div>
  );
}

function timeAgo(ts) {
  if (!ts) return 'never';
  const s = Math.round((Date.now() - ts) / 1000);
  if (s < 5) return 'just now';
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  return `${Math.round(s / 3600)}h ago`;
}

// ── Subtle status chip in the topbar ────────────────────────────────────────
function SyncStatusChip({ trello, onClick }) {
  const { status, lastSync, error } = trello;
  const klass = status === 'live' ? 'sync-ok' : status === 'error' ? 'sync-err' : 'sync-mute';
  const label = status === 'live'   ? `Synced ${timeAgo(lastSync)}`
              : status === 'error'  ? 'Sync error'
              : status === 'connecting' ? 'Connecting…'
              : status === 'disconnected' ? 'Local data'
              : 'Mock data';
  return (
    <button className={`sync-chip ${klass}`} onClick={onClick} title={error || label}>
      <span className="dot"/> {label}
    </button>
  );
}

Object.assign(window, { ConnectScreen, StageMappingPanel, SyncStatusChip, parseBoardId, timeAgo });
