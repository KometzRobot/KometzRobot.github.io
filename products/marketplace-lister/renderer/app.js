// State
const state = {
  photos: [],
  previewIndex: 0,
  ollamaReady: false,
  hasVision: false,
  models: [],
};

// DOM refs
const photoGrid = document.getElementById('photo-grid');
const photoActions = document.getElementById('photo-actions');
const photoCount = document.getElementById('photo-count');
const smartScanSection = document.getElementById('smart-scan-section');
const scanStatus = document.getElementById('scan-status');
const scanStep = document.getElementById('scan-step');
const listingPreview = document.getElementById('listing-preview');
const previewEmpty = document.getElementById('preview-empty');
const regenerateSection = document.getElementById('regenerate-section');
const aiStatusDot = document.getElementById('ai-status-dot');
const aiStatusText = document.getElementById('ai-status-text');
const aiScanNote = document.getElementById('ai-scan-note');

// Sales tips by category
const SALES_TIPS = {
  electronics: [
    'Include model number in the title — buyers search by model',
    'Mention if charger/cables are included',
    'State battery health if applicable',
    'Note the original retail price to show the deal',
  ],
  furniture: [
    'Include exact dimensions (HxWxD)',
    'Mention material (solid wood, particle board, etc.)',
    'Note if it disassembles for transport',
    'Pet-free / smoke-free home sells better',
  ],
  clothing: [
    'Include brand, size, and fit (slim, regular, etc.)',
    'Mention fabric content',
    'Note if worn once or still has tags',
    'State measurements, not just label size',
  ],
  home: [
    'Include dimensions and weight',
    'Mention the brand and original price',
    'Note any cosmetic imperfections honestly',
    'Group related items together for bundle pricing',
  ],
  sports: [
    'Include size/weight specs',
    'Note what sport/activity it\'s designed for',
    'Mention if it\'s been used indoors or outdoors',
    'Include any accessories that come with it',
  ],
  auto: [
    'Include part number and vehicle compatibility',
    'Note OEM vs aftermarket',
    'Mention the reason for selling',
    'State if it\'s been tested and works',
  ],
  tools: [
    'Include brand and model number',
    'Note if corded or cordless (battery included?)',
    'Mention what projects it\'s suited for',
    'State if it includes a case or accessories',
  ],
  gaming: [
    'Note the platform (PS5, Xbox, Switch, PC)',
    'Include if physical disc or digital code',
    'Mention if it includes DLC or extras',
    'State if controller/accessories are included',
  ],
  default: [
    'First photo matters most — clean background, good lighting',
    'Price competitively — check similar listings in your area',
    'Respond quickly to messages — first 30 minutes matter',
    'Be honest about condition — it builds trust and avoids returns',
  ]
};

// Platform badge labels
const PLATFORM_BADGES = {
  facebook: 'FB',
  kijiji: 'Kijiji',
  ebay: 'eBay',
  craigslist: 'CL',
};

