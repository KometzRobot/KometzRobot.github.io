const { app, BrowserWindow, ipcMain, Tray, Menu } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');
const crypto = require('crypto');

// Cinder desktop app — wraps the HTML console in a native window
// Communicates with local Ollama instance for inference
// Designed for portable USB operation

let mainWindow;
let tray = null;
const OLLAMA_BASE = 'http://127.0.0.1:11434';

// ── USB / Portable Detection ──────────────────────────────
// When running from USB, __dirname is on the removable drive
// Data (memory, settings) stored relative to app location
const DATA_DIR = path.join(__dirname, 'data');
const SETTINGS_FILE = path.join(DATA_DIR, 'settings.json');
const PASSWORD_FILE = path.join(DATA_DIR, '.auth');

function ensureDataDir() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
}

// ── Password / Auth System ────────────────────────────────
function hashPassword(pw) {
  const salt = crypto.randomBytes(16).toString('hex');
  const hash = crypto.scryptSync(pw, salt, 64).toString('hex');
  return `${salt}:${hash}`;
}

function verifyPassword(pw, stored) {
  const [salt, hash] = stored.split(':');
  const test = crypto.scryptSync(pw, salt, 64).toString('hex');
  return test === hash;
}

function isFirstRun() {
  ensureDataDir();
  return !fs.existsSync(PASSWORD_FILE);
}

function setPassword(pw) {
  ensureDataDir();
  fs.writeFileSync(PASSWORD_FILE, hashPassword(pw), 'utf8');
}

function checkPassword(pw) {
  if (!fs.existsSync(PASSWORD_FILE)) return false;
  const stored = fs.readFileSync(PASSWORD_FILE, 'utf8').trim();
  return verifyPassword(pw, stored);
}

// ── Window Creation ───────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 900,
    height: 700,
    minWidth: 480,
    minHeight: 600,
    title: 'Cinder',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    backgroundColor: '#1a1210',
    frame: true,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Show password/setup screen first if needed
  if (isFirstRun()) {
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'setup.html'));
  } else {
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'login.html'));
  }

  // Minimize to tray on close (don't quit) — Joel: close = keep running
  mainWindow.on('close', (e) => {
    if (!app.isQuitting) {
      e.preventDefault();
      mainWindow.hide();
    }
  });
}

// ── Startup Dependency Check ─────────────────────────────
// Verify Ollama and Python are available before launch.
// Missing deps get reported to the renderer via IPC.

async function checkDependencies() {
  const deps = { ollama: false, python: false, ollamaRunning: false, cinderModel: false };

  // Check Python3
  const pyResult = await runCmd('python3', ['--version'], 5000);
  deps.python = pyResult.ok;

  // Check Ollama binary
  const ollamaResult = await runCmd('ollama', ['--version'], 5000);
  deps.ollama = ollamaResult.ok || ollamaResult.stdout.includes('ollama');

  // Check Ollama API is responding
  if (deps.ollama) {
    try {
      const data = await httpGet(`${OLLAMA_BASE}/api/tags`);
      const parsed = JSON.parse(data);
      deps.ollamaRunning = true;
      deps.cinderModel = (parsed.models || []).some(m => m.name.startsWith('cinder'));
    } catch {
      deps.ollamaRunning = false;
    }
  }

  return deps;
}

ipcMain.handle('deps:check', async () => {
  return checkDependencies();
});

app.whenReady().then(async () => {
  await initSession();
  createWindow();
});

app.on('before-quit', () => { app.isQuitting = true; });

app.on('activate', () => {
  if (mainWindow) mainWindow.show();
});

// ── Auth IPC ───────────────────────────────────────────────

ipcMain.handle('auth:setup', async (event, { password, loadMain }) => {
  setPassword(password);
  // If loadMain is true or not specified and no vault flow, go to main page
  // When vault is available, setup.html handles the transition after vault init
  if (loadMain !== false) {
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  }
  return { ok: true };
});

// Explicit navigation to main page (called by setup.html after vault init)
ipcMain.handle('auth:goMain', async () => {
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  return { ok: true };
});

