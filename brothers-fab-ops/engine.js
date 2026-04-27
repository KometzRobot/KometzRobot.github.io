// ─────────────────────────────────────────────────────────────────────────────
// Brothers Fab Ops — Correlation Engine
// ─────────────────────────────────────────────────────────────────────────────
//
// One bus, one window, many small rules. Surfaces don't poll; they subscribe.
//
//   Sources           Bus           Correlator         Surfaces
//   ───────           ───           ──────────         ────────
//   Trello poll  ┐                  rule₁ ──┐
//   UI actions   ├──▶  Event[] ──▶  rule₂ ──┼──▶ Signal[]  ──▶  React (subscribe)
//   Timer tick   ┘                  rule₃ ──┘
//                                   …
//
// Why this shape:
//
// • Decoupled — surfaces never know Trello exists. They subscribe to signals
//   like "margin-erosion:BF-2041" or "answer-needed:BF-2039" and render.
// • Auditable — every signal carries `because: Event[]` so we can show the
//   user EXACTLY which raw events fired the rule. No mystery alerts.
// • Composable — rules are pure(ish) functions over a sliding window. New
//   correlation = one new file, registered into the engine. No surface edits.
// • Replayable — the event log is the source of truth; rules can be re-run
//   over history to test new correlations against real shop data.
// • Confidence-typed — rules emit { confidence: 0..1 } so the UI can decide
//   what's a hard alert vs a soft hint.
//
// ─────────────────────────────────────────────────────────────────────────────