// Toast helper
function showToast(message) {
  let toast = document.querySelector('.toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2500);
}

// ========== DRAG AND DROP ==========
photoGrid.addEventListener('dragover', (e) => {
  e.preventDefault();
  photoGrid.classList.add('drag-over');
});

photoGrid.addEventListener('dragleave', () => {
  photoGrid.classList.remove('drag-over');
});

photoGrid.addEventListener('drop', async (e) => {
  e.preventDefault();
  photoGrid.classList.remove('drag-over');

  const files = [];
  for (const file of e.dataTransfer.files) {
    if (file.type.startsWith('image/')) {
      files.push(file.path);
    }
  }
  if (files.length > 0) {
    await addPhotos(files);
  }
});

// ========== PHOTO MANAGEMENT ==========
document.getElementById('btn-add-photos').addEventListener('click', async () => {
  const files = await window.api.selectPhotos();
  if (!files || files.length === 0) return;
  await addPhotos(files);
});

async function addPhotos(filePaths) {
  const enhance = document.getElementById('chk-enhance').checked;
  const squareCrop = document.getElementById('chk-square').checked;

  // Clear placeholder
  const placeholder = photoGrid.querySelector('.photo-placeholder');
  if (placeholder) placeholder.remove();

  for (const filePath of filePaths) {
    const thumbDiv = document.createElement('div');
    thumbDiv.className = 'photo-thumb processing';
    thumbDiv.dataset.path = filePath;
    photoGrid.appendChild(thumbDiv);

    const result = await window.api.processPhoto(filePath, { enhance, squareCrop });
    thumbDiv.classList.remove('processing');

    if (result.error) {
      thumbDiv.style.background = '#440000';
      thumbDiv.title = result.error;
      continue;
    }

    const img = document.createElement('img');
    img.src = result.preview;
    img.alt = 'Photo';
    thumbDiv.appendChild(img);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'remove-btn';
    removeBtn.textContent = 'X';
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const idx = state.photos.findIndex(p => p.processedPath === result.processedPath);
      if (idx !== -1) state.photos.splice(idx, 1);
      thumbDiv.remove();
      updatePhotoCount();
      if (state.photos.length === 0) {
        photoGrid.innerHTML = `<div class="photo-placeholder" id="drop-zone">
          <div class="drop-icon">&#128247;</div>
          <p>Drag & drop photos here</p>
          <p class="drop-hint">or click "Add Photos"</p>
        </div>`;
      }
    });
    thumbDiv.appendChild(removeBtn);

    state.photos.push(result);
  }

  updatePhotoCount();
}

function updatePhotoCount() {
  const count = state.photos.length;
  photoCount.textContent = `${count} photo${count !== 1 ? 's' : ''}`;
  photoActions.style.display = count > 0 ? 'flex' : 'none';

  // Update scan note based on AI availability
  updateScanNote();
}

function updateScanNote() {
  const count = state.photos.length;
  if (count === 0) {
    aiScanNote.textContent = 'Add photos to enable Smart Scan';
  } else if (state.ollamaReady && state.hasVision) {
    aiScanNote.textContent = 'AI vision + text generation ready';
    aiScanNote.style.color = '#00e676';
  } else if (state.ollamaReady) {
    aiScanNote.textContent = 'AI text generation ready (no vision model — will use smart templates)';
    aiScanNote.style.color = '#ffa726';
  } else {
    aiScanNote.textContent = 'Ollama not detected — using smart template generator';
    aiScanNote.style.color = '#888';
  }
}

// Save processed photos
document.getElementById('btn-save-photos').addEventListener('click', async () => {
  if (state.photos.length === 0) return;
  const paths = state.photos.map(p => p.processedPath);
  const result = await window.api.savePhotos(paths);
  if (result.saved) {
    showToast(`Saved ${result.files.length} photos`);
  }
});

// Add feature input
document.getElementById('btn-add-feature').addEventListener('click', () => {
  const list = document.getElementById('features-list');
  const input = document.createElement('input');
  input.type = 'text';
  input.className = 'feature-input';
  input.placeholder = 'e.g. Works perfectly';
  list.appendChild(input);
  input.focus();
});

// ========== SALES TIPS ==========
function showSalesTips() {
  const category = document.getElementById('category').value || 'default';
  const tips = SALES_TIPS[category] || SALES_TIPS.default;
  const tipsList = document.getElementById('tips-list');
  const tipsSection = document.getElementById('sales-tips');

  tipsList.innerHTML = '';
  tips.forEach(tip => {
    const li = document.createElement('li');
    li.textContent = tip;
    tipsList.appendChild(li);
  });
  tipsSection.style.display = 'block';
}

// Show tips when category changes
document.getElementById('category').addEventListener('change', showSalesTips);

// ========== SMART SCAN ==========
document.getElementById('btn-smart-scan').addEventListener('click', runSmartScan);
document.getElementById('btn-rescan')?.addEventListener('click', runSmartScan);