ipcMain.handle('auth:login', async (event, { password }) => {
  if (checkPassword(password)) {
    // Attempt vault mount in background (don't block login)
    findVaultPartition().then(device => {
      if (device) {
        mountVault(password, device).catch(() => {});
      }
    }).catch(() => {});
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
    return { ok: true };
  }
  return { ok: false, error: 'Wrong password' };
});

ipcMain.handle('auth:isFirstRun', async () => isFirstRun());

ipcMain.handle('auth:changePassword', async (event, { currentPassword, newPassword }) => {
  if (!checkPassword(currentPassword)) {
    return { ok: false, error: 'Current password is incorrect' };
  }
  setPassword(newPassword);
  return { ok: true };
});

// ── Ollama API Bridge ──────────────────────────────────────

// Check if Ollama is running
ipcMain.handle('ollama:check', async () => {
  try {
    const data = await httpGet(`${OLLAMA_BASE}/api/tags`);
    const parsed = JSON.parse(data);
    const models = parsed.models || [];
    const hasCinder = models.some(m => m.name.startsWith('cinder'));
    return { running: true, models: models.map(m => m.name), hasCinder };
  } catch {
    return { running: false, models: [], hasCinder: false };
  }
});

// Send message to Cinder via Ollama streaming API
ipcMain.handle('ollama:chat', async (event, { model, messages }) => {
  return new Promise((resolve, reject) => {
    const payload = JSON.stringify({
      model: model || 'cinder',
      messages,
      stream: false
    });

    const req = http.request(`${OLLAMA_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }, (res) => {
      let body = '';
      res.on('data', chunk => { body += chunk; });
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body);
          resolve({ content: parsed.message?.content || '', error: null });
        } catch (e) {
          resolve({ content: '', error: 'Failed to parse Ollama response' });
        }
      });
    });

    req.on('error', (e) => {
      resolve({ content: '', error: `Ollama connection failed: ${e.message}` });
    });

    req.setTimeout(120000, () => {
      req.destroy();
      resolve({ content: '', error: 'Request timed out (120s)' });
    });

    req.write(payload);
    req.end();
  });
});

// Stream chat (sends chunks back to renderer)
ipcMain.handle('ollama:stream', async (event, { model, messages }) => {
  return new Promise((resolve) => {
    const payload = JSON.stringify({
      model: model || 'cinder',
      messages,
      stream: true
    });

    let fullContent = '';

    const req = http.request(`${OLLAMA_BASE}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }, (res) => {
      res.on('data', chunk => {
        const lines = chunk.toString().split('\n').filter(Boolean);
        for (const line of lines) {
          try {
            const parsed = JSON.parse(line);
            if (parsed.message?.content) {
              fullContent += parsed.message.content;
              mainWindow.webContents.send('ollama:chunk', parsed.message.content);
            }
            if (parsed.done) {
              mainWindow.webContents.send('ollama:done');
            }
          } catch {}
        }
      });
      res.on('end', () => resolve({ content: fullContent, error: null }));
    });

    req.on('error', (e) => {
      resolve({ content: '', error: `Ollama connection failed: ${e.message}` });
    });

    req.setTimeout(120000, () => {
      req.destroy();
      resolve({ content: '', error: 'Request timed out' });
    });

    req.write(payload);
    req.end();
  });
});

// ── Memory System (SQLite via cinder_memory.py) ──────────────
// All memory operations route through the Python backend for
// portable, searchable, persistent storage on USB.

const { execFile } = require('child_process');
const MEMORY_SCRIPT = path.join(__dirname, 'scripts', 'cinder_memory.py');
let currentSessionId = null;

function memoryCmd(args, timeout = 10000) {
  return new Promise((resolve) => {
    execFile('python3', [MEMORY_SCRIPT, '--json', ...args], {
      timeout,
      cwd: __dirname
    }, (err, stdout, stderr) => {
      if (err) {
        resolve({ error: err.message || stderr });
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim()));
      } catch (e) {
        resolve({ error: `Parse error: ${e.message}`, raw: stdout });
      }
    });
  });
}

