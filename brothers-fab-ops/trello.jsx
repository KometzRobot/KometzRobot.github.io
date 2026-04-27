// Trello adapter — Brothers Fab Ops
// ─────────────────────────────────────────────────────────────────────────────
// Live read/write integration. Trello is source of truth (admin-wins) per
// product spec — every poll reconciles local state against Trello. Writes are
// optimistic but rolled back if the next poll disagrees.
//
// No Trello branding surfaces in the UI by spec. Status indicator is a small
// dot. The "Trello" name only appears on the Connect screen and in this file.
//
// API: https://developer.atlassian.com/cloud/trello/rest/
// Auth: API key + token, sent as query params. Token is requested via
//       https://trello.com/1/authorize?... and pasted by the user.

const TRELLO_API   = 'https://api.trello.com/1';
const TRELLO_AUTH  = 'https://trello.com/1/authorize';
const APP_NAME     = 'Brothers Fab Ops';
const LS_KEY       = 'bf_trello_v1';
const POLL_MS      = 15000;

// 8 fab stages we want to render — Trello lists get mapped onto these.
const FAB_STAGES = [
  { id: 'quote',      label: 'Quote / Lead' },
  { id: 'approved',   label: 'Approved' },
  { id: 'design',     label: 'Design' },
  { id: 'sourcing',   label: 'Sourcing' },
  { id: 'frame',      label: 'Frame / Build' },
  { id: 'plumbing',   label: 'Plumbing & Gas' },
  { id: 'electrical', label: 'Electrical' },
  { id: 'delivered',  label: 'Delivered' },
];

// ── Persistence ──────────────────────────────────────────────────────────────
function loadConfig() {
  try { return JSON.parse(localStorage.getItem(LS_KEY) || 'null'); }
  catch { return null; }
}
function saveConfig(cfg) {
  localStorage.setItem(LS_KEY, JSON.stringify(cfg));
}
function clearConfig() {
  localStorage.removeItem(LS_KEY);
}

// ── Low-level fetch ──────────────────────────────────────────────────────────
async function trelloFetch(path, { key, token }, opts = {}) {
  const url = new URL(TRELLO_API + path);
  url.searchParams.set('key', key);
  url.searchParams.set('token', token);
  if (opts.params) {
    for (const [k, v] of Object.entries(opts.params)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    }
  }
  const init = { method: opts.method || 'GET' };
  if (opts.body) {
    init.headers = { 'Content-Type': 'application/json' };
    init.body = JSON.stringify(opts.body);
  }
  if (opts.formData) {
    init.body = opts.formData;
  }
  const res = await fetch(url.toString(), init);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`Trello ${res.status}: ${text || res.statusText}`);
  }
  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}

// ── High-level reads ─────────────────────────────────────────────────────────
async function fetchBoardSnapshot(cfg) {
  const { boardId } = cfg;
  // One round-trip with `?lists=open&cards=open&...` would be ideal but Trello
  // limits nested includes — so we batch in parallel.
  const [board, lists, cards, members, actions, labels] = await Promise.all([
    trelloFetch(`/boards/${boardId}`, cfg, { params: { fields: 'name,desc,prefs' } }),
    trelloFetch(`/boards/${boardId}/lists`, cfg, { params: { filter: 'open' } }),
    trelloFetch(`/boards/${boardId}/cards`, cfg, { params: {
      filter: 'open',
      fields: 'name,desc,idList,due,dueComplete,idMembers,idLabels,shortUrl,dateLastActivity,badges',
      attachments: 'true',
      attachment_fields: 'name,url,date,mimeType,previews',
      checklists: 'all',
      checklist_fields: 'name',
    }}),
    trelloFetch(`/boards/${boardId}/members`, cfg, { params: { fields: 'fullName,initials,avatarUrl' } }),
    trelloFetch(`/boards/${boardId}/actions`, cfg, { params: { filter: 'commentCard,updateCard:idList,addAttachmentToCard,createCard', limit: 50 } }),
    trelloFetch(`/boards/${boardId}/labels`, cfg, { params: { fields: 'name,color' } }),
  ]);
  return { board, lists, cards, members, actions, labels, fetchedAt: Date.now() };
}