async function runSmartScan() {
  if (state.photos.length === 0) {
    showToast('Add photos first');
    return;
  }

  const btn = document.getElementById('btn-smart-scan');
  btn.disabled = true;
  scanStatus.style.display = 'block';

  const platform = document.getElementById('platform').value;
  const imagePaths = state.photos.map(p => p.processedPath || p.originalPath);

  // If Ollama is available with vision, use Smart Scan
  if (state.ollamaReady && state.hasVision) {
    scanStep.textContent = 'AI analyzing your item...';
    const result = await window.api.smartScan(imagePaths, platform);

    if (result.success) {
      const scanned = result.scanned;
      fillFormFromScan(scanned);

      if (result.generated) {
        const gen = result.generated;
        document.getElementById('price').value = gen.price || scanned.suggestedPrice || '';
        showListingPreview(gen.title, gen.body, gen.price || scanned.suggestedPrice);
        scanStep.textContent = 'Listing ready!';
      } else {
        document.getElementById('price').value = scanned.suggestedPrice || '';
        scanStep.textContent = result.warning ? `Scan done (${result.warning})` : 'Scan complete';
      }
    } else {
      scanStep.textContent = `Vision failed: ${result.error} — using smart template`;
      await runSmartTemplate(platform);
    }
  } else if (state.ollamaReady) {
    // No vision model but Ollama available — use AI text generation on form data
    scanStep.textContent = 'Generating AI listing...';
    await runAIGenerate(platform);
  } else {
    // No Ollama at all — use smart template generator
    scanStep.textContent = 'Generating smart listing...';
    await runSmartTemplate(platform);
  }

  btn.disabled = false;
  showSalesTips();
  setTimeout(() => { scanStatus.style.display = 'none'; }, 2000);
}

function fillFormFromScan(scanned) {
  document.getElementById('item-name').value = scanned.itemName;

  const catSelect = document.getElementById('category');
  for (const opt of catSelect.options) {
    if (opt.value === scanned.category) {
      catSelect.value = scanned.category;
      break;
    }
  }

  const condSelect = document.getElementById('condition');
  for (const opt of condSelect.options) {
    if (opt.value === scanned.condition) {
      condSelect.value = scanned.condition;
      break;
    }
  }

  document.getElementById('description').value = scanned.visionDescription;

  const featuresList = document.getElementById('features-list');
  featuresList.innerHTML = '';
  const features = scanned.features.length > 0 ? scanned.features : [''];
  for (const f of features) {
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'feature-input';
    input.value = f;
    input.placeholder = 'e.g. Works perfectly';
    featuresList.appendChild(input);
  }
}

async function runAIGenerate(platform) {
  const itemName = document.getElementById('item-name').value.trim();
  if (!itemName) {
    // If no name entered, use smart template instead
    await runSmartTemplate(platform);
    return;
  }

  const features = getFeatures();
  const details = {
    itemName,
    category: document.getElementById('category').value,
    condition: document.getElementById('condition').value,
    price: document.getElementById('price').value,
    description: document.getElementById('description').value.trim(),
    features,
    platform
  };

  const result = await window.api.aiGenerate(details);
  if (result.success) {
    showListingPreview(result.title, result.body, details.price);
    scanStep.textContent = 'AI listing generated!';
  } else {
    scanStep.textContent = 'AI failed — using smart template';
    await runSmartTemplate(platform);
  }
}

// ========== SMART TEMPLATE GENERATOR (NO AI NEEDED) ==========
async function runSmartTemplate(platform) {
  const itemName = document.getElementById('item-name').value.trim();
  if (!itemName) {
    scanStep.textContent = 'Enter an item name first';
    return;
  }

  const features = getFeatures();
  const details = {
    itemName,
    category: document.getElementById('category').value,
    condition: document.getElementById('condition').value,
    price: document.getElementById('price').value,
    description: document.getElementById('description').value.trim(),
    features,
    platform
  };

  const result = await window.api.generateListing(details);
  showListingPreview(result.title, result.body, result.price);
  scanStep.textContent = 'Listing generated!';
}

function getFeatures() {
  const features = [];
  document.querySelectorAll('.feature-input').forEach(input => {
    const val = input.value.trim();
    if (val) features.push(val);
  });
  return features;
}

