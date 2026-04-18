const { contextBridge, ipcRenderer } = require('electron');

// Expose safe API to renderer process
contextBridge.exposeInMainWorld('cinder', {
  // Auth
  setup: (password, loadMain) => ipcRenderer.invoke('auth:setup', { password, loadMain }),
  login: (password) => ipcRenderer.invoke('auth:login', { password }),
  isFirstRun: () => ipcRenderer.invoke('auth:isFirstRun'),
  goMain: () => ipcRenderer.invoke('auth:goMain'),
  changePassword: (currentPassword, newPassword) => ipcRenderer.invoke('auth:changePassword', { currentPassword, newPassword }),

  // Ollama
  checkOllama: () => ipcRenderer.invoke('ollama:check'),
  chat: (model, messages) => ipcRenderer.invoke('ollama:chat', { model, messages }),
  stream: (model, messages) => ipcRenderer.invoke('ollama:stream', { model, messages }),
  onChunk: (callback) => ipcRenderer.on('ollama:chunk', (_, chunk) => callback(chunk)),
  onDone: (callback) => ipcRenderer.on('ollama:done', () => callback()),

  // Memory — SQLite backend via cinder_memory.py
  saveMessage: (role, content) => ipcRenderer.invoke('memory:save', { role, content }),
  loadMessages: (opts) => ipcRenderer.invoke('memory:load', opts || {}),
  loadAllMessages: (limit) => ipcRenderer.invoke('memory:loadAll', { limit }),
  searchMemory: (query) => ipcRenderer.invoke('memory:search', { query }),
  remember: (type, content) => ipcRenderer.invoke('memory:remember', { type, content }),
  getSessions: () => ipcRenderer.invoke('memory:sessions'),
  newSession: () => ipcRenderer.invoke('memory:newSession'),
  currentSession: () => ipcRenderer.invoke('memory:currentSession'),
  getStats: () => ipcRenderer.invoke('memory:stats'),
  distillSession: (session) => ipcRenderer.invoke('memory:distill', { session }),
  buildIndex: () => ipcRenderer.invoke('memory:buildIndex'),
  recallMemories: (query) => ipcRenderer.invoke('memory:recall', { query }),

  // Vault — VeraCrypt encrypted partition management
  vaultStatus: () => ipcRenderer.invoke('vault:status'),
  vaultInit: (password) => ipcRenderer.invoke('vault:init', { password }),
  vaultMount: (password) => ipcRenderer.invoke('vault:mount', { password }),
  vaultDismount: () => ipcRenderer.invoke('vault:dismount'),

  // XP / Evolution system
  getXP: () => ipcRenderer.invoke('xp:get'),
  addXP: (amount, source) => ipcRenderer.invoke('xp:add', { amount, source }),
  prestige: () => ipcRenderer.invoke('xp:prestige'),
  lockGold: () => ipcRenderer.invoke('xp:lockGold'),
  onEvolution: (callback) => ipcRenderer.on('xp:evolution', (_, data) => callback(data)),

  // Legacy aliases (keep for backwards compat during transition)
  saveMemory: (role, content) => ipcRenderer.invoke('memory:save', { role, content }),
  loadMemory: () => ipcRenderer.invoke('memory:load', {})
});