(function () {
  // ── Event ──────────────────────────────────────────────────────────────────
  // A single, flat shape for everything that happens in the system.
  //
  //   {
  //     id:    'evt_a8f2',                     unique
  //     ts:    1714074610234,                  ms epoch
  //     src:   'trello' | 'tablet' | 'system' | 'admin' | 'portal',
  //     kind:  'card.moved' | 'photo.added' | 'comment.added' |
  //            'checklist.toggled' | 'punch.in' | 'material.logged' |
  //            'budget.updated' | 'eta.changed' | 'crew.assigned' | …,
  //     jobId: 'BF-2041' | null,               correlation key
  //     actor: 'jesse' | 'chris' | null,
  //     payload: { …kind-specific… },
  //   }

  const MAX_EVENTS = 5000;          // sliding ring — last ~24h on a busy day
  const WINDOW_MS  = 36 * 3600e3;   // rules see 36h of history
  const TICK_MS    = 5000;          // re-evaluate every 5s

  // ── State ──────────────────────────────────────────────────────────────────
  const state = {
    events: [],                 // newest-last
    signals: new Map(),         // key → Signal
    rules: [],                  // registered rules
    listeners: { events: new Set(), signals: new Set() },
    seenIds: new Set(),         // dedupe (Trello polls give us repeats)
  };

  // ── Public API ─────────────────────────────────────────────────────────────
  const engine = {
    emit, emitMany, register, on, off,
    snapshot,
    rulesFor, signalsFor, signalsByKind,
    explain, replay, prune,
    // Helpers exposed for rules + tests
    util: {
      newer: (events, ms) => events.filter(e => e.ts > Date.now() - ms),
      byJob: (events, jobId) => events.filter(e => e.jobId === jobId),
      ofKind: (events, ...kinds) => events.filter(e => kinds.includes(e.kind)),
      latest: (events, kind) => [...events].reverse().find(e => e.kind === kind),
      sumPayload: (events, key) => events.reduce((n, e) => n + (e.payload?.[key] || 0), 0),
      since: (ts) => Date.now() - ts,
      hours: (ms) => ms / 3600e3,
    },
  };

  // ── Emit ───────────────────────────────────────────────────────────────────
  function emit(evt) {
    const ev = normalize(evt);
    if (!ev) return;
    if (state.seenIds.has(ev.id)) return;
    state.seenIds.add(ev.id);
    state.events.push(ev);
    if (state.events.length > MAX_EVENTS) {
      const drop = state.events.shift();
      state.seenIds.delete(drop.id);
    }
    notify('events', ev);
  }
  function emitMany(events) { events.forEach(emit); }

  function normalize(e) {
    if (!e || !e.kind) return null;
    return {
      id: e.id || `evt_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`,
      ts: e.ts || Date.now(),
      src: e.src || 'system',
      kind: e.kind,
      jobId: e.jobId || null,
      actor: e.actor || null,
      payload: e.payload || {},
    };
  }

  // ── Rules ──────────────────────────────────────────────────────────────────
  // A rule is:
  //   {
  //     id:        'margin-erosion',
  //     label:     'Margin erosion',
  //     watches:   ['budget.updated','material.logged','card.moved'],   // hint only
  //     evaluate(ctx) { return [Signal, …] }
  //   }
  //
  // Signal:
  //   { key, ruleId, jobId, severity:'info|warn|alert', confidence:0..1,
  //     title, body, because:[evtId], suggested:[Action], expiresAt }
  function register(rule) {
    if (!rule.id || !rule.evaluate) throw new Error('rule needs id + evaluate');
    state.rules = state.rules.filter(r => r.id !== rule.id).concat(rule);
  }

  // ── Evaluation loop ────────────────────────────────────────────────────────
  let timer = null;
  function startLoop() {
    if (timer) return;
    timer = setInterval(evaluate, TICK_MS);
  }
  function evaluate() {
    const window = engine.util.newer(state.events, WINDOW_MS);
    const ctx = { events: window, util: engine.util, now: Date.now() };
    const next = new Map();
    for (const rule of state.rules) {
      let out;
      try { out = rule.evaluate(ctx) || []; }
      catch (err) {
        console.warn(`[engine] rule ${rule.id} threw`, err);
        continue;
      }
      for (const sig of out) {
        const key = sig.key || `${rule.id}:${sig.jobId || 'global'}`;
        next.set(key, {
          key,
          ruleId: rule.id,
          ruleLabel: rule.label,
          severity: sig.severity || 'info',
          confidence: sig.confidence ?? 0.7,
          jobId: sig.jobId || null,
          title: sig.title,
          body: sig.body || '',
          because: sig.because || [],
          suggested: sig.suggested || [],
          firstSeen: state.signals.get(key)?.firstSeen || Date.now(),
          lastSeen: Date.now(),
          expiresAt: sig.expiresAt || null,
        });
      }
    }
    // Honour expiries
    for (const [k, s] of next) if (s.expiresAt && s.expiresAt < Date.now()) next.delete(k);
    state.signals = next;
    notify('signals', state.signals);
  }

  // Re-evaluate immediately on a write so the UI feels live.
  function notify(channel, payload) {
    state.listeners[channel].forEach(fn => { try { fn(payload); } catch (e) { console.warn(e); } });
    if (channel === 'events') queueMicrotask(evaluate);
  }
  function on(channel, fn) { state.listeners[channel].add(fn); return () => off(channel, fn); }
  function off(channel, fn) { state.listeners[channel].delete(fn); }

  // ── Inspect ────────────────────────────────────────────────────────────────
  function snapshot() {
    return {
      events: state.events.slice(-200),
      signals: [...state.signals.values()],
      rules: state.rules.map(r => ({ id: r.id, label: r.label, watches: r.watches || [] })),
    };
  }
  function rulesFor(jobId) {
    return [...state.signals.values()].filter(s => s.jobId === jobId);
  }
  function signalsFor(jobId) { return rulesFor(jobId); }
  function signalsByKind(ruleId) {
    return [...state.signals.values()].filter(s => s.ruleId === ruleId);
  }
  function explain(signalKey) {
    const sig = state.signals.get(signalKey);
    if (!sig) return null;
    const events = sig.because.map(id => state.events.find(e => e.id === id)).filter(Boolean);
    return { signal: sig, events };
  }
  function replay(events) {
    state.events = []; state.seenIds.clear();
    emitMany(events);
    evaluate();
  }
  function prune(beforeMs) {
    state.events = state.events.filter(e => e.ts >= beforeMs);
  }

  // ── Built-in rules ─────────────────────────────────────────────────────────
  // Concrete starter set covering the patterns that matter on the shop floor.
  // Each is small, pure, and reads like a domain sentence.

  // 1. Stage moved without a proof photo within N hours.
  register({
    id: 'stage-without-proof',
    label: 'Stage transition without proof photo',
    watches: ['card.moved', 'photo.added'],
    evaluate({ events, util, now }) {
      const moves = util.ofKind(events, 'card.moved');
      const out = [];
      for (const m of moves) {
        if (now - m.ts > 4 * 3600e3) continue;            // only recent moves matter
        const photosAfter = events.filter(e =>
          e.kind === 'photo.added' && e.jobId === m.jobId && e.ts > m.ts
        );
        if (photosAfter.length === 0 && now - m.ts > 4 * 3600e3 - 60e3) {
          out.push({
            key: `proof:${m.jobId}:${m.id}`,
            jobId: m.jobId,
            severity: 'warn',
            confidence: 0.85,
            title: `${m.jobId} moved to ${m.payload.toStage}, no photo logged`,
            body: `Stage changed ${Math.round(util.hours(now - m.ts))}h ago — flag a quick photo so the customer feed and admin sign-off don't stall.`,
            because: [m.id],
            suggested: [{ action: 'request-photo', jobId: m.jobId }],
            expiresAt: m.ts + 24 * 3600e3,
          });
        }
      }
      return out;
    },
  });

  // 2. Spend pace ahead of progress pace → margin erosion.
  register({
    id: 'margin-erosion',
    label: 'Margin erosion',
    watches: ['budget.updated', 'progress.updated'],
    evaluate({ events, util }) {
      // Latest budget + progress per job.
      const latestBy = (kind) => {
        const m = new Map();
        for (const e of events) if (e.kind === kind && e.jobId) m.set(e.jobId, e);
        return m;
      };
      const budgets = latestBy('budget.updated');
      const progress = latestBy('progress.updated');
      const out = [];
      for (const [jobId, b] of budgets) {
        const p = progress.get(jobId);
        if (!p) continue;
        const spendPct = b.payload.spent / b.payload.quote;
        const progPct  = p.payload.progress;
        const gap = spendPct - progPct;
        if (gap > 0.08) {
          const sev = gap > 0.18 ? 'alert' : 'warn';
          out.push({
            key: `margin:${jobId}`,
            jobId, severity: sev,
            confidence: Math.min(0.95, 0.6 + gap * 2),
            title: `${jobId} burning faster than building`,
            body: `${Math.round(spendPct*100)}% spent vs ${Math.round(progPct*100)}% complete. Gap +${Math.round(gap*100)}%.`,
            because: [b.id, p.id],
            suggested: [{ action: 'review-overages', jobId }],
          });
        }
      }
      return out;
    },
  });

  // 3. Customer asked a question, no reply in 24h.
  register({
    id: 'answer-needed',
    label: 'Customer answer needed',
    watches: ['comment.added'],
    evaluate({ events, util, now }) {
      const customer = util.ofKind(events, 'comment.added').filter(e => e.payload.from === 'customer');
      const out = [];
      for (const q of customer) {
        if (!/[?¿]/.test(q.payload.text || '')) continue;
        const reply = events.find(e =>
          e.kind === 'comment.added' && e.jobId === q.jobId &&
          e.ts > q.ts && e.payload.from !== 'customer'
        );
        if (!reply && now - q.ts > 24 * 3600e3) {
          out.push({
            key: `answer:${q.id}`,
            jobId: q.jobId,
            severity: 'warn', confidence: 0.9,
            title: `${q.jobId} — customer waiting for an answer`,
            body: `"${(q.payload.text || '').slice(0, 120)}" — open ${Math.round(util.hours(now - q.ts))}h.`,
            because: [q.id],
            suggested: [{ action: 'draft-reply', jobId: q.jobId, to: q.actor }],
          });
        }
      }
      return out;
    },
  });

  // 4. Material crosses reorder threshold AND ≥2 active jobs need it.
  register({
    id: 'bulk-buy-opportunity',
    label: 'Bulk-buy opportunity',
    watches: ['inventory.updated', 'material.logged'],
    evaluate({ events, util }) {
      const inv = util.latest(events, 'inventory.updated');
      if (!inv) return [];
      const usedBy = new Map(); // sku → Set<jobId>
      for (const e of util.ofKind(events, 'material.logged')) {
        const sku = e.payload.sku;
        if (!usedBy.has(sku)) usedBy.set(sku, new Set());
        usedBy.get(sku).add(e.jobId);
      }
      const out = [];
      for (const m of inv.payload.items || []) {
        if (m.stock > m.reorder) continue;
        const consumers = usedBy.get(m.sku) || new Set();
        if (consumers.size >= 2) {
          out.push({
            key: `bulk:${m.sku}`,
            jobId: null,
            severity: 'info', confidence: 0.8,
            title: `Bulk-buy: ${m.name}`,
            body: `${consumers.size} active jobs need this. ${m.stock} ${m.unit} left, reorder at ${m.reorder}. Consolidate the order with ${m.vendor}.`,
            because: [inv.id],
            suggested: [{ action: 'create-po', sku: m.sku, jobs: [...consumers] }],
          });
        }
      }
      return out;
    },
  });

  // 5. Punch-in idle — punched in, no events for >2h.
  register({
    id: 'idle-punch-in',
    label: 'Idle punch-in',
    watches: ['punch.in', 'photo.added', 'material.logged', 'checklist.toggled'],
    evaluate({ events, util, now }) {
      // Per actor: most recent punch.in not followed by a punch.out.
      const ins = util.ofKind(events, 'punch.in');
      const outs = util.ofKind(events, 'punch.out');
      const out = [];
      for (const pi of ins) {
        const closed = outs.find(po => po.actor === pi.actor && po.ts > pi.ts);
        if (closed) continue;
        const lastSignal = events
          .filter(e => e.actor === pi.actor && e.ts > pi.ts && e.kind !== 'punch.in')
          .sort((a, b) => b.ts - a.ts)[0];
        const since = lastSignal ? lastSignal.ts : pi.ts;
        if (now - since > 2 * 3600e3) {
          out.push({
            key: `idle:${pi.actor}`,
            jobId: pi.jobId,
            severity: 'info', confidence: 0.6,
            title: `${pi.actor} idle for ${Math.round(util.hours(now - since))}h`,
            body: `Punched in at ${new Date(pi.ts).toLocaleTimeString()} — no activity since.`,
            because: [pi.id],
            suggested: [{ action: 'check-in', actor: pi.actor }],
          });
        }
      }
      return out;
    },
  });

  // 6. ETA slip cascade — due passed, stage hasn't progressed.
  register({
    id: 'eta-slip',
    label: 'ETA slip',
    watches: ['eta.changed', 'card.moved'],
    evaluate({ events, util, now }) {
      const etas = new Map();
      for (const e of events) if (e.kind === 'eta.changed' && e.jobId) etas.set(e.jobId, e);
      const out = [];
      for (const [jobId, e] of etas) {
        const due = new Date(e.payload.due).getTime();
        if (isNaN(due) || due > now) continue;
        const moved = events.find(m => m.kind === 'card.moved' && m.jobId === jobId && m.ts > due);
        if (moved) continue; // already advanced
        out.push({
          key: `slip:${jobId}`,
          jobId, severity: 'alert', confidence: 0.9,
          title: `${jobId} past due, stage unchanged`,
          body: `Due ${e.payload.due}. Recompute downstream ETAs and let the customer know.`,
          because: [e.id],
          suggested: [
            { action: 'recompute-eta', jobId },
            { action: 'notify-customer', jobId },
          ],
        });
      }
      return out;
    },
  });

  // 7. Crew double-booked — two open punch-ins for same actor.
  register({
    id: 'crew-double-booked',
    label: 'Crew double-booked',
    watches: ['punch.in'],
    evaluate({ events, util }) {
      const ins = util.ofKind(events, 'punch.in');
      const outs = util.ofKind(events, 'punch.out');
      const open = ins.filter(pi => !outs.some(po => po.actor === pi.actor && po.ts > pi.ts));
      const byActor = new Map();
      for (const pi of open) {
        if (!byActor.has(pi.actor)) byActor.set(pi.actor, []);
        byActor.get(pi.actor).push(pi);
      }
      const out = [];
      for (const [actor, list] of byActor) {
        if (list.length < 2) continue;
        out.push({
          key: `dbl:${actor}`,
          jobId: null, severity: 'warn', confidence: 0.95,
          title: `${actor} punched in on ${list.length} jobs`,
          body: list.map(p => p.jobId).join(', ') + ' — close one before the other accrues hours.',
          because: list.map(p => p.id),
          suggested: [{ action: 'reconcile-punch', actor }],
        });
      }
      return out;
    },
  });

  // 8. Photo cluster anomaly — one job suddenly gets 6+ photos in 30min.
  // Could be progress burst (good signal for portal), or a problem (rework).
  register({
    id: 'photo-burst',
    label: 'Photo burst',
    watches: ['photo.added'],
    evaluate({ events, util, now }) {
      const recent = events.filter(e => e.kind === 'photo.added' && now - e.ts < 30 * 60e3);
      const byJob = new Map();
      for (const e of recent) {
        if (!byJob.has(e.jobId)) byJob.set(e.jobId, []);
        byJob.get(e.jobId).push(e);
      }
      const out = [];
      for (const [jobId, list] of byJob) {
        if (list.length < 6) continue;
        out.push({
          key: `burst:${jobId}`,
          jobId, severity: 'info', confidence: 0.7,
          title: `${jobId} — ${list.length} photos in 30 min`,
          body: `Looks like a burst. Curate 2–3 for the customer feed?`,
          because: list.map(e => e.id),
          suggested: [{ action: 'curate-photos', jobId }],
          expiresAt: now + 4 * 3600e3,
        });
      }
      return out;
    },
  });

  // 9. Checklist stalled — same incomplete item for >48h.
  register({
    id: 'checklist-stalled',
    label: 'Checklist stalled',
    watches: ['checklist.toggled'],
    evaluate({ events, util, now }) {
      // Latest toggle per (jobId, itemId).
      const last = new Map();
      for (const e of util.ofKind(events, 'checklist.toggled')) {
        const k = `${e.jobId}|${e.payload.itemId}`;
        const prev = last.get(k);
        if (!prev || e.ts > prev.ts) last.set(k, e);
      }
      const out = [];
      for (const [, e] of last) {
        if (e.payload.complete) continue;
        if (now - e.ts < 48 * 3600e3) continue;
        out.push({
          key: `stall:${e.jobId}:${e.payload.itemId}`,
          jobId: e.jobId, severity: 'info', confidence: 0.65,
          title: `${e.jobId} — "${e.payload.label}" stalled 48h+`,
          body: `Last touched ${new Date(e.ts).toLocaleString()}. Reassign or break it down?`,
          because: [e.id],
          suggested: [{ action: 'reassign-item', jobId: e.jobId, itemId: e.payload.itemId }],
        });
      }
      return out;
    },
  });

  // 10. AHS-relevant stage advance — auto-prep inspection checklist.
  register({
    id: 'ahs-prep',
    label: 'AHS inspection prep',
    watches: ['card.moved'],
    evaluate({ events, util, now }) {
      const out = [];
      const moves = util.ofKind(events, 'card.moved');
      for (const m of moves) {
        if (m.payload.toStage !== 'electrical') continue;
        if (now - m.ts > 24 * 3600e3) continue;
        out.push({
          key: `ahs:${m.jobId}`,
          jobId: m.jobId, severity: 'info', confidence: 0.9,
          title: `${m.jobId} entering electrical — queue AHS gas + electrical inspection`,
          body: `Auto-add the 18-item AHS checklist and book inspector window.`,
          because: [m.id],
          suggested: [
            { action: 'attach-ahs-checklist', jobId: m.jobId },
            { action: 'book-inspector', jobId: m.jobId },
          ],
        });
      }
      return out;
    },
  });

  // ── Boot ───────────────────────────────────────────────────────────────────
  startLoop();

  if (typeof window !== 'undefined') window.bfEngine = engine;
})();