// Create a new session on app start
async function initSession() {
  const result = await memoryCmd(['new-session']);
  if (result.session_id) {
    currentSessionId = result.session_id;
  }
  return currentSessionId;
}

// Save a conversation message to the current session
ipcMain.handle('memory:save', async (event, { role, content }) => {
  if (!currentSessionId) await initSession();
  const args = ['save', role, content];
  if (currentSessionId) args.push(currentSessionId);
  return memoryCmd(args);
});

// Load recent messages (optionally for a specific session)
ipcMain.handle('memory:load', async (event, opts = {}) => {
  const args = ['load'];
  if (opts.limit) args.push('--limit', String(opts.limit));
  if (opts.session) args.push('--session', opts.session);
  else if (currentSessionId) args.push('--session', currentSessionId);
  return memoryCmd(args);
});

// Load all messages across sessions (for history panel)
ipcMain.handle('memory:loadAll', async (event, { limit } = {}) => {
  const args = ['load', '--limit', String(limit || 50)];
  return memoryCmd(args);
});

// Search conversations and memories via TF-IDF
ipcMain.handle('memory:search', async (event, { query }) => {
  const recallScript = path.join(__dirname, 'scripts', 'memory-recall.py');
  if (fs.existsSync(recallScript)) {
    return new Promise((resolve) => {
      execFile('python3', [recallScript, '--json', query], {
        timeout: 10000,
        cwd: __dirname
      }, (err, stdout) => {
        if (!err && stdout) {
          try {
            resolve({ results: JSON.parse(stdout), source: 'sqlite' });
            return;
          } catch {}
        }
        resolve({ results: [], source: 'error' });
      });
    });
  }
  return { results: [], source: 'none' };
});

// Save a named memory (fact, preference, event, insight)
ipcMain.handle('memory:remember', async (event, { type, content }) => {
  return memoryCmd(['remember', type || 'fact', content]);
});

// Get session list
ipcMain.handle('memory:sessions', async () => {
  return memoryCmd(['sessions']);
});

// Create a new conversation session (distills previous session first)
ipcMain.handle('memory:newSession', async () => {
  // Auto-distill the previous session before starting a new one
  if (currentSessionId) {
    memoryCmd(['distill', currentSessionId]).catch(() => {});
  }
  const result = await memoryCmd(['new-session']);
  if (result.session_id) currentSessionId = result.session_id;
  return result;
});

// Get current session ID
ipcMain.handle('memory:currentSession', async () => {
  if (!currentSessionId) await initSession();
  return { session_id: currentSessionId };
});

// Get memory stats
ipcMain.handle('memory:stats', async () => {
  return memoryCmd(['stats']);
});

// Distill a session into long-term memories
ipcMain.handle('memory:distill', async (event, { session } = {}) => {
  const args = ['distill'];
  if (session) args.push(session);
  return memoryCmd(args);
});

// Rebuild search index
ipcMain.handle('memory:buildIndex', async () => {
  return memoryCmd(['build-index'], 30000);
});

// Recall relevant memories for context injection
ipcMain.handle('memory:recall', async (event, { query } = {}) => {
  const args = ['recall'];
  if (query) args.push(query);
  return memoryCmd(args);
});

// ── VeraCrypt Vault Management ────────────────────────────
// Handles the CINDER-VAULT partition: detect, init, mount, unmount.
// Same password as app login — one password for everything.

const os = require('os');

function getVeraCryptBin() {
  const platform = os.platform();
  if (platform === 'win32') return 'C:\\Program Files\\VeraCrypt\\VeraCrypt.exe';
  if (platform === 'darwin') return '/Applications/VeraCrypt.app/Contents/MacOS/VeraCrypt';
  return 'veracrypt'; // Linux — assumed in PATH
}

function runCmd(cmd, args, timeout = 30000) {
  return new Promise((resolve) => {
    execFile(cmd, args, { timeout }, (err, stdout, stderr) => {
      resolve({ ok: !err, stdout: (stdout || '').trim(), stderr: (stderr || '').trim(), code: err?.code });
    });
  });
}

