const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

let sharp;
try {
  sharp = require('sharp');
} catch (e) {
  console.warn('Sharp not available — photo processing will be limited');
  sharp = null;
}

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'Marketplace Lister',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => app.quit());

// Photo selection dialog
ipcMain.handle('select-photos', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: 'Images', extensions: ['jpg', 'jpeg', 'png', 'webp', 'bmp'] }
    ]
  });
  if (result.canceled) return [];
  return result.filePaths;
});

// Process a single photo: auto-enhance, resize, crop
ipcMain.handle('process-photo', async (event, filePath, options) => {
  // If sharp isn't available, just return the original with a basic preview
  if (!sharp) {
    return {
      originalPath: filePath,
      processedPath: filePath,
      preview: `file://${filePath}`,
      width: 0,
      height: 0,
      noSharp: true
    };
  }
  try {
    const metadata = await sharp(filePath).metadata();
    let pipeline = sharp(filePath);

    // Auto-rotate based on EXIF
    pipeline = pipeline.rotate();

    // Normalize/enhance: slight contrast + saturation boost
    if (options.enhance) {
      pipeline = pipeline.modulate({
        brightness: 1.05,
        saturation: 1.1
      }).sharpen({ sigma: 1.0 });
    }

    // Remove background noise with slight blur on edges (optional)
    // Resize to FB Marketplace optimal: 1200x1200 max, maintain aspect
    const maxDim = 1200;
    if (metadata.width > maxDim || metadata.height > maxDim) {
      pipeline = pipeline.resize(maxDim, maxDim, {
        fit: 'inside',
        withoutEnlargement: true
      });
    }

    // Square crop if requested
    if (options.squareCrop) {
      const size = Math.min(metadata.width, metadata.height, maxDim);
      pipeline = pipeline.resize(size, size, { fit: 'cover', position: 'centre' });
    }

    // Output as JPEG with good quality
    const outputDir = path.join(app.getPath('temp'), 'marketplace-lister');
    if (!fs.existsSync(outputDir)) fs.mkdirSync(outputDir, { recursive: true });

    const outputName = `processed_${Date.now()}_${path.basename(filePath, path.extname(filePath))}.jpg`;
    const outputPath = path.join(outputDir, outputName);

    await pipeline.jpeg({ quality: 90 }).toFile(outputPath);

    // Get base64 for preview
    const previewBuffer = await sharp(outputPath)
      .resize(300, 300, { fit: 'inside' })
      .jpeg({ quality: 70 })
      .toBuffer();

    return {
      originalPath: filePath,
      processedPath: outputPath,
      preview: `data:image/jpeg;base64,${previewBuffer.toString('base64')}`,
      width: metadata.width,
      height: metadata.height
    };
  } catch (err) {
    return { error: err.message, originalPath: filePath };
  }
});

// Save processed photos to a chosen folder
ipcMain.handle('save-photos', async (event, processedPaths) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory', 'createDirectory'],
    title: 'Save processed photos to...'
  });
  if (result.canceled) return { saved: false };

  const destDir = result.filePaths[0];
  const savedFiles = [];
  for (const src of processedPaths) {
    const dest = path.join(destDir, path.basename(src));
    fs.copyFileSync(src, dest);
    savedFiles.push(dest);
  }
  return { saved: true, files: savedFiles };
});

// Copy text to clipboard
ipcMain.handle('copy-to-clipboard', async (event, text) => {
  const { clipboard } = require('electron');
  clipboard.writeText(text);
  return true;
});

// Check if Ollama is available
ipcMain.handle('check-ollama', async () => {
  try {
    const http = require('http');
    return new Promise((resolve) => {
      const req = http.get('http://localhost:11434/api/tags', { timeout: 3000 }, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            const parsed = JSON.parse(data);
            const models = (parsed.models || []).map(m => m.name);
            resolve({ available: true, models });
          } catch { resolve({ available: false, models: [] }); }
        });
      });
      req.on('error', () => resolve({ available: false, models: [] }));
      req.on('timeout', () => { req.destroy(); resolve({ available: false, models: [] }); });
    });
  } catch { return { available: false, models: [] }; }
});

