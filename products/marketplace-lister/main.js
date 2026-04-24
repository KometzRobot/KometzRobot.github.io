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
    width: 1280,
    height: 800,
    minWidth: 1000,
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
  const { itemName, category, condition, price, description, features, platform } = details;
  const http = require('http');

  const platformGuides = {
    facebook: 'Write a Facebook Marketplace listing. Be concise, casual, and honest. No emojis. No hashtags.',
    kijiji: 'Write a Kijiji listing. Be clear and descriptive. Include condition details. Canadian spelling.',
    ebay: 'Write an eBay listing. Be professional and detailed. Include item specifics, shipping info, and return policy mention.',
    craigslist: 'Write a Craigslist listing. Be brief and direct. Include the key facts only.'
  };

  const guide = platformGuides[platform] || platformGuides.facebook;

  const prompt = `${guide} Include a short title (under 80 chars) and a description (under 200 words).

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

// Smart Scan: vision analyze + auto-fill + generate listing in one shot
ipcMain.handle('smart-scan', async (event, imagePaths, platform) => {
  const http = require('http');

  // Step 1: Vision analysis on the first photo
  let imageBase64;
  try {
    const imageBuffer = fs.readFileSync(imagePaths[0]);
    imageBase64 = imageBuffer.toString('base64');
  } catch (err) {
    return { success: false, error: `Cannot read image: ${err.message}`, step: 'vision' };
  }

  const visionPrompt = `You are helping create a marketplace listing for this item. Look at the photo carefully and respond with ONLY the following format, no extra text:

ITEM_NAME: [what it is, include brand if visible]
CATEGORY: [one of: electronics, furniture, clothing, home, sports, toys, auto, tools, collectibles, music, gaming, books, baby, appliances, other]
CONDITION: [one of: new, like-new, good, fair, for-parts]
SUGGESTED_PRICE: [estimated resale value in CAD, just the number]
FEATURES: [comma-separated list of 3-5 key selling points you can see]
DESCRIPTION: [one sentence about the item — what it is, what makes it worth buying]`;

  const visionBody = JSON.stringify({
    model: 'moondream:1.8b',
    messages: [{
      role: 'user',
      content: visionPrompt,
      images: [imageBase64]
    }],
    stream: false,
    options: { temperature: 0.3, num_predict: 400 }
  });

  const visionResult = await new Promise((resolve) => {
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
          resolve({ success: true, text: (parsed.message?.content || '').trim() });
        } catch {
          resolve({ success: false, error: 'Failed to parse vision response' });
        }
      });
    });
    req.on('error', () => resolve({ success: false, error: 'Ollama not reachable' }));
    req.on('timeout', () => { req.destroy(); resolve({ success: false, error: 'Vision analysis timed out' }); });
    req.write(visionBody);
    req.end();
  });

  if (!visionResult.success) {
    return { success: false, error: visionResult.error, step: 'vision' };
  }

  // Parse structured vision output
  const visionText = visionResult.text;
  const parseField = (label) => {
    const match = visionText.match(new RegExp(`${label}:\\s*(.+?)(?:\\n|$)`, 'i'));
    return match ? match[1].trim() : '';
  };

  const scannedData = {
    itemName: parseField('ITEM_NAME') || 'Unknown Item',
    category: parseField('CATEGORY') || 'other',
    condition: parseField('CONDITION') || 'good',
    suggestedPrice: parseField('SUGGESTED_PRICE') || '',
    features: (parseField('FEATURES') || '').split(',').map(f => f.trim()).filter(Boolean),
    visionDescription: parseField('DESCRIPTION') || visionText
  };

  // Step 2: Generate a sales-optimized listing using text model
  const platformGuides = {
    facebook: 'Facebook Marketplace listing. Casual, honest, no emojis, no hashtags. Calgary pickup.',
    kijiji: 'Kijiji listing. Clear, descriptive. Canadian spelling. Calgary, AB.',
    ebay: 'eBay listing. Professional, detailed. Mention shipping and condition.',
    craigslist: 'Craigslist listing. Brief, direct, key facts only. Calgary.'
  };

  const guide = platformGuides[platform] || platformGuides.facebook;

  const genPrompt = `Write a ${guide}

The item has been identified from a photo:
Item: ${scannedData.itemName}
Category: ${scannedData.category}
Condition: ${scannedData.condition}
Price: $${scannedData.suggestedPrice || 'TBD'}
Key features: ${scannedData.features.join(', ') || 'See photo'}
Photo description: ${scannedData.visionDescription}

Write a listing that will SELL this item. Make the buyer want it. Be honest but highlight what makes it worth the price.