// Check if VeraCrypt is installed
async function veracryptInstalled() {
  const bin = getVeraCryptBin();
  const result = await runCmd(bin, ['--text', '--version'], 5000);
  return result.ok || result.stdout.includes('VeraCrypt');
}

// Find the CINDER-VAULT partition/device
async function findVaultPartition() {
  const platform = os.platform();

  if (platform === 'linux') {
    // Use lsblk to find partition labeled CINDER-VAULT or by partition name
    const result = await runCmd('lsblk', ['-nrpo', 'NAME,PARTLABEL,LABEL,SIZE,TYPE'], 5000);
    if (result.ok) {
      for (const line of result.stdout.split('\n')) {
        if (line.includes('CINDER-VAULT')) {
          return line.split(' ')[0]; // /dev/sdX2
        }
      }
    }
    // Fallback: check if USB app is running from a partition, vault is next partition
    const appDrive = path.parse(__dirname).root;
    if (appDrive && appDrive !== '/') {
      const mountResult = await runCmd('findmnt', ['-n', '-o', 'SOURCE', appDrive], 5000);
      if (mountResult.ok) {
        const src = mountResult.stdout; // e.g., /dev/sdb1
        const match = src.match(/^(\/dev\/\w+?)(\d+)$/);
        if (match) {
          const vaultDev = `${match[1]}${parseInt(match[2]) + 1}`;
          return vaultDev; // e.g., /dev/sdb2
        }
      }
    }
  } else if (platform === 'darwin') {
    const result = await runCmd('diskutil', ['list', '-plist'], 5000);
    if (result.ok && result.stdout.includes('CINDER-VAULT')) {
      // Parse diskutil output for the vault partition
      const lines = result.stdout.split('\n');
      for (let i = 0; i < lines.length; i++) {
        if (lines[i].includes('CINDER-VAULT') && i > 0) {
          const devMatch = lines.slice(Math.max(0, i - 5), i + 5).join('\n').match(/disk\d+s\d+/);
          if (devMatch) return `/dev/${devMatch[0]}`;
        }
      }
    }
  } else if (platform === 'win32') {
    // On Windows, look for a raw/unformatted partition via diskpart or wmic
    // VeraCrypt can mount by partition number — use volume file instead
    const vaultFile = path.join(path.dirname(__dirname), 'vault.hc');
    if (fs.existsSync(vaultFile)) return vaultFile;
    // Also check for the vault container on the same drive as the app
    const appDrive = path.parse(__dirname).root; // e.g., D:\
    const altVault = path.join(appDrive, 'vault.hc');
    if (fs.existsSync(altVault)) return altVault;
  }

  // Last resort: check for vault container file next to app
  const containerFile = path.join(path.dirname(__dirname), 'vault.hc');
  if (fs.existsSync(containerFile)) return containerFile;

  return null;
}

// Get vault mount point
function getVaultMountPoint() {
  const platform = os.platform();
  if (platform === 'win32') return 'V:'; // V for Vault
  const mountDir = path.join(os.tmpdir(), 'cinder-vault');
  if (!fs.existsSync(mountDir)) fs.mkdirSync(mountDir, { recursive: true });
  return mountDir;
}

// Check if vault is currently mounted
async function isVaultMounted() {
  const bin = getVeraCryptBin();
  const result = await runCmd(bin, ['--text', '--list'], 5000);
  if (result.ok && result.stdout) {
    return result.stdout.includes('CINDER-VAULT') || result.stdout.includes('cinder-vault') || result.stdout.includes('vault.hc');
  }
  // Also check mount point directly
  const mountPoint = getVaultMountPoint();
  if (os.platform() !== 'win32') {
    return fs.existsSync(mountPoint) && fs.readdirSync(mountPoint).length > 0;
  }
  return false;
}

// Initialize vault (first time — creates VeraCrypt volume)
async function initVault(password, device) {
  const bin = getVeraCryptBin();
  const args = [
    '--text', '--create', device,
    '--volume-type', 'normal',
    '--encryption', 'AES',
    '--hash', 'SHA-512',
    '--filesystem', 'exFAT',
    '--password', password,
    '--pim', '0',
    '--keyfiles', '',
    '--random-source', os.platform() === 'win32' ? '' : '/dev/urandom',
    '--non-interactive'
  ];
  // Remove empty args
  const filteredArgs = args.filter(a => a !== '');
  return runCmd(bin, filteredArgs, 120000); // 2 min timeout for creation
}