// ========== LISTING PREVIEW ==========
function showListingPreview(title, body, price) {
  previewEmpty.style.display = 'none';
  listingPreview.style.display = 'block';
  regenerateSection.style.display = 'flex';

  // Set preview photo
  if (state.photos.length > 0) {
    const photosContainer = document.getElementById('preview-photos');
    photosContainer.style.display = 'block';
    state.previewIndex = 0;
    document.getElementById('preview-main-photo').src = state.photos[0].preview;

    // Show/hide nav arrows
    const prevBtn = document.getElementById('btn-photo-prev');
    const nextBtn = document.getElementById('btn-photo-next');
    if (state.photos.length > 1) {
      prevBtn.style.display = 'block';
      nextBtn.style.display = 'block';
    } else {
      prevBtn.style.display = 'none';
      nextBtn.style.display = 'none';
    }

    // Photo dots
    const dotsContainer = document.getElementById('preview-photo-dots');
    dotsContainer.innerHTML = '';
    if (state.photos.length > 1) {
      state.photos.forEach((_, i) => {
        const dot = document.createElement('span');
        dot.className = `dot${i === 0 ? ' active' : ''}`;
        dot.addEventListener('click', () => navigatePhoto(i));
        dotsContainer.appendChild(dot);
      });
    }
  }

  // Set text content
  document.getElementById('preview-title').textContent = title || 'Untitled';
  document.getElementById('preview-description').textContent = body || '';
  document.getElementById('preview-price').textContent = price ? `$${price}` : 'Price not set';

  const conditionMap = {
    'new': 'New', 'like-new': 'Like New', 'good': 'Good',
    'fair': 'Fair', 'for-parts': 'For Parts'
  };
  const cond = document.getElementById('condition').value;
  document.getElementById('preview-condition').textContent = conditionMap[cond] || cond;

  // Platform badge
  const platform = document.getElementById('platform').value;
  document.getElementById('preview-platform-badge').textContent = PLATFORM_BADGES[platform] || platform;

  listingPreview.scrollIntoView({ behavior: 'smooth' });
}

// Photo carousel navigation
function navigatePhoto(index) {
  if (index < 0 || index >= state.photos.length) return;
  state.previewIndex = index;
  document.getElementById('preview-main-photo').src = state.photos[index].preview;
  document.querySelectorAll('#preview-photo-dots .dot').forEach((d, j) => {
    d.classList.toggle('active', j === index);
  });
}

document.getElementById('btn-photo-prev')?.addEventListener('click', () => {
  navigatePhoto(state.previewIndex > 0 ? state.previewIndex - 1 : state.photos.length - 1);
});

document.getElementById('btn-photo-next')?.addEventListener('click', () => {
  navigatePhoto(state.previewIndex < state.photos.length - 1 ? state.previewIndex + 1 : 0);
});

// Copy buttons on preview (reads from contenteditable elements)
document.getElementById('btn-copy-title').addEventListener('click', async () => {
  const text = document.getElementById('preview-title').textContent;
  await window.api.copyToClipboard(text);
  showToast('Title copied!');
});

document.getElementById('btn-copy-desc').addEventListener('click', async () => {
  const text = document.getElementById('preview-description').textContent;
  await window.api.copyToClipboard(text);
  showToast('Description copied!');
});

document.getElementById('btn-copy-all').addEventListener('click', async () => {
  const title = document.getElementById('preview-title').textContent;
  const body = document.getElementById('preview-description').textContent;
  const price = document.getElementById('preview-price').textContent;
  const fullText = `${title}\n\n${body}\n\n${price}`;
  await window.api.copyToClipboard(fullText);
  showToast('Full listing copied!');
});

// Re-generate with edits
document.getElementById('btn-regenerate').addEventListener('click', async () => {
  const itemName = document.getElementById('item-name').value.trim();
  if (!itemName) {
    showToast('Enter an item name');
    return;
  }

  const btn = document.getElementById('btn-regenerate');
  btn.disabled = true;
  btn.textContent = 'Generating...';

  const features = getFeatures();
  const details = {
    itemName,
    category: document.getElementById('category').value,
    condition: document.getElementById('condition').value,
    price: document.getElementById('price').value,
    description: document.getElementById('description').value.trim(),
    features,
    platform: document.getElementById('platform').value
  };

  if (state.ollamaReady) {
    const result = await window.api.aiGenerate(details);
    btn.disabled = false;
    btn.textContent = 'Re-generate with Edits';

    if (result.success) {
      showListingPreview(result.title, result.body, details.price);
      showToast('Listing re-generated!');
    } else {
      // Fall back to template
      const tmpl = await window.api.generateListing(details);
      showListingPreview(tmpl.title, tmpl.body, tmpl.price);
      showToast('Re-generated (template mode)');
    }
  } else {
    const result = await window.api.generateListing(details);
    btn.disabled = false;
    btn.textContent = 'Re-generate with Edits';
    showListingPreview(result.title, result.body, result.price);
    showToast('Listing re-generated!');
  }
});

