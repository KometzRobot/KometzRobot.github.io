// State
const state = {
  photos: [], // { originalPath, processedPath, preview }
};

// DOM refs
const photoGrid = document.getElementById('photo-grid');
const photoActions = document.getElementById('photo-actions');
const photoCount = document.getElementById('photo-count');
const outputSection = document.getElementById('output-section');

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
  setTimeout(() => toast.classList.remove('show'), 2000);
}

// Add photos
document.getElementById('btn-add-photos').addEventListener('click', async () => {
  const files = await window.api.selectPhotos();
  if (!files || files.length === 0) return;

  const enhance = document.getElementById('chk-enhance').checked;
  const squareCrop = document.getElementById('chk-square').checked;

  // Clear placeholder
  const placeholder = photoGrid.querySelector('.photo-placeholder');
  if (placeholder) placeholder.remove();

  for (const filePath of files) {
    // Show processing placeholder
    const thumbDiv = document.createElement('div');
    thumbDiv.className = 'photo-thumb processing';
    thumbDiv.dataset.path = filePath;
    photoGrid.appendChild(thumbDiv);

    // Process photo
    const result = await window.api.processPhoto(filePath, { enhance, squareCrop });

    thumbDiv.classList.remove('processing');

    if (result.error) {
      thumbDiv.style.background = '#440000';
      thumbDiv.title = result.error;
      continue;
    }

    // Show preview
    const img = document.createElement('img');
    img.src = result.preview;
    img.alt = 'Photo';
    thumbDiv.appendChild(img);

    // Remove button
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
        photoGrid.innerHTML = '<div class="photo-placeholder">Drop photos here or click "Add Photos"</div>';
        photoActions.style.display = 'none';
      }
    });
    thumbDiv.appendChild(removeBtn);

    state.photos.push(result);
  }

  updatePhotoCount();
});

function updatePhotoCount() {
  const count = state.photos.length;
  photoCount.textContent = `${count} photo${count !== 1 ? 's' : ''}`;
  photoActions.style.display = count > 0 ? 'flex' : 'none';
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

// Generate listing
document.getElementById('btn-generate').addEventListener('click', async () => {
  const itemName = document.getElementById('item-name').value.trim();
  if (!itemName) {
    showToast('Enter an item name');
    return;
  }

  const features = [];
  document.querySelectorAll('.feature-input').forEach(input => {
    const val = input.value.trim();
    if (val) features.push(val);
  });

  const details = {
    itemName,
    category: document.getElementById('category').value,
    condition: document.getElementById('condition').value,
    price: document.getElementById('price').value,
    description: document.getElementById('description').value.trim(),
    features
  };

  const result = await window.api.generateListing(details);

  document.getElementById('output-title').textContent = result.title;
  document.getElementById('output-body').textContent = result.body;
  document.getElementById('output-price').textContent = result.price ? `$${result.price}` : 'Not set';
  outputSection.style.display = 'block';

  // Scroll to output
  outputSection.scrollIntoView({ behavior: 'smooth' });
});

// Copy buttons
document.addEventListener('click', async (e) => {
  if (e.target.classList.contains('btn-copy')) {
    const targetId = e.target.dataset.target;
    const text = document.getElementById(targetId).textContent;
    await window.api.copyToClipboard(text);
    showToast('Copied!');
  }
});

// Copy all
document.getElementById('btn-copy-all').addEventListener('click', async () => {
  const title = document.getElementById('output-title').textContent;
  const body = document.getElementById('output-body').textContent;
  const price = document.getElementById('output-price').textContent;
  const fullText = `Title: ${title}\n\nDescription:\n${body}\nPrice: ${price}`;
  await window.api.copyToClipboard(fullText);
  showToast('Full listing copied!');
});

// Check for Ollama on startup
(async () => {
  const ollama = await window.api.checkOllama();
  if (ollama.available) {
    document.getElementById('btn-ai-generate').style.display = 'block';
    // Check for vision model
    const hasVision = ollama.models.some(m =>
      m.includes('moondream') || m.includes('llava') || m.includes('minicpm')
    );
    if (hasVision) {
      document.getElementById('btn-analyze-photo').style.display = 'inline-block';
    }
  }
})();

// Vision analyze button — auto-identify item from first photo
document.getElementById('btn-analyze-photo').addEventListener('click', async () => {
  if (state.photos.length === 0) {
    showToast('Add photos first');
    return;
  }

  const btn = document.getElementById('btn-analyze-photo');
  btn.disabled = true;
  btn.textContent = 'Analyzing...';

  // Use the first photo's processed path (or original if no processing)
  const photoPath = state.photos[0].processedPath || state.photos[0].originalPath;
  const result = await window.api.aiVisionAnalyze(photoPath);

  btn.disabled = false;
  btn.textContent = 'Analyze Photo (AI Vision)';

  if (result.success) {
    // Put the analysis into the description field
    document.getElementById('description').value = result.analysis;
    showToast('Photo analyzed! Edit the details and generate listing.');
  } else {
    showToast(result.error || 'Vision analysis failed');
  }
});

// AI Generate button
document.getElementById('btn-ai-generate').addEventListener('click', async () => {
  const itemName = document.getElementById('item-name').value.trim();
  if (!itemName) {
    showToast('Enter an item name');
    return;
  }

  const btn = document.getElementById('btn-ai-generate');
  btn.disabled = true;
  btn.textContent = 'Generating...';

  const features = [];
  document.querySelectorAll('.feature-input').forEach(input => {
    const val = input.value.trim();
    if (val) features.push(val);
  });

  const details = {
    itemName,
    category: document.getElementById('category').value,
    condition: document.getElementById('condition').value,
    price: document.getElementById('price').value,
    description: document.getElementById('description').value.trim(),
    features
  };

  const result = await window.api.aiGenerate(details);

  btn.disabled = false;
  btn.textContent = 'AI Generate (Ollama)';

  if (result.success) {
    document.getElementById('output-title').textContent = result.title;
    document.getElementById('output-body').textContent = result.body;
    document.getElementById('output-price').textContent = details.price ? `$${details.price}` : 'Not set';
    outputSection.style.display = 'block';
    outputSection.scrollIntoView({ behavior: 'smooth' });
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