// ── Mapping: Trello → fab job ────────────────────────────────────────────────
// Stage map is { listId → fabStageId }. If a list isn't mapped we infer from
// list name (case-insensitive substring match), else fall back to 'quote'.
const NAME_HINTS = [
  ['delivered', ['delivered', 'done', 'complete', 'shipped', 'closeout']],
  ['electrical', ['electrical', 'electric', 'wiring']],
  ['plumbing', ['plumb', 'gas', 'glycol']],
  ['frame', ['frame', 'build', 'weld', 'fabrication']],
  ['sourcing', ['sourcing', 'materials', 'order', 'procure']],
  ['design', ['design', 'planning', 'cad']],
  ['approved', ['approved', 'deposit', 'kickoff', 'in progress']],
  ['quote', ['quote', 'lead', 'inbox', 'backlog', 'todo', 'to do', 'new']],
];
function inferStageFromName(name) {
  const n = (name || '').toLowerCase();
  for (const [stage, keys] of NAME_HINTS) {
    if (keys.some(k => n.includes(k))) return stage;
  }
  return 'quote';
}
function buildStageMap(lists, override) {
  const map = {};
  for (const list of lists) {
    map[list.id] = override?.[list.id] || inferStageFromName(list.name);
  }
  return map;
}

function pickAvatarUrl(member) {
  if (!member?.avatarUrl) return null;
  return member.avatarUrl + '/50.png';
}

// Generate a deterministic accent color from the card id.
function colorForCard(id) {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `oklch(0.70 0.13 ${hue})`;
}

function cardToJob(card, ctx) {
  const stage = ctx.stageMap[card.idList] || 'quote';
  const checklists = card.checklists || [];
  const totalItems = checklists.reduce((n, cl) => n + (cl.checkItems?.length || 0), 0);
  const doneItems  = checklists.reduce((n, cl) => n + (cl.checkItems?.filter(ci => ci.state === 'complete').length || 0), 0);
  const checklistProgress = totalItems ? doneItems / totalItems : 0;
  // Stage-based progress floor — Trello stage gives us baseline, checklists refine.
  const stageIdx = FAB_STAGES.findIndex(s => s.id === stage);
  const stageProgress = stageIdx < 0 ? 0 : (stageIdx + 0.5) / FAB_STAGES.length;
  const progress = totalItems ? checklistProgress : stageProgress;

  const photoAttachments = (card.attachments || []).filter(a =>
    (a.mimeType || '').startsWith('image/') || /\.(png|jpe?g|webp|gif)$/i.test(a.url || '')
  );

  const crew = (card.idMembers || []).map(mid => {
    const m = ctx.members.find(x => x.id === mid);
    return m ? { id: mid, name: m.fullName, initials: m.initials, avatar: pickAvatarUrl(m) } : null;
  }).filter(Boolean);

  // Try to extract a job code (BF-XXXX) from card name; else short id.
  const codeMatch = card.name.match(/\b(BF[-\s]?\d{3,5})\b/i);
  const id = codeMatch ? codeMatch[1].toUpperCase().replace(/\s/, '-') : `T-${card.id.slice(-4).toUpperCase()}`;

  return {
    id,
    trelloId: card.id,
    name: card.name.replace(/\b(BF[-\s]?\d{3,5})\b/i, '').trim() || card.name,
    type: ctx.labels.filter(l => (card.idLabels || []).includes(l.id)).map(l => l.name).filter(Boolean).join(' · ') || 'Untitled job',
    stage,
    progress,
    eta: card.due ? card.due.slice(0, 10) : null,
    etaConfidence: card.due ? (card.dueComplete ? 'high' : 'medium') : 'low',
    crew,
    color: colorForCard(card.id),
    description: card.desc || '',
    photos: photoAttachments.length,
    photoUrls: photoAttachments.map(a => ({ url: a.url, name: a.name, date: a.date, previews: a.previews })),
    nextMilestone: nextChecklistItem(checklists),
    nextMilestoneDate: card.due ? card.due.slice(0, 10) : null,
    blockers: 0,
    pendingApprovals: 0,
    unread: 0,
    checklists,
    shortUrl: card.shortUrl,
    lastActivity: card.dateLastActivity,
    // Mocked financial fields — Trello doesn't carry these. Surfaces will
    // fall back to placeholders rather than fabricate hard numbers.
    quote: null,
    spent: null,
    hoursBudget: null,
    hoursLogged: null,
    started: null,
    client: null,
  };
}

function nextChecklistItem(checklists) {
  for (const cl of checklists) {
    const item = (cl.checkItems || []).find(ci => ci.state === 'incomplete');
    if (item) return item.name;
  }
  return null;
}