Format your response EXACTLY like this:
TITLE: [catchy title under 80 chars]
DESCRIPTION:
[compelling description, 50-150 words, emphasizes value and condition]
PRICE: [price as a number only]`;

  const genBody = JSON.stringify({
    model: 'qwen2.5:14b',
    prompt: genPrompt,
    stream: false,
    options: { temperature: 0.7, num_predict: 500 }
  });

  const genResult = await new Promise((resolve) => {
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
          resolve({ success: true, text: (parsed.response || '').trim() });
        } catch {
          resolve({ success: false, error: 'Failed to parse generation response' });
        }
      });
    });
    req.on('error', () => resolve({ success: false, error: 'Ollama not reachable for generation' }));
    req.on('timeout', () => { req.destroy(); resolve({ success: false, error: 'Listing generation timed out' }); });
    req.write(genBody);
    req.end();
  });

  if (!genResult.success) {
    // Return scanned data even if generation failed — user can still use the auto-filled fields
    return {
      success: true,
      scanned: scannedData,
      generated: null,
      warning: genResult.error
    };
  }

  // Parse generated listing
  const genText = genResult.text;
  const titleMatch = genText.match(/TITLE:\s*(.+)/i);
  const descMatch = genText.match(/DESCRIPTION:\s*([\s\S]+?)(?:PRICE:|$)/i);
  const priceMatch = genText.match(/PRICE:\s*\$?(\d+)/i);

  return {
    success: true,
    scanned: scannedData,
    generated: {
      title: titleMatch ? titleMatch[1].trim() : scannedData.itemName,
      body: descMatch ? descMatch[1].trim() : genText,
      price: priceMatch ? priceMatch[1] : scannedData.suggestedPrice
    }
  };
});

// Generate listing text from item details (smart template — no AI needed)
ipcMain.handle('generate-listing', async (event, details) => {
  const { itemName, category, condition, price, description, features, platform } = details;

  const conditionMap = {
    'new': 'Brand New',
    'like-new': 'Like New',
    'good': 'Good Condition',
    'fair': 'Fair — Priced Accordingly',
    'for-parts': 'For Parts / Repair'
  };

  const conditionText = conditionMap[condition] || condition;

  // Build a sales-optimized title based on platform
  let title = itemName;
  if (platform === 'facebook' || platform === 'kijiji') {
    // Short, punchy titles work best on FB/Kijiji
    if (condition === 'new') title += ' — Brand New';
    else if (condition === 'like-new') title += ' — Like New';
    if (price && parseFloat(price) > 0) title += ` — $${price}`;
  } else if (platform === 'ebay') {
    // eBay titles should be descriptive for search
    if (condition === 'new') title += ' NEW';
    if (category) {
      const catLabels = {
        electronics: '', furniture: '', clothing: '', home: '',
        sports: 'Sports', tools: 'Tools', auto: 'Auto',
        gaming: 'Gaming', collectibles: 'Collectible', music: 'Musical'
      };
      const label = catLabels[category];
      if (label) title = `${label} ${title}`;
    }
  }

  // Build body with sales psychology
  let body = '';

  // Opening hook — what it is and why it's worth buying
  if (description) {
    body += description + '\n\n';
  } else {
    // Auto-generate an opening if none provided
    const openers = {
      'new': `${itemName} — brand new, never used.`,
      'like-new': `${itemName} in excellent shape — barely used, looks and works like new.`,
      'good': `${itemName} in solid working condition. Well taken care of.`,
      'fair': `${itemName} — shows some wear but still fully functional. Priced to sell.`,
      'for-parts': `${itemName} — selling as-is for parts or repair. May be fixable.`
    };
    body += (openers[condition] || `${itemName} for sale.`) + '\n\n';
  }

  // Features section — formatted for easy scanning
  if (features && features.length > 0) {
    body += 'What You Get:\n';
    for (const f of features) {
      body += `  - ${f}\n`;
    }
    body += '\n';
  }

  // Condition details
  body += `Condition: ${conditionText}\n`;

  // Price justification hint
  if (price && parseFloat(price) > 0) {
    body += `Asking: $${price}`;
    if (condition === 'new' || condition === 'like-new') {
      body += ' (well below retail)\n';
    } else if (condition === 'fair' || condition === 'for-parts') {
      body += ' (priced to move)\n';
    } else {
      body += ' (firm / OBO)\n';
    }
  }

  // Platform-specific closing — each reads naturally for that marketplace
  const closings = {
    facebook: `\nPickup in Calgary. Cash or e-transfer.\nMessage if interested — I respond quickly.\nCheck my other listings too!`,
    kijiji: `\nPickup in Calgary, AB. Cash or e-transfer accepted.\nSerious inquiries please — include your offer when messaging.\nPriced to sell. Don't miss out.`,
    ebay: `\nShipping available — message for a quote to your location.\nReturns accepted within 14 days if not as described.\nPositive feedback appreciated.`,
    craigslist: `\nCalgary pickup only. Cash.\nText is preferred. Available evenings and weekends.`
  };

  body += closings[platform] || closings.facebook;

  return { title, body, price };
});
