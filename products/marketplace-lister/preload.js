const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  selectPhotos: () => ipcRenderer.invoke('select-photos'),
  processPhoto: (filePath, options) => ipcRenderer.invoke('process-photo', filePath, options),
  savePhotos: (processedPaths) => ipcRenderer.invoke('save-photos', processedPaths),
  copyToClipboard: (text) => ipcRenderer.invoke('copy-to-clipboard', text),
  generateListing: (details) => ipcRenderer.invoke('generate-listing', details),
  checkOllama: () => ipcRenderer.invoke('check-ollama'),
  aiGenerate: (details) => ipcRenderer.invoke('ai-generate', details),
  aiVisionAnalyze: (imagePath) => ipcRenderer.invoke('ai-vision-analyze', imagePath),
  smartScan: (imagePaths, platform) => ipcRenderer.invoke('smart-scan', imagePaths, platform)
});