// AI-generate a listing description via Ollama
ipcMain.handle('ai-generate', async (event, details) => {
  const { itemName, category, condition, price, description, features } = details;
  const http = require('http');

  const prompt = `Write a Facebook Marketplace listing for this item. Be concise, compelling, and honest. No emojis. No hashtags. Include a short title (under 80 chars) and a description (under 200 words).

Item: ${itemName}
Category: ${category || 'General'}
Condition: ${condition || 'Good'}
Price: ${price ? '$' + price : 'Not set'}
Notes: ${description || 'None'}
Features: ${features && features.length > 0 ? features.join(', ') : 'None listed'}
Location: Calgary, AB

Format your response EXACTLY like this:
TITLE: [your title here]
DESCRIPTION:
[your description here]`;

  const body = JSON.stringify({
    model: 'qwen2.5:14b',
    prompt,
    stream: false,
    options: { temperature: 0.7, num_predict: 400 }
  });

  return new Promise((resolve) => {
    const req = http.request({
      hostname: 'localhost', port: 11434, path: '/api/generate',
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      timeout: 60000
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          const response = parsed.response || '';
          // Parse TITLE: and DESCRIPTION: from response
          const titleMatch = response.match(/TITLE:\s*(.+)/i);
          const descMatch = response.match(/DESCRIPTION:\s*([\s\S]+)/i);
          resolve({
            success: true,
            title: titleMatch ? titleMatch[1].trim() : itemName,
            body: descMatch ? descMatch[1].trim() : response.trim()
          });
        } catch {
          resolve({ success: false, error: 'Failed to parse AI response' });
        }
      });
    });
    req.on('error', () => resolve({ success: false, error: 'Ollama not reachable' }));
    req.on('timeout', () => { req.destroy(); resolve({ success: false, error: 'AI generation timed out' }); });
    req.write(body);
    req.end();
  });
});

// Vision-based photo analysis — auto-identify item from photo
ipcMain.handle('ai-vision-analyze', async (event, imagePath) => {
  const http = require('http');

  // Read image and convert to base64
  let imageBase64;
  try {
    const imageBuffer = fs.readFileSync(imagePath);
    imageBase64 = imageBuffer.toString('base64');
  } catch (err) {
    return { success: false, error: `Cannot read image: ${err.message}` };
  }

  const body = JSON.stringify({
    model: 'moondream:1.8b',
    messages: [{
      role: 'user',
      content: 'What is this item? Describe it for a marketplace listing. Include: product name, brand if visible, condition, color, material, key features. Be concise and factual.',
      images: [imageBase64]
    }],
    stream: false,
    options: { temperature: 0.3, num_predict: 300 }
  });

  return new Promise((resolve) => {
    const req = http.request({
      hostname: 'localhost', port: 11434, path: '/api/chat',
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      timeout: 120000
    }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(data);
          const response = parsed.message?.content || '';
          resolve({ success: true, analysis: response.trim() });
        } catch {
          resolve({ success: false, error: 'Failed to parse vision response' });
        }
      });
    });
    req.on('error', () => resolve({ success: false, error: 'Ollama not reachable' }));
    req.on('timeout', () => { req.destroy(); resolve({ success: false, error: 'Vision analysis timed out' }); });
    req.write(body);
    req.end();
  });
});

// Generate listing text from item details (template-based fallback)
ipcMain.handle('generate-listing', async (event, details) => {
  const { itemName, category, condition, price, description, features } = details;

  const conditionMap = {
    'new': 'Brand New',
    'like-new': 'Like New',
    'good': 'Good Condition',
    'fair': 'Fair Condition',
    'for-parts': 'For Parts/Not Working'
  };

  const conditionText = conditionMap[condition] || condition;

  let title = itemName;
  if (conditionText && condition !== 'new') {
    title += ` — ${conditionText}`;
  }

  let body = '';
  if (description) {
    body += description + '\n\n';
  }

  if (features && features.length > 0) {
    body += 'Details:\n';
    for (const f of features) {
      body += `• ${f}\n`;
    }
    body += '\n';
  }

  body += `Condition: ${conditionText}\n`;

  if (price) {
    body += `Price: $${price}\n`;
  }

  body += '\nPickup in Calgary. Cash or e-transfer.\n';
  body += 'Message me if interested — serious buyers only.\n';

  return { title, body, price };
});