// Mount vault
async function mountVault(password, device) {
  const bin = getVeraCryptBin();
  const mountPoint = getVaultMountPoint();
  const args = [
    '--text', '--mount', device, mountPoint,
    '--password', password,
    '--pim', '0',
    '--keyfiles', '',
    '--non-interactive',
    '--protect-hidden', 'no'
  ];
  return runCmd(bin, args, 30000);
}

// Dismount vault
async function dismountVault() {
  const bin = getVeraCryptBin();
  const mountPoint = getVaultMountPoint();
  return runCmd(bin, ['--text', '--dismount', mountPoint, '--non-interactive'], 15000);
}

// ── Vault IPC Handlers ────────────────────────────────────

ipcMain.handle('vault:status', async () => {
  const installed = await veracryptInstalled();
  if (!installed) return { available: false, reason: 'VeraCrypt not installed' };
  const device = await findVaultPartition();
  const mounted = device ? await isVaultMounted() : false;
  return {
    available: true,
    device: device || null,
    mounted,
    mountPoint: mounted ? getVaultMountPoint() : null
  };
});

ipcMain.handle('vault:init', async (event, { password }) => {
  const installed = await veracryptInstalled();
  if (!installed) return { ok: false, error: 'VeraCrypt not installed. Download from veracrypt.fr' };
  const device = await findVaultPartition();
  if (!device) return { ok: false, error: 'CINDER-VAULT partition not found. Is this running from the Cinder USB?' };
  const result = await initVault(password, device);
  if (!result.ok) return { ok: false, error: result.stderr || 'Vault creation failed' };
  // Mount immediately after creation
  const mountResult = await mountVault(password, device);
  return { ok: mountResult.ok, error: mountResult.ok ? null : mountResult.stderr, mountPoint: getVaultMountPoint() };
});

ipcMain.handle('vault:mount', async (event, { password }) => {
  const installed = await veracryptInstalled();
  if (!installed) return { ok: false, error: 'VeraCrypt not installed' };
  const already = await isVaultMounted();
  if (already) return { ok: true, mountPoint: getVaultMountPoint(), alreadyMounted: true };
  const device = await findVaultPartition();
  if (!device) return { ok: false, error: 'CINDER-VAULT partition not found' };
  const result = await mountVault(password, device);
  return { ok: result.ok, error: result.ok ? null : result.stderr, mountPoint: getVaultMountPoint() };
});

ipcMain.handle('vault:dismount', async () => {
  const result = await dismountVault();
  return { ok: result.ok, error: result.ok ? null : result.stderr };
});

// Auto-dismount vault on app quit
app.on('before-quit', async () => {
  app.isQuitting = true;
  try { await dismountVault(); } catch {}
});

// ── XP / Evolution System ─────────────────────────────────
// Cinder gains XP through use. Evolution milestones trigger
// Pokemon-style animations. Prestige resets at level 100.

const XP_FILE = path.join(DATA_DIR, 'xp.json');

// Evolution milestone levels — these trigger the big popup
const EVOLUTION_MILESTONES = [1, 5, 10, 15, 25, 50, 60, 70, 80, 90, 100];

// Evolution names for each milestone tier
const EVOLUTION_NAMES = {
  1:   'Spark',
  5:   'Kindling',
  10:  'Flicker',
  15:  'Blaze',
  25:  'Furnace',
  50:  'Inferno',
  60:  'Radiant',
  70:  'Solar',
  80:  'Nova',
  90:  'Stellar',
  100: 'Gold Cinder'
};

function loadXP() {
  ensureDataDir();
  if (fs.existsSync(XP_FILE)) {
    try {
      return JSON.parse(fs.readFileSync(XP_FILE, 'utf8'));
    } catch { /* fall through */ }
  }
  return { totalXP: 0, level: 0, prestige: 0, evolutionsSeen: [], lastDaily: null };
}