// Convert Trello actions → activity feed entries.
function actionToActivity(action, ctx) {
  const t = new Date(action.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const member = action.memberCreator || {};
  const who = member.fullName || member.username || 'someone';
  const cardName = action.data?.card?.name || '';
  const codeMatch = cardName.match(/\b(BF[-\s]?\d{3,5})\b/i);
  const jobId = codeMatch ? codeMatch[1].toUpperCase().replace(/\s/, '-') : (action.data?.card?.id ? `T-${action.data.card.id.slice(-4).toUpperCase()}` : '');
  const base = { id: action.id, jobId, t, who, whoName: who };
  switch (action.type) {
    case 'commentCard':
      return { ...base, kind: 'message', title: `${who} commented on ${cardName}`, body: `"${(action.data.text || '').slice(0, 140)}"` };
    case 'updateCard':
      if (action.data.listAfter && action.data.listBefore) {
        return { ...base, kind: 'stage', title: `Moved to ${action.data.listAfter.name}`, body: `from ${action.data.listBefore.name} · ${cardName}` };
      }
      return null;
    case 'addAttachmentToCard':
      return { ...base, kind: 'photo', title: `Attachment added — ${cardName}`, body: action.data?.attachment?.name || '' };
    case 'createCard':
      return { ...base, kind: 'new', title: `New job — ${cardName}`, body: action.data?.list?.name || '' };
    default:
      return null;
  }
}

// ── Writes ───────────────────────────────────────────────────────────────────
async function moveCardToStage(cfg, ctx, cardId, stageId) {
  // Find a list in the current board mapped to that stage.
  const targetListId = Object.entries(ctx.stageMap).find(([, s]) => s === stageId)?.[0];
  if (!targetListId) throw new Error(`No Trello list is mapped to stage "${stageId}"`);
  return trelloFetch(`/cards/${cardId}`, cfg, { method: 'PUT', params: { idList: targetListId } });
}
async function addCardComment(cfg, cardId, text) {
  return trelloFetch(`/cards/${cardId}/actions/comments`, cfg, { method: 'POST', params: { text } });
}
async function uploadCardAttachment(cfg, cardId, file) {
  const fd = new FormData();
  fd.append('key', cfg.key);
  fd.append('token', cfg.token);
  fd.append('file', file);
  fd.append('name', file.name);
  // Use raw fetch so FormData boundary stays intact.
  const res = await fetch(`${TRELLO_API}/cards/${cardId}/attachments`, { method: 'POST', body: fd });
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
  return res.json();
}
async function setCardDueDate(cfg, cardId, isoDate) {
  return trelloFetch(`/cards/${cardId}`, cfg, { method: 'PUT', params: { due: isoDate } });
}
async function toggleCheckItem(cfg, cardId, checkItemId, complete) {
  return trelloFetch(`/cards/${cardId}/checkItem/${checkItemId}`, cfg, {
    method: 'PUT', params: { state: complete ? 'complete' : 'incomplete' },
  });
}
async function addCardMember(cfg, cardId, memberId) {
  return trelloFetch(`/cards/${cardId}/idMembers`, cfg, { method: 'POST', params: { value: memberId } });
}
async function removeCardMember(cfg, cardId, memberId) {
  return trelloFetch(`/cards/${cardId}/idMembers/${memberId}`, cfg, { method: 'DELETE' });
}

// ── Hook ─────────────────────────────────────────────────────────────────────
function useTrello() {
  const [config, setConfig]   = React.useState(loadConfig);
  const [snapshot, setSnap]   = React.useState(null);
  const [status, setStatus]   = React.useState(config ? 'connecting' : 'disconnected'); // disconnected | connecting | live | error | mock
  const [error, setError]     = React.useState(null);
  const [lastSync, setLast]   = React.useState(null);
  const pendingRef            = React.useRef([]); // optimistic moves we expect to see reflected

  const ctx = React.useMemo(() => {
    if (!snapshot) return null;
    const stageMap = buildStageMap(snapshot.lists, config?.stageMap);
    return {
      stageMap,
      members: snapshot.members,
      labels: snapshot.labels,
      lists: snapshot.lists,
      board: snapshot.board,
    };
  }, [snapshot, config?.stageMap]);

  const jobs = React.useMemo(() => {
    if (!snapshot || !ctx) return null;
    return snapshot.cards.map(c => cardToJob(c, ctx));
  }, [snapshot, ctx]);

  const activity = React.useMemo(() => {
    if (!snapshot || !ctx) return null;
    return snapshot.actions.map(a => actionToActivity(a, ctx)).filter(Boolean).slice(0, 30);
  }, [snapshot, ctx]);

  // Poll loop
  React.useEffect(() => {
    if (!config) { setStatus('disconnected'); return; }
    let alive = true;
    let timer;
    async function tick() {
      try {
        const snap = await fetchBoardSnapshot(config);
        if (!alive) return;
        setSnap(snap);
        setStatus('live');
        setLast(Date.now());
        setError(null);
      } catch (e) {
        if (!alive) return;
        setStatus('error');
        setError(e.message);
      } finally {
        if (alive) timer = setTimeout(tick, POLL_MS);
      }
    }
    tick();
    return () => { alive = false; clearTimeout(timer); };
  }, [config]);

  const connect = React.useCallback(async (cfg) => {
    setStatus('connecting');
    setError(null);
    try {
      // Validate creds + board id with a single ping.
      await trelloFetch(`/boards/${cfg.boardId}`, cfg, { params: { fields: 'name' } });
      saveConfig(cfg);
      setConfig(cfg);
    } catch (e) {
      setStatus('error');
      setError(e.message);
      throw e;
    }
  }, []);

  const disconnect = React.useCallback(() => {
    clearConfig();
    setConfig(null);
    setSnap(null);
    setStatus('disconnected');
  }, []);

  // Action wrappers — all optimistic, all reconciled by next poll.
  const moveStage = React.useCallback(async (cardId, stageId) => {
    if (!config || !ctx) throw new Error('Not connected');
    // Optimistic local update
    setSnap(s => s && {
      ...s,
      cards: s.cards.map(c => {
        if (c.id !== cardId) return c;
        const targetListId = Object.entries(ctx.stageMap).find(([, st]) => st === stageId)?.[0];
        return targetListId ? { ...c, idList: targetListId } : c;
      }),
    });
    try {
      await moveCardToStage(config, ctx, cardId, stageId);
    } catch (e) {
      // Rollback by forcing a re-poll — handled by tick on next interval.
      throw e;
    }
  }, [config, ctx]);

  const comment = React.useCallback((cardId, text) => addCardComment(config, cardId, text), [config]);
  const attach  = React.useCallback((cardId, file)  => uploadCardAttachment(config, cardId, file), [config]);
  const setDue  = React.useCallback((cardId, iso)   => setCardDueDate(config, cardId, iso), [config]);
  const toggleCheck = React.useCallback((cardId, ciId, complete) => toggleCheckItem(config, cardId, ciId, complete), [config]);
  const addMember    = React.useCallback((cardId, mid) => addCardMember(config, cardId, mid), [config]);
  const removeMember = React.useCallback((cardId, mid) => removeCardMember(config, cardId, mid), [config]);

  // Update mapping override on the fly.
  const setStageMapping = React.useCallback((listId, stageId) => {
    setConfig(prev => {
      const next = { ...prev, stageMap: { ...(prev?.stageMap || {}), [listId]: stageId } };
      saveConfig(next);
      return next;
    });
  }, []);

  return {
    config, status, error, lastSync,
    snapshot, ctx, jobs, activity,
    connect, disconnect,
    moveStage, comment, attach, setDue, toggleCheck, addMember, removeMember,
    setStageMapping,
    // Convenience
    isConnected: !!config && status === 'live',
    members: ctx?.members || [],
    lists: ctx?.lists || [],
    board: ctx?.board,
  };
}

// ── Authorize URL helper ─────────────────────────────────────────────────────
function buildAuthorizeUrl(apiKey) {
  const u = new URL(TRELLO_AUTH);
  u.searchParams.set('expiration', 'never');
  u.searchParams.set('name', APP_NAME);
  u.searchParams.set('scope', 'read,write,account');
  u.searchParams.set('response_type', 'token');
  u.searchParams.set('key', apiKey);
  return u.toString();
}

// ── Export ───────────────────────────────────────────────────────────────────
Object.assign(window, {
  useTrello,
  bfTrello: {
    FAB_STAGES,
    buildAuthorizeUrl,
    inferStageFromName,
    loadConfig, saveConfig, clearConfig,
    fetchBoardSnapshot,
    cardToJob, actionToActivity,
  },
});
