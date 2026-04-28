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
    backgroundColor: '#e4d8c8',
    frame: true,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  // Start maximized — Joel: "cinder app needs to launch as a maximized window"
  mainWindow.maximize();

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
  // Detect python first, then create window immediately
  // Don't let session init block the window from appearing
  await detectPython();
  createWindow();
  // Initialize session in background — non-blocking
  initSession().catch(() => {});
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
let pythonBin = null; // Detected at startup

// Detect python binary — python3 on Linux/Mac, python or py on Windows
async function detectPython() {
  if (pythonBin) return pythonBin;
  const candidates = os.platform() === 'win32'
    ? ['python', 'py', 'python3']
    : ['python3', 'python'];
  for (const cmd of candidates) {
    const result = await runCmd(cmd, ['--version'], 3000);
    if (result.ok && result.stdout.includes('Python')) {
      pythonBin = cmd;
      return pythonBin;
    }
  }
  return null;
}

function memoryCmd(args, timeout = 10000) {
  return new Promise(async (resolve) => {
    const py = pythonBin || await detectPython();
    if (!py) {
      resolve({ error: 'Python not found. Memory features require Python.' });
      return;
    }
    execFile(py, [MEMORY_SCRIPT, '--json', ...args], {
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
    return new Promise(async (resolve) => {
      const py = pythonBin || await detectPython();
      if (!py) { resolve({ results: [], source: 'no-python' }); return; }
      execFile(py, [recallScript, '--json', query], {
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

// ── Software Vault (AES-256-GCM) ─────────────────────────
// Encrypted file vault using Node.js crypto. No external tools needed.
// Same password as app login — one key for everything.
// Files stored as encrypted blobs in vault/ directory on USB.

const os = require('os');

const VAULT_DIR = path.join(path.dirname(__dirname), 'vault');
const VAULT_META = path.join(VAULT_DIR, '.vault-meta');
const VAULT_ALGO = 'aes-256-gcm';
const VAULT_SALT_LEN = 32;
const VAULT_IV_LEN = 16;
const VAULT_TAG_LEN = 16;
const VAULT_KEY_LEN = 32;

let _vaultKey = null; // Derived key, held in memory while vault is "mounted"
let _vaultMountDir = null; // Temp directory for decrypted files

function deriveVaultKey(password, salt) {
  return crypto.scryptSync(password, salt, VAULT_KEY_LEN);
}

function encryptBuffer(buf, key) {
  const iv = crypto.randomBytes(VAULT_IV_LEN);
  const cipher = crypto.createCipheriv(VAULT_ALGO, key, iv);
  const encrypted = Buffer.concat([cipher.update(buf), cipher.final()]);
  const tag = cipher.getAuthTag();
  // Format: [salt is stored separately] [16-byte IV][16-byte tag][encrypted data]
  return Buffer.concat([iv, tag, encrypted]);
}

function decryptBuffer(buf, key) {
  const iv = buf.subarray(0, VAULT_IV_LEN);
  const tag = buf.subarray(VAULT_IV_LEN, VAULT_IV_LEN + VAULT_TAG_LEN);
  const data = buf.subarray(VAULT_IV_LEN + VAULT_TAG_LEN);
  const decipher = crypto.createDecipheriv(VAULT_ALGO, key, iv);
  decipher.setAuthTag(tag);
  return Buffer.concat([decipher.update(data), decipher.final()]);
}

function vaultExists() {
  return fs.existsSync(VAULT_DIR) && fs.existsSync(VAULT_META);
}

function isVaultMounted() {
  return _vaultKey !== null && _vaultMountDir !== null;
}

function getVaultMountPoint() {
  if (_vaultMountDir) return _vaultMountDir;
  const dir = path.join(os.tmpdir(), 'cinder-vault-' + process.pid);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return dir;
}

// Initialize vault — creates vault directory and meta file
function initVault(password) {
  if (!fs.existsSync(VAULT_DIR)) fs.mkdirSync(VAULT_DIR, { recursive: true });
  const salt = crypto.randomBytes(VAULT_SALT_LEN);
  const key = deriveVaultKey(password, salt);
  // Store salt and a verification token
  const verifyToken = crypto.randomBytes(32);
  const encryptedToken = encryptBuffer(verifyToken, key);
  const meta = {
    version: 1,
    salt: salt.toString('hex'),
    verify: encryptedToken.toString('hex'),
    verifyPlain: verifyToken.toString('hex'),
    created: new Date().toISOString()
  };
  fs.writeFileSync(VAULT_META, JSON.stringify(meta, null, 2));
  return { ok: true, salt };
}

// Verify password against vault
function verifyVaultPassword(password) {
  if (!vaultExists()) return false;
  try {
    const meta = JSON.parse(fs.readFileSync(VAULT_META, 'utf8'));
    const salt = Buffer.from(meta.salt, 'hex');
    const key = deriveVaultKey(password, salt);
    const encToken = Buffer.from(meta.verify, 'hex');
    const decrypted = decryptBuffer(encToken, key);
    return decrypted.toString('hex') === meta.verifyPlain;
  } catch {
    return false;
  }
}

// Mount vault — derive key, decrypt files to temp
function mountVault(password) {
  if (!vaultExists()) return { ok: false, error: 'Vault not initialized' };
  if (!verifyVaultPassword(password)) return { ok: false, error: 'Wrong vault password' };

  const meta = JSON.parse(fs.readFileSync(VAULT_META, 'utf8'));
  const salt = Buffer.from(meta.salt, 'hex');
  _vaultKey = deriveVaultKey(password, salt);
  _vaultMountDir = getVaultMountPoint();

  // Decrypt all vault files to temp
  const files = fs.readdirSync(VAULT_DIR).filter(f => f.endsWith('.enc'));
  for (const encFile of files) {
    try {
      const encData = fs.readFileSync(path.join(VAULT_DIR, encFile));
      const decData = decryptBuffer(encData, _vaultKey);
      const originalName = encFile.replace(/\.enc$/, '');
      fs.writeFileSync(path.join(_vaultMountDir, originalName), decData);
    } catch {
      // Skip corrupted files
    }
  }

  return { ok: true, mountPoint: _vaultMountDir };
}

// Dismount vault — wipe temp files, clear key
function dismountVault() {
  if (_vaultMountDir && fs.existsSync(_vaultMountDir)) {
    // Securely wipe temp files
    const files = fs.readdirSync(_vaultMountDir);
    for (const f of files) {
      const fp = path.join(_vaultMountDir, f);
      try {
        // Overwrite with random data before delete
        const size = fs.statSync(fp).size;
        if (size > 0) fs.writeFileSync(fp, crypto.randomBytes(size));
        fs.unlinkSync(fp);
      } catch {}
    }
    try { fs.rmdirSync(_vaultMountDir); } catch {}
  }
  _vaultKey = null;
  _vaultMountDir = null;
  return { ok: true };
}

// Add file to vault (encrypt and store)
function addToVault(filePath) {
  if (!_vaultKey) return { ok: false, error: 'Vault not unlocked' };
  const data = fs.readFileSync(filePath);
  const encrypted = encryptBuffer(data, _vaultKey);
  const name = path.basename(filePath) + '.enc';
  fs.writeFileSync(path.join(VAULT_DIR, name), encrypted);
  return { ok: true, name: path.basename(filePath) };
}

// List vault files
function listVaultFiles() {
  if (!fs.existsSync(VAULT_DIR)) return [];
  return fs.readdirSync(VAULT_DIR)
    .filter(f => f.endsWith('.enc'))
    .map(f => f.replace(/\.enc$/, ''));
}

// ── Vault IPC Handlers ────────────────────────────────────

ipcMain.handle('vault:status', async () => {
  const exists = vaultExists();
  const mounted = isVaultMounted();
  return {
    available: true, // Always available — no external tools needed
    device: exists ? VAULT_DIR : null,
    mounted,
    mountPoint: mounted ? _vaultMountDir : null,
    files: listVaultFiles()
  };
});

ipcMain.handle('vault:init', async (event, { password }) => {
  const result = initVault(password);
  if (!result.ok) return result;
  // Mount immediately after creation
  return mountVault(password);
});

ipcMain.handle('vault:mount', async (event, { password }) => {
  if (isVaultMounted()) return { ok: true, mountPoint: _vaultMountDir, alreadyMounted: true };
  return mountVault(password);
});

ipcMain.handle('vault:dismount', async () => {
  return dismountVault();
});

// Auto-dismount vault on app quit
app.on('before-quit', async () => {
  app.isQuitting = true;
  try { dismountVault(); } catch {}
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