function saveXP(data) {
  ensureDataDir();
  fs.writeFileSync(XP_FILE, JSON.stringify(data, null, 2), 'utf8');
}

function xpForLevel(lvl) {
  // Quadratic scaling: level N requires N*N*50 total XP
  return lvl * lvl * 50;
}

function levelFromXP(totalXP) {
  return Math.floor(Math.sqrt(totalXP / 50));
}

function addXP(amount, source) {
  const data = loadXP();
  const oldLevel = data.level;
  data.totalXP += amount;
  data.level = levelFromXP(data.totalXP);

  // Cap at 100 per prestige cycle
  if (data.level > 100) data.level = 100;

  // Check for new evolution milestone
  let newEvolution = null;
  for (const milestone of EVOLUTION_MILESTONES) {
    if (data.level >= milestone && oldLevel < milestone && !data.evolutionsSeen.includes(milestone)) {
      data.evolutionsSeen.push(milestone);
      newEvolution = { level: milestone, name: EVOLUTION_NAMES[milestone] };
      break; // One at a time
    }
  }

  // Daily bonus — once per calendar day
  const today = new Date().toISOString().slice(0, 10);
  let dailyBonus = false;
  if (data.lastDaily !== today) {
    data.totalXP += 50;
    data.lastDaily = today;
    dailyBonus = true;
    data.level = levelFromXP(data.totalXP);
    if (data.level > 100) data.level = 100;
  }

  saveXP(data);

  return {
    totalXP: data.totalXP,
    level: data.level,
    prestige: data.prestige,
    xpGained: amount + (dailyBonus ? 50 : 0),
    source,
    dailyBonus,
    newEvolution,
    nextLevel: data.level < 100 ? data.level + 1 : null,
    xpToNext: data.level < 100 ? xpForLevel(data.level + 1) - data.totalXP : 0,
    currentEvolution: getEvolutionName(data.level)
  };
}

function getEvolutionName(level) {
  let name = 'Ember';
  for (const milestone of EVOLUTION_MILESTONES) {
    if (level >= milestone) name = EVOLUTION_NAMES[milestone];
  }
  return name;
}

// IPC: Get current XP state
ipcMain.handle('xp:get', async () => {
  const data = loadXP();
  return {
    totalXP: data.totalXP,
    level: data.level,
    prestige: data.prestige,
    evolutionsSeen: data.evolutionsSeen,
    currentEvolution: getEvolutionName(data.level),
    nextLevel: data.level < 100 ? data.level + 1 : null,
    xpToNext: data.level < 100 ? xpForLevel(data.level + 1) - data.totalXP : 0,
    xpForNext: data.level < 100 ? xpForLevel(data.level + 1) : 0,
    canPrestige: data.level >= 100 || data.evolutionsSeen.length >= 10
  };
});

// IPC: Award XP (called by renderer after actions)
ipcMain.handle('xp:add', async (event, { amount, source }) => {
  const result = addXP(amount, source);
  // Notify renderer of evolution if one happened
  if (result.newEvolution && mainWindow) {
    mainWindow.webContents.send('xp:evolution', result.newEvolution);
  }
  return result;
});

// IPC: Prestige reset
ipcMain.handle('xp:prestige', async () => {
  const data = loadXP();
  if (data.level < 100 && data.evolutionsSeen.length < 10) {
    return { ok: false, error: 'Not ready for prestige' };
  }
  data.prestige += 1;
  data.totalXP = 0;
  data.level = 0;
  data.evolutionsSeen = [];
  saveXP(data);
  return {
    ok: true,
    prestige: data.prestige,
    message: `Prestige ${data.prestige}! Cinder resets, wiser than before.`
  };
});

// IPC: Lock in Gold Cinder (no more resets)
ipcMain.handle('xp:lockGold', async () => {
  const data = loadXP();
  if (data.level < 100) return { ok: false, error: 'Must reach level 100 first' };
  data.goldLocked = true;
  saveXP(data);
  return { ok: true, message: 'Gold Cinder locked in. No more resets.' };
});

// ── Utilities ──────────────────────────────────────────────

function httpGet(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}