// ========== ORIGINAL BUTTONS (still work) ==========
// Generate listing (template)
document.getElementById('btn-generate').addEventListener('click', async () => {
  const itemName = document.getElementById('item-name').value.trim();
  if (!itemName) {
    showToast('Enter an item name');
    return;
  }

  const features = getFeatures();
  const platform = document.getElementById('platform').value;
  const details = {
    itemName,
    category: document.getElementById('category').value,
    condition: document.getElementById('condition').value,
    price: document.getElementById('price').value,
    description: document.getElementById('description').value.trim(),
    features,
    platform
  };

  const result = await window.api.generateListing(details);
  showListingPreview(result.title, result.body, result.price);
  showSalesTips();
});

// Vision analyze button (standalone)
document.getElementById('btn-analyze-photo').addEventListener('click', async () => {
  if (state.photos.length === 0) {
    showToast('Add photos first');
    return;
  }

  const btn = document.getElementById('btn-analyze-photo');
  btn.disabled = true;
  btn.textContent = 'Analyzing...';

  const photoPath = state.photos[0].processedPath || state.photos[0].originalPath;
  const result = await window.api.aiVisionAnalyze(photoPath);

  btn.disabled = false;
  btn.textContent = 'Analyze Photo';

  if (result.success) {
    document.getElementById('description').value = result.analysis;
    showToast('Photo analyzed! Edit details and generate.');
  } else {
    showToast(result.error || 'Vision analysis failed');
  }
});

// AI Generate button (standalone)
document.getElementById('btn-ai-generate').addEventListener('click', async () => {
  const itemName = document.getElementById('item-name').value.trim();
  if (!itemName) {
    showToast('Enter an item name');
    return;
  }

  const btn = document.getElementById('btn-ai-generate');
  btn.disabled = true;
  btn.textContent = 'Generating...';

  const features = getFeatures();
  const details = {
    itemName,
    category: document.getElementById('category').value,
    condition: document.getElementById('condition').value,
    price: document.getElementById('price').value,
    description: document.getElementById('description').value.trim(),
    features,
    platform: document.getElementById('platform').value
  };

  const result = await window.api.aiGenerate(details);

  btn.disabled = false;
  btn.textContent = 'AI Generate';

  if (result.success) {
    showListingPreview(result.title, result.body, details.price);
    showToast('AI listing generated!');
  } else {
    showToast(result.error || 'AI generation failed');
  }
});

// Keyboard shortcut: Enter in item-name triggers generate
document.getElementById('item-name').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    document.getElementById('btn-generate').click();
  }
});

// ========== AI STATUS CHECK ==========
(async () => {
  const ollama = await window.api.checkOllama();
  if (ollama.available) {
    state.ollamaReady = true;
    state.models = ollama.models;
    document.getElementById('btn-ai-generate').style.display = 'block';

    const hasVision = ollama.models.some(m =>
      m.includes('moondream') || m.includes('llava') || m.includes('minicpm')
    );

    if (hasVision) {
      state.hasVision = true;
      document.getElementById('btn-analyze-photo').style.display = 'inline-block';
      aiStatusDot.className = 'status-dot online';
      aiStatusText.textContent = 'AI Ready (Vision + Text)';
    } else {
      aiStatusDot.className = 'status-dot partial';
      aiStatusText.textContent = 'AI Ready (Text only)';
    }
  } else {
    aiStatusDot.className = 'status-dot offline';
    aiStatusText.textContent = 'AI Offline — Template Mode';
  }

  updateScanNote();
})();
