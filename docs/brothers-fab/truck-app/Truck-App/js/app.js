// ============================================
// Main App — Food Truck Layout Builder
// ============================================

const app = {
  // Scene
  scene: null,
  camera: null,
  renderer: null,
  controls: null,

  // Truck
  truckLengthFt: 20,
  truckGroup: null,
  floorMesh: null,

  // Grid
  gridCellsX: 40,  // 20ft / 0.5ft
  gridCellsZ: 16,  // 8ft / 0.5ft

  // State
  placedItems: [],
  selectedItem: null,
  activeEquipId: null,
  ghostMesh: null,
  ghostValid: false,
  ghostRotation: 0,
  _wallMountSpin: 0,      // 0, PI/2, PI, PI*1.5 — spin on wall surface
  _wallMountFlipped: false, // flip inward/outward

  // Raycasting
  raycaster: new THREE.Raycaster(),
  mouse: new THREE.Vector2(),
  floorPlane: new THREE.Plane(new THREE.Vector3(0, 1, 0), 0),

  // State for new features
  truckWidthFt: 8,
  colorAccents: false,
  smoothTargetPos: null,
  viewPreset: 'iso',
  floorMaterial: 'bare',
  wallMaterial: 'default',
  sceneBackground: 'light', // light, grey, dark, asphalt, concrete, checker
  _truckWalls: [],  // per-wall refs for dynamic transparency
  _dimensionGroup: null,  // 3D dimension lines
  _exteriorGroup: null,   // exterior truck shell (cab, chassis, wheels)

  // Truck chassis type — affects wheel wells and structure
  truckType: 'step-van', // 'step-van', 'box-truck', 'ups-style', 'flatbed'
  showWheelWells: true,
  _wheelWellBoxes: [], // collision boxes (world units) for wheel wells
  wallVisibility: 'auto', // 'auto' (dynamic), 'off', 'low', 'full'
  frontWallOpacity: 0.15,   // 0-1 slider value (used in auto mode for facing walls)
  showRoof: false,
  utilityMode: null, // 'electrical', 'water', 'gas', or null
  utilityGroup: null,
  utilityLines: { electrical: [], water: [], gas: [] },
  _utilityDrawingFrom: null,
  _utilityNodes: [], // {pos, itemId, mesh, type}

  // Undo stack (checkpoint history)
  undoStack: [],
  redoStack: [],
  maxUndoSteps: 50,

  // Auto-save
  autoSaveKey: 'truck-builder-autosave-v1',
  autoSaveTimer: null,

  // ---- Initialization ----
  init() {
    try {
      this.setupScene();
      this.buildTruck();
      this.buildGridOverlay();
      this.setupControls();
      this.setupEventListeners();
    } catch (e) {
      console.error('Scene init failed:', e);
      this._showFriendlyError('The 3D engine couldn\'t start up.', e.message, 'This usually means your browser doesn\'t support WebGL, or something got corrupted. Try refreshing — if that doesn\'t work, try Chrome or Edge.');
      return;
    }

    // UI — use new API, each wrapped to tolerate missing elements
    const uiCalls = [
      () => UI.populateEquipmentList(),
      () => UI.initSearch(),
      () => UI.initModeSwitcher(),
      () => UI.initColorToggle(),
      () => UI.initFullscreen(),
      () => UI.initViewPresets(),
      () => UI.initNewButton(() => this.clearAll()),
      () => UI.initExportButton(() => this.exportLayout()),
      () => UI.initImportButton((layout) => this.importLayout(layout)),
      () => UI.initTemplatesPanel(
        (tpl) => this.loadTemplate(tpl),
        () => this.listUserTemplates()
      ),
      () => UI.initInternalControls((len, wid) => this.resizeTruck(len, wid)),
      () => UI.initQuotePanel((data) => this.submitQuote(data)),
      () => UI.initMobileDrawers(),
      () => UI.initTooltips(),
      () => UI.initCollapsibles(),
      () => UI.initSaveLoadPanel(
        (name, tags) => this.saveLayout(name, tags),
        (layout) => this.loadLayout(layout),
        () => this.listSavedLayouts(),
        (id) => this.deleteSavedLayout(id)
      )
    ];
    uiCalls.forEach((fn, i) => {
      try { fn(); }
      catch (e) { console.warn('UI init step ' + i + ' failed:', e); }
    });

    // Property panel buttons
    const btnRot = document.getElementById('btn-rotate');
    if (btnRot) btnRot.addEventListener('click', () => this.rotateSelected());
    const btnDel = document.getElementById('btn-delete');
    if (btnDel) btnDel.addEventListener('click', () => this.deleteSelected());
    const btnCycleVar = document.getElementById('btn-cycle-variant');
    if (btnCycleVar) btnCycleVar.addEventListener('click', () => this.cycleSelectedVariant());
    const btnMove = document.getElementById('btn-move');
    if (btnMove) btnMove.addEventListener('click', () => this.moveSelected());
    const btnDup = document.getElementById('btn-duplicate');
    if (btnDup) btnDup.addEventListener('click', () => this.duplicateSelected());
    const btnDupMenu = document.getElementById('btn-duplicate-menu');
    if (btnDupMenu) btnDupMenu.addEventListener('click', () => this.duplicateSelected());
    const btnUndo = document.getElementById('btn-undo-panel');
    if (btnUndo) btnUndo.addEventListener('click', () => this.undo());
    const btnRedo = document.getElementById('btn-redo-panel');
    if (btnRedo) btnRedo.addEventListener('click', () => this.redo());
    const btnClearAll = document.getElementById('btn-clear-all');
    if (btnClearAll) btnClearAll.addEventListener('click', () => {
      if (confirm('Remove all placed items?')) this.clearAll();
    });
    const btnClearPen = document.getElementById('btn-clear-pen');
    if (btnClearPen) btnClearPen.addEventListener('click', () => {
      // Clear laser pen
      const penCanvas = document.getElementById('pen-canvas');
      if (penCanvas) penCanvas.getContext('2d').clearRect(0, 0, penCanvas.width, penCanvas.height);
      // Clear permanent draw
      this._drawStrokes = [];
      this._drawUndoStack = [];
      this._redrawAllStrokes();
      UI.showToast('Pen cleared', 'info');
    });

    this.animate();
    this.handleResize();

    UI.setStatus('Select equipment from the sidebar to begin');
    UI.setDimensionsInfo(`${this.truckLengthFt}ft × ${this.truckWidthFt}ft`);

    // Wire surface swatches
    this.initSurfaceSwatches();
    this.initUtilityOverlays();
    this.initInternalQuickActions();

    // Hide the loading splash (small delay so users see the branded loader)
    setTimeout(() => {
      const loader = document.getElementById('loader');
      if (loader) loader.classList.add('hidden');
    }, 700);

    // Check for autosave recovery
    setTimeout(() => this.checkAutoSaveRecovery(), 1200);

    // Pen tool — fade + solid modes combined
    this.initPenTool();

    // Height adjust buttons for elevated items
    this.initHeightAdjust();

    // Controls help overlay — visible on boot with a flash
    this.initControlsHelp();

    // Audio system
    this.initAudioSystem();

    // Welcome popup (first launch)
    this.showWelcomePopup();
    this.initLightsToggle();
    this.initReportsMenu();
    this.initTopbarMenus();
    this.initMeasureTool();
    this.initZoomSlider();
    this.initDimSteppers();
    this.initSoundToggle();
    this.initExitButton();
  },

  showWelcomePopup() {
    if (localStorage.getItem('truck-builder-welcome-dismissed')) return;
    const overlay = document.getElementById('welcome-overlay');
    if (!overlay) return;
    overlay.classList.remove('hidden');
    const closeBtn = document.getElementById('welcome-close-btn');
    const backdrop = document.getElementById('welcome-backdrop');
    const dismiss = () => {
      const check = document.getElementById('welcome-dismiss-check');
      if (check && check.checked) {
        localStorage.setItem('truck-builder-welcome-dismissed', '1');
      }
      overlay.classList.add('hidden');
    };
    if (closeBtn) closeBtn.addEventListener('click', dismiss);
    if (backdrop) backdrop.addEventListener('click', dismiss);
  },

  initHeightAdjust() {
    const panel = document.getElementById('height-adjust');
    const upBtn = document.getElementById('btn-height-up');
    const downBtn = document.getElementById('btn-height-down');
    const display = document.getElementById('height-display');
    if (!panel || !upBtn || !downBtn) return;

    const step = 0.25; // 6 inches per click
    let pulseTimer = null;

    const flashBar = () => {
      const bar = document.getElementById('height-item-bar');
      if (!bar) return;
      bar.classList.add('pulse');
      if (pulseTimer) clearTimeout(pulseTimer);
      pulseTimer = setTimeout(() => bar.classList.remove('pulse'), 250);
    };

    const updateDisplay = () => {
      if (!this.ghostMesh) return;
      const base = (this.ghostMesh.userData.elevationCells || 0) * CELL_SIZE;
      const total = base + (this._ghostHeightOffset || 0);
      const ft = Math.floor(total * 2) / 2;
      if (display) display.textContent = ft.toFixed(1) + "' sill";
      flashBar();
    };

    const clampH = (val) => {
      if (!this.ghostMesh) return val;
      const wh = { 'step-van': 7.0, 'box-truck': 8.0, 'ups-style': 6.5, 'flatbed': 7.5 };
      const ceil = wh[this.truckType] || 6.5;
      const d = this.ghostMesh.userData;
      const baseY = (d.elevationCells || 0) * CELL_SIZE;
      const itemH = d.heightCells * CELL_SIZE;
      return Math.max(-baseY, Math.min(ceil - itemH - baseY, val));
    };

    upBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!this.ghostMesh) return;
      this._ghostHeightOffset = clampH((this._ghostHeightOffset || 0) + step);
      updateDisplay();
    });

    downBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      if (!this.ghostMesh) return;
      this._ghostHeightOffset = clampH((this._ghostHeightOffset || 0) - step);
      updateDisplay();
    });

    panel.addEventListener('wheel', (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!this.ghostMesh) return;
      const dir = e.deltaY < 0 ? 1 : -1;
      this._ghostHeightOffset = clampH((this._ghostHeightOffset || 0) + dir * step);
      updateDisplay();
    });

    // Show/hide based on ghost state — check every frame in animate
    this._heightAdjustPanel = panel;
    this._heightAdjustDisplay = display;
  },

  updateHeightAdjustVisibility() {
    if (!this._heightAdjustPanel) return;
    const show = this.ghostMesh && (this.ghostMesh.userData.elevated || this._isWallMount(this.ghostMesh.userData.equipId));
    this._heightAdjustPanel.style.display = show ? 'flex' : 'none';
    if (!show) return;

    const wallHeights = { 'step-van': 7.0, 'box-truck': 8.0, 'ups-style': 6.5, 'flatbed': 7.5 };
    const ceilH = wallHeights[this.truckType] || 6.5;
    const data = this.ghostMesh.userData;
    const base = (data.elevationCells || 0) * CELL_SIZE;
    const offset = this._ghostHeightOffset || 0;
    const sillY = base + offset;
    const itemH = data.heightCells * CELL_SIZE;
    const topY = sillY + itemH;

    // Update text
    const ft = Math.round(sillY * 2) / 2;
    if (this._heightAdjustDisplay) {
      this._heightAdjustDisplay.textContent = ft.toFixed(1) + "' sill";
    }

    // Update gauge bar position (track is 120px, bottom=floor, top=ceiling)
    const track = document.getElementById('height-track');
    const bar = document.getElementById('height-item-bar');
    const ceilMark = document.getElementById('height-ceil-mark');
    const counterMark = document.getElementById('height-counter-mark');
    const floorMark = document.getElementById('height-floor-mark');
    if (track && bar) {
      const trackH = 120;
      const pxPerFt = trackH / ceilH;
      const barBottom = sillY * pxPerFt;
      const barH = Math.max(4, itemH * pxPerFt);
      bar.style.bottom = barBottom + 'px';
      bar.style.height = barH + 'px';
      bar.style.top = 'auto';

      // Color: green if fits, orange if touching ceiling, red if over
      if (topY > ceilH) bar.style.background = '#e53e3e';
      else if (topY > ceilH - 0.25) bar.style.background = '#e8a020';
      else bar.style.background = 'var(--accent)';
    }
    // Position reference marks
    if (ceilMark) ceilMark.style.bottom = '100%';
    if (floorMark) floorMark.style.bottom = '0';
    if (counterMark) {
      const counterPx = (3.0 / ceilH) * 120; // 3ft counter height
      counterMark.style.bottom = counterPx + 'px';
    }
  },

  initControlsHelp() {
    const overlay = document.getElementById('controls-help-overlay');
    const btn = document.getElementById('btn-help-toggle');
    if (!overlay) return;

    // Flash on boot to draw attention
    setTimeout(() => overlay.classList.add('flash'), 900);

    const toggle = () => {
      overlay.classList.toggle('hidden');
    };

    if (btn) btn.addEventListener('click', toggle);

    // H key shortcut
    document.addEventListener('keydown', (e) => {
      if (e.key === 'h' || e.key === 'H') {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
        toggle();
      }
    });
  },

  _soundEnabled: true,

  _defaultCamDist: null,

  // ---- Pen Tool (combined fade + solid) ----
  _penActive: false,
  _penModeIdx: 0, // 0-5 = fade colors, 6-11 = solid colors
  _penColors: ['#ffdd00', '#ff3333', '#33cc55', '#3388ff', '#ffffff', '#222222'],
  _penColorNames: { '#ffdd00':'Yellow', '#ff3333':'Red', '#33cc55':'Green', '#3388ff':'Blue', '#ffffff':'White', '#222222':'Black' },
  _penWidth: 4,

  // Solid-mode persistent strokes (shared with undo/redo)
  _drawStrokes: [],
  _drawUndoStack: [],
  _drawCurrentStroke: null,

  _penIsSolid()  { return this._penModeIdx >= 6; },
  _penColor()    { return this._penColors[this._penModeIdx % 6]; },

  initPenTool() {
    const btn = document.getElementById('btn-pen-tool');
    const fadeOverlay = document.getElementById('pen-overlay');
    const fadeCanvas  = document.getElementById('pen-canvas');
    const solidOverlay = document.getElementById('draw-overlay');
    const solidCanvas  = document.getElementById('draw-canvas');
    if (!btn || !fadeOverlay || !fadeCanvas || !solidOverlay || !solidCanvas) return;

    const fadeCtx  = fadeCanvas.getContext('2d');
    const solidCtx = solidCanvas.getContext('2d');

    const resizeCanvases = () => {
      const vp = document.getElementById('viewport');
      if (vp) {
        fadeCanvas.width = solidCanvas.width = vp.clientWidth;
        fadeCanvas.height = solidCanvas.height = vp.clientHeight;
        this._redrawAllStrokes();
      }
    };
    window.addEventListener('resize', resizeCanvases);
    setTimeout(resizeCanvases, 100);

    let drawing = false;
    let lastX = 0, lastY = 0;

    // ── UI helpers ──
    const updateBtn = () => {
      const color = this._penColor();
      const solid = this._penIsSolid();
      btn.style.background = this._penActive ? color + '44' : '';
      btn.style.boxShadow  = this._penActive ? '0 0 0 2px ' + color : '';
      btn.style.color       = this._penActive ? color : '';
      btn.textContent       = solid ? '\u270F\uFE0F' : '\u2508'; // ✏️ or ┈
      btn.title             = solid ? 'Pen tool (P) — solid' : 'Pen tool (P) — fade';
    };

    const showOverlays = (solid) => {
      if (solid) {
        fadeOverlay.style.display = 'none';
        fadeOverlay.style.pointerEvents = 'none';
        solidOverlay.style.display = 'block';
        solidOverlay.style.pointerEvents = 'auto';
      } else {
        solidOverlay.style.pointerEvents = 'none';
        fadeOverlay.style.display = 'block';
        fadeOverlay.style.pointerEvents = 'auto';
      }
    };

    // ── Activate / Deactivate ──
    const activate = () => {
      this._penActive = true;
      document.body.classList.add('pen-mode');
      resizeCanvases();
      showOverlays(this._penIsSolid());
      updateBtn();
      if (!this._penIsSolid()) ensureRender();
      const mode = this._penIsSolid() ? 'Solid' : 'Fade';
      UI.showToast(mode + ' ' + (this._penColorNames[this._penColor()] || '') + ' · Click to cycle · ESC exit', 'info');
    };

    const deactivate = () => {
      this._penActive = false;
      document.body.classList.remove('pen-mode');
      fadeOverlay.style.display = 'none';
      fadeOverlay.style.pointerEvents = 'none';
      solidOverlay.style.pointerEvents = 'none';
      btn.style.background = '';
      btn.style.boxShadow = '';
      btn.style.color = '';
      btn.textContent = '\u2508'; // ┈
      btn.title = 'Pen tool (P) — fade/solid cycle';
      fadePoints.length = 0;
      renderRunning = false;
      fadeCtx.clearRect(0, 0, fadeCanvas.width, fadeCanvas.height);
    };

    // ── Cycle: advance to next of 12 slots ──
    const cycleMode = () => {
      this._penModeIdx = (this._penModeIdx + 1) % 12;
      showOverlays(this._penIsSolid());
      updateBtn();
      if (!this._penIsSolid()) ensureRender();
      const mode = this._penIsSolid() ? 'Solid' : 'Fade';
      UI.showToast(mode + ' ' + (this._penColorNames[this._penColor()] || ''), 'info');
    };

    // ── Button click ──
    btn.addEventListener('click', () => {
      if (!this._penActive) activate();
      else cycleMode();
    });

    // P key toggles / cycles, Escape exits
    document.addEventListener('keydown', (e) => {
      if (['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) return;
      if (e.key === 'p' || e.key === 'P') {
        if (!this._penActive) activate();
        else cycleMode();
      }
      if (e.key === 'Escape' && this._penActive) deactivate();
    });

    // Right-click exits
    fadeOverlay.addEventListener('contextmenu', (e) => { e.preventDefault(); deactivate(); });
    solidOverlay.addEventListener('contextmenu', (e) => { e.preventDefault(); deactivate(); });

    // ══════════════════════════════════════
    //  FADE mode — chase-tail point buffer
    // ══════════════════════════════════════
    const fadePoints = [];
    const MAX_TRAIL = 80;
    const DRAIN_RATE = 2;
    let renderRunning = false;

    const renderPoints = () => {
      if (!this._penActive && fadePoints.length === 0) { renderRunning = false; return; }
      fadeCtx.clearRect(0, 0, fadeCanvas.width, fadeCanvas.height);

      if (!drawing) {
        for (let d = 0; d < DRAIN_RATE; d++) {
          if (fadePoints.length > 0) fadePoints.shift();
        }
      }
      while (fadePoints.length > MAX_TRAIL) fadePoints.shift();

      fadeCtx.lineCap = 'round';
      fadeCtx.lineJoin = 'round';
      const len = fadePoints.length;
      for (let i = 0; i < len; i++) {
        const p = fadePoints[i];
        const alpha = (i + 1) / len;
        fadeCtx.globalAlpha = alpha * alpha;
        fadeCtx.strokeStyle = p.color;
        fadeCtx.lineWidth = p.width * (0.5 + alpha * 0.5);
        fadeCtx.shadowColor = p.color;
        fadeCtx.shadowBlur = alpha * p.width;
        fadeCtx.beginPath();
        fadeCtx.moveTo(p.x1, p.y1);
        fadeCtx.lineTo(p.x2, p.y2);
        fadeCtx.stroke();
      }
      fadeCtx.globalAlpha = 1;
      fadeCtx.shadowBlur = 0;
      requestAnimationFrame(renderPoints);
    };

    const ensureRender = () => {
      if (!renderRunning) { renderRunning = true; renderPoints(); }
    };

    // ── FADE drawing events ──
    fadeOverlay.addEventListener('mousedown', (e) => {
      if (!this._penActive || this._penIsSolid() || e.button !== 0) return;
      drawing = true;
      const rect = fadeCanvas.getBoundingClientRect();
      lastX = e.clientX - rect.left;
      lastY = e.clientY - rect.top;
      ensureRender();
      e.preventDefault(); e.stopPropagation();
    });

    fadeOverlay.addEventListener('mousemove', (e) => {
      if (!drawing || this._penIsSolid()) return;
      const rect = fadeCanvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      fadePoints.push({ x1: lastX, y1: lastY, x2: x, y2: y, color: this._penColor(), width: this._penWidth });
      lastX = x; lastY = y;
      e.preventDefault();
    });

    const stopFadeDraw = () => { drawing = false; };
    fadeOverlay.addEventListener('mouseup', stopFadeDraw);
    fadeOverlay.addEventListener('mouseleave', stopFadeDraw);

    // ══════════════════════════════════════
    //  SOLID mode — persistent strokes
    // ══════════════════════════════════════
    solidOverlay.addEventListener('mousedown', (e) => {
      if (!this._penActive || !this._penIsSolid() || e.button !== 0) return;
      drawing = true;
      const rect = solidCanvas.getBoundingClientRect();
      this._drawCurrentStroke = {
        color: this._penColor(),
        width: 3,
        points: [{ x: e.clientX - rect.left, y: e.clientY - rect.top }]
      };
      e.preventDefault(); e.stopPropagation();
    });

    solidOverlay.addEventListener('mousemove', (e) => {
      if (!drawing || !this._penIsSolid() || !this._drawCurrentStroke) return;
      const rect = solidCanvas.getBoundingClientRect();
      const pt = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      this._drawCurrentStroke.points.push(pt);

      const pts = this._drawCurrentStroke.points;
      if (pts.length < 2) return;
      const p1 = pts[pts.length - 2];
      const p2 = pts[pts.length - 1];
      solidCtx.strokeStyle = this._drawCurrentStroke.color;
      solidCtx.lineWidth = this._drawCurrentStroke.width;
      solidCtx.lineCap = 'round';
      solidCtx.lineJoin = 'round';
      solidCtx.beginPath();
      solidCtx.moveTo(p1.x, p1.y);
      solidCtx.lineTo(p2.x, p2.y);
      solidCtx.stroke();
      e.preventDefault();
    });

    const stopSolidDraw = () => {
      if (drawing && this._drawCurrentStroke && this._drawCurrentStroke.points.length > 1) {
        this._drawStrokes.push(this._drawCurrentStroke);
        this._drawUndoStack = [];
      }
      this._drawCurrentStroke = null;
      drawing = false;
    };
    solidOverlay.addEventListener('mouseup', stopSolidDraw);
    solidOverlay.addEventListener('mouseleave', stopSolidDraw);

    // Stop drawing when hovering UI elements
    document.querySelectorAll('#viewport-bottom-right-btns, #viewport-bottom-btns, #view-presets, #status-bar, #height-adjust').forEach(el => {
      el.addEventListener('mouseenter', () => { stopFadeDraw(); stopSolidDraw(); });
    });

    // ── Undo / Redo / Clear for solid strokes ──
    const undoBtn  = document.getElementById('btn-undo-panel');
    const redoBtn  = document.getElementById('btn-redo-panel');
    const clearBtn = document.getElementById('btn-clear-all');

    if (undoBtn) {
      undoBtn.addEventListener('click', () => {
        if (this._drawStrokes.length > 0) {
          this._drawUndoStack.push(this._drawStrokes.pop());
          this._redrawAllStrokes();
        }
      });
    }
    if (redoBtn) {
      redoBtn.addEventListener('click', () => {
        if (this._drawUndoStack.length > 0) {
          this._drawStrokes.push(this._drawUndoStack.pop());
          this._redrawAllStrokes();
        }
      });
    }
    // Clear pen button handles draw strokes (not clear-all items button)
  },

  _redrawAllStrokes() {
    const canvas = document.getElementById('draw-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    this._drawStrokes.forEach(stroke => {
      if (stroke.points.length < 2) return;
      ctx.strokeStyle = stroke.color;
      ctx.lineWidth = stroke.width;
      ctx.beginPath();
      ctx.moveTo(stroke.points[0].x, stroke.points[0].y);
      for (let i = 1; i < stroke.points.length; i++) {
        ctx.lineTo(stroke.points[i].x, stroke.points[i].y);
      }
      ctx.stroke();
    });
  },

  // ---- Measure Tool ----
  _measureActive: false,
  _measureStart: null,
  _measureCanvas: null,

  initMeasureTool() {
    const btn = document.getElementById('btn-measure-tool');
    const overlay = document.getElementById('measure-overlay');
    const label = document.getElementById('measure-label');
    if (!btn || !overlay) return;

    // Create drawing canvas
    const canvas = document.createElement('canvas');
    overlay.insertBefore(canvas, label);
    this._measureCanvas = canvas;

    const resizeCanvas = () => {
      const vp = document.getElementById('viewport');
      if (vp) {
        canvas.width = vp.clientWidth;
        canvas.height = vp.clientHeight;
        canvas.style.width = vp.clientWidth + 'px';
        canvas.style.height = vp.clientHeight + 'px';
      }
    };
    window.addEventListener('resize', resizeCanvas);
    // Initial size
    setTimeout(resizeCanvas, 100);

    const toggleMeasure = () => {
      this._measureActive = !this._measureActive;
      document.body.classList.toggle('measure-mode', this._measureActive);
      overlay.style.display = this._measureActive ? 'block' : 'none';
      overlay.style.pointerEvents = this._measureActive ? 'auto' : 'none';
      btn.style.background = this._measureActive ? 'rgba(255,153,64,0.3)' : '';
      if (this._measureActive) {
        resizeCanvas();
        UI.showToast('Measure: click + drag, release to copy', 'info');
      } else {
        const ctx2d = canvas.getContext('2d');
        ctx2d.clearRect(0, 0, canvas.width, canvas.height);
        label.style.display = 'none';
      }
    };

    btn.addEventListener('click', toggleMeasure);
    document.addEventListener('keydown', (e) => {
      if ((e.key === 'm' || e.key === 'M') && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)) {
        toggleMeasure();
      }
    });

    // Get world position from screen coords
    const screenToWorld = (sx, sy) => {
      const rect = this.renderer.domElement.getBoundingClientRect();
      const mx = ((sx - rect.left) / rect.width) * 2 - 1;
      const my = -((sy - rect.top) / rect.height) * 2 + 1;
      this.raycaster.setFromCamera(new THREE.Vector2(mx, my), this.camera);
      const pt = new THREE.Vector3();
      if (this.raycaster.ray.intersectPlane(this.floorPlane, pt)) return pt;
      return null;
    };

    // Screen project
    const worldToScreen = (wp) => {
      const v = wp.clone().project(this.camera);
      const rect = this.renderer.domElement.getBoundingClientRect();
      return {
        x: (v.x * 0.5 + 0.5) * rect.width,
        y: (-v.y * 0.5 + 0.5) * rect.height
      };
    };

    const vpEl = document.getElementById('viewport');
    let startWorld = null;
    let dragging = false;

    overlay.addEventListener('mousedown', (e) => {
      if (!this._measureActive || e.button !== 0) return;
      startWorld = screenToWorld(e.clientX, e.clientY);
      if (!startWorld) return;
      this._measureStart = { sx: e.clientX, sy: e.clientY, world: startWorld };
      dragging = true;
      e.stopPropagation();
      e.preventDefault();
    }, true);

    overlay.addEventListener('mousemove', (e) => {
      if (!dragging || !this._measureActive) return;
      const endWorld = screenToWorld(e.clientX, e.clientY);
      if (!endWorld || !this._measureStart) return;

      const dx = endWorld.x - this._measureStart.world.x;
      const dz = endWorld.z - this._measureStart.world.z;
      const distWorld = Math.sqrt(dx * dx + dz * dz);
      // 1 world unit = 1 foot (CELL_SIZE=0.5, 2 cells/ft → 1 unit = 1ft)
      const feet = distWorld;
      const ft = Math.floor(feet);
      const inches = Math.round((feet - ft) * 12);
      const text = `${ft}'${inches}" (${feet.toFixed(2)} ft)`;

      // Draw line on canvas
      const ctx2d = canvas.getContext('2d');
      ctx2d.clearRect(0, 0, canvas.width, canvas.height);
      const rect = this.renderer.domElement.getBoundingClientRect();
      const s1 = { x: this._measureStart.sx - rect.left, y: this._measureStart.sy - rect.top };
      const s2 = { x: e.clientX - rect.left, y: e.clientY - rect.top };

      // Dashed line
      ctx2d.setLineDash([8, 5]);
      ctx2d.strokeStyle = '#ff9940';
      ctx2d.lineWidth = 3;
      ctx2d.beginPath();
      ctx2d.moveTo(s1.x, s1.y);
      ctx2d.lineTo(s2.x, s2.y);
      ctx2d.stroke();

      // End dots
      ctx2d.setLineDash([]);
      ctx2d.fillStyle = '#ff9940';
      [s1, s2].forEach(p => {
        ctx2d.beginPath();
        ctx2d.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx2d.fill();
      });

      // Label at midpoint
      label.textContent = text;
      label.style.display = 'block';
      label.style.left = ((s1.x + s2.x) / 2) + 'px';
      label.style.top = ((s1.y + s2.y) / 2 - 20) + 'px';

      e.stopPropagation();
      e.preventDefault();
    }, true);

    const endMeasure = (e) => {
      if (!dragging || !this._measureActive) return;
      dragging = false;
      const endWorld = screenToWorld(e.clientX, e.clientY);
      if (!endWorld || !this._measureStart) return;

      const dx = endWorld.x - this._measureStart.world.x;
      const dz = endWorld.z - this._measureStart.world.z;
      const distWorld = Math.sqrt(dx * dx + dz * dz);
      const feet = distWorld;
      const ft = Math.floor(feet);
      const inches = Math.round((feet - ft) * 12);
      const text = `${ft}'${inches}" (${feet.toFixed(2)} ft)`;

      // Copy to clipboard
      navigator.clipboard.writeText(text).then(() => {
        UI.showToast(`${text} — copied`, 'success');
      }).catch(() => {
        UI.showToast(text, 'info');
      });

      // Fade out after a moment
      setTimeout(() => {
        const ctx2d = canvas.getContext('2d');
        ctx2d.clearRect(0, 0, canvas.width, canvas.height);
        label.style.display = 'none';
      }, 1200);

      this._measureStart = null;
      e.stopPropagation();
      e.preventDefault();
    };

    overlay.addEventListener('mouseup', endMeasure);
  },

  initZoomSlider() {
    const slider = document.getElementById('zoom-slider');
    const label = document.getElementById('zoom-label');
    if (!slider) return;

    // Capture default distance on first frame
    const captureDefault = () => {
      if (!this._defaultCamDist && this.controls) {
        this._defaultCamDist = this.camera.position.distanceTo(this.controls.target);
      }
    };
    setTimeout(captureDefault, 100);

    slider.addEventListener('input', () => {
      captureDefault();
      const pct = parseInt(slider.value);
      if (label) label.textContent = pct + '%';
      // 100% = default distance. Higher % = closer. Lower = further.
      const scale = 100 / pct;
      const dir = this.camera.position.clone().sub(this.controls.target).normalize();
      const newDist = this._defaultCamDist * scale;
      this.camera.position.copy(this.controls.target).addScaledVector(dir, newDist);
      this.controls.update();
    });

    // Sync slider when user scrolls to zoom
    this.renderer.domElement.addEventListener('wheel', () => {
      captureDefault();
      setTimeout(() => {
        const dist = this.camera.position.distanceTo(this.controls.target);
        const pct = Math.round((this._defaultCamDist / dist) * 100);
        slider.value = Math.max(10, Math.min(200, pct));
        if (label) label.textContent = slider.value + '%';
      }, 50);
    });
  },

  initDimSteppers() {
    const lengthSel = document.getElementById('truck-length-select');
    const widthSel = document.getElementById('truck-width-select');
    const lengthDisp = document.getElementById('truck-length-display');
    const widthDisp = document.getElementById('truck-width-display');

    document.querySelectorAll('.dim-step-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const dim = btn.dataset.dim;
        const dir = parseInt(btn.dataset.dir);
        const sel = dim === 'length' ? lengthSel : widthSel;
        const disp = dim === 'length' ? lengthDisp : widthDisp;
        if (!sel) return;
        const newIdx = sel.selectedIndex + dir;
        if (newIdx < 0 || newIdx >= sel.options.length) return;
        sel.selectedIndex = newIdx;
        sel.dispatchEvent(new Event('change'));
        disp.textContent = sel.options[newIdx].text;
      });
    });
  },

  _equipLightsOn: true,

  initLightsToggle() {
    const btn = document.getElementById('btn-lights-toggle');
    if (!btn) return;
    btn.classList.add('active');
    btn.addEventListener('click', () => {
      this._equipLightsOn = !this._equipLightsOn;
      btn.classList.toggle('active', this._equipLightsOn);
      // Toggle all equipment lights and glow meshes in placed items
      this.placedItems.forEach(item => {
        item.traverse(child => {
          if (child.userData.isEquipLight) {
            child.visible = this._equipLightsOn;
          }
          if (child.userData.isLightGlow) {
            child.material.opacity = this._equipLightsOn ? 1 : 0.2;
            child.material.transparent = !this._equipLightsOn;
          }
        });
      });
      UI.showToast('Equipment lights: ' + (this._equipLightsOn ? 'ON' : 'OFF'), 'info');
    });
  },

  initReportsMenu() {
    const self = this;
    const openPanel = (title, html) => {
      const overlay = document.getElementById('quote-overlay');
      const panel = document.getElementById('quote-panel');
      if (!overlay || !panel) return;
      const header = panel.querySelector('.quote-header h2');
      const body = panel.querySelector('.quote-body');
      if (header) header.textContent = title;
      if (body) body.innerHTML = html;
      overlay.classList.remove('hidden');
    };

    const actionBtn = (label, cls) => `<button class="btn-action report-action${cls ? ' ' + cls : ''}">${label}</button>`;

    // ---- COST BREAKDOWN ----
    const costsBtn = document.getElementById('btn-show-costs');
    if (costsBtn) costsBtn.addEventListener('click', () => {
      const items = self.placedItems;
      let equipCost = 0;
      const lines = [];
      const counts = {};
      items.forEach(item => {
        const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
        if (!def) return;
        const name = def.name;
        if (!counts[name]) counts[name] = { count: 0, unit: def.cost || 0 };
        counts[name].count++;
        equipCost += def.cost || 0;
      });
      for (const [name, info] of Object.entries(counts)) {
        lines.push(`<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border);font-size:12px;"><span>${info.count}× ${name}</span><span style="font-family:monospace;">$${(info.unit * info.count).toLocaleString()}</span></div>`);
      }
      const labor = Math.round(equipCost * 0.25);
      const materials = Math.round(equipCost * 0.15);
      const total = equipCost + labor + materials;
      const markup = `
        <div style="margin-top:12px;padding-top:10px;border-top:2px solid var(--border);">
          <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px;"><span>Equipment Subtotal</span><span style="font-family:monospace;">$${equipCost.toLocaleString()}</span></div>
          <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px;color:var(--text-secondary);"><span>Labor (est. 25%)</span><span style="font-family:monospace;">$${labor.toLocaleString()}</span></div>
          <div style="display:flex;justify-content:space-between;padding:3px 0;font-size:12px;color:var(--text-secondary);"><span>Materials (est. 15%)</span><span style="font-family:monospace;">$${materials.toLocaleString()}</span></div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;font-size:14px;font-weight:700;border-top:2px solid var(--accent);margin-top:6px;"><span>Quote Total</span><span style="font-family:monospace;color:var(--accent-deep);">$${total.toLocaleString()}</span></div>
        </div>`;
      const actions = `<div style="display:flex;gap:6px;margin-top:14px;">
        ${actionBtn('Copy to Clipboard', 'copy-costs')}
        ${actionBtn('Download CSV', 'dl-costs-csv')}
        ${actionBtn('Print', 'print-costs')}
      </div>`;
      openPanel('COST BREAKDOWN', (lines.length ? lines.join('') : '<p style="color:var(--text-muted);font-size:12px;">Place equipment to see costs.</p>') + markup + actions);
      // Wire actions
      const body = document.querySelector('#quote-panel .quote-body');
      body.querySelector('.copy-costs')?.addEventListener('click', () => {
        const text = Object.entries(counts).map(([n, i]) => `${i.count}x ${n}: $${(i.unit*i.count).toLocaleString()}`).join('\n') + `\n---\nTotal: $${total.toLocaleString()}`;
        navigator.clipboard.writeText(text).then(() => UI.showToast('Copied', 'success'));
      });
      body.querySelector('.dl-costs-csv')?.addEventListener('click', () => {
        let csv = 'Item,Qty,Unit Cost,Total\n';
        for (const [n, i] of Object.entries(counts)) csv += `"${n}",${i.count},${i.unit},${i.unit*i.count}\n`;
        csv += `\nLabor (25%),,,$${labor}\nMaterials (15%),,,$${materials}\nTOTAL,,,$${total}`;
        const blob = new Blob([csv], {type:'text/csv'});
        const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'cost-breakdown.csv'; a.click();
        UI.showToast('Downloaded CSV', 'success');
      });
      body.querySelector('.print-costs')?.addEventListener('click', () => { window.print(); });
    });

    // ---- COMPLIANCE CHECKS ----
    const compBtn = document.getElementById('btn-show-compliance');
    if (compBtn) compBtn.addEventListener('click', () => {
      const hasItem = (id) => self.placedItems.some(i => i.userData.equipId === id);
      const hasCold = self.placedItems.some(i => ['refrigerator','freezer','under-counter-fridge','sandwich-prep','chest-freezer','glass-door-cooler'].includes(i.userData.equipId));
      const hasWindow = self.placedItems.some(i => i.userData.equipId.includes('window') || i.userData.equipId === 'cash-register');
      const checks = [
        { label: 'Hand wash sink', ok: hasItem('hand-wash-sink'), fix: 'Add a Hand Wash Sink from Sinks category' },
        { label: '3-compartment sink', ok: hasItem('3-comp-sink'), fix: 'Add a 3-Comp Sink — required by health dept. for washing/rinsing/sanitizing' },
        { label: 'Exhaust hood over cooking', ok: hasItem('hood-exhaust'), fix: 'Add Hood / Exhaust — required over any cooking equipment producing grease-laden vapors' },
        { label: 'Fire suppression system', ok: hasItem('fire-suppression'), fix: 'Add Fire Suppression — required under hood for all commercial cooking' },
        { label: 'Cold storage present', ok: hasCold, fix: 'Add a Refrigerator or Freezer for food-safe temp storage' },
        { label: 'Service window / POS', ok: hasWindow, fix: 'Add a Serving Window or Cash Register for customer interaction' }
      ];
      const passed = checks.filter(c => c.ok).length;
      const html = checks.map(c => `
        <div style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);">
          <span style="font-size:16px;line-height:1;">${c.ok ? '✅' : '⚠️'}</span>
          <div>
            <div style="font-size:12px;font-weight:600;color:${c.ok ? 'var(--accent-deep)' : 'var(--text-primary)'}">${c.label}</div>
            ${c.ok ? '' : '<div style="font-size:11px;color:var(--text-secondary);margin-top:2px;">' + c.fix + '</div>'}
          </div>
        </div>`).join('');
      const summary = `<div style="margin-bottom:12px;padding:10px;background:${passed === checks.length ? 'rgba(42,157,143,0.08)' : 'rgba(232,160,32,0.08)'};border-radius:6px;font-size:13px;font-weight:600;color:${passed === checks.length ? 'var(--accent-deep)' : '#b8860b'};">${passed}/${checks.length} checks passed${passed === checks.length ? ' — ready for inspection' : ' — review items below'}</div>`;
      const actions = `<div style="display:flex;gap:6px;margin-top:14px;">
        ${actionBtn('Copy Report', 'copy-compliance')}
        ${actionBtn('Print', 'print-compliance')}
      </div>`;
      openPanel('COMPLIANCE CHECKS', summary + html + actions);
      const body = document.querySelector('#quote-panel .quote-body');
      body.querySelector('.copy-compliance')?.addEventListener('click', () => {
        const text = checks.map(c => `${c.ok ? '✓' : '✗'} ${c.label}${c.ok ? '' : ' — ' + c.fix}`).join('\n');
        navigator.clipboard.writeText(text).then(() => UI.showToast('Copied', 'success'));
      });
      body.querySelector('.print-compliance')?.addEventListener('click', () => { window.print(); });
    });

    // ---- BILL OF MATERIALS ----
    const bomBtn = document.getElementById('btn-show-bom');
    if (bomBtn) bomBtn.addEventListener('click', () => {
      const counts = {};
      self.placedItems.forEach(item => {
        const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
        if (!def) return;
        if (!counts[def.id]) counts[def.id] = { name: def.name, count: 0, cost: def.cost || 0, w: def.widthCells/2, d: def.depthCells/2, h: def.heightCells/2, desc: def.description || '' };
        counts[def.id].count++;
      });
      const rows = Object.values(counts);
      let html = '<table style="width:100%;border-collapse:collapse;font-size:11px;">';
      html += '<tr style="border-bottom:2px solid var(--border);text-align:left;"><th style="padding:4px;">Qty</th><th style="padding:4px;">Item</th><th style="padding:4px;">Size</th><th style="padding:4px;text-align:right;">Unit</th><th style="padding:4px;text-align:right;">Total</th></tr>';
      let grandTotal = 0;
      rows.forEach(r => {
        const total = r.cost * r.count;
        grandTotal += total;
        html += `<tr style="border-bottom:1px solid var(--border);"><td style="padding:4px;font-weight:700;">${r.count}</td><td style="padding:4px;">${r.name}<div style="font-size:9px;color:var(--text-muted);">${r.desc}</div></td><td style="padding:4px;font-family:monospace;font-size:10px;">${r.w}'×${r.d}'×${r.h}'</td><td style="padding:4px;text-align:right;font-family:monospace;">$${r.cost.toLocaleString()}</td><td style="padding:4px;text-align:right;font-family:monospace;font-weight:600;">$${total.toLocaleString()}</td></tr>`;
      });
      html += `<tr style="border-top:2px solid var(--accent);"><td colspan="4" style="padding:6px;font-weight:700;">Grand Total</td><td style="padding:6px;text-align:right;font-family:monospace;font-weight:700;font-size:13px;color:var(--accent-deep);">$${grandTotal.toLocaleString()}</td></tr></table>`;
      if (rows.length === 0) html = '<p style="color:var(--text-muted);font-size:12px;">Place equipment to generate BOM.</p>';
      const actions = `<div style="display:flex;gap:6px;margin-top:14px;">
        ${actionBtn('Copy to Clipboard', 'copy-bom2')}
        ${actionBtn('Download CSV', 'dl-bom-csv')}
        ${actionBtn('Print', 'print-bom')}
      </div>`;
      openPanel('BILL OF MATERIALS', html + actions);
      const body = document.querySelector('#quote-panel .quote-body');
      body.querySelector('.copy-bom2')?.addEventListener('click', () => {
        const text = rows.map(r => `${r.count}x ${r.name} (${r.w}'×${r.d}'×${r.h}') — $${(r.cost*r.count).toLocaleString()}`).join('\n') + `\nTotal: $${grandTotal.toLocaleString()}`;
        navigator.clipboard.writeText(text).then(() => UI.showToast('Copied', 'success'));
      });
      body.querySelector('.dl-bom-csv')?.addEventListener('click', () => {
        let csv = 'Qty,Item,Description,Width ft,Depth ft,Height ft,Unit Cost,Total\n';
        rows.forEach(r => csv += `${r.count},"${r.name}","${r.desc}",${r.w},${r.d},${r.h},${r.cost},${r.cost*r.count}\n`);
        const blob = new Blob([csv], {type:'text/csv'});
        const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'bill-of-materials.csv'; a.click();
        UI.showToast('Downloaded CSV', 'success');
      });
      body.querySelector('.print-bom')?.addEventListener('click', () => { window.print(); });
    });

    // ---- BUILD CHECKLIST ----
    const clBtn = document.getElementById('btn-show-checklist');
    if (clBtn) clBtn.addEventListener('click', () => {
      const items = self.placedItems;
      const hasItem = (id) => items.some(i => i.userData.equipId === id);
      const steps = [
        { phase: 'Prep', tasks: ['Strip chassis to bare frame', 'Sand and prime all surfaces', 'Weld mounting brackets'] },
        { phase: 'Structure', tasks: ['Install floor pan and level', 'Frame walls', 'Install ceiling joists', 'Mount wheel well covers'] },
        { phase: 'Surfaces', tasks: ['Install floor material', 'Mount wall panels', 'Seal all joints and seams'] },
        { phase: 'Plumbing', tasks: hasItem('3-comp-sink') || hasItem('hand-wash-sink') ? ['Run fresh water supply lines', 'Run grey water drain lines', 'Install water heater if needed', 'Mount sinks and connect', 'Pressure test all connections'] : ['No plumbing items placed'] },
        { phase: 'Electrical', tasks: ['Run main power feed from generator bay', 'Install breaker panel', 'Wire all outlets and equipment circuits', 'Install lighting', 'Test all circuits'] },
        { phase: 'Gas', tasks: hasItem('propane-tank') ? ['Mount propane tank', 'Run gas lines to equipment', 'Install gas shutoff valve', 'Pressure test and leak check'] : ['No gas items placed'] },
        { phase: 'Equipment', tasks: items.length > 0 ? ['Position and secure all equipment', 'Connect utilities to each unit', 'Test each piece individually'] : ['No equipment placed yet'] },
        { phase: 'Safety', tasks: ['Install fire suppression system', 'Mount fire extinguisher', 'Install emergency exit signage', 'Test hood ventilation airflow'] },
        { phase: 'Final', tasks: ['Full systems test under load', 'Health department pre-inspection', 'Touch-up paint and detailing', 'Client walkthrough'] }
      ];
      let html = '';
      steps.forEach(s => {
        html += `<div style="margin-bottom:10px;"><div style="font-size:10px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:var(--accent-deep);margin-bottom:4px;">${s.phase}</div>`;
        s.tasks.forEach(t => {
          html += `<label style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12px;cursor:pointer;"><input type="checkbox" class="pill-toggle" style="width:28px !important;height:15px;flex-shrink:0;"><span>${t}</span></label>`;
        });
        html += '</div>';
      });
      const actions = `<div style="display:flex;gap:6px;margin-top:14px;">
        ${actionBtn('Copy Checklist', 'copy-cl')}
        ${actionBtn('Download', 'dl-cl')}
        ${actionBtn('Print', 'print-cl')}
      </div>`;
      openPanel('BUILD CHECKLIST', html + actions);
      const body = document.querySelector('#quote-panel .quote-body');
      body.querySelector('.copy-cl')?.addEventListener('click', () => {
        const text = steps.map(s => s.phase + ':\n' + s.tasks.map(t => '  [ ] ' + t).join('\n')).join('\n\n');
        navigator.clipboard.writeText(text).then(() => UI.showToast('Copied', 'success'));
      });
      body.querySelector('.dl-cl')?.addEventListener('click', () => {
        const text = steps.map(s => s.phase.toUpperCase() + '\n' + s.tasks.map(t => '[ ] ' + t).join('\n')).join('\n\n');
        const blob = new Blob([text], {type:'text/plain'});
        const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'build-checklist.txt'; a.click();
        UI.showToast('Downloaded', 'success');
      });
      body.querySelector('.print-cl')?.addEventListener('click', () => { window.print(); });
    });

    // ---- INTERNAL NOTES ----
    const notesBtn = document.getElementById('btn-show-notes');
    if (notesBtn) notesBtn.addEventListener('click', () => {
      const notes = document.getElementById('internal-notes');
      const html = `
        <textarea id="notes-editor" style="width:100%;min-height:250px;padding:12px;border:1px solid var(--border);border-radius:6px;font-family:inherit;font-size:13px;resize:vertical;line-height:1.6;">${notes ? notes.value : ''}</textarea>
        <div style="display:flex;gap:6px;margin-top:10px;">
          ${actionBtn('Save Notes', 'save-notes')}
          ${actionBtn('Copy', 'copy-notes')}
          ${actionBtn('Clear', 'clear-notes')}
        </div>`;
      openPanel('INTERNAL NOTES', html);
      const body = document.querySelector('#quote-panel .quote-body');
      body.querySelector('.save-notes')?.addEventListener('click', () => {
        const editor = document.getElementById('notes-editor');
        if (editor && notes) { notes.value = editor.value; UI.showToast('Notes saved', 'success'); }
      });
      body.querySelector('.copy-notes')?.addEventListener('click', () => {
        const editor = document.getElementById('notes-editor');
        if (editor) navigator.clipboard.writeText(editor.value).then(() => UI.showToast('Copied', 'success'));
      });
      body.querySelector('.clear-notes')?.addEventListener('click', () => {
        const editor = document.getElementById('notes-editor');
        if (editor && confirm('Clear all notes?')) { editor.value = ''; if (notes) notes.value = ''; }
      });
    });
  },

  initTopbarMenus() {
    // Wire up any topbar dropdown menus
    document.querySelectorAll('.topbar-menu-wrap').forEach(wrap => {
      const btn = wrap.querySelector('.top-btn');
      const menu = wrap.querySelector('.topbar-dropdown');
      if (!btn || !menu) return;
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        // Close all other menus first
        document.querySelectorAll('.topbar-dropdown').forEach(m => {
          if (m !== menu) m.classList.add('hidden');
        });
        menu.classList.toggle('hidden');
      });
      // Close when clicking a menu item
      menu.querySelectorAll('.dropdown-item').forEach(item => {
        item.addEventListener('click', () => menu.classList.add('hidden'));
      });
    });
    // Close all menus when clicking outside
    document.addEventListener('click', () => {
      document.querySelectorAll('.topbar-dropdown').forEach(m => m.classList.add('hidden'));
    });
  },

  initSoundToggle() {
    const btn = document.getElementById('btn-sound-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      this._soundEnabled = !this._soundEnabled;
      btn.textContent = this._soundEnabled ? '🔊' : '🔇';
      btn.style.opacity = this._soundEnabled ? '1' : '0.5';
    });
  },

  initExitButton() {
    const btn = document.getElementById('btn-exit');
    if (!btn) return;
    btn.addEventListener('click', () => {
      // Auto-save before exit
      this.autoSave();

      const audio = new Audio('sounds/coolman.webm');
      audio.volume = 0.18;
      audio.play().catch(() => {});

      // Wait for the full clip to finish, then close
      audio.addEventListener('ended', () => {
        try { window.close(); } catch(e) {}
        setTimeout(() => {
          document.body.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100vh;background:#f8f9fa;font-family:sans-serif;color:#1a1a2e;"><div style="text-align:center;"><h1 style="font-size:24px;margin-bottom:8px;">Cool man, alright.</h1><p style="color:#9aa0a6;">You can close this tab.</p></div></div>';
        }, 200);
      });
      // Fallback if audio fails to load/play
      audio.addEventListener('error', () => {
        try { window.close(); } catch(e) {}
      });
    });
  },

  // ---- Surface Materials ----
  initSurfaceSwatches() {
    document.querySelectorAll('#floor-swatches .swatch').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#floor-swatches .swatch').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.setFloorMaterial(btn.dataset.floor);
      });
    });
    document.querySelectorAll('#wall-swatches .swatch').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('#wall-swatches .swatch').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.setWallMaterial(btn.dataset.wall);
      });
    });

    // Wall visibility cycle: auto (dynamic) → full → low → off
    const wallsBtn = document.getElementById('btn-walls-cycle');
    const wallsDropdown = document.getElementById('walls-slider-dropdown');
    if (wallsBtn) {
      const updateLabel = () => {
        wallsBtn.textContent = 'WALLS: ' + this.wallVisibility.toUpperCase();
        wallsBtn.classList.toggle('active', this.wallVisibility !== 'auto');
      };
      updateLabel();
      // Left click: cycle wall mode
      wallsBtn.addEventListener('click', (e) => {
        const order = ['auto', 'full', 'low', 'off'];
        const idx = order.indexOf(this.wallVisibility);
        this.wallVisibility = order[(idx + 1) % order.length];
        updateLabel();
        UI.showToast('Walls: ' + this.wallVisibility.toUpperCase(), 'info');
      });
      // Right click: toggle opacity slider dropdown
      wallsBtn.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        if (wallsDropdown) wallsDropdown.classList.toggle('open');
      });
      // Close dropdown when clicking elsewhere
      document.addEventListener('click', (e) => {
        if (wallsDropdown && !wallsBtn.contains(e.target) && !wallsDropdown.contains(e.target)) {
          wallsDropdown.classList.remove('open');
        }
      });
    }

    // Roof toggle
    const roofBtn = document.getElementById('btn-roof-toggle');
    if (roofBtn) {
      roofBtn.classList.toggle('active', this.showRoof);
      roofBtn.addEventListener('click', () => {
        this.showRoof = !this.showRoof;
        roofBtn.classList.toggle('active', this.showRoof);
        if (this._ceilingMesh) {
          this._ceilingMesh.visible = this.showRoof;
        }
        UI.showToast('Roof: ' + (this.showRoof ? 'ON' : 'OFF'), 'info');
      });
    }

    // Front wall opacity slider
    const frontSlider = document.getElementById('front-wall-slider');
    const frontLabel = document.getElementById('front-wall-label');
    if (frontSlider) {
      frontSlider.addEventListener('input', () => {
        const pct = parseInt(frontSlider.value);
        this.frontWallOpacity = pct / 100;
        if (frontLabel) frontLabel.textContent = pct + '%';
        this.buildTruck();
        this.buildGridOverlay();
      });
    }

    // Wheel wells visibility toggle (in view-preset bar)
    const wellsBtn = document.getElementById('btn-wheels-toggle');
    if (wellsBtn) {
      wellsBtn.classList.toggle('active', this.showWheelWells);
      wellsBtn.addEventListener('click', () => {
        this.showWheelWells = !this.showWheelWells;
        wellsBtn.classList.toggle('active', this.showWheelWells);
        // Also sync the internal checkbox if present
        const cb = document.getElementById('wheel-wells-toggle');
        if (cb) cb.checked = this.showWheelWells;
        this.buildTruck();
        this.buildGridOverlay();
        UI.showToast('Wheel wells ' + (this.showWheelWells ? 'ON' : 'OFF'), 'info');
      });
    }

    // Background cycle
    const bgBtn = document.getElementById('btn-bg-cycle');
    if (bgBtn) {
      bgBtn.addEventListener('click', () => {
        const order = ['light', 'grey', 'dark', 'asphalt', 'concrete', 'checker'];
        const idx = order.indexOf(this.sceneBackground);
        this.sceneBackground = order[(idx + 1) % order.length];
        this.applySceneBackground();
        bgBtn.textContent = 'BG: ' + this.sceneBackground.toUpperCase();
      });
    }
  },

  // ---- Scene Background ----
  applySceneBackground() {
    const type = this.sceneBackground;

    // Remove the current ground plane
    const oldGround = this.scene.getObjectByName('ground-plane');
    if (oldGround) this.scene.remove(oldGround);

    // Set scene clear color — never pure white; keep a grey tone so equipment pops
    const bgColors = {
      light: 0xd0d4d8,
      grey: 0x999999,
      dark: 0x333333,
      asphalt: 0x1a1a1a,
      concrete: 0x888888,
      checker: 0x777777
    };
    this.scene.background = new THREE.Color(bgColors[type] || 0xb0b0b0);

    // Ground plane — MASSIVE so it always fills the view and never shows an edge
    const groundGeo = new THREE.PlaneGeometry(5000, 5000);
    let groundMat;

    if (type === 'asphalt') {
      const canvas = document.createElement('canvas');
      canvas.width = 512; canvas.height = 512;
      const ctx = canvas.getContext('2d');
      // Dark asphalt base
      ctx.fillStyle = '#1e1e1e';
      ctx.fillRect(0, 0, 512, 512);
      // Noise specks
      for (let i = 0; i < 8000; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 512;
        const shade = 20 + Math.random() * 40;
        const size = 1 + Math.random() * 2;
        ctx.fillStyle = `rgb(${shade},${shade},${shade})`;
        ctx.fillRect(x, y, size, size);
      }
      // Yellow parking line
      ctx.strokeStyle = '#d4a017';
      ctx.lineWidth = 4;
      ctx.setLineDash([20, 15]);
      ctx.beginPath();
      ctx.moveTo(256, 0);
      ctx.lineTo(256, 512);
      ctx.stroke();
      const tex = new THREE.CanvasTexture(canvas);
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(500, 500);
      groundMat = new THREE.MeshPhongMaterial({ map: tex, flatShading: true });
    } else if (type === 'concrete') {
      const canvas = document.createElement('canvas');
      canvas.width = 512; canvas.height = 512;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#6a6a6a';
      ctx.fillRect(0, 0, 512, 512);
      // Concrete texture noise
      for (let i = 0; i < 5000; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 512;
        const shade = 80 + Math.random() * 60;
        ctx.fillStyle = `rgba(${shade},${shade},${shade},0.5)`;
        ctx.fillRect(x, y, 2, 2);
      }
      // Expansion joint lines
      ctx.strokeStyle = '#333';
      ctx.lineWidth = 2;
      ctx.strokeRect(0, 0, 512, 512);
      ctx.beginPath();
      ctx.moveTo(256, 0);
      ctx.lineTo(256, 512);
      ctx.moveTo(0, 256);
      ctx.lineTo(512, 256);
      ctx.stroke();
      const tex = new THREE.CanvasTexture(canvas);
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(400, 400);
      groundMat = new THREE.MeshPhongMaterial({ map: tex, flatShading: true });
    } else if (type === 'checker') {
      const canvas = document.createElement('canvas');
      canvas.width = 64; canvas.height = 64;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#444';
      ctx.fillRect(0, 0, 64, 64);
      ctx.fillStyle = '#666';
      ctx.fillRect(0, 0, 32, 32);
      ctx.fillRect(32, 32, 32, 32);
      const tex = new THREE.CanvasTexture(canvas);
      tex.magFilter = THREE.NearestFilter;
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      tex.repeat.set(1500, 1500);
      groundMat = new THREE.MeshPhongMaterial({ map: tex, flatShading: true });
    } else {
      // Plain color modes: use ShadowMaterial — invisible except where shadows fall.
      // Soft, subtle shadow tint so there's no visible ground edge.
      groundMat = new THREE.ShadowMaterial({
        color: 0x000000,
        opacity: 0.2,
        transparent: true
      });
    }

    const ground = new THREE.Mesh(groundGeo, groundMat);
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = -2.5;  // Ground at bottom of wheels (floor is at Y=0, chassis + clearance = 2.5ft below)
    ground.receiveShadow = true;
    ground.name = 'ground-plane';
    this.scene.add(ground);
  },

  // ---- Utility Overlays ----
  initUtilityOverlays() {
    const equipBtn = document.getElementById('btn-util-equip');
    const buttons = {
      'electrical': document.getElementById('btn-util-elec'),
      'water': document.getElementById('btn-util-water'),
      'gas': document.getElementById('btn-util-gas')
    };

    const setActiveBtn = (btn) => {
      [equipBtn, ...Object.values(buttons)].forEach(b => b && b.classList.remove('active'));
      if (btn) btn.classList.add('active');
    };

    // EQUIP button clears utility overlay and returns to normal mode
    if (equipBtn) {
      equipBtn.addEventListener('click', () => {
        this.utilityMode = null;
        setActiveBtn(equipBtn);
        this.updateUtilityOverlay();
      });
    }

    Object.entries(buttons).forEach(([type, btn]) => {
      if (!btn) return;
      btn.addEventListener('click', () => {
        if (this.utilityMode === type) {
          // Clicking active button goes back to equip mode
          this.utilityMode = null;
          setActiveBtn(equipBtn);
        } else {
          this.utilityMode = type;
          setActiveBtn(btn);
        }
        this.updateUtilityOverlay();
      });
    });
  },

  updateUtilityOverlay() {
    // Remove existing overlay
    if (this.utilityGroup) {
      this.scene.remove(this.utilityGroup);
      this.utilityGroup = null;
    }
    this._utilityNodes = [];
    this._utilityDrawingFrom = null;

    // Toggle dim/blur overlay + mode-specific tint class
    const dimOverlay = document.getElementById('utility-mode-overlay');
    const hint = document.getElementById('utility-mode-hint');
    if (dimOverlay) {
      dimOverlay.classList.toggle('active', !!this.utilityMode);
      dimOverlay.classList.remove('mode-electrical', 'mode-water', 'mode-gas');
      if (this.utilityMode) dimOverlay.classList.add('mode-' + this.utilityMode);
    }
    if (hint) hint.classList.toggle('active', !!this.utilityMode);

    // Apply/remove scene tint (dim + shift toward utility color)
    this._applySceneTint(this.utilityMode);

    // Swap sidebar between equipment and utility tools
    this._updateSidebarMode();

    if (!this.utilityMode) {
      if (hint) hint.textContent = '';
      UI.setStatus('Select equipment to begin');
      return;
    }

    const type = this.utilityMode;
    const color = type === 'electrical' ? 0xffaa00 :
                  type === 'water' ? 0x4a9eff : 0xff6633;

    const group = new THREE.Group();
    group.name = 'utility-overlay';

    // Collect connection nodes on relevant items
    const sourceIds = UI._utilitySources[type] || [];
    const reqMap = UI._utilityRequirements;
    const sources = this.placedItems.filter(i => sourceIds.includes(i.userData.equipId));
    const consumers = this.placedItems.filter(i => {
      const needs = reqMap[i.userData.equipId] || [];
      return needs.includes(type) && !sourceIds.includes(i.userData.equipId);
    });

    // CS2-style auto-connection: items within a short path to any source are "connected"
    // Orange/warning color for items that have NO source or are too far
    const WARN_COLOR = 0xff7722;
    const MAX_AUTO_DIST = 12; // grid cells = ~6 ft — simulates road-embedded utility coverage

    const isConnected = (item) => {
      if (sources.length === 0) return false;
      const p = new THREE.Vector3(item.position.x, 0, item.position.z);
      for (const s of sources) {
        const d = Math.abs(p.x - s.position.x) + Math.abs(p.z - s.position.z);
        if (d <= MAX_AUTO_DIST) return true;
      }
      return false;
    };

    // Source nodes (bright utility color, always fully lit)
    sources.forEach(src => {
      const node = this._addUtilityNode(group, src, color, 'source', 0.18);
      this._utilityNodes.push(node);
    });
    // Consumer nodes — tinted orange if unconnected
    consumers.forEach(c => {
      const connected = isConnected(c);
      const nodeColor = connected ? color : WARN_COLOR;
      const node = this._addUtilityNode(group, c, nodeColor, 'consumer', 0.13);
      this._utilityNodes.push(node);
    });

    // Draw existing lines for this utility
    const existingLines = this.utilityLines[type] || [];
    existingLines.forEach(seg => {
      this._addUtilitySegment(group, seg.from, seg.to, color);
    });

    this.scene.add(group);
    this.utilityGroup = group;

    const typeName = type.charAt(0).toUpperCase() + type.slice(1);
    const unitName = type === 'electrical' ? 'wire' : type === 'water' ? 'PEX' : 'gas line';
    const hintEl = document.getElementById('utility-mode-hint');
    if (hintEl) {
      hintEl.textContent = `${typeName.toUpperCase()} — Click nodes to connect ${unitName} · Right-click to remove line`;
    }
    UI.setStatus(`${typeName} wiring mode — click a node to start a line, click another to connect, right-click a line to delete`);

    // Update total length display
    const total = existingLines.reduce((sum, s) => {
      const dx = Math.abs(s.to[0] - s.from[0]);
      const dz = Math.abs(s.to[2] - s.from[2]);
      return sum + Math.sqrt(dx * dx + dz * dz);
    }, 0);
    const feet = Math.round(total * 2);
    if (feet > 0) UI.showToast(`${typeName}: ${feet} ft of ${unitName} placed`, 'info');
  },

  _addUtilityNode(group, item, color, nodeType, radius) {
    // Lift node slightly above the item top for easy clicking
    const itemH = (item.userData.heightCells || 6) * CELL_SIZE;
    const pos = new THREE.Vector3(item.position.x, itemH * 0.5 + 0.3, item.position.z);

    // Bright core sphere (always visible)
    const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 1 });
    const sphere = new THREE.Mesh(new THREE.SphereGeometry(radius, 16, 12), mat);
    sphere.position.copy(pos);
    sphere.userData.isUtilityNode = true;
    sphere.userData.nodePos = pos.clone();
    sphere.userData.itemId = item.userData.equipId;
    group.add(sphere);

    // Glowing halo ring around the node
    const halo = new THREE.Mesh(
      new THREE.TorusGeometry(radius * 1.8, radius * 0.22, 8, 24),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7 })
    );
    halo.rotation.x = -Math.PI / 2;
    halo.position.copy(pos);
    group.add(halo);

    // Source items get an extra prominent outer ring + vertical beam
    if (nodeType === 'source') {
      const outerRing = new THREE.Mesh(
        new THREE.TorusGeometry(radius * 2.8, radius * 0.18, 8, 28),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 })
      );
      outerRing.rotation.x = -Math.PI / 2;
      outerRing.position.copy(pos);
      group.add(outerRing);
      // Vertical column of light
      const beam = new THREE.Mesh(
        new THREE.CylinderGeometry(radius * 0.3, radius * 0.3, itemH * 1.5, 8),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.3 })
      );
      beam.position.set(pos.x, itemH * 0.75, pos.z);
      group.add(beam);
    }

    // Dashed line from node DOWN to the item base (shows connection to physical equipment)
    const dashedGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(pos.x, 0.02, pos.z),
      new THREE.Vector3(pos.x, pos.y, pos.z)
    ]);
    const dashedMat = new THREE.LineDashedMaterial({
      color, dashSize: 0.12, gapSize: 0.08, transparent: true, opacity: 0.55
    });
    const stem = new THREE.Line(dashedGeo, dashedMat);
    stem.computeLineDistances();
    group.add(stem);

    return { mesh: sphere, pos: pos.clone(), itemId: item.userData.equipId, type: nodeType };
  },

  _addUtilitySegment(group, from, to, color) {
    const a = new THREE.Vector3(from[0], from[1], from[2]);
    const b = new THREE.Vector3(to[0], to[1], to[2]);
    // Manhattan L-route: x first, then z
    const mid = new THREE.Vector3(b.x, a.y, a.z);
    const pts = [a, mid, b];
    const lineMat = new THREE.LineBasicMaterial({ color, linewidth: 3, transparent: true, opacity: 0.95 });
    const lineGeo = new THREE.BufferGeometry().setFromPoints(pts);
    const line = new THREE.Line(lineGeo, lineMat);
    line.userData.isUtilitySegment = true;
    line.userData.segFrom = from;
    line.userData.segTo = to;
    group.add(line);

    // Also draw thick tubes for visibility
    for (let i = 0; i < pts.length - 1; i++) {
      const p1 = pts[i], p2 = pts[i + 1];
      const len = p1.distanceTo(p2);
      if (len < 0.01) continue;
      const cyl = new THREE.Mesh(
        new THREE.CylinderGeometry(0.035, 0.035, len, 8),
        new THREE.MeshBasicMaterial({ color })
      );
      const midPt = p1.clone().add(p2).multiplyScalar(0.5);
      cyl.position.copy(midPt);
      const dir = p2.clone().sub(p1).normalize();
      cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
      cyl.userData.isUtilitySegment = true;
      cyl.userData.segFrom = from;
      cyl.userData.segTo = to;
      group.add(cyl);
    }
  },

  _updateSidebarMode() {
    const eqPanel = document.getElementById('equipment-panel');
    const utilPanel = document.getElementById('utility-panel');
    const title = document.getElementById('utility-panel-title');
    const stats = document.getElementById('utility-stats');
    if (!eqPanel || !utilPanel) return;

    if (!this.utilityMode) {
      eqPanel.style.display = '';
      utilPanel.style.display = 'none';
      return;
    }

    // Show utility panel
    eqPanel.style.display = 'none';
    utilPanel.style.display = '';
    utilPanel.classList.remove('mode-electrical', 'mode-water', 'mode-gas');
    utilPanel.classList.add('mode-' + this.utilityMode);

    const labels = {
      electrical: 'ELECTRICAL WIRING',
      water: 'WATER / PEX LINES',
      gas: 'GAS LINES'
    };
    if (title) title.textContent = labels[this.utilityMode] || 'UTILITY';

    // Show line length, connection counts, etc.
    if (stats) {
      const lines = this.utilityLines[this.utilityMode] || [];
      let total = 0;
      lines.forEach(s => {
        const dx = Math.abs(s.to[0] - s.from[0]);
        const dz = Math.abs(s.to[2] - s.from[2]);
        total += dx + dz; // Manhattan
      });
      const feet = Math.round(total * 2);
      const unitName = this.utilityMode === 'electrical' ? 'wire' :
                       this.utilityMode === 'water' ? 'PEX' : 'gas line';
      stats.innerHTML = `
        <div class="stat-row"><span>Segments</span><span>${lines.length}</span></div>
        <div class="stat-row"><span>Total ${unitName}</span><span>${feet} ft</span></div>
        <div class="stat-row"><span>Nodes</span><span>${this._utilityNodes.length}</span></div>
      `;
    }
  },

  // Apply / remove a scene-wide tint for utility mode
  _applySceneTint(mode) {
    const tintMap = {
      electrical: new THREE.Color(0x7a5a20),
      water: new THREE.Color(0x1e4860),
      gas: new THREE.Color(0x6a2818)
    };
    const tintFactor = 0.55; // how much toward the tint (0 = no change, 1 = full tint)

    const processMesh = (mesh) => {
      if (!mesh.material || !mesh.material.color) return;
      if (!mesh.userData._origColor) {
        mesh.userData._origColor = mesh.material.color.getHex();
      }
      if (!mode) {
        // Restore
        mesh.material.color.setHex(mesh.userData._origColor);
      } else {
        // Blend original toward tint
        const orig = new THREE.Color(mesh.userData._origColor);
        const tint = tintMap[mode];
        if (!tint) return;
        const r = orig.r * (1 - tintFactor) + tint.r * tintFactor;
        const g = orig.g * (1 - tintFactor) + tint.g * tintFactor;
        const b = orig.b * (1 - tintFactor) + tint.b * tintFactor;
        mesh.material.color.setRGB(r * 0.6, g * 0.6, b * 0.6); // also darken
      }
    };

    // Tint all placed items
    this.placedItems.forEach(item => {
      item.traverse(c => { if (c.isMesh) processMesh(c); });
    });

    // Tint truck walls
    if (this._truckWalls) {
      this._truckWalls.forEach(w => processMesh(w.mesh));
    }

    // Tint floor
    if (this.floorMesh) processMesh(this.floorMesh);
  },

  // Handle click in utility mode — node-to-node line drawing
  handleUtilityClick(event) {
    if (!this.utilityMode) return false;
    const canvas = this.renderer.domElement;
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.mouse, this.camera);

    // Find a utility node under the cursor
    const nodeMeshes = this._utilityNodes.map(n => n.mesh);
    const hits = this.raycaster.intersectObjects(nodeMeshes, false);
    if (hits.length === 0) return true; // consume event

    const nodeMesh = hits[0].object;
    const nodePos = nodeMesh.userData.nodePos;

    if (!this._utilityDrawingFrom) {
      // Start a new line from this node
      this._utilityDrawingFrom = [nodePos.x, nodePos.y, nodePos.z];
      // Visual feedback — highlight the source node
      nodeMesh.material.color.setHex(0xffffff);
      UI.setStatus('Click another node to connect');
    } else {
      // Complete the line
      const toPos = [nodePos.x, nodePos.y, nodePos.z];
      const from = this._utilityDrawingFrom;
      if (!(from[0] === toPos[0] && from[2] === toPos[2])) {
        this.utilityLines[this.utilityMode].push({ from, to: toPos });
        this.autoSave();
      }
      this._utilityDrawingFrom = null;
      this.updateUtilityOverlay();
    }
    return true;
  },

  handleUtilityRightClick(event) {
    if (!this.utilityMode) return false;
    // Cancel in-progress line first
    if (this._utilityDrawingFrom) {
      this._utilityDrawingFrom = null;
      this.updateUtilityOverlay();
      return true;
    }
    // Find segment under cursor and delete it
    const canvas = this.renderer.domElement;
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.mouse, this.camera);

    if (!this.utilityGroup) return true;
    const segs = [];
    this.utilityGroup.traverse(c => {
      if (c.userData.isUtilitySegment) segs.push(c);
    });
    const hits = this.raycaster.intersectObjects(segs, false);
    if (hits.length > 0) {
      const hit = hits[0].object;
      const segFrom = hit.userData.segFrom;
      const segTo = hit.userData.segTo;
      const arr = this.utilityLines[this.utilityMode];
      const idx = arr.findIndex(s =>
        s.from[0] === segFrom[0] && s.from[2] === segFrom[2] &&
        s.to[0] === segTo[0] && s.to[2] === segTo[2]
      );
      if (idx !== -1) {
        arr.splice(idx, 1);
        this.updateUtilityOverlay();
        UI.showToast('Line removed', 'info');
      }
    }
    return true;
  },

  // ---- Internal Quick Actions ----
  initInternalQuickActions() {
    const dup = document.getElementById('btn-duplicate');
    if (dup) dup.addEventListener('click', () => this.duplicateSelected());

    const cv = document.getElementById('btn-center-view');
    if (cv) cv.addEventListener('click', () => {
      // Re-center orbit target on the full truck (box body + cab)
      const truckW = this.gridCellsX * CELL_SIZE;
      const truckD = this.gridCellsZ * CELL_SIZE;
      this.controls.target.set(truckW / 2 - 2.5, 2, truckD / 2);
      this.controls.update();
      UI.showToast('Centered', 'info');
    });

    const print = document.getElementById('btn-print');
    if (print) print.addEventListener('click', () => window.print());

    const reset = document.getElementById('btn-reset-camera');
    if (reset) reset.addEventListener('click', () => {
      // Full reset — default position, zoom, angle (accounts for cab)
      const cx = this.truckLengthFt * CELL_SIZE * CELLS_PER_FOOT / 2 - 2.5;
      const cz = this.truckWidthFt * CELL_SIZE * CELLS_PER_FOOT / 2;
      const dist = 48;
      this.camera.position.set(cx + dist * 0.45, dist * 0.5, cz + dist * 0.4);
      this.controls.target.set(cx, 2, cz);
      this.controls.update();
      // Reset zoom slider
      const slider = document.getElementById('zoom-slider');
      const label = document.getElementById('zoom-label');
      if (slider) { slider.value = 100; }
      if (label) { label.textContent = '100%'; }
      this._defaultCamDist = null; // recapture
      UI.showToast('Camera reset', 'info');
    });

    const copyBom = document.getElementById('btn-copy-bom');
    if (copyBom) copyBom.addEventListener('click', () => this.copyBomToClipboard());

    const downloadBom = document.getElementById('btn-download-bom');
    if (downloadBom) downloadBom.addEventListener('click', () => this.downloadBomText());

    const clearGuidesBtn = document.getElementById('btn-clear-guides');
    if (clearGuidesBtn) clearGuidesBtn.addEventListener('click', () => UI.clearGuideLines());

    const portfolioBtn = document.getElementById('btn-portfolio');
    if (portfolioBtn) portfolioBtn.addEventListener('click', () => this.generatePortfolio());

    const pngBtn = document.getElementById('btn-screenshot');
    if (pngBtn) pngBtn.addEventListener('click', () => this.saveScreenshot('png'));
    const jpgBtn = document.getElementById('btn-screenshot-jpg');
    if (jpgBtn) jpgBtn.addEventListener('click', () => this.saveScreenshot('jpg'));
    const recBtn = document.getElementById('btn-record-video');
    if (recBtn) recBtn.addEventListener('click', () => this.recordRotationVideo());

    const matList = document.getElementById('btn-materials-list');
    if (matList) matList.addEventListener('click', () => this.downloadMaterialsList());

    const saveCheck = document.getElementById('btn-save-checklist');
    if (saveCheck) saveCheck.addEventListener('click', () => this.downloadChecklist());
  },

  // Generate comprehensive materials list
  generateMaterialsList() {
    const txt = [];
    txt.push('='.repeat(60));
    txt.push('BROTHERS FABRICATION — MATERIALS LIST');
    txt.push('='.repeat(60));
    txt.push(`Generated: ${new Date().toLocaleString()}`);
    txt.push(`Truck: ${this.truckLengthFt}ft L × ${this.truckWidthFt}ft W × ${this._getCeilingHeight().toFixed(1)}ft H`);
    txt.push('');

    // Equipment list
    txt.push('-- EQUIPMENT --');
    const counts = {};
    this.placedItems.forEach(item => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
      if (!def) return;
      if (!counts[def.name]) counts[def.name] = { count: 0, unit: def.cost || 0 };
      counts[def.name].count++;
    });
    let equipTotal = 0;
    Object.entries(counts).forEach(([name, info]) => {
      const subtotal = info.count * info.unit;
      equipTotal += subtotal;
      txt.push(`  ${String(info.count).padStart(3)}x  ${name.padEnd(34)} $${info.unit.toString().padStart(6)} ea  $${subtotal}`);
    });
    txt.push(`       ${''.padEnd(34)} ${''.padStart(9)}        $${equipTotal.toLocaleString()}`);
    txt.push('');

    // Consumables / line estimates
    txt.push('-- LINES & CONSUMABLES (estimates) --');
    const wire = document.getElementById('wire-est').textContent;
    const pex = document.getElementById('pex-est').textContent;
    const gas = document.getElementById('gas-est').textContent;
    txt.push(`  12/10-gauge electrical wire:   ${wire}`);
    txt.push(`  1/2" PEX water line:           ${pex}`);
    txt.push(`  3/8" braided gas line:         ${gas}`);
    txt.push('');

    // Surfaces
    txt.push('-- FABRICATION SURFACES --');
    const walls = document.getElementById('wall-sqft').textContent;
    const floor = document.getElementById('floor-sqft').textContent;
    txt.push(`  Wall sheet metal:              ${walls}`);
    txt.push(`  Floor material:                ${floor}`);
    txt.push(`  Wall material selected:        ${this.wallMaterial}`);
    txt.push(`  Floor material selected:       ${this.floorMaterial}`);
    txt.push('');

    // Power
    txt.push('-- POWER CALCULATIONS --');
    const load = document.getElementById('power-load').textContent;
    const peak = document.getElementById('power-peak').textContent;
    const supply = document.getElementById('power-supply').textContent;
    const status = document.getElementById('power-status').textContent;
    txt.push(`  Total continuous load:         ${load}`);
    txt.push(`  Peak load (+25% safety):       ${peak}`);
    txt.push(`  Generator supply:              ${supply}`);
    txt.push(`  Status:                        ${status}`);
    txt.push('');

    // Water
    txt.push('-- WATER CAPACITY --');
    const fresh = document.getElementById('water-fresh').textContent;
    const grey = document.getElementById('water-grey').textContent;
    txt.push(`  Fresh water tank:              ${fresh}`);
    txt.push(`  Grey water tank:               ${grey}`);
    txt.push('');

    // Totals
    const labor = Math.round(equipTotal * 0.25);
    const materials = Math.round(equipTotal * 0.15);
    const quoteTotal = equipTotal + labor + materials;
    txt.push('-- QUOTE SUMMARY --');
    txt.push(`  Equipment subtotal:            $${equipTotal.toLocaleString()}`);
    txt.push(`  Labor (est. 25%):              $${labor.toLocaleString()}`);
    txt.push(`  Materials (est. 15%):          $${materials.toLocaleString()}`);
    txt.push(`  QUOTE TOTAL:                   $${quoteTotal.toLocaleString()}`);
    txt.push('');
    txt.push('='.repeat(60));
    return txt.join('\n');
  },

  downloadMaterialsList() {
    const content = this.generateMaterialsList();
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `brofab-materials-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    UI.showToast('Materials list downloaded', 'success');
  },

  generateChecklist() {
    const items = [];
    items.push('# Build Checklist');
    items.push(`Truck: ${this.truckLengthFt}' × ${this.truckWidthFt}'`);
    items.push(`Generated: ${new Date().toLocaleString()}`);
    items.push('');

    items.push('## Pre-Build');
    items.push('- [ ] Confirm truck chassis & dimensions');
    items.push(`- [ ] Order ${document.getElementById('wall-sqft').textContent} of wall sheet metal (${this.wallMaterial})`);
    items.push(`- [ ] Order ${document.getElementById('floor-sqft').textContent} of flooring (${this.floorMaterial})`);
    items.push(`- [ ] Order ${document.getElementById('wire-est').textContent} of electrical wire`);
    items.push(`- [ ] Order ${document.getElementById('pex-est').textContent} of PEX tubing`);
    items.push(`- [ ] Order ${document.getElementById('gas-est').textContent} of gas line`);
    items.push('');

    items.push('## Equipment Installation');
    const counts = {};
    this.placedItems.forEach(item => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
      if (!def) return;
      if (!counts[def.name]) counts[def.name] = 0;
      counts[def.name]++;
    });
    Object.entries(counts).forEach(([name, count]) => {
      items.push(`- [ ] Install ${count}× ${name}`);
    });
    items.push('');

    items.push('## Utilities');
    items.push(`- [ ] Run electrical (${document.getElementById('wire-est').textContent} of wire)`);
    items.push(`- [ ] Run water lines (${document.getElementById('pex-est').textContent} of PEX)`);
    items.push(`- [ ] Run gas lines (${document.getElementById('gas-est').textContent})`);
    items.push(`- [ ] Install generator (supply: ${document.getElementById('power-supply').textContent})`);
    items.push(`- [ ] Mount fresh water tank (${document.getElementById('water-fresh').textContent})`);
    items.push(`- [ ] Mount grey water tank (${document.getElementById('water-grey').textContent})`);
    items.push('');

    items.push('## Compliance');
    const checkOK = (id) => document.getElementById(id)?.classList.contains('ok');
    items.push(`- [${checkOK('check-handwash') ? 'x' : ' '}] Hand wash sink present`);
    items.push(`- [${checkOK('check-3comp') ? 'x' : ' '}] 3-compartment sink present`);
    items.push(`- [${checkOK('check-hood') ? 'x' : ' '}] Exhaust hood installed`);
    items.push(`- [${checkOK('check-fire') ? 'x' : ' '}] Fire suppression installed`);
    items.push(`- [${checkOK('check-fridge') ? 'x' : ' '}] Cold storage present`);
    items.push(`- [${checkOK('check-service') ? 'x' : ' '}] Service window present`);
    items.push('- [ ] Health inspection passed');
    items.push('- [ ] Fire marshal inspection passed');
    items.push('- [ ] DOT inspection passed');
    items.push('');

    items.push('## Finishing');
    items.push('- [ ] Seal all seams');
    items.push('- [ ] Install lighting');
    items.push('- [ ] Exterior paint / branding');
    items.push('- [ ] Final QA walkthrough');
    items.push('- [ ] Customer training & handoff');

    return items.join('\n');
  },

  downloadChecklist() {
    const content = this.generateChecklist();
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `brofab-checklist-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
    UI.showToast('Checklist downloaded', 'success');
  },

  // Render inline build checklist in the sidebar panel (live-updating)
  // Render faux partition wall when a bay-type generator is placed
  updateGeneratorBay() {
    // Remove old partition
    const old = this.scene.getObjectByName('gen-bay-partition');
    if (old) this.scene.remove(old);
    const oldLabel = this.scene.getObjectByName('gen-bay-label');
    if (oldLabel) this.scene.remove(oldLabel);

    // Check if any placed item is a bay generator
    let bayItem = null;
    let bayDef = null;
    for (const item of this.placedItems) {
      const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
      if (def && def.generatorBay) {
        bayItem = item;
        bayDef = def;
        break;
      }
    }
    if (!bayItem || !bayDef) return;

    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;
    const wallHeights = {
      'step-van': 7.0, 'box-truck': 8.0, 'ups-style': 6.5, 'flatbed': 7.5
    };
    const wallH = wallHeights[this.truckType] || 6.5;
    const bayDepth = bayDef.bayDepthFt || 2;

    // Determine which end the generator is closer to (front or back)
    const genX = bayItem.position.x;
    const isFront = genX > truckW / 2;
    const partitionX = isFront ? truckW - bayDepth : bayDepth;

    // Partition wall — semi-transparent with a gap for access
    const partGeo = new THREE.BoxGeometry(0.08, wallH, truckD * 0.85);
    const partMat = new THREE.MeshPhongMaterial({
      color: 0xd0d0d0,
      transparent: true,
      opacity: 0.7,
      side: THREE.DoubleSide
    });
    const partition = new THREE.Mesh(partGeo, partMat);
    partition.position.set(partitionX, wallH / 2, truckD / 2);
    partition.castShadow = true;
    partition.receiveShadow = true;
    partition.name = 'gen-bay-partition';
    this.scene.add(partition);

    // Vent louver indicator on partition (dark rectangle)
    const ventGeo = new THREE.BoxGeometry(0.02, wallH * 0.3, truckD * 0.25);
    const ventMat = new THREE.MeshPhongMaterial({ color: 0x555555 });
    const vent = new THREE.Mesh(ventGeo, ventMat);
    vent.position.set(partitionX, wallH * 0.7, truckD * 0.25);
    vent.name = 'gen-bay-label';
    this.scene.add(vent);
  },

  renderBuildChecklist() {
    const el = document.getElementById('build-checklist');
    if (!el) return;
    if (this.placedItems.length === 0) {
      el.innerHTML = '<p class="muted">Place items to generate checklist</p>';
      return;
    }
    const checks = [
      { label: 'Hand wash sink', ok: document.getElementById('check-handwash')?.classList.contains('ok') },
      { label: '3-comp sink', ok: document.getElementById('check-3comp')?.classList.contains('ok') },
      { label: 'Exhaust hood', ok: document.getElementById('check-hood')?.classList.contains('ok') },
      { label: 'Fire suppression', ok: document.getElementById('check-fire')?.classList.contains('ok') },
      { label: 'Cold storage', ok: document.getElementById('check-fridge')?.classList.contains('ok') },
      { label: 'Service point', ok: document.getElementById('check-service')?.classList.contains('ok') },
      { label: 'Generator sized', ok: (document.getElementById('power-status')?.textContent || '').includes('OK') },
      { label: 'Fresh water tank', ok: this.placedItems.some(i => i.userData.equipId.startsWith('fresh-water')) },
      { label: 'Grey water tank', ok: this.placedItems.some(i => i.userData.equipId.startsWith('grey-water')) },
      { label: 'Control panel', ok: this.placedItems.some(i => i.userData.equipId === 'control-panel') }
    ];
    const done = checks.filter(c => c.ok).length;
    let html = `<div style="font-size:11px;color:var(--text-secondary);margin-bottom:8px;">${done}/${checks.length} requirements met</div>`;
    html += '<div class="checklist-items">';
    checks.forEach(c => {
      html += `<div class="cl-row ${c.ok ? 'ok' : ''}"><span class="cl-mark">${c.ok ? '✓' : '○'}</span><span>${c.label}</span></div>`;
    });
    html += '</div>';
    el.innerHTML = html;
  },

  duplicateSelected() {
    if (!this.selectedItem) {
      UI.showToast('Select an item first', 'error');
      return;
    }
    const item = this.selectedItem;
    const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
    if (!def) return;

    // Find nearby empty spot
    const offsets = [[2, 0], [0, 2], [-2, 0], [0, -2], [2, 2], [-2, -2]];
    for (const [dx, dz] of offsets) {
      const newX = item.userData.gridX + dx * CELL_SIZE;
      const newZ = item.userData.gridZ + dz * CELL_SIZE;
      const snap = this.snapToGrid({ x: newX, z: newZ }, def.widthCells, def.depthCells, item.userData.rotation || 0);
      if (this.isPlacementValid(snap.x, snap.z, snap.effW, snap.effD, null, !!item.userData.elevated)) {
        this.pushCheckpoint();
        const dup = createEquipmentMesh(def, false, item.userData.variant || 0);
        const y = item.userData.elevated ? item.userData.elevationCells * CELL_SIZE : 0;
        dup.position.set(snap.x, y, snap.z);
        dup.rotation.y = item.userData.rotation || 0;
        dup.userData.gridX = snap.x;
        dup.userData.gridZ = snap.z;
        dup.userData.effW = snap.effW;
        dup.userData.effD = snap.effD;
        dup.userData.rotation = item.userData.rotation || 0;
        this.scene.add(dup);
        this.placedItems.push(dup);
        UI.updateSummary(this.placedItems);
    this.updateGeneratorBay();
        UI.showToast(`Duplicated ${def.name}`, 'success');
        this.autoSave();
        return;
      }
    }
    UI.showToast('No space to duplicate', 'error');
  },

  generateBomText() {
    const counts = {};
    this.placedItems.forEach(item => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
      if (def) {
        if (!counts[def.name]) counts[def.name] = { count: 0, cost: def.cost || 0 };
        counts[def.name].count++;
      }
    });
    let text = `BROTHERS FABRICATION — BILL OF MATERIALS\n`;
    text += `=========================================\n`;
    text += `Truck: ${this.truckLengthFt}ft x ${this.truckWidthFt}ft\n`;
    text += `Generated: ${new Date().toLocaleString()}\n\n`;
    text += `Qty  Item                              Unit       Total\n`;
    text += `---  --------------------------------  ---------  ---------\n`;
    let total = 0;
    for (const [name, info] of Object.entries(counts)) {
      const rowTotal = info.count * info.cost;
      total += rowTotal;
      text += `${String(info.count).padEnd(5)}${name.padEnd(34)}$${String(info.cost).padEnd(10)}$${rowTotal}\n`;
    }
    text += `\nEquipment Total:   $${total.toLocaleString()}\n`;
    text += `Labor (est 25%):   $${Math.round(total * 0.25).toLocaleString()}\n`;
    text += `Materials (est 15%): $${Math.round(total * 0.15).toLocaleString()}\n`;
    text += `QUOTE TOTAL:       $${Math.round(total * 1.4).toLocaleString()}\n`;
    return text;
  },

  copyBomToClipboard() {
    const text = this.generateBomText();
    navigator.clipboard.writeText(text).then(
      () => UI.showToast('BOM copied to clipboard', 'success'),
      () => UI.showToast('Copy failed', 'error')
    );
  },

  downloadBomText() {
    const text = this.generateBomText();
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `brofab-bom-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    UI.showToast('BOM downloaded', 'success');
  },

  // Get wall opacity based on visibility setting
  getWallOpacity() {
    switch (this.wallVisibility) {
      case 'off': return 0;
      case 'low': return 0.3;
      case 'medium': return 0.55;
      case 'full': return 0.95;
      default: return 0.55;
    }
  },

  setFloorMaterial(material) {
    this.floorMaterial = material;
    if (!this.floorMesh) return;
    const mat = this.getFloorMaterial(material);
    this.floorMesh.material = mat;
    UI.showToast(`Floor: ${material}`, 'info');
  },

  getFloorMaterial(type) {
    const makeCanvas = (draw, size) => {
      const sz = size || 512;
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = sz;
      const ctx = canvas.getContext('2d');
      draw(ctx, sz);
      const tex = new THREE.CanvasTexture(canvas);
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      tex.encoding = THREE.sRGBEncoding;
      tex.needsUpdate = true;
      return tex;
    };

    switch (type) {
      case 'diamond': {
        const tex = makeCanvas((ctx, sz) => {
          ctx.fillStyle = '#959595';
          ctx.fillRect(0, 0, sz, sz);
          // Fine brush base
          for (let y = 0; y < sz; y++) {
            const s = 140 + Math.random() * 35;
            ctx.fillStyle = `rgba(${s},${s},${s},0.15)`;
            ctx.fillRect(0, y, sz, 1);
          }
          // Dense small diagonal ellipses
          const stepX = 16;
          const stepY = 10;
          for (let row = 0; row < sz / stepY + 1; row++) {
            for (let col = 0; col < sz / stepX + 1; col++) {
              const cx = col * stepX + ((row % 2) * stepX / 2);
              const cy = row * stepY;
              ctx.save();
              ctx.translate(cx + 0.8, cy + 0.8);
              ctx.rotate(Math.PI / 4);
              ctx.beginPath();
              ctx.ellipse(0, 0, 5, 1.8, 0, 0, Math.PI * 2);
              ctx.fillStyle = 'rgba(0,0,0,0.3)';
              ctx.fill();
              ctx.restore();
              ctx.save();
              ctx.translate(cx, cy);
              ctx.rotate(Math.PI / 4);
              ctx.beginPath();
              ctx.ellipse(0, 0, 4.5, 1.5, 0, 0, Math.PI * 2);
              ctx.fillStyle = '#a8a8a8';
              ctx.fill();
              ctx.restore();
              ctx.save();
              ctx.translate(cx - 0.3, cy - 0.3);
              ctx.rotate(Math.PI / 4);
              ctx.beginPath();
              ctx.ellipse(0, 0, 3.5, 0.8, 0, 0, Math.PI);
              ctx.fillStyle = 'rgba(215,215,215,0.6)';
              ctx.fill();
              ctx.restore();
            }
          }
        });
        tex.repeat.set(5, 3);
        return new THREE.MeshPhongMaterial({ map: tex, shininess: 50 });
      }
      case 'vinyl': {
        const tex = makeCanvas((ctx, sz) => {
          ctx.fillStyle = '#8b7050';
          ctx.fillRect(0, 0, sz, sz);
          const plankH = 72;
          const planks = Math.ceil(sz / plankH);
          for (let p = 0; p < planks; p++) {
            const y = p * plankH;
            // Each plank has unique warm wood tone
            const base = 130 + Math.random() * 40;
            const r = base + 20;
            const g = base - 5;
            const b = base - 35;
            ctx.fillStyle = `rgb(${r},${g},${b})`;
            ctx.fillRect(0, y + 2, sz, plankH - 2);

            // Heartwood — slightly darker center band
            const bandY = y + plankH * 0.3 + Math.random() * plankH * 0.2;
            ctx.fillStyle = `rgba(${r-25},${g-20},${b-15},0.3)`;
            ctx.fillRect(0, bandY, sz, plankH * 0.25);

            // Wood grain — many wavy lines following the plank
            for (let g2 = 0; g2 < 35; g2++) {
              const gy = y + 4 + Math.random() * (plankH - 8);
              const dark = Math.random() > 0.5;
              ctx.strokeStyle = dark
                ? `rgba(60,40,20,${0.08 + Math.random() * 0.14})`
                : `rgba(180,150,110,${0.06 + Math.random() * 0.1})`;
              ctx.lineWidth = 0.4 + Math.random() * 0.8;
              ctx.beginPath();
              ctx.moveTo(0, gy);
              for (let gx = 0; gx < sz; gx += 8) {
                ctx.lineTo(gx, gy + (Math.random() - 0.5) * 1.2);
              }
              ctx.stroke();
            }

            // Knot — occasional dark oval
            if (Math.random() < 0.25) {
              const kx = 60 + Math.random() * (sz - 120);
              const ky = y + plankH * 0.35 + Math.random() * plankH * 0.3;
              const krad = 4 + Math.random() * 6;
              // Knot rings
              for (let ring = krad; ring > 0; ring -= 1.5) {
                ctx.beginPath();
                ctx.ellipse(kx, ky, ring * 1.4, ring, Math.random() * 0.3, 0, Math.PI * 2);
                ctx.strokeStyle = `rgba(50,30,15,${0.1 + (krad - ring) * 0.04})`;
                ctx.lineWidth = 0.6;
                ctx.stroke();
              }
              ctx.beginPath();
              ctx.ellipse(kx, ky, 2, 1.5, 0, 0, Math.PI * 2);
              ctx.fillStyle = `rgba(45,28,12,0.5)`;
              ctx.fill();
            }

            // Plank gap — dark groove between boards
            ctx.fillStyle = 'rgba(30,18,8,0.7)';
            ctx.fillRect(0, y, sz, 2);
            // Highlight edge below gap
            ctx.fillStyle = `rgba(${r+20},${g+15},${b+10},0.3)`;
            ctx.fillRect(0, y + 2, sz, 1);

            // Staggered end joint — brick-pattern offset
            const stagger = [0.35, 0.7, 0.15, 0.55, 0.85, 0.25, 0.6];
            const xCut = sz * stagger[p % stagger.length];
            ctx.fillStyle = 'rgba(30,18,8,0.5)';
            ctx.fillRect(xCut, y, 2.5, plankH);
            ctx.fillStyle = `rgba(${r+15},${g+10},${b+5},0.25)`;
            ctx.fillRect(xCut + 2.5, y, 1, plankH);
          }
        });
        tex.repeat.set(2, 1);
        return new THREE.MeshPhongMaterial({ map: tex, shininess: 8 });
      }
      case 'rubber': {
        const tex = makeCanvas((ctx, sz) => {
          ctx.fillStyle = '#2e2e2e';
          ctx.fillRect(0, 0, sz, sz);
          // Fine coin-top grid
          const spacing = 12;
          for (let row = 0; row < sz / spacing; row++) {
            for (let col = 0; col < sz / spacing; col++) {
              const cx = col * spacing + spacing / 2;
              const cy = row * spacing + spacing / 2;
              ctx.beginPath();
              ctx.arc(cx, cy, 4.5, 0, Math.PI * 2);
              ctx.fillStyle = 'rgba(0,0,0,0.3)';
              ctx.fill();
              const grad = ctx.createRadialGradient(cx - 0.8, cy - 0.8, 0, cx, cy, 4);
              grad.addColorStop(0, 'rgba(90,90,90,0.8)');
              grad.addColorStop(0.5, 'rgba(55,55,55,0.6)');
              grad.addColorStop(1, 'rgba(35,35,35,0.4)');
              ctx.beginPath();
              ctx.arc(cx, cy, 4, 0, Math.PI * 2);
              ctx.fillStyle = grad;
              ctx.fill();
            }
          }
        });
        tex.repeat.set(5, 3);
        return new THREE.MeshPhongMaterial({ map: tex, shininess: 2 });
      }
      case 'bare':
      default: {
        const tex = makeCanvas((ctx, sz) => {
          ctx.fillStyle = '#d0d0d0';
          ctx.fillRect(0, 0, sz, sz);
          for (let y = 0; y < sz; y++) {
            const shade = 180 + Math.random() * 55;
            ctx.fillStyle = `rgba(${shade},${shade},${shade},0.5)`;
            ctx.fillRect(0, y, sz, 1);
          }
          for (let i = 0; i < 12; i++) {
            const sy = Math.random() * sz;
            ctx.strokeStyle = `rgba(150,150,150,${0.35 + Math.random() * 0.25})`;
            ctx.lineWidth = 0.8;
            ctx.beginPath();
            ctx.moveTo(0, sy);
            ctx.lineTo(sz, sy + (Math.random() - 0.5) * 6);
            ctx.stroke();
          }
          ctx.strokeStyle = 'rgba(120,120,120,0.5)';
          ctx.lineWidth = 2;
          for (let x = 0; x < sz; x += Math.round(sz / 3)) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, sz);
            ctx.stroke();
          }
        });
        tex.repeat.set(2, 1);
        return new THREE.MeshPhongMaterial({ map: tex, shininess: 30 });
      }
    }
  },

  setWallMaterial(material) {
    this.wallMaterial = material;
    // Rebuild truck to apply new wall color
    this.buildTruck();
    this.buildGridOverlay();
    UI.showToast(`Walls: ${material}`, 'info');
  },

  getWallColor(type) {
    // Use white so texture map is not tinted/darkened
    return 0xffffff;
  },

  getWallTexture(type) {
    const makeCanvas = (draw) => {
      const c = document.createElement('canvas');
      c.width = c.height = 512;
      const ctx = c.getContext('2d');
      draw(ctx, 512);
      const tex = new THREE.CanvasTexture(c);
      tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
      tex.encoding = THREE.sRGBEncoding;
      tex.needsUpdate = true;
      return tex;
    };

    switch (type) {
      case 'stainless': {
        const tex = makeCanvas((ctx, sz) => {
          // Grey brushed stainless base
          ctx.fillStyle = '#a8a8a8';
          ctx.fillRect(0, 0, sz, sz);
          // Vertical brush grain
          for (let x = 0; x < sz; x++) {
            const s = 135 + Math.random() * 75;
            ctx.fillStyle = `rgba(${s},${s},${s},0.55)`;
            ctx.fillRect(x, 0, 1, sz);
          }
          // Large square panels with seams
          const panelSz = sz / 2;
          for (let py = 0; py < sz; py += panelSz) {
            for (let px = 0; px < sz; px += panelSz) {
              // Seam groove
              ctx.fillStyle = 'rgba(30,30,30,0.4)';
              ctx.fillRect(px, py, sz, 2.5);
              ctx.fillRect(px, py, 2.5, panelSz);
              ctx.fillStyle = 'rgba(180,180,180,0.3)';
              ctx.fillRect(px, py + 2.5, sz, 1);
              ctx.fillRect(px + 2.5, py, 1, panelSz);
              // Screw heads every ~1ft
              const screwStep = panelSz / 2;
              for (let sy = py + screwStep / 2; sy < py + panelSz; sy += screwStep) {
                for (let sx = px + screwStep / 2; sx < px + panelSz; sx += screwStep) {
                  ctx.beginPath();
                  ctx.arc(sx, sy, 3.5, 0, Math.PI * 2);
                  ctx.fillStyle = 'rgba(0,0,0,0.2)';
                  ctx.fill();
                  ctx.beginPath();
                  ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
                  ctx.fillStyle = 'rgba(160,160,160,0.7)';
                  ctx.fill();
                  // Hex socket
                  ctx.beginPath();
                  ctx.arc(sx, sy, 1.2, 0, Math.PI * 2);
                  ctx.fillStyle = 'rgba(80,80,80,0.4)';
                  ctx.fill();
                }
              }
            }
          }
        });
        tex.repeat.set(3, 3);
        return tex;
      }
      case 'aluminum': {
        const tex = makeCanvas((ctx, sz) => {
          // White aluminum — vertical strip panels like wallpaper
          ctx.fillStyle = '#f4f4f4';
          ctx.fillRect(0, 0, sz, sz);
          // Vertical strips — each ~3" wide
          const stripW = sz / 8;
          for (let x = 0; x < sz; x += stripW) {
            // Alternating very slight tone shift
            const tone = (x / stripW) % 2 === 0 ? 240 : 235;
            ctx.fillStyle = `rgb(${tone},${tone},${tone})`;
            ctx.fillRect(x + 1, 0, stripW - 1, sz);
            // Strip edge groove — shadow left, highlight right
            ctx.fillStyle = 'rgba(0,0,0,0.12)';
            ctx.fillRect(x, 0, 1.5, sz);
            ctx.fillStyle = 'rgba(255,255,255,0.4)';
            ctx.fillRect(x + 1.5, 0, 0.8, sz);
          }
          // Horizontal seam every 4ft
          const seamY = sz / 2;
          ctx.fillStyle = 'rgba(0,0,0,0.1)';
          ctx.fillRect(0, seamY, sz, 2);
          ctx.fillStyle = 'rgba(255,255,255,0.2)';
          ctx.fillRect(0, seamY + 2, sz, 1);
        });
        tex.repeat.set(4, 4);
        return tex;
      }
      case 'frp': {
        const tex = makeCanvas((ctx, sz) => {
          ctx.fillStyle = '#ddd5c5';
          ctx.fillRect(0, 0, sz, sz);
          // Heavy fiberglass speckle — 3 layers of different sized dots
          // Layer 1: large light speckles
          for (let i = 0; i < 8000; i++) {
            const s = 215 + Math.random() * 35;
            ctx.fillStyle = `rgba(${s},${s-5},${s-20},0.8)`;
            ctx.beginPath();
            ctx.arc(Math.random()*sz, Math.random()*sz, 1.5 + Math.random()*2, 0, Math.PI*2);
            ctx.fill();
          }
          // Layer 2: small dark speckles
          for (let i = 0; i < 12000; i++) {
            const s = 160 + Math.random() * 50;
            ctx.fillStyle = `rgba(${s},${s-8},${s-25},0.6)`;
            ctx.beginPath();
            ctx.arc(Math.random()*sz, Math.random()*sz, 0.5 + Math.random()*1.2, 0, Math.PI*2);
            ctx.fill();
          }
          // Layer 3: occasional larger blotches
          for (let i = 0; i < 300; i++) {
            const s = 180 + Math.random() * 40;
            ctx.fillStyle = `rgba(${s},${s-10},${s-30},0.4)`;
            ctx.beginPath();
            ctx.arc(Math.random()*sz, Math.random()*sz, 2 + Math.random()*4, 0, Math.PI*2);
            ctx.fill();
          }
          // H-channel divider
          ctx.fillStyle = 'rgba(150,140,120,0.5)';
          ctx.fillRect(sz/2 - 3, 0, 6, sz);
          ctx.fillStyle = 'rgba(210,200,180,0.35)';
          ctx.fillRect(sz/2 - 1, 0, 2, sz);
          // Panel border
          ctx.strokeStyle = 'rgba(140,130,110,0.45)';
          ctx.lineWidth = 2.5;
          ctx.strokeRect(4, 4, sz-8, sz-8);
        });
        tex.repeat.set(2, 2);
        return tex;
      }
      case 'pvc': {
        const tex = makeCanvas((ctx, sz) => {
          ctx.fillStyle = '#e4e4ea';
          ctx.fillRect(0, 0, sz, sz);
          // Large square panel grid with per-tile shade variation
          const panelSz = sz / 2;
          for (let py = 0; py < sz; py += panelSz) {
            for (let px = 0; px < sz; px += panelSz) {
              // Each tile gets a slightly different shade
              const tileShade = 225 + Math.random() * 20;
              ctx.fillStyle = `rgb(${tileShade},${tileShade},${tileShade + 4})`;
              ctx.fillRect(px + 2, py + 2, panelSz - 3, panelSz - 3);
              // Subtle surface noise per tile
              for (let i = 0; i < 800; i++) {
                const s = tileShade - 10 + Math.random() * 20;
                ctx.fillStyle = `rgba(${s},${s},${s+3},0.2)`;
                ctx.fillRect(px + Math.random()*panelSz, py + Math.random()*panelSz, 2, 2);
              }
              // Panel edge groove
              ctx.fillStyle = 'rgba(0,0,0,0.18)';
              ctx.fillRect(px, py, panelSz + 1, 2.5);
              ctx.fillRect(px, py, 2.5, panelSz + 1);
              ctx.fillStyle = 'rgba(255,255,255,0.25)';
              ctx.fillRect(px + 2.5, py + 2.5, panelSz - 2, 1);
              ctx.fillRect(px + 2.5, py + 2.5, 1, panelSz - 2);
              // Screw heads — every ~1ft = panelSz/2
              const screwSpacing = panelSz / 2;
              for (let sy = py + screwSpacing / 2; sy < py + panelSz; sy += screwSpacing) {
                for (let sx = px + screwSpacing / 2; sx < px + panelSz; sx += screwSpacing) {
                  // Screw recess shadow
                  ctx.beginPath();
                  ctx.arc(sx, sy, 3.5, 0, Math.PI * 2);
                  ctx.fillStyle = 'rgba(0,0,0,0.12)';
                  ctx.fill();
                  // Screw head
                  ctx.beginPath();
                  ctx.arc(sx, sy, 2.5, 0, Math.PI * 2);
                  ctx.fillStyle = 'rgba(190,190,200,0.7)';
                  ctx.fill();
                  // Phillips cross
                  ctx.strokeStyle = 'rgba(100,100,110,0.4)';
                  ctx.lineWidth = 0.8;
                  ctx.beginPath();
                  ctx.moveTo(sx - 1.5, sy); ctx.lineTo(sx + 1.5, sy);
                  ctx.moveTo(sx, sy - 1.5); ctx.lineTo(sx, sy + 1.5);
                  ctx.stroke();
                }
              }
            }
          }
        });
        tex.repeat.set(2, 2);
        return tex;
      }
      default: {
        // Default painted wall — subtle orange-peel texture
        const tex = makeCanvas((ctx, sz) => {
          ctx.fillStyle = '#f0f0f0';
          ctx.fillRect(0, 0, sz, sz);
          for (let i = 0; i < 6000; i++) {
            const s = 230 + Math.random() * 20;
            ctx.fillStyle = `rgba(${s},${s},${s},0.4)`;
            const r = 1 + Math.random() * 2;
            ctx.beginPath();
            ctx.arc(Math.random() * sz, Math.random() * sz, r, 0, Math.PI * 2);
            ctx.fill();
          }
        });
        tex.repeat.set(4, 4);
        return tex;
      }
    }
  },

  // Clear all items
  clearAll() {
    this.pushCheckpoint();
    this.placedItems.slice().forEach(i => {
      this.scene.remove(i);
    });
    this.placedItems = [];
    this.deselectItem();
    this.cancelPlacement();
    UI.updateSummary(this.placedItems);
    this.updateGeneratorBay();
    UI.showToast('Cleared all items', 'info');
    this.autoSave();
  },

  // ---- Serialization (for autosave, undo, save/load) ----
  serialize() {
    return {
      truckLengthFt: this.truckLengthFt,
      truckWidthFt: this.truckWidthFt,
      colorAccents: this.colorAccents,
      items: this.placedItems.map(item => ({
        equipmentId: item.userData.equipId,
        gridX: item.userData.gridX,
        gridZ: item.userData.gridZ,
        rotation: item.userData.rotation || 0,
        variant: item.userData.variant || 0
      })),
      internalNotes: document.getElementById('internal-notes')?.value || ''
    };
  },

  deserialize(state) {
    if (!state) return;
    // Clear existing items
    this.placedItems.slice().forEach(i => this.scene.remove(i));
    this.placedItems = [];
    this.deselectItem();
    this.cancelPlacement();

    // Restore truck dimensions
    if (state.truckLengthFt) this.truckLengthFt = state.truckLengthFt;
    if (state.truckWidthFt) this.truckWidthFt = state.truckWidthFt;
    this.buildTruck();
    this.buildGridOverlay();

    // Restore items
    (state.items || []).forEach(it => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === it.equipmentId);
      if (!def) return;
      const mesh = createEquipmentMesh(def, false, it.variant || 0);
      const snapped = this.snapToGrid({ x: it.gridX, z: it.gridZ }, def.widthCells, def.depthCells, it.rotation || 0);
      const y = def.elevated ? this._getDynamicElevation(def) : 0;
      mesh.position.set(snapped.x, y, snapped.z);
      mesh.rotation.y = it.rotation || 0;
      mesh.userData.gridX = snapped.x;
      mesh.userData.gridZ = snapped.z;
      mesh.userData.effW = snapped.effW;
      mesh.userData.effD = snapped.effD;
      mesh.userData.rotation = it.rotation || 0;
      this.scene.add(mesh);
      this.placedItems.push(mesh);
    });

    // Restore notes
    if (state.internalNotes) {
      const notes = document.getElementById('internal-notes');
      if (notes) notes.value = state.internalNotes;
    }

    UI.updateSummary(this.placedItems);
    this.updateGeneratorBay();
    UI.setDimensionsInfo(`${this.truckLengthFt}ft × ${this.truckWidthFt}ft`);
  },

  // ---- Checkpoint / Undo ----
  pushCheckpoint() {
    this.undoStack.push(this.serialize());
    if (this.undoStack.length > this.maxUndoSteps) {
      this.undoStack.shift();
    }
    // Clear redo stack on new action
    this.redoStack = [];
  },

  undo() {
    if (this.undoStack.length === 0) {
      UI.showToast('Nothing to undo', 'info');
      return;
    }
    // Save current state to redo stack
    this.redoStack.push(this.serialize());
    const prev = this.undoStack.pop();
    this.deserialize(prev);
    UI.showToast('Undo', 'info');
  },

  redo() {
    if (this.redoStack.length === 0) {
      UI.showToast('Nothing to redo', 'info');
      return;
    }
    this.undoStack.push(this.serialize());
    const next = this.redoStack.pop();
    this.deserialize(next);
    UI.showToast('Redo', 'info');
  },

  // ---- Auto-save to localStorage ----
  autoSave() {
    if (this.autoSaveTimer) clearTimeout(this.autoSaveTimer);
    this.autoSaveTimer = setTimeout(() => {
      try {
        const state = {
          ...this.serialize(),
          savedAt: Date.now()
        };
        localStorage.setItem(this.autoSaveKey, JSON.stringify(state));
      } catch (e) {
        console.warn('Autosave failed:', e);
      }
    }, 500); // debounced
  },

  checkAutoSaveRecovery() {
    try {
      const saved = localStorage.getItem(this.autoSaveKey);
      if (!saved) return;
      const state = JSON.parse(saved);
      if (!state.items || state.items.length === 0) return;

      const ageMin = Math.round((Date.now() - (state.savedAt || 0)) / 60000);
      const ageText = ageMin < 1 ? 'just now' :
                      ageMin < 60 ? `${ageMin} min ago` :
                      `${Math.floor(ageMin / 60)} hr ago`;

      // Non-blocking toast with a restore button rather than confirm()
      this.showRecoveryPrompt(state, ageText);
    } catch (e) {
      console.warn('Autosave recovery failed:', e);
    }
  },

  showRecoveryPrompt(state, ageText) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = 'toast info';
    toast.style.cssText = 'display:flex;gap:10px;align-items:center;pointer-events:auto;max-width:300px;padding:10px 14px;';
    toast.innerHTML = `
      <span style="flex:1;">Auto-save found (${state.items.length} items, ${ageText})</span>
      <button style="background:var(--accent);border:none;color:#fff;padding:4px 10px;border-radius:3px;font-weight:700;cursor:pointer;font-size:10px;">RESTORE</button>
      <button style="background:transparent;border:1px solid rgba(255,255,255,0.3);color:#fff;padding:4px 8px;border-radius:3px;cursor:pointer;font-size:10px;">✕</button>
    `;
    const [restoreBtn, dismissBtn] = toast.querySelectorAll('button');
    restoreBtn.addEventListener('click', () => {
      this.deserialize(state);
      UI.showToast('Restored', 'success');
      toast.remove();
    });
    dismissBtn.addEventListener('click', () => {
      localStorage.removeItem(this.autoSaveKey);
      toast.remove();
    });
    container.appendChild(toast);
    // Auto-dismiss after 45 seconds
    setTimeout(() => { if (toast.parentNode) toast.remove(); }, 45000);
  },

  // Rebuild all placed items (e.g., when color toggle changes)
  rebuildAllItems() {
    const snapshot = this.placedItems.map(item => ({
      equipId: item.userData.equipId,
      gridX: item.userData.gridX,
      gridZ: item.userData.gridZ,
      effW: item.userData.effW,
      effD: item.userData.effD,
      rotation: item.userData.rotation || 0,
      variant: item.userData.variant || 0,
      elevated: item.userData.elevated,
      elevationCells: item.userData.elevationCells
    }));

    // Remove all
    this.placedItems.slice().forEach(i => this.scene.remove(i));
    this.placedItems = [];

    // Rebuild
    snapshot.forEach(s => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === s.equipId);
      if (!def) return;
      const item = createEquipmentMesh(def, false, s.variant);
      const y = s.elevated ? s.elevationCells * CELL_SIZE : 0;
      item.position.set(s.gridX, y, s.gridZ);
      item.rotation.y = s.rotation;
      item.userData.gridX = s.gridX;
      item.userData.gridZ = s.gridZ;
      item.userData.effW = s.effW;
      item.userData.effD = s.effD;
      item.userData.rotation = s.rotation;
      this.scene.add(item);
      this.placedItems.push(item);
    });
  },

  // View presets
  setViewPreset(preset) {
    this.viewPreset = preset;
    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;
    // Center on full truck including cab
    const cx = truckW / 2 - 2.5;
    const cz = truckD / 2;

    this.controls.target.set(cx, 2, cz);
    const dist = 40;
    switch (preset) {
      case 'iso':
        this.camera.position.set(cx + dist * 0.8, dist * 0.65, cz + dist * 0.7);
        break;
      case 'top':
        this.camera.position.set(cx + 0.01, dist * 1.4, cz);
        break;
      case 'front':
        this.camera.position.set(cx, 3, cz + dist);
        break;
      case 'side':
        this.camera.position.set(cx + dist, 3, cz);
        break;
    }
    this.camera.lookAt(cx, 2, cz);
    this.controls.update();
  },

  // Cycle variant of selected item
  cycleSelectedVariant() {
    if (!this.selectedItem) return;
    const item = this.selectedItem;
    const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
    if (!def) return;

    const nextVariant = ((item.userData.variant || 0) + 1) % 3;
    const snapshot = {
      equipId: item.userData.equipId,
      gridX: item.userData.gridX,
      gridZ: item.userData.gridZ,
      effW: item.userData.effW,
      effD: item.userData.effD,
      rotation: item.userData.rotation || 0,
      elevated: item.userData.elevated,
      elevationCells: item.userData.elevationCells
    };

    this.scene.remove(item);
    const idx = this.placedItems.indexOf(item);
    if (idx !== -1) this.placedItems.splice(idx, 1);

    const newItem = createEquipmentMesh(def, false, nextVariant);
    const y = snapshot.elevated ? snapshot.elevationCells * CELL_SIZE : 0;
    newItem.position.set(snapshot.gridX, y, snapshot.gridZ);
    newItem.rotation.y = snapshot.rotation;
    newItem.userData.gridX = snapshot.gridX;
    newItem.userData.gridZ = snapshot.gridZ;
    newItem.userData.effW = snapshot.effW;
    newItem.userData.effD = snapshot.effD;
    newItem.userData.rotation = snapshot.rotation;
    this.scene.add(newItem);
    this.placedItems.push(newItem);

    this.selectedItem = null;
    this.selectItem(newItem);
  },

  // ---- Templates ----
  loadTemplate(tpl) {
    if (!tpl) return;
    // Convert template format to layout format and reuse loadLayout
    const layout = {
      name: tpl.name,
      truck_length_ft: tpl.truck_length_ft,
      truck_width_ft: tpl.truck_width_ft,
      layout_json: tpl.items.map(it => ({
        equipmentId: it.equipmentId,
        gridX: it.gridX,
        gridZ: it.gridZ,
        rotation: it.rotation || 0,
        variant: it.variant || 0
      }))
    };
    this.loadLayout(layout);
  },

  async listUserTemplates() {
    try {
      const res = await fetch(
        `${window.SUPABASE_URL}/rest/v1/saved_layouts?is_template=eq.true&select=*&order=created_at.desc&limit=50`,
        {
          headers: {
            'apikey': window.SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${window.SUPABASE_ANON_KEY}`
          }
        }
      );
      if (res.ok) return await res.json();
    } catch (e) {
      console.error(e);
    }
    return [];
  },

  // Import a layout from a JSON file the user uploads
  importLayout(parsedJson) {
    if (!parsedJson) {
      UI.showToast('Invalid layout file', 'error');
      return;
    }
    // Expected shape: { truckLength, truckWidth, items: [...] } OR { layout_json: [...], truck_length_ft, truck_width_ft }
    const layout = {
      name: parsedJson.name || 'Imported layout',
      truck_length_ft: parsedJson.truckLength || parsedJson.truck_length_ft || 20,
      truck_width_ft: parsedJson.truckWidth || parsedJson.truck_width_ft || 8,
      layout_json: parsedJson.items || parsedJson.layout_json || []
    };
    // Normalize items — items from exportLayout use positionX/positionZ
    layout.layout_json = layout.layout_json.map(it => ({
      equipmentId: it.equipmentId,
      gridX: it.gridX !== undefined ? it.gridX : it.positionX,
      gridZ: it.gridZ !== undefined ? it.gridZ : it.positionZ,
      rotation: typeof it.rotation === 'number'
        ? (it.rotation > Math.PI * 2 ? THREE.MathUtils.degToRad(it.rotation) : it.rotation)
        : 0,
      variant: it.variant || 0
    }));
    this.loadLayout(layout);
    UI.showToast('Layout imported', 'success');
  },

  // Export as JSON
  exportLayout() {
    const layout = {
      truckLength: this.truckLengthFt,
      truckWidth: this.truckWidthFt,
      items: this.placedItems.map(item => ({
        equipmentId: item.userData.equipId,
        name: item.userData.name,
        positionX: item.userData.gridX,
        positionZ: item.userData.gridZ,
        rotation: Math.round(THREE.MathUtils.radToDeg(item.userData.rotation || 0)),
        variant: item.userData.variant || 0,
        widthCells: item.userData.widthCells,
        depthCells: item.userData.depthCells
      }))
    };
    const json = JSON.stringify(layout, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `truck-layout-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    UI.showToast('Layout exported', 'success');
  },

  // ---- Save/Load Layout (Supabase) ----
  async saveLayout(name, tags, isTemplate) {
    const layoutData = this.placedItems.map(item => ({
      equipmentId: item.userData.equipId,
      name: item.userData.name,
      gridX: item.userData.gridX,
      gridZ: item.userData.gridZ,
      rotation: item.userData.rotation || 0,
      variant: item.userData.variant || 0
    }));

    const payload = {
      name,
      tags: tags || null,
      truck_length_ft: this.truckLengthFt,
      truck_width_ft: this.truckWidthFt,
      layout_json: layoutData,
      item_count: this.placedItems.length,
      internal_notes: document.getElementById('internal-notes')?.value || null,
      is_template: !!isTemplate
    };

    try {
      const res = await fetch(`${window.SUPABASE_URL}/rest/v1/saved_layouts`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'apikey': window.SUPABASE_ANON_KEY,
          'Authorization': `Bearer ${window.SUPABASE_ANON_KEY}`,
          'Prefer': 'return=minimal'
        },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        UI.showToast(`Saved "${name}"`, 'success');
        return true;
      } else {
        UI.showToast('Save failed: ' + res.status, 'error');
        return false;
      }
    } catch (e) {
      UI.showToast('Save error: ' + e.message, 'error');
      return false;
    }
  },

  async listSavedLayouts() {
    try {
      const res = await fetch(
        `${window.SUPABASE_URL}/rest/v1/saved_layouts?select=*&order=created_at.desc&limit=50`,
        {
          headers: {
            'apikey': window.SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${window.SUPABASE_ANON_KEY}`
          }
        }
      );
      if (res.ok) return await res.json();
    } catch (e) {
      console.error(e);
    }
    return [];
  },

  async loadLayout(layout) {
    this.clearAll();
    this.truckLengthFt = layout.truck_length_ft;
    this.truckWidthFt = layout.truck_width_ft || 8;
    this.buildTruck();
    this.buildGridOverlay();

    const items = layout.layout_json || [];
    items.forEach(it => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === it.equipmentId);
      if (!def) return;
      const mesh = createEquipmentMesh(def, false, it.variant || 0);
      const snapped = this.snapToGrid({ x: it.gridX, z: it.gridZ }, def.widthCells, def.depthCells, it.rotation || 0);
      const y = def.elevated ? this._getDynamicElevation(def) : 0;
      mesh.position.set(snapped.x, y, snapped.z);
      mesh.rotation.y = it.rotation || 0;
      mesh.userData.gridX = snapped.x;
      mesh.userData.gridZ = snapped.z;
      mesh.userData.effW = snapped.effW;
      mesh.userData.effD = snapped.effD;
      mesh.userData.rotation = it.rotation || 0;
      this.scene.add(mesh);
      this.placedItems.push(mesh);
    });

    if (layout.internal_notes) {
      const notes = document.getElementById('internal-notes');
      if (notes) notes.value = layout.internal_notes;
    }

    UI.updateSummary(this.placedItems);
    this.updateGeneratorBay();
    UI.showToast(`Loaded "${layout.name}"`, 'success');
  },

  async deleteSavedLayout(id) {
    try {
      const res = await fetch(
        `${window.SUPABASE_URL}/rest/v1/saved_layouts?id=eq.${id}`,
        {
          method: 'DELETE',
          headers: {
            'apikey': window.SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${window.SUPABASE_ANON_KEY}`
          }
        }
      );
      if (res.ok) {
        UI.showToast('Deleted', 'info');
        return true;
      }
    } catch (e) { console.error(e); }
    return false;
  },

  // ---- Scene Setup ----
  setupScene() {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xd0d4d8);

    // Perspective camera with narrow FOV — iso-like at rest, natural when orbiting
    const aspect = window.innerWidth / window.innerHeight;
    this.camera = new THREE.PerspectiveCamera(24, aspect, 0.5, 500);

    // Camera positioned to frame full truck (box body + cab) nicely on load
    // Cab extends ~5ft in front of box body, so center is shifted back
    const cx = this.truckLengthFt * CELL_SIZE * CELLS_PER_FOOT / 2 - 2.5;
    const cz = this.truckWidthFt * CELL_SIZE * CELLS_PER_FOOT / 2;
    const dist = 48;
    this.camera.position.set(cx + dist * 0.45, dist * 0.5, cz + dist * 0.4);
    this.camera.lookAt(cx, 2, cz);

    // Renderer
    const canvas = document.getElementById('canvas');
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: true,
      alpha: false
    });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.shadowMap.autoUpdate = true;
    this.renderer.outputEncoding = THREE.sRGBEncoding;
    this.renderer.physicallyCorrectLights = true;

    // ---- Lighting: clean, neutral, good shadow definition ----

    // Ambient — neutral white, moderate fill so nothing is pure black
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
    this.scene.add(ambientLight);

    // Hemisphere — soft sky blue from above, warm bounce from below (floor)
    const hemiLight = new THREE.HemisphereLight(0xc8daf0, 0xe8ddd0, 0.35);
    this.scene.add(hemiLight);

    // Key light — main directional, warm-neutral, strong shadows
    const dirLight = new THREE.DirectionalLight(0xfff6e8, 2.5);
    dirLight.position.set(16, 28, 14);
    dirLight.castShadow = true;
    dirLight.shadow.mapSize.set(4096, 4096);
    dirLight.shadow.camera.left = -30;
    dirLight.shadow.camera.right = 30;
    dirLight.shadow.camera.top = 30;
    dirLight.shadow.camera.bottom = -30;
    dirLight.shadow.camera.near = 0.5;
    dirLight.shadow.camera.far = 80;
    dirLight.shadow.bias = -0.0003;
    dirLight.shadow.normalBias = 0.02;
    this.scene.add(dirLight);

    // Fill light — cool blue from opposite side, lifts shadow areas
    const fillLight = new THREE.DirectionalLight(0xa8c0e8, 0.8);
    fillLight.position.set(-14, 12, -8);
    this.scene.add(fillLight);

    // Rim/back light — subtle edge definition from behind
    const rimLight = new THREE.DirectionalLight(0xdde8f0, 0.4);
    rimLight.position.set(-4, 8, -20);
    this.scene.add(rimLight);

    // Tone mapping — natural, not over-processed
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 0.95;

    // Ground plane — created by applySceneBackground() with chosen style
    this.applySceneBackground();
  },

  // ---- Build Truck Shell ----
  buildTruck() {
    if (this.truckGroup) {
      this.scene.remove(this.truckGroup);
    }

    this.truckGroup = new THREE.Group();

    const truckW = this.truckLengthFt * CELL_SIZE * CELLS_PER_FOOT;
    const truckD = this.truckWidthFt * CELL_SIZE * CELLS_PER_FOOT;
    // Interior ceiling height by chassis type (feet, matches equipment scale)
    const wallHeights = {
      'step-van': 7.0,     // 7ft — standard step van (P700 class)
      'box-truck': 8.0,    // 8ft — taller box truck
      'ups-style': 6.5,    // 6.5ft — older narrow vans
      'flatbed': 7.5       // 7.5ft — custom flatbed build
    };
    const wallH = wallHeights[this.truckType] || 6.5;
    const wallThickness = 0.04;

    // Update grid cells
    this.gridCellsX = this.truckLengthFt * CELLS_PER_FOOT;
    this.gridCellsZ = this.truckWidthFt * CELLS_PER_FOOT;

    // Floor — material depends on floorMaterial setting
    const floorGeo = new THREE.BoxGeometry(truckW, 0.06, truckD);
    const floorMat = this.getFloorMaterial(this.floorMaterial);
    this.floorMesh = new THREE.Mesh(floorGeo, floorMat);
    this.floorMesh.position.set(truckW / 2, -0.03, truckD / 2);
    this.floorMesh.receiveShadow = true;
    this.floorMesh.name = 'truck-floor';
    this.truckGroup.add(this.floorMesh);

    // Per-wall material clones so each wall can have its own opacity
    // (updated live based on camera angle)
    const wallColor = this.getWallColor(this.wallMaterial);
    const wallTex = this.getWallTexture(this.wallMaterial);
    const makeWallMat = () => new THREE.MeshPhongMaterial({
      color: wallColor,
      map: wallTex,
      transparent: true,
      opacity: 0.92,
      side: THREE.DoubleSide,
      shininess: 20
    });
    // Reset the walls ref
    this._truckWalls = [];

    // Helper: create a wall with its own material clone + normal for dynamic opacity
    const addWall = (geo, pos, normal) => {
      const mat = makeWallMat();
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(pos);
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      this.truckGroup.add(mesh);
      this._truckWalls.push({ mesh, material: mat, edges: null, edgeMaterial: null, normal });
    };

    // Back wall (far side, outward normal -Z)
    const backGeo = new THREE.BoxGeometry(truckW, wallH, wallThickness);
    addWall(backGeo, new THREE.Vector3(truckW / 2, wallH / 2, -wallThickness / 2), new THREE.Vector3(0, 0, -1));

    // Left wall (outward normal -X)
    const sideGeo = new THREE.BoxGeometry(wallThickness, wallH, truckD);
    addWall(sideGeo, new THREE.Vector3(-wallThickness / 2, wallH / 2, truckD / 2), new THREE.Vector3(-1, 0, 0));

    // Right wall (outward normal +X)
    addWall(sideGeo, new THREE.Vector3(truckW + wallThickness / 2, wallH / 2, truckD / 2), new THREE.Vector3(1, 0, 0));

    // Front wall (outward normal +Z)
    const frontGeo = new THREE.BoxGeometry(truckW, wallH, wallThickness);
    addWall(frontGeo, new THREE.Vector3(truckW / 2, wallH / 2, truckD + wallThickness / 2), new THREE.Vector3(0, 0, 1));

    // Ceiling (roof) — toggleable
    const ceilGeo = new THREE.BoxGeometry(truckW, 0.04, truckD);
    const ceilMat = new THREE.MeshStandardMaterial({
      color: 0xe0e0e0,
      transparent: true,
      opacity: 0.92,
      side: THREE.DoubleSide,
      roughness: 0.5,
      metalness: 0.05
    });
    // Visible ceiling — user toggle
    const ceiling = new THREE.Mesh(ceilGeo, ceilMat);
    ceiling.position.set(truckW / 2, wallH, truckD / 2);
    ceiling.castShadow = false;
    ceiling.receiveShadow = true;
    ceiling.visible = this.showRoof;
    this.truckGroup.add(ceiling);
    this._ceilingMesh = ceiling;
    this._ceilingEdges = null;

    // ---- Doors ----
    // ---- DOOR SYSTEM ----
    // Punch material — invisible but writes depth, making wall behind it disappear
    const punchMat = new THREE.MeshBasicMaterial({
      colorWrite: false, depthWrite: true, side: THREE.DoubleSide
    });
    // Door panel — opaque, darker than walls so visible
    const doorPanelMat = new THREE.MeshPhongMaterial({
      color: 0xa0a0a0, side: THREE.DoubleSide, shininess: 12
    });
    // Frame
    const doorFrameMat = new THREE.MeshPhongMaterial({
      color: 0x666666, side: THREE.DoubleSide, shininess: 8
    });
    // Dark opening
    const doorOpenMat = new THREE.MeshBasicMaterial({
      color: 0x080a10, transparent: true, opacity: 0.5,
      side: THREE.DoubleSide
    });

    // Helper: punch a hole in the wall + add opening/door visuals
    const buildDoor = (wallX, centerZ, doorW, doorH, isOpen, type) => {
      // Always punch a hole through the wall at the door location
      const punch = new THREE.Mesh(
        new THREE.BoxGeometry(0.4, doorH * 0.98, doorW * 0.96), punchMat
      );
      punch.position.set(wallX, doorH / 2, centerZ);
      punch.renderOrder = -1;
      this.truckGroup.add(punch);

      // Frame around the hole — proportional to door size
      const ft = Math.max(0.03, doorW * 0.04);
      const fDepth = 0.12;
      // Top
      const fTop = new THREE.Mesh(new THREE.BoxGeometry(fDepth, ft, doorW + ft * 2), doorFrameMat);
      fTop.position.set(wallX, doorH + ft / 2, centerZ);
      this.truckGroup.add(fTop);
      // Sides
      for (let s of [-1, 1]) {
        const fSide = new THREE.Mesh(new THREE.BoxGeometry(fDepth, doorH, ft), doorFrameMat);
        fSide.position.set(wallX, doorH / 2, centerZ + s * (doorW / 2 + ft / 2));
        this.truckGroup.add(fSide);
      }
      // Threshold
      const fBot = new THREE.Mesh(new THREE.BoxGeometry(fDepth, ft, doorW + ft * 2), doorFrameMat);
      fBot.position.set(wallX, ft / 2, centerZ);
      this.truckGroup.add(fBot);

      if (isOpen) {
        // Dark opening visible from both sides
        const opening = new THREE.Mesh(
          new THREE.BoxGeometry(0.35, doorH * 0.95, doorW * 0.94), doorOpenMat
        );
        opening.position.set(wallX, doorH / 2, centerZ);
        this.truckGroup.add(opening);
      } else {
        // Closed door panel(s)
        if (type === 'double') {
          const halfW = doorW * 0.48;
          for (let s of [-1, 1]) {
            const panel = new THREE.Mesh(new THREE.BoxGeometry(0.05, doorH * 0.95, halfW), doorPanelMat);
            panel.position.set(wallX, doorH / 2, centerZ + s * halfW / 2);
            this.truckGroup.add(panel);
            // Handle
            const h = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.12, 8), doorFrameMat);
            h.position.set(wallX + 0.05, doorH * 0.45, centerZ + s * halfW * 0.7);
            this.truckGroup.add(h);
          }
          // Center gap
          const gap = new THREE.Mesh(new THREE.BoxGeometry(0.1, doorH * 0.95, 0.02), doorFrameMat);
          gap.position.set(wallX, doorH / 2, centerZ);
          this.truckGroup.add(gap);
        } else if (type === 'roll-up') {
          const panel = new THREE.Mesh(new THREE.BoxGeometry(0.05, doorH * 0.95, doorW * 0.94), doorPanelMat);
          panel.position.set(wallX, doorH / 2, centerZ);
          this.truckGroup.add(panel);
          // Ridges
          for (let i = 1; i <= 6; i++) {
            const ridge = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.015, doorW * 0.92), doorFrameMat);
            ridge.position.set(wallX, doorH * i / 7, centerZ);
            this.truckGroup.add(ridge);
          }
        } else {
          // Single door
          const panel = new THREE.Mesh(new THREE.BoxGeometry(0.05, doorH * 0.95, doorW * 0.94), doorPanelMat);
          panel.position.set(wallX, doorH / 2, centerZ);
          this.truckGroup.add(panel);
          const h = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.12, 8), doorFrameMat);
          h.position.set(wallX + 0.05, doorH * 0.45, centerZ + doorW * 0.3);
          this.truckGroup.add(h);
          // Slide track
          if (type === 'slide') {
            const track = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.03, doorW * 1.2), doorFrameMat);
            track.position.set(wallX, doorH + 0.03, centerZ);
            this.truckGroup.add(track);
          }
        }
      }
    };

    // Side wall door — same logic but rotated (door on left Z=0 or right Z=truckD wall)
    const buildDoorSide = (wallZ, centerX, doorW, doorH, isOpen, type) => {
      const punch = new THREE.Mesh(
        new THREE.BoxGeometry(doorW * 0.96, doorH * 0.98, 0.4), punchMat
      );
      punch.position.set(centerX, doorH / 2, wallZ);
      punch.renderOrder = -1;
      this.truckGroup.add(punch);

      const ft = Math.max(0.03, doorW * 0.04);
      const fD = 0.12;
      const fTop = new THREE.Mesh(new THREE.BoxGeometry(doorW + ft * 2, ft, fD), doorFrameMat);
      fTop.position.set(centerX, doorH + ft / 2, wallZ);
      this.truckGroup.add(fTop);
      for (let s of [-1, 1]) {
        const fSide = new THREE.Mesh(new THREE.BoxGeometry(ft, doorH, fD), doorFrameMat);
        fSide.position.set(centerX + s * (doorW / 2 + ft / 2), doorH / 2, wallZ);
        this.truckGroup.add(fSide);
      }
      const fBot = new THREE.Mesh(new THREE.BoxGeometry(doorW + ft * 2, ft, fD), doorFrameMat);
      fBot.position.set(centerX, ft / 2, wallZ);
      this.truckGroup.add(fBot);

      if (isOpen) {
        const opening = new THREE.Mesh(
          new THREE.BoxGeometry(doorW * 0.94, doorH * 0.95, 0.35), doorOpenMat
        );
        opening.position.set(centerX, doorH / 2, wallZ);
        this.truckGroup.add(opening);
      } else {
        const panel = new THREE.Mesh(
          new THREE.BoxGeometry(doorW * 0.94, doorH * 0.95, 0.05), doorPanelMat
        );
        panel.position.set(centerX, doorH / 2, wallZ);
        this.truckGroup.add(panel);
        const h = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.12, 8), doorFrameMat);
        h.position.set(centerX + doorW * 0.3, doorH * 0.45, wallZ + (wallZ > truckD / 2 ? 0.05 : -0.05));
        this.truckGroup.add(h);
        if (type === 'slide') {
          const track = new THREE.Mesh(new THREE.BoxGeometry(doorW * 1.2, 0.03, 0.03), doorFrameMat);
          track.position.set(centerX, doorH + 0.03, wallZ);
          this.truckGroup.add(track);
        }
      }
    };

    // Rear door (at truckW — near wheel wells)
    if (this.rearDoorType !== 'none') {
      const rearH = wallH * 0.88;
      const rearW = this.rearDoorType === 'single' ? truckD * 0.4
                   : this.rearDoorType === 'roll-up' ? truckD * 0.8
                   : truckD * 0.84;
      buildDoor(truckW, truckD / 2, rearW, rearH, this.rearDoorOpen, this.rearDoorType);
    }

    // Man door — can be on any wall
    if (this.manDoorType !== 'none') {
      const manSizes = { narrow: 0.2, standard: 0.3, wide: 0.4 };
      const manSizeFrac = manSizes[this.manDoorSize] || 0.3;
      const manH = wallH * 0.82;
      const wall = this.manDoorWall || 'front';

      if (wall === 'front') {
        // Front wall (X=0), door centered on Z
        const manW = truckD * manSizeFrac;
        buildDoor(0, truckD / 2, manW, manH, this.manDoorOpen, this.manDoorType);
      } else if (wall === 'left-rear') {
        // Left wall (Z=0), near rear (high X)
        const manW = truckW * manSizeFrac;
        buildDoorSide(0, truckW * 0.8, manW, manH, this.manDoorOpen, this.manDoorType);
      } else if (wall === 'left-front') {
        // Left wall (Z=0), near front (low X)
        const manW = truckW * manSizeFrac;
        buildDoorSide(0, truckW * 0.2, manW, manH, this.manDoorOpen, this.manDoorType);
      } else if (wall === 'right-rear') {
        // Right wall (Z=truckD), near rear
        const manW = truckW * manSizeFrac;
        buildDoorSide(truckD, truckW * 0.8, manW, manH, this.manDoorOpen, this.manDoorType);
      } else if (wall === 'right-front') {
        // Right wall (Z=truckD), near front
        const manW = truckW * manSizeFrac;
        buildDoorSide(truckD, truckW * 0.2, manW, manH, this.manDoorOpen, this.manDoorType);
      }
    }

    // Interior corner outlines — dark lines defining the inside of the truck shell
    const interiorPts = [
      // Floor-level rectangle
      new THREE.Vector3(0, 0.01, 0), new THREE.Vector3(truckW, 0.01, 0),
      new THREE.Vector3(truckW, 0.01, 0), new THREE.Vector3(truckW, 0.01, truckD),
      new THREE.Vector3(truckW, 0.01, truckD), new THREE.Vector3(0, 0.01, truckD),
      new THREE.Vector3(0, 0.01, truckD), new THREE.Vector3(0, 0.01, 0),
      // Vertical corners
      new THREE.Vector3(0, 0.01, 0), new THREE.Vector3(0, wallH, 0),
      new THREE.Vector3(truckW, 0.01, 0), new THREE.Vector3(truckW, wallH, 0),
      new THREE.Vector3(truckW, 0.01, truckD), new THREE.Vector3(truckW, wallH, truckD),
      new THREE.Vector3(0, 0.01, truckD), new THREE.Vector3(0, wallH, truckD),
      // Ceiling-level rectangle
      new THREE.Vector3(0, wallH, 0), new THREE.Vector3(truckW, wallH, 0),
      new THREE.Vector3(truckW, wallH, 0), new THREE.Vector3(truckW, wallH, truckD),
      new THREE.Vector3(truckW, wallH, truckD), new THREE.Vector3(0, wallH, truckD),
      new THREE.Vector3(0, wallH, truckD), new THREE.Vector3(0, wallH, 0)
    ];
    const interiorGeo = new THREE.BufferGeometry().setFromPoints(interiorPts);
    const interiorMat = new THREE.LineBasicMaterial({
      color: 0x111111,
      transparent: true,
      opacity: 0.75,
      linewidth: 2
    });
    const interiorLines = new THREE.LineSegments(interiorGeo, interiorMat);
    this.truckGroup.add(interiorLines);

    // ---- Wheel Wells ----
    this._wheelWellBoxes = [];
    if (this.showWheelWells) {
      const wellConfig = this.getWheelWellConfig();
      const colorSel = document.getElementById('wheel-well-color');
      const colorMode = colorSel ? colorSel.value : 'dark';

      wellConfig.forEach(w => {
        const wellGeo = new THREE.BoxGeometry(w.w, w.h, w.d);
        let wellMat;
        if (colorMode === 'match' && this.floorMesh && this.floorMesh.material) {
          wellMat = this.floorMesh.material.clone();
          if (wellMat.map) {
            wellMat.map = wellMat.map.clone();
            wellMat.map.repeat.set(1, 1);
            wellMat.map.needsUpdate = true;
          }
        } else if (colorMode === 'light') {
          wellMat = new THREE.MeshPhongMaterial({ color: 0xd8d8d8, shininess: 15 });
        } else {
          wellMat = new THREE.MeshPhongMaterial({ color: 0x555555, shininess: 15 });
        }
        const mesh = new THREE.Mesh(wellGeo, wellMat);
        mesh.position.set(w.x, w.h / 2, w.z);
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        this.truckGroup.add(mesh);
        this._wheelWellBoxes.push({
          x: w.x, z: w.z,
          halfW: w.w / 2, halfD: w.d / 2
        });
      });
    }

    // ---- EXTERIOR TRUCK SHELL ----
    // Adds cab, outer skin, chassis frame, wheels, and bumpers so the
    // configurator looks like a real food truck instead of a floating box.
    // All exterior geometry lives in _exteriorGroup for easy toggling.
    const ext = new THREE.Group();
    ext.name = 'exterior-shell';

    // -- Dimensions --
    const shellThick = 0.15;           // ~2" aluminum skin + insulation
    const chassisH = 1.5;              // frame rail depth below floor
    const groundClear = 1.0;           // ground clearance under frame
    const floorAboveGround = chassisH + groundClear; // 2.5 ft
    const wheelRadius = 1.25;          // 30" diameter tires
    const wheelWidth = 0.7;
    const cabLength = 5.0;             // driver cab length
    const cabRoofDrop = 0.6;           // cab roof sits lower than box roof
    const cabH = wallH - cabRoofDrop;
    const bumperH = 0.8;
    const bumperDepth = 0.4;

    // Outer box body dimensions (wraps around interior)
    const outerW = truckW + shellThick * 2;     // length
    const outerD = truckD + shellThick * 2;     // width
    const outerH = wallH + shellThick;          // height (floor to roof exterior)

    // -- Materials --
    const bodyMat = new THREE.MeshPhongMaterial({
      color: 0xe8e8e8, shininess: 40, transparent: true, opacity: 0.35,
      side: THREE.DoubleSide
    });
    const chassisMat = new THREE.MeshPhongMaterial({
      color: 0x2a2a2a, shininess: 10
    });
    const tireMat = new THREE.MeshPhongMaterial({
      color: 0x1a1a1a, shininess: 5
    });
    const rimMat = new THREE.MeshPhongMaterial({
      color: 0x888888, shininess: 60, specular: 0x444444
    });
    const cabMat = new THREE.MeshPhongMaterial({
      color: 0xe0e0e0, shininess: 30, transparent: true, opacity: 0.3,
      side: THREE.DoubleSide
    });
    const glassMat = new THREE.MeshPhongMaterial({
      color: 0x88bbdd, transparent: true, opacity: 0.25,
      shininess: 90, side: THREE.DoubleSide
    });
    const bumperMat = new THREE.MeshPhongMaterial({
      color: 0x444444, shininess: 20
    });

    // -- Box Body Outer Skin --
    // The interior walls are at X=[0, truckW], Z=[0, truckD], Y=[0, wallH].
    // Outer skin wraps around that with shellThick offset.
    const oX = -shellThick;   // outer origin X
    const oZ = -shellThick;   // outer origin Z
    const oY = -shellThick;   // outer origin Y (slightly below floor for skin thickness)

    // Roof outer skin
    const roofGeo = new THREE.BoxGeometry(outerW, shellThick, outerD);
    const roofMesh = new THREE.Mesh(roofGeo, bodyMat);
    roofMesh.position.set(oX + outerW / 2, wallH + shellThick / 2, oZ + outerD / 2);
    roofMesh.castShadow = true;
    ext.add(roofMesh);

    // Left outer wall (Z = oZ side)
    const sideOutGeo = new THREE.BoxGeometry(outerW, outerH, shellThick);
    const leftOuter = new THREE.Mesh(sideOutGeo, bodyMat);
    leftOuter.position.set(oX + outerW / 2, oY + outerH / 2, oZ + shellThick / 2);
    leftOuter.castShadow = true;
    ext.add(leftOuter);

    // Right outer wall (Z = oZ + outerD side)
    const rightOuter = new THREE.Mesh(sideOutGeo, bodyMat);
    rightOuter.position.set(oX + outerW / 2, oY + outerH / 2, oZ + outerD - shellThick / 2);
    rightOuter.castShadow = true;
    ext.add(rightOuter);

    // Rear outer wall (X = truckW + shellThick side)
    const rearOutGeo = new THREE.BoxGeometry(shellThick, outerH, outerD);
    const rearOuter = new THREE.Mesh(rearOutGeo, bodyMat);
    rearOuter.position.set(truckW + shellThick / 2, oY + outerH / 2, oZ + outerD / 2);
    rearOuter.castShadow = true;
    ext.add(rearOuter);

    // Floor underside skin
    const floorSkinGeo = new THREE.BoxGeometry(outerW, shellThick, outerD);
    const floorSkin = new THREE.Mesh(floorSkinGeo, bodyMat);
    floorSkin.position.set(oX + outerW / 2, -shellThick / 2, oZ + outerD / 2);
    ext.add(floorSkin);

    // -- Chassis Frame --
    // Two parallel frame rails running the full truck length + cab
    const totalLength = outerW + cabLength;
    const railW = 0.3;                   // rail width (3.6")
    const railH = chassisH * 0.6;        // rail height
    const railY = -shellThick - railH / 2;
    for (const zOff of [truckD * 0.2, truckD * 0.8]) {
      const rail = new THREE.Mesh(
        new THREE.BoxGeometry(totalLength, railH, railW), chassisMat
      );
      rail.position.set(oX + outerW / 2 - cabLength / 2, railY, zOff);
      rail.castShadow = true;
      ext.add(rail);
    }

    // Cross members
    const crossCount = Math.floor(totalLength / 3);
    for (let i = 0; i <= crossCount; i++) {
      const cx2 = oX - cabLength + (totalLength * i / crossCount);
      const cross = new THREE.Mesh(
        new THREE.BoxGeometry(railW, railH * 0.6, truckD * 0.6), chassisMat
      );
      cross.position.set(cx2, railY, truckD / 2);
      ext.add(cross);
    }

    // -- Cab --
    // Positioned at X < 0 (in front of the box body)
    const cabStartX = -shellThick - cabLength;
    const cabFloorY = 0;        // cab floor at same height as box floor
    const cabCenterX = cabStartX + cabLength / 2;
    const cabCenterZ = truckD / 2;

    // Cab roof
    const cabRoofGeo = new THREE.BoxGeometry(cabLength, shellThick, outerD);
    const cabRoof = new THREE.Mesh(cabRoofGeo, cabMat);
    cabRoof.position.set(cabCenterX, cabH, cabCenterZ);
    cabRoof.castShadow = true;
    ext.add(cabRoof);

    // Cab left wall
    const cabSideGeo = new THREE.BoxGeometry(cabLength, cabH, shellThick);
    const cabLeft = new THREE.Mesh(cabSideGeo, cabMat);
    cabLeft.position.set(cabCenterX, cabH / 2, oZ + shellThick / 2);
    cabLeft.castShadow = true;
    ext.add(cabLeft);

    // Cab right wall
    const cabRight = new THREE.Mesh(cabSideGeo, cabMat);
    cabRight.position.set(cabCenterX, cabH / 2, oZ + outerD - shellThick / 2);
    cabRight.castShadow = true;
    ext.add(cabRight);

    // Cab front wall (with windshield cutout implied by transparency)
    const cabFrontGeo = new THREE.BoxGeometry(shellThick, cabH, outerD);
    const cabFront = new THREE.Mesh(cabFrontGeo, cabMat);
    cabFront.position.set(cabStartX, cabH / 2, cabCenterZ);
    cabFront.castShadow = true;
    ext.add(cabFront);

    // Windshield (glass panel on front, upper portion)
    const windshieldH = cabH * 0.45;
    const windshieldW = outerD * 0.85;
    const windshieldGeo = new THREE.BoxGeometry(0.05, windshieldH, windshieldW);
    const windshield = new THREE.Mesh(windshieldGeo, glassMat);
    windshield.position.set(cabStartX - 0.02, cabH - windshieldH / 2 - 0.2, cabCenterZ);
    ext.add(windshield);

    // Cab floor
    const cabFloorGeo = new THREE.BoxGeometry(cabLength, shellThick, outerD);
    const cabFloor = new THREE.Mesh(cabFloorGeo, chassisMat);
    cabFloor.position.set(cabCenterX, -shellThick / 2, cabCenterZ);
    ext.add(cabFloor);

    // -- Hood / Engine Area --
    // Slight downward slope at front of cab (below windshield)
    const hoodH = cabH * 0.35;
    const hoodLength = cabLength * 0.4;
    const hoodGeo = new THREE.BoxGeometry(hoodLength, hoodH, outerD * 0.95);
    const hoodMesh = new THREE.Mesh(hoodGeo, cabMat);
    hoodMesh.position.set(cabStartX + hoodLength / 2, hoodH / 2, cabCenterZ);
    hoodMesh.castShadow = true;
    ext.add(hoodMesh);

    // -- Wheels --
    // Food trucks typically have 4 rear wheels (dual) + 2 front = 6
    // Or 2 rear + 2 front = 4 for lighter step vans
    const wheelY = -floorAboveGround + wheelRadius;
    const wheelSegments = 24;

    const makeWheel = (wx, wz, isDual) => {
      // Tire
      const tireGeo = new THREE.CylinderGeometry(wheelRadius, wheelRadius, isDual ? wheelWidth * 2.2 : wheelWidth, wheelSegments);
      const tire = new THREE.Mesh(tireGeo, tireMat);
      tire.rotation.x = Math.PI / 2;
      tire.position.set(wx, wheelY, wz);
      tire.castShadow = true;
      ext.add(tire);

      // Rim (smaller cylinder inside)
      const rimRadius = wheelRadius * 0.55;
      const rimGeo = new THREE.CylinderGeometry(rimRadius, rimRadius, isDual ? wheelWidth * 2.3 : wheelWidth + 0.05, wheelSegments);
      const rim = new THREE.Mesh(rimGeo, rimMat);
      rim.rotation.x = Math.PI / 2;
      rim.position.set(wx, wheelY, wz);
      ext.add(rim);

      // Hub cap
      const hubGeo = new THREE.CylinderGeometry(rimRadius * 0.4, rimRadius * 0.4, isDual ? wheelWidth * 2.4 : wheelWidth + 0.1, 12);
      const hub = new THREE.Mesh(hubGeo, new THREE.MeshPhongMaterial({ color: 0x666666, shininess: 40 }));
      hub.rotation.x = Math.PI / 2;
      hub.position.set(wx, wheelY, wz);
      ext.add(hub);
    };

    const isDualRear = (this.truckType === 'box-truck' || this.truckType === 'flatbed');
    const rearWheelX = truckW * this.wheelWellPosition;
    const frontWheelX = cabStartX + cabLength * 0.35;

    // Rear wheels (at wheel well position)
    makeWheel(rearWheelX, -0.1, isDualRear);             // left rear
    makeWheel(rearWheelX, truckD + 0.1, isDualRear);     // right rear

    // Front wheels (in the cab area)
    makeWheel(frontWheelX, 0.1, false);                   // left front
    makeWheel(frontWheelX, truckD - 0.1, false);          // right front

    // -- Bumpers --
    // Rear bumper
    const rearBumperGeo = new THREE.BoxGeometry(bumperDepth, bumperH, outerD + 0.3);
    const rearBumper = new THREE.Mesh(rearBumperGeo, bumperMat);
    rearBumper.position.set(truckW + shellThick + bumperDepth / 2, -floorAboveGround + bumperH / 2 + 0.3, cabCenterZ);
    rearBumper.castShadow = true;
    ext.add(rearBumper);

    // Front bumper
    const frontBumperGeo = new THREE.BoxGeometry(bumperDepth, bumperH, outerD + 0.3);
    const frontBumper = new THREE.Mesh(frontBumperGeo, bumperMat);
    frontBumper.position.set(cabStartX - bumperDepth / 2, -floorAboveGround + bumperH / 2 + 0.3, cabCenterZ);
    frontBumper.castShadow = true;
    ext.add(frontBumper);

    // -- Step (entry step at man door side) --
    const stepGeo = new THREE.BoxGeometry(1.5, 0.15, 1.2);
    const stepMat = new THREE.MeshPhongMaterial({ color: 0x555555, shininess: 15 });
    // Step below the front wall (X=0) man door
    const stepMesh = new THREE.Mesh(stepGeo, stepMat);
    stepMesh.position.set(-0.75, -floorAboveGround * 0.5, truckD / 2);
    ext.add(stepMesh);

    // -- Headlights (small glowing boxes on cab front) --
    const headlightGeo = new THREE.BoxGeometry(0.1, 0.4, 0.6);
    const headlightMat = new THREE.MeshPhongMaterial({
      color: 0xffffcc, emissive: 0xffff88, emissiveIntensity: 0.3,
      transparent: true, opacity: 0.8
    });
    for (const zOff of [outerD * 0.2, outerD * 0.8]) {
      const hl = new THREE.Mesh(headlightGeo, headlightMat);
      hl.position.set(cabStartX - 0.05, cabH * 0.35, oZ + zOff);
      ext.add(hl);
    }

    // -- Taillights --
    const taillightGeo = new THREE.BoxGeometry(0.1, 0.35, 0.5);
    const taillightMat = new THREE.MeshPhongMaterial({
      color: 0xff3333, emissive: 0xff0000, emissiveIntensity: 0.2,
      transparent: true, opacity: 0.8
    });
    for (const zOff of [outerD * 0.15, outerD * 0.85]) {
      const tl = new THREE.Mesh(taillightGeo, taillightMat);
      tl.position.set(truckW + shellThick + 0.05, wallH * 0.25, oZ + zOff);
      ext.add(tl);
    }

    this.truckGroup.add(ext);
    this._exteriorGroup = ext;

    // ---- Interior lighting — gentle, even, no hotspots ----
    const lightCount = Math.max(3, Math.floor(truckW / 2.5));
    for (let i = 0; i < lightCount; i++) {
      const x = truckW * (i + 0.5) / lightCount;
      const light = new THREE.PointLight(0xfff8ee, 1.5, truckW * 0.8, 1.5);
      light.position.set(x, wallH * 0.9, truckD / 2);
      this.truckGroup.add(light);
    }

    // Gentle fill from serving side
    const daylight = new THREE.PointLight(0xe8eef4, 1, truckW, 1.5);
    daylight.position.set(truckW / 2, wallH * 0.4, truckD + 1);
    this.truckGroup.add(daylight);

    this.scene.add(this.truckGroup);

    // Center camera target — account for cab extending beyond box body
    const cx = (truckW - cabLength) / 2;
    const cz = truckD / 2;
    if (this.controls) {
      this.controls.target.set(cx, 2, cz);
      this.controls.update();
    }
  },

  // ---- Grid Overlay on Floor ----
  buildGridOverlay() {
    // Remove old grid
    const oldGrid = this.scene.getObjectByName('grid-overlay');
    if (oldGrid) this.scene.remove(oldGrid);

    const gridGroup = new THREE.Group();
    gridGroup.name = 'grid-overlay';

    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;

    // Grid lines
    const gridMat = new THREE.LineBasicMaterial({
      color: 0xbbbbbb,
      transparent: true,
      opacity: 0.3
    });

    const points = [];

    // Vertical lines (along X)
    for (let i = 0; i <= this.gridCellsX; i++) {
      const x = i * CELL_SIZE;
      points.push(new THREE.Vector3(x, 0.005, 0));
      points.push(new THREE.Vector3(x, 0.005, truckD));
    }

    // Horizontal lines (along Z)
    for (let j = 0; j <= this.gridCellsZ; j++) {
      const z = j * CELL_SIZE;
      points.push(new THREE.Vector3(0, 0.005, z));
      points.push(new THREE.Vector3(truckW, 0.005, z));
    }

    const gridGeo = new THREE.BufferGeometry().setFromPoints(points);
    const gridLines = new THREE.LineSegments(gridGeo, gridMat);
    gridGroup.add(gridLines);

    // BIG floor tiles (1ft = 2 cells) — matches Fights in Tight Spaces reference
    const bigTileSize = CELL_SIZE * 2; // 1 foot tiles
    const tileMat = new THREE.MeshBasicMaterial({
      color: 0xcccccc,
      transparent: true,
      opacity: 0.2,
      side: THREE.DoubleSide
    });

    const tileCellsX = Math.floor(this.gridCellsX / 2);
    const tileCellsZ = Math.floor(this.gridCellsZ / 2);
    for (let i = 0; i < tileCellsX; i++) {
      for (let j = 0; j < tileCellsZ; j++) {
        if ((i + j) % 2 === 0) continue; // checkerboard
        const tileGeo = new THREE.PlaneGeometry(bigTileSize * 0.92, bigTileSize * 0.92);
        const tile = new THREE.Mesh(tileGeo, tileMat);
        tile.rotation.x = -Math.PI / 2;
        tile.position.set(
          i * bigTileSize + bigTileSize / 2,
          0.003,
          j * bigTileSize + bigTileSize / 2
        );
        gridGroup.add(tile);
      }
    }

    // Also add larger darker grid outlines every 1ft
    const bigGridPoints = [];
    for (let i = 0; i <= tileCellsX; i++) {
      const x = i * bigTileSize;
      bigGridPoints.push(new THREE.Vector3(x, 0.006, 0));
      bigGridPoints.push(new THREE.Vector3(x, 0.006, tileCellsZ * bigTileSize));
    }
    for (let j = 0; j <= tileCellsZ; j++) {
      const z = j * bigTileSize;
      bigGridPoints.push(new THREE.Vector3(0, 0.006, z));
      bigGridPoints.push(new THREE.Vector3(tileCellsX * bigTileSize, 0.006, z));
    }
    const bigGridGeo = new THREE.BufferGeometry().setFromPoints(bigGridPoints);
    const bigGridMat = new THREE.LineBasicMaterial({
      color: 0x888888,
      transparent: true,
      opacity: 0.5
    });
    const bigGridLines = new THREE.LineSegments(bigGridGeo, bigGridMat);
    gridGroup.add(bigGridLines);

    this.scene.add(gridGroup);
  },

  // ---- Camera Controls ----
  setupControls() {
    this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.2; // Tighter damping — less floaty
    this.controls.enablePan = true;
    this.controls.panSpeed = 1.4; // Much faster pan
    this.controls.enableRotate = true;
    this.controls.rotateSpeed = 1.2; // Much faster rotate
    this.controls.zoomSpeed = 1.6; // Faster zoom
    this.controls.minDistance = 8;
    this.controls.maxDistance = 150;
    this.controls.maxPolarAngle = Math.PI / 2.2; // Allow slight look below floor to see chassis/wheels
    this.controls.minPolarAngle = Math.PI / 8;   // Don't go fully top-down

    // Left handled by app, middle pans, right orbits
    this.controls.mouseButtons = {
      LEFT: null, // We handle left click ourselves (placement/selection)
      MIDDLE: THREE.MOUSE.PAN,
      RIGHT: THREE.MOUSE.ROTATE
    };

    // Center on the full truck (box body + cab), slightly lower to show exterior
    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;
    this.controls.target.set(truckW / 2 - 2.5, 2, truckD / 2);
    this.controls.update();
  },

  // ---- Event Listeners ----
  setupEventListeners() {
    const canvas = this.renderer.domElement;

    // Track mouse down/up to distinguish clicks from drags
    this._mouseDownPos = null;
    this._rightDownPos = null;
    this._middleDownPos = null;
    this._dragPickupTarget = null;
    // Capture phase so OrbitControls doesn't eat the event first
    canvas.addEventListener('mousedown', (e) => {
      if (e.button === 0) {
        this._mouseDownPos = { x: e.clientX, y: e.clientY };
        // If pressing on a placed item (and no ghost active) → IMMEDIATELY pick it up
        // This makes click-and-drag feel responsive
        if (!this.ghostMesh && !this.utilityMode) {
          const target = this.raycastPlacedItem(e);
          if (target) {
            this.selectItem(target);
            this.moveSelected();
            this._startedDrag = true; // mark as drag-pickup so mouseup drops correctly
            // Position ghost at cursor immediately
            this.onMouseMove(e);
            if (this.ghostTarget) {
              this.ghostMesh.position.copy(this.ghostTarget);
            }
          }
        }
      } else if (e.button === 1) {
        this._middleDownPos = { x: e.clientX, y: e.clientY };
      } else if (e.button === 2) {
        this._rightDownPos = { x: e.clientX, y: e.clientY };
      }
    }, true);
    // Window-level mouseup so OrbitControls can't eat it
    window.addEventListener('mouseup', (e) => {
      if (e.button === 0 && this._mouseDownPos) {
        const dx = e.clientX - this._mouseDownPos.x;
        const dy = e.clientY - this._mouseDownPos.y;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // If user is holding a ghost from a drag-pickup AND moved significantly → drop here
        if (dist >= 6 && this.ghostMesh && this._startedDrag) {
          this.onMouseMove(e);
          if (this.ghostTarget) {
            this.ghostMesh.position.copy(this.ghostTarget);
            const data = this.ghostMesh.userData;
            const snapped = this.snapToGrid(this.ghostTarget, data.widthCells, data.depthCells, this.ghostRotation);
            this.ghostValid = this.isPlacementValid(snapped.x, snapped.z, snapped.effW, snapped.effD, null);
          }
          if (this.ghostValid) {
            this.placeEquipment();
          } else {
            UI.showToast('Cannot drop here — collision or out of bounds', 'error');
          }
          this._startedDrag = false;
        }
        // If no significant drag, leave ghost active for click-to-place workflow
        // (the 'click' event handler will handle placement if user clicks on the floor)

        this._mouseDownPos = null;
        this._dragPickupTarget = null;
      }
    }, true);

    canvas.addEventListener('mouseup', (e) => {
      if (e.button === 1) {
        // Middle click handled by 'auxclick' event instead
        this._middleDownPos = null;
      } else if (e.button === 2 && this._rightDownPos) {
        const dx = e.clientX - this._rightDownPos.x;
        const dy = e.clientY - this._rightDownPos.y;
        if (Math.sqrt(dx * dx + dy * dy) < 5) {
          this.onMouseRightClick(e);
        }
        this._rightDownPos = null;
      }
    });

    // Window-level mousemove (capture) so drag works even if orbit controls captures
    window.addEventListener('mousemove', (e) => {
      // If user pressed down on a placed item and moves far enough → pick it up as ghost
      if (this._dragPickupTarget && this._mouseDownPos && !this.ghostMesh) {
        const dx = e.clientX - this._mouseDownPos.x;
        const dy = e.clientY - this._mouseDownPos.y;
        if (Math.sqrt(dx * dx + dy * dy) >= 6) {
          this.selectItem(this._dragPickupTarget);
          this.moveSelected();
          this._dragPickupTarget = null;
          this._startedDrag = true;
        }
      }
      // Only update ghost position if event is over the canvas
      const rect = canvas.getBoundingClientRect();
      if (e.clientX >= rect.left && e.clientX <= rect.right &&
          e.clientY >= rect.top && e.clientY <= rect.bottom) {
        this.onMouseMove(e);
      }
    });

    // Direct click listener — browsers fire this after a non-drag mousedown+mouseup.
    // Most reliable for placement even with OrbitControls capturing pointer events.
    canvas.addEventListener('click', (e) => {
      if (e.button !== 0 && e.button !== undefined) return;
      this.onMouseClick(e);
    });

    // Right-click handled via contextmenu event (fires reliably even with OrbitControls)
    canvas.addEventListener('contextmenu', (e) => {
      e.preventDefault();
      // Only fire as "click" if we didn't drag
      if (this._rightDownPos) {
        const dx = e.clientX - this._rightDownPos.x;
        const dy = e.clientY - this._rightDownPos.y;
        if (Math.sqrt(dx * dx + dy * dy) < 5) {
          this.onMouseRightClick(e);
        }
        this._rightDownPos = null;
      } else {
        // No prior mousedown captured — fire anyway
        this.onMouseRightClick(e);
      }
    });

    // Middle-click (via auxclick which fires reliably after non-drag middle-mouseup)
    canvas.addEventListener('auxclick', (e) => {
      if (e.button !== 1) return;
      e.preventDefault();
      // Distance check (skip if this was a pan drag)
      if (this._middleDownPos) {
        const dx = e.clientX - this._middleDownPos.x;
        const dy = e.clientY - this._middleDownPos.y;
        this._middleDownPos = null;
        if (Math.sqrt(dx * dx + dy * dy) >= 5) return;
      }
      // Rotate ghost while placing
      if (this.ghostMesh) {
        this.ghostRotation = (this.ghostRotation + Math.PI / 2) % (Math.PI * 2);
        this.ghostMesh.rotation.y = this.ghostRotation;
        UI.setStatus('Rotated to ' + Math.round(this.ghostRotation * 180 / Math.PI) + '°');
      } else if (this.selectedItem) {
        // Middle click on selected placed item: rotate it
        this.rotateSelected();
      }
    });

    // Scroll wheel → height adjust when placing elevated/wall items
    // Use window-level capture so it fires even when pen overlay is active
    window.addEventListener('wheel', (e) => {
      if (this.ghostMesh && (this.ghostMesh.userData.elevated || this._isWallMount(this.ghostMesh.userData.equipId))) {
        e.preventDefault();
        e.stopPropagation();
        const dir = e.deltaY < 0 ? 1 : -1;
        const wh = { 'step-van': 7.0, 'box-truck': 8.0, 'ups-style': 6.5, 'flatbed': 7.5 };
        const ceil = wh[this.truckType] || 6.5;
        const data = this.ghostMesh.userData;
        const baseY = (data.elevationCells || 0) * CELL_SIZE;
        const itemH = data.heightCells * CELL_SIZE;
        const maxOffset = ceil - itemH - baseY;
        const minOffset = -baseY;
        this._ghostHeightOffset = Math.max(minOffset, Math.min(maxOffset, (this._ghostHeightOffset || 0) + dir * 0.25));
        UI.setStatus('Height: ' + this._formatHeight());
        const hBar = document.getElementById('height-item-bar');
        if (hBar) { hBar.classList.add('pulse'); setTimeout(() => hBar.classList.remove('pulse'), 200); }
      }
    }, { passive: false, capture: true });

    window.addEventListener('resize', () => this.handleResize());

    window.addEventListener('keydown', (e) => {
      // Ignore keyboard shortcuts when user is typing in a form input
      const tag = (e.target && e.target.tagName) || '';
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      // Undo / Redo
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        if (e.shiftKey) this.redo();
        else this.undo();
        e.preventDefault();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'y') {
        this.redo();
        e.preventDefault();
        return;
      }

      switch (e.key.toLowerCase()) {
        case 'arrowup':
        case 'pageup':
          if (this.ghostMesh && (this.ghostMesh.userData.elevated || this._isWallMount(this.ghostMesh.userData.equipId))) {
            const whu = { 'step-van': 7.0, 'box-truck': 8.0, 'ups-style': 6.5, 'flatbed': 7.5 };
            const cu = whu[this.truckType] || 6.5;
            const du = this.ghostMesh.userData;
            const maxU = cu - du.heightCells * CELL_SIZE - (du.elevationCells || 0) * CELL_SIZE;
            this._ghostHeightOffset = Math.min(maxU, (this._ghostHeightOffset || 0) + 0.25);
            UI.setStatus(`Height: ${this._formatHeight()}`);
            const hb = document.getElementById('height-item-bar');
            if (hb) { hb.classList.add('pulse'); setTimeout(() => hb.classList.remove('pulse'), 200); }
          }
          e.preventDefault();
          break;
        case 'arrowdown':
        case 'pagedown':
          if (this.ghostMesh && (this.ghostMesh.userData.elevated || this._isWallMount(this.ghostMesh.userData.equipId))) {
            const dd = this.ghostMesh.userData;
            const minD = -((dd.elevationCells || 0) * CELL_SIZE);
            this._ghostHeightOffset = Math.max(minD, (this._ghostHeightOffset || 0) - 0.25);
            UI.setStatus(`Height: ${this._formatHeight()}`);
            const hb2 = document.getElementById('height-item-bar');
            if (hb2) { hb2.classList.add('pulse'); setTimeout(() => hb2.classList.remove('pulse'), 200); }
          }
          e.preventDefault();
          break;
        case 'r':
          if (this.ghostMesh) {
            const rDef = EQUIPMENT_CATALOG.find(eq => eq.id === this.ghostMesh.userData.equipId);
            if (rDef && rDef.wallMount) {
              // Spin on the wall surface
              this._wallMountSpin = (this._wallMountSpin + Math.PI / 2) % (Math.PI * 2);
              UI.showToast('Spin ' + Math.round(this._wallMountSpin * 180 / Math.PI) + '°', 'info');
            } else {
              this.ghostRotation = (this.ghostRotation + Math.PI / 2) % (Math.PI * 2);
              this.ghostMesh.rotation.y = this.ghostRotation;
            }
          } else if (this.selectedItem) {
            this.rotateSelected();
          }
          e.preventDefault();
          break;
        case 'f':
          if (this.ghostMesh) {
            const fDef = EQUIPMENT_CATALOG.find(eq => eq.id === this.ghostMesh.userData.equipId);
            if (fDef && fDef.wallMount) {
              this._wallMountFlipped = !this._wallMountFlipped;
              UI.showToast(this._wallMountFlipped ? 'Flipped inward' : 'Facing outward', 'info');
            }
          }
          e.preventDefault();
          break;
        case 'v':
          // Cycle variant while placing
          if (this.ghostMesh && this.activeEquipId) {
            this.ghostVariant = (this.ghostVariant + 1) % 3;
            this.regenerateGhost();
          }
          e.preventDefault();
          break;
        case 'delete':
        case 'backspace':
          if (this.selectedItem) {
            this.deleteSelected();
            e.preventDefault();
          }
          break;
        case 'escape':
          if (this.ghostMesh) {
            this.cancelPlacement();
          } else if (this.selectedItem) {
            this.deselectItem();
          }
          break;
      }
    });
  },

  // Regenerate ghost mesh (used when variant changes)
  regenerateGhost() {
    if (!this.ghostMesh || !this.activeEquipId) return;
    const def = EQUIPMENT_CATALOG.find(e => e.id === this.activeEquipId);
    if (!def) return;

    const oldPos = this.ghostMesh.position.clone();
    const oldRot = this.ghostMesh.rotation.y;

    this.scene.remove(this.ghostMesh);
    this.ghostMesh = createEquipmentMesh(def, true, this.ghostVariant);
    this.ghostMesh.position.copy(oldPos);
    this.ghostMesh.rotation.y = oldRot;
    this.scene.add(this.ghostMesh);

    UI.setStatus(`Placing ${def.name} (variant ${this.ghostVariant + 1}/3) — click to place, V to change variant, R to rotate`);
  },

  // ---- Mouse Handling ----
  getMouseGridPos(event) {
    const canvas = this.renderer.domElement;
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    this.raycaster.setFromCamera(this.mouse, this.camera);
    const intersectPoint = new THREE.Vector3();
    this.raycaster.ray.intersectPlane(this.floorPlane, intersectPoint);
    return intersectPoint;
  },

  snapToGrid(pos, widthCells, depthCells, rotation) {
    // Account for rotation swapping width/depth
    let effW = widthCells;
    let effD = depthCells;
    const rotSteps = Math.round(rotation / (Math.PI / 2)) % 4;
    if (rotSteps % 2 !== 0) {
      effW = depthCells;
      effD = widthCells;
    }

    // Snap to grid cell, centering the item
    const halfW = (effW * CELL_SIZE) / 2;
    const halfD = (effD * CELL_SIZE) / 2;

    let gx = Math.round((pos.x - halfW) / CELL_SIZE) * CELL_SIZE + halfW;
    let gz = Math.round((pos.z - halfD) / CELL_SIZE) * CELL_SIZE + halfD;

    return { x: gx, z: gz, effW, effD };
  },

  _isWallMount(equipId) {
    const def = EQUIPMENT_CATALOG.find(e => e.id === equipId);
    return def && def.wallMount === true;
  },

  _getCeilingHeight() {
    const wh = { 'step-van': 7.0, 'box-truck': 8.0, 'ups-style': 6.5, 'flatbed': 7.5 };
    return wh[this.truckType] || 6.5;
  },

  // Is this a ceiling-mount item? (LEDs, hood, vents, AC, roof items)
  _isCeilingMount(equipId) {
    const def = EQUIPMENT_CATALOG.find(e => e.id === equipId);
    if (!def || !def.elevated) return false;
    // Ceiling items: hood, vents, fans, AC, LEDs, trim, speakers, rooftop stuff
    const ceilIds = ['hood-exhaust','roof-vent','exhaust-fan','ac-unit',
      'led-panel','led-strip','work-light','led-trim','rooftop-sign','speaker-system'];
    return ceilIds.includes(def.id);
  },

  // Get the dynamic elevation for an item based on chassis ceiling
  _getDynamicElevation(def) {
    if (!def || !def.elevated) return 0;
    const ceilH = this._getCeilingHeight();
    const itemH = def.heightCells * CELL_SIZE;

    if (def.roofTop) {
      // Sits ON TOP of the roof (signs, AC, roof vents)
      return ceilH;
    }
    if (this._isCeilingMount(def.id)) {
      // Hangs UNDER ceiling (hood, lights, fans, speakers)
      return ceilH - itemH;
    }
    // Everything else uses catalog elevation (wall items, shelves, panels, windows)
    return (def.elevationCells || 0) * CELL_SIZE;
  },

  _formatHeight() {
    const _fhDef = this.ghostMesh ? EQUIPMENT_CATALOG.find(e => e.id === this.ghostMesh.userData.equipId) : null;
    const baseY = this.ghostMesh && this.ghostMesh.userData.elevated && _fhDef
      ? this._getDynamicElevation(_fhDef)
      : 0;
    const totalY = baseY + (this._ghostHeightOffset || 0);
    const feet = totalY;
    const ft = Math.floor(feet);
    const inches = Math.round((feet - ft) * 12);
    return `${ft}'${inches}"`;
  },

  onMouseMove(event) {
    if (!this.ghostMesh) return;

    const pos = this.getMouseGridPos(event);
    if (!pos) return;

    const data = this.ghostMesh.userData;
    const def = EQUIPMENT_CATALOG.find(e => e.id === data.equipId);
    const isWallMount = def && def.wallMount;

    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;

    let finalX, finalZ, finalY, finalRotY;

    if (isWallMount) {
      // Snap to nearest wall — detect which wall the cursor is closest to
      const distLeft = pos.z;
      const distRight = truckD - pos.z;
      const distBack = pos.x;
      const distFront = truckW - pos.x;
      const minDist = Math.min(distLeft, distRight, distBack, distFront);

      const halfW = (data.widthCells * CELL_SIZE) / 2;
      const halfD = (data.depthCells * CELL_SIZE) / 2;
      finalY = this._getDynamicElevation(def);

      // Windows straddle the wall (punch through). Everything else sits inside.
      const isWindowItem = def.isWindow;
      // Offset: windows center on wall, others offset inward by half depth
      const inset = isWindowItem ? 0 : halfD;

      let baseRotY = 0;
      if (minDist === distRight) {
        finalZ = truckD - inset;
        finalX = Math.round((pos.x - halfW) / CELL_SIZE) * CELL_SIZE + halfW;
        finalX = Math.max(halfW, Math.min(truckW - halfW, finalX));
        baseRotY = 0;
      } else if (minDist === distLeft) {
        finalZ = inset;
        finalX = Math.round((pos.x - halfW) / CELL_SIZE) * CELL_SIZE + halfW;
        finalX = Math.max(halfW, Math.min(truckW - halfW, finalX));
        baseRotY = Math.PI;
      } else if (minDist === distFront) {
        finalX = truckW - inset;
        finalZ = Math.round((pos.z - halfW) / CELL_SIZE) * CELL_SIZE + halfW;
        finalZ = Math.max(halfW, Math.min(truckD - halfW, finalZ));
        baseRotY = Math.PI / 2;
      } else {
        finalX = inset;
        finalZ = Math.round((pos.z - halfW) / CELL_SIZE) * CELL_SIZE + halfW;
        finalZ = Math.max(halfW, Math.min(truckD - halfW, finalZ));
        baseRotY = -Math.PI / 2;
      }

      // Apply spin (R key) and flip (F key)
      finalRotY = baseRotY + this._wallMountSpin;
      if (this._wallMountFlipped) finalRotY += Math.PI;

      finalY += this._ghostHeightOffset || 0;

      // Clamp to stay between floor and ceiling
      const wallHeights = { 'step-van': 7.0, 'box-truck': 8.0, 'ups-style': 6.5, 'flatbed': 7.5 };
      const ceilH = wallHeights[this.truckType] || 6.5;
      const itemH = data.heightCells * CELL_SIZE;
      if (finalY < 0) finalY = 0;
      if (finalY + itemH > ceilH) finalY = ceilH - itemH;
      if (finalY < 0) finalY = 0; // item taller than ceiling — sit on floor

      // Also clamp X along the wall to stay within truck length
      finalX = Math.max(halfW, Math.min(truckW - halfW, finalX));
    } else {
      const snapped = this.snapToGrid(pos, data.widthCells, data.depthCells, this.ghostRotation);
      finalX = snapped.x;
      finalZ = snapped.z;
      finalY = data.elevated ? this._getDynamicElevation(def) : 0;
      finalY += this._ghostHeightOffset || 0;
      // Clamp between floor and ceiling
      const ceilClamp = this._getCeilingHeight() - data.heightCells * CELL_SIZE;
      if (finalY > ceilClamp) finalY = ceilClamp;
      if (finalY < 0) finalY = 0;
      finalRotY = this.ghostRotation;
    }

    this.ghostTarget = new THREE.Vector3(finalX, finalY, finalZ);
    // Snap instantly on first move (ghost starts at origin)
    if (!this._ghostHasMoved) {
      this.ghostMesh.position.copy(this.ghostTarget);
      this._ghostHasMoved = true;
    }
    this.ghostMesh.rotation.y = isWallMount ? finalRotY : this.ghostRotation;
    // Store wall rotation for placement
    if (isWallMount) this._wallMountRotation = finalRotY;

    // Validate
    const effW = data.widthCells;
    const effD = data.depthCells;
    const valid = isWallMount ? true : this.isPlacementValid(finalX, finalZ, effW, effD, null);
    this.ghostValid = valid;

    this.ghostMesh.traverse((child) => {
      if (child.isMesh && child.material) {
        if (child.material.color) {
          child.material.color.setHex(valid ? 0x88ff88 : 0xff4444);
        }
        child.material.opacity = valid ? 0.4 : 0.35;
      }
    });

    const isCeil = this._isCeilingMount(data.equipId);
    UI.setStatus(valid
      ? (isWallMount ? 'Click to mount · Scroll/↑↓ height · R spin · F flip'
        : isCeil ? 'Click to place · Scroll/↑↓ to adjust drop height'
        : 'Click to place')
      : 'Invalid placement — overlaps or out of bounds');
  },

  onMouseClick(event) {
    // Utility drawing mode handles its own clicks
    if (this.utilityMode && this.handleUtilityClick(event)) {
      return;
    }

    // If placing equipment
    if (this.ghostMesh) {
      // Make sure ghost is at the cursor position BEFORE checking validity
      // (in case the user clicks without mousemove first)
      this.onMouseMove(event);
      // Snap ghost instantly to the click position and run a fresh validity check
      if (this.ghostTarget) {
        this.ghostMesh.position.copy(this.ghostTarget);
        const data = this.ghostMesh.userData;
        const clickDef = EQUIPMENT_CATALOG.find(e => e.id === data.equipId);
        if (clickDef && clickDef.wallMount) {
          this.ghostValid = true;
        } else {
          const snapped = this.snapToGrid(this.ghostTarget, data.widthCells, data.depthCells, this.ghostRotation);
          this.ghostValid = this.isPlacementValid(snapped.x, snapped.z, snapped.effW, snapped.effD, null);
        }
      }
      if (this.ghostValid) {
        this.placeEquipment();
      } else {
        UI.showToast('Cannot place here — collision or out of bounds', 'error');
      }
      return;
    }

    // Raycast against placed items
    const target = this.raycastPlacedItem(event);

    if (target) {
      // Click on placed item: select AND immediately pick it up to move
      this.selectItem(target);
      this.moveSelected();
    } else {
      // Click empty space: deselect
      if (this.selectedItem) this.deselectItem();
    }
  },

  onMouseRightClick(event) {
    // Utility mode: right-click removes segments or cancels in-progress line
    if (this.utilityMode && this.handleUtilityRightClick(event)) {
      return;
    }

    // Cancel active placement ghost first
    if (this.ghostMesh) {
      this.cancelPlacement();
      return;
    }

    // Always clear any existing selection first
    const wasSelected = this.selectedItem;
    if (wasSelected) this.deselectItem();

    // Then try to delete whatever is under the cursor
    const target = this.raycastPlacedItem(event);
    if (target) {
      this.selectItem(target);
      this.deleteSelected();
    }
    // If nothing under cursor and nothing was selected, it's just a dismiss
  },

  // Helper: raycast mouse against placed items, return the group or null
  raycastPlacedItem(event) {
    const canvas = this.renderer.domElement;
    const rect = canvas.getBoundingClientRect();
    this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.mouse, this.camera);

    const meshes = [];
    this.placedItems.forEach(item => {
      item.traverse((child) => {
        if (child.isMesh) meshes.push(child);
      });
    });
    const hits = this.raycaster.intersectObjects(meshes, false);
    if (hits.length > 0) {
      let target = hits[0].object;
      while (target.parent && !target.userData.equipId) {
        target = target.parent;
      }
      if (target.userData.equipId) return target;
    }
    return null;
  },

  // Pick up the selected item for re-placement
  moveSelected() {
    if (!this.selectedItem) return;
    const item = this.selectedItem;
    const equipId = item.userData.equipId;
    const variant = item.userData.variant || 0;
    const rotation = item.userData.rotation || 0;

    // Remove from placed items
    this.scene.remove(item);
    const idx = this.placedItems.indexOf(item);
    if (idx !== -1) this.placedItems.splice(idx, 1);
    this.selectedItem = null;
    UI.hideProperties();
    UI.updateSummary(this.placedItems);
    this.updateGeneratorBay();

    // Start placement with same variant and rotation
    this.startPlacement(equipId);
    this.ghostVariant = variant;
    this.ghostRotation = rotation;
    this.regenerateGhost();
    if (this.ghostMesh) this.ghostMesh.rotation.y = rotation;

    UI.setStatus('Moving item — click to place, right-click to cancel');
  },

  // ---- Placement System ----
  startPlacement(equipId) {
    // Clear any existing ghost (without touching sidebar UI state)
    if (this.ghostMesh) {
      this.scene.remove(this.ghostMesh);
      this.ghostMesh = null;
    }
    this.deselectItem();

    const def = EQUIPMENT_CATALOG.find(e => e.id === equipId);
    if (!def) return;

    this.activeEquipId = equipId;
    this.ghostRotation = 0;
    this._ghostHeightOffset = 0;
    // Random variant for this placement session (0, 1, or 2)
    this.ghostVariant = Math.floor(Math.random() * 3);
    this.ghostMesh = createEquipmentMesh(def, true, this.ghostVariant);
    this.ghostMesh.position.set(-100, 0, -100); // offscreen initially
    this.scene.add(this.ghostMesh);

    UI.setStatus(`Placing ${def.name} (variant ${this.ghostVariant + 1}/3) — click to place, V to change variant, R to rotate`);
  },

  placeEquipment() {
    if (!this.ghostMesh || !this.activeEquipId) return;

    const def = EQUIPMENT_CATALOG.find(e => e.id === this.activeEquipId);
    if (!def) return;

    // Save checkpoint before placing
    this.pushCheckpoint();

    // Create solid mesh at ghost position, using same variant as ghost
    const item = createEquipmentMesh(def, false, this.ghostVariant);
    item.position.copy(this.ghostMesh.position);

    // Wall-mounted items use auto-detected wall rotation
    const rot = (def.wallMount && this._wallMountRotation !== undefined)
      ? this._wallMountRotation
      : this.ghostRotation;
    item.rotation.y = rot;
    item.userData.rotation = rot;

    // Store grid info for collision
    item.userData.gridX = this.ghostMesh.position.x;
    item.userData.gridZ = this.ghostMesh.position.z;
    item.userData.effW = def.widthCells;
    item.userData.effD = def.depthCells;

    this.scene.add(item);
    this.placedItems.push(item);

    // Try to upgrade to GLTF model if available
    if (typeof tryUpgradeToModel === 'function') {
      tryUpgradeToModel(item, def);
    }

    // Update UI
    UI.setItemCount(this.placedItems.length);
    UI.updateSummary(this.placedItems);
    this.updateGeneratorBay();
    UI.showToast(`${def.name} placed`, 'success');
    this.autoSave();

    // Auto-cancel placement after drop — user explicitly requested no floating ghost
    this.cancelPlacement();
  },

  cancelPlacement() {
    if (this.ghostMesh) {
      this.scene.remove(this.ghostMesh);
      this.ghostMesh = null;
    }
    this.ghostTarget = null;
    this.activeEquipId = null;
    this.ghostRotation = 0;
    this._wallMountSpin = 0;
    this._wallMountFlipped = false;
    this._wallMountRotation = undefined;
    this._ghostHasMoved = false;
    UI.clearActiveEquipment();
    UI.setStatus('Select equipment to begin');
  },

  // ---- Selection ----
  selectItem(item) {
    this.deselectItem();
    this.selectedItem = item;

    // Highlight
    item.traverse((child) => {
      if (child.isMesh && child.material && !child.userData._origColor) {
        child.userData._origColor = child.material.color.getHex();
        child.userData._origEmissive = child.material.emissive ? child.material.emissive.getHex() : 0;
        if (child.material.emissive) {
          child.material.emissive.setHex(0x1a3a5c);
        }
      }
    });

    UI.showProperties(item);
    UI.setStatus(`Selected: ${item.userData.name} — R to rotate, Del to remove`);
  },

  deselectItem() {
    if (!this.selectedItem) return;

    // Remove highlight
    this.selectedItem.traverse((child) => {
      if (child.isMesh && child.material && child.userData._origColor !== undefined) {
        child.material.color.setHex(child.userData._origColor);
        if (child.material.emissive) {
          child.material.emissive.setHex(child.userData._origEmissive || 0);
        }
        delete child.userData._origColor;
        delete child.userData._origEmissive;
      }
    });

    this.selectedItem = null;
    UI.hideProperties();
    UI.setStatus('Select equipment to begin');
  },

  // ---- Rotation ----
  rotateSelected() {
    if (!this.selectedItem) return;

    const item = this.selectedItem;
    const newRot = (item.userData.rotation || 0) + Math.PI / 2;

    // Compute new effective dimensions
    const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
    if (!def) return;

    const snapped = this.snapToGrid(item.position, def.widthCells, def.depthCells, newRot);

    // Check if rotated position is valid
    const idx = this.placedItems.indexOf(item);
    if (this.isPlacementValid(snapped.x, snapped.z, snapped.effW, snapped.effD, item, !!item.userData.elevated)) {
      item.rotation.y = newRot;
      item.position.set(snapped.x, item.position.y, snapped.z);
      item.userData.rotation = newRot;
      item.userData.gridX = snapped.x;
      item.userData.gridZ = snapped.z;
      item.userData.effW = snapped.effW;
      item.userData.effD = snapped.effD;
      UI.showProperties(item);
      UI.showToast('Rotated', 'info');
    } else {
      UI.showToast('Cannot rotate — would cause collision', 'error');
    }
  },

  // ---- Deletion ----
  deleteSelected() {
    if (!this.selectedItem) return;

    this.pushCheckpoint();
    const name = this.selectedItem.userData.name;
    this.scene.remove(this.selectedItem);
    const idx = this.placedItems.indexOf(this.selectedItem);
    if (idx !== -1) this.placedItems.splice(idx, 1);

    this.selectedItem = null;
    UI.hideProperties();
    UI.setItemCount(this.placedItems.length);
    UI.updateSummary(this.placedItems);
    this.updateGeneratorBay();
    UI.showToast(`${name} removed`, 'removed');
    UI.setStatus('Select equipment to begin');
  },

  // ---- Collision Detection (AABB) ----
  isPlacementValid(cx, cz, effW, effD, excludeItem, isElevated) {
    const halfW = (effW * CELL_SIZE) / 2;
    const halfD = (effD * CELL_SIZE) / 2;

    const minX = cx - halfW;
    const maxX = cx + halfW;
    const minZ = cz - halfD;
    const maxZ = cz + halfD;

    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;

    // Boundary check — wall-mounted items can extend beyond walls (they straddle the wall plane)
    const tol = isElevated ? 2.0 : 0.01;
    if (minX < -tol || maxX > truckW + tol || minZ < -tol || maxZ > truckD + tol) {
      return false;
    }

    // Determine elevation state of the item being placed
    if (isElevated === undefined && this.ghostMesh) {
      isElevated = !!this.ghostMesh.userData.elevated;
    }

    // Wheel well collision (floor items only)
    if (!isElevated && this._wheelWellBoxes && this._wheelWellBoxes.length > 0) {
      for (const w of this._wheelWellBoxes) {
        const wMinX = w.x - w.halfW;
        const wMaxX = w.x + w.halfW;
        const wMinZ = w.z - w.halfD;
        const wMaxZ = w.z + w.halfD;
        if (minX < wMaxX - 0.01 && maxX > wMinX + 0.01 &&
            minZ < wMaxZ - 0.01 && maxZ > wMinZ + 0.01) {
          return false;
        }
      }
    }

    // Overlap check: elevated items only collide with elevated items,
    // floor items only collide with floor items
    for (const item of this.placedItems) {
      if (item === excludeItem) continue;
      const itemElevated = !!item.userData.elevated;
      if (isElevated !== itemElevated) continue;

      const iHalfW = (item.userData.effW * CELL_SIZE) / 2;
      const iHalfD = (item.userData.effD * CELL_SIZE) / 2;
      const iMinX = item.userData.gridX - iHalfW;
      const iMaxX = item.userData.gridX + iHalfW;
      const iMinZ = item.userData.gridZ - iHalfD;
      const iMaxZ = item.userData.gridZ + iHalfD;

      // AABB overlap
      if (minX < iMaxX - 0.01 && maxX > iMinX + 0.01 &&
          minZ < iMaxZ - 0.01 && maxZ > iMinZ + 0.01) {
        return false;
      }
    }

    return true;
  },

  // ---- Truck Resizing ----
  resizeTruck(lengthFt, widthFt) {
    // Remove all placed items
    this.placedItems.forEach(item => this.scene.remove(item));
    this.placedItems = [];
    this.deselectItem();
    this.cancelPlacement();

    this.truckLengthFt = lengthFt;
    if (widthFt !== undefined) this.truckWidthFt = widthFt;
    this.buildTruck();
    this.buildGridOverlay();

    // Re-center camera on full truck (box body + cab)
    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;
    this.controls.target.set(truckW / 2 - 2.5, 2, truckD / 2);
    this.controls.update();

    UI.setItemCount(0);
    UI.updateSummary([]);
    UI.setDimensionsInfo(`${this.truckLengthFt}ft × ${this.truckWidthFt}ft`);
    UI.showToast(`Truck resized to ${lengthFt}ft × ${this.truckWidthFt}ft`, 'info');
  },

  // ---- Quote Submission ----
  // ---- Audio System ----
  _audioUnlocked: false,
  _audioCtx: null,

  // Unlock audio on first user interaction — browsers block audio until a gesture
  initAudioSystem() {
    const unlock = () => {
      if (this._audioUnlocked) return;
      if (!this._audioCtx) {
        this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      }
      if (this._audioCtx.state === 'suspended') {
        this._audioCtx.resume();
      }
      const buf = this._audioCtx.createBuffer(1, 1, 22050);
      const src = this._audioCtx.createBufferSource();
      src.buffer = buf;
      src.connect(this._audioCtx.destination);
      src.start(0);
      this._audioUnlocked = true;
    };
    ['click', 'touchstart', 'keydown'].forEach(evt => {
      document.addEventListener(evt, unlock, { once: true, passive: true });
    });
  },

  async submitQuote(formData) {
    const layoutData = this.placedItems.map(item => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
      return {
        equipmentId: item.userData.equipId,
        name: item.userData.name,
        positionX: item.userData.gridX,
        positionZ: item.userData.gridZ,
        rotation: Math.round(THREE.MathUtils.radToDeg(item.userData.rotation || 0)),
        widthCells: item.userData.widthCells,
        depthCells: item.userData.depthCells,
        dimensions: def ? getFormattedDims(def) : ''
      };
    });

    const submission = {
      customer_name: formData.name,
      email: formData.email,
      phone: formData.phone || null,
      truck_length_ft: parseInt(formData.truckLength),
      truck_width_ft: this.truckWidthFt,
      notes: formData.notes || null,
      layout_json: layoutData,
      item_count: this.placedItems.length
    };

    // Try Supabase if configured
    // Demo mode: save a complete text file instead of hitting backend
    const lines = [];
    lines.push('='.repeat(60));
    lines.push('BROTHERS FABRICATION — QUOTE REQUEST');
    lines.push('='.repeat(60));
    lines.push(`Submitted: ${new Date().toLocaleString()}`);
    lines.push('');
    lines.push('-- CUSTOMER --');
    lines.push(`Name:      ${formData.name}`);
    lines.push(`Email:     ${formData.email}`);
    lines.push(`Phone:     ${formData.phone || '(not provided)'}`);
    lines.push(`Timeline:  ${formData.timeline || '(not specified)'}`);
    lines.push(`Budget:    ${formData.budget || '(not specified)'}`);
    lines.push('');
    lines.push('-- TRUCK --');
    lines.push(`Length:    ${formData.truckLength} ft`);
    lines.push(`Width:     ${this.truckWidthFt} ft`);
    lines.push('');
    lines.push('-- NOTES --');
    lines.push(formData.notes || '(none)');
    lines.push('');
    // Attach the full materials list
    lines.push(this.generateMaterialsList());
    lines.push('');
    lines.push('-- RAW LAYOUT JSON --');
    lines.push(JSON.stringify(layoutData, null, 2));

    const blob = new Blob([lines.join('\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const safeName = (formData.name || 'anon').replace(/[^a-z0-9]/gi, '_').toLowerCase();
    a.href = url;
    a.download = `brofab-quote-${safeName}-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    UI.showToast('Quote saved — check your downloads!', 'success');
    return true;
  },

  // ---- Portfolio / Client Package Generator ----
  async generatePortfolio() {
    if (typeof JSZip === 'undefined') {
      UI.showToast('JSZip not loaded — cannot generate portfolio', 'error');
      return;
    }
    if (this.placedItems.length === 0) {
      UI.showToast('Place some equipment first', 'error');
      return;
    }

    UI.showToast('Generating portfolio — hold tight...', 'info');
    const zip = new JSZip();
    const folder = zip.folder('truck-layout-portfolio');

    // Save current state
    const origCamPos = this.camera.position.clone();
    const origTarget = this.controls.target.clone();
    const origWallVis = this.wallVisibility;
    const origRoof = this.showRoof;
    const origDims = UI.showDimensions;

    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;
    const cx = truckW / 2;
    const cz = truckD / 2;
    const ceilH = this._getCeilingHeight();

    const takeShot = async (name) => {
      this.controls.update();
      this.renderer.render(this.scene, this.camera);
      await new Promise(r => setTimeout(r, 100));
      this.renderer.render(this.scene, this.camera);
      const dataUrl = this.renderer.domElement.toDataURL('image/png', 0.95);
      const data = dataUrl.split(',')[1];
      folder.file(name, data, { base64: true });
    };

    const lookAt = (x, y, z) => {
      this.controls.target.set(x, y, z);
      this.camera.lookAt(x, y, z);
    };

    try {
      // 1. EXTERIOR — full walls + roof, isometric
      this.wallVisibility = 'full';
      this.showRoof = true;
      if (this._ceilingMesh) this._ceilingMesh.visible = true;
      this._truckWalls.forEach(w => { w.material.opacity = 0.95; w.material.visible = true; });

      this.camera.position.set(cx + 30, 20, cz + 25);
      lookAt(cx, ceilH / 2, cz);
      await takeShot('01-exterior-iso.png');

      // 2. EXTERIOR — front 3/4 angle
      this.camera.position.set(cx + 25, 15, cz - 20);
      lookAt(cx, ceilH / 2, cz);
      await takeShot('02-exterior-front.png');

      // 3. EXTERIOR — rear view
      this.camera.position.set(cx - 25, 12, cz + 15);
      lookAt(cx, ceilH / 2, cz);
      await takeShot('03-exterior-rear.png');

      // 4. SERVING SIDE — eye level from customer perspective
      this.camera.position.set(cx, ceilH * 0.5, cz + 20);
      lookAt(cx, ceilH * 0.4, cz);
      await takeShot('04-serving-side.png');

      // 5. INTERIOR — roof off, walls transparent, isometric
      this.showRoof = false;
      if (this._ceilingMesh) this._ceilingMesh.visible = false;
      this.wallVisibility = 'low';
      this._truckWalls.forEach(w => { w.material.opacity = 0.25; w.material.visible = true; });

      this.camera.position.set(cx + 28, 22, cz + 22);
      lookAt(cx, 2.5, cz);
      await takeShot('05-interior-iso.png');

      // 6. INTERIOR — top down
      this.camera.position.set(cx + 0.01, 30, cz);
      lookAt(cx, 0, cz);
      await takeShot('06-interior-topdown.png');

      // 7. INTERIOR — close up from serving side looking in
      this._truckWalls.forEach(w => { w.material.opacity = 0.15; w.material.visible = true; });
      this.camera.position.set(cx, ceilH * 0.4, cz + 8);
      lookAt(cx, ceilH * 0.3, cz);
      await takeShot('07-interior-closeup-service.png');

      // 8. INTERIOR — close up from cooking side
      this.camera.position.set(cx, ceilH * 0.4, cz - 8);
      lookAt(cx, ceilH * 0.3, cz);
      await takeShot('08-interior-closeup-cooking.png');

      // 9. WITH MEASUREMENTS — iso view, dims on
      UI.showDimensions = true;
      document.body.classList.add('ruler-on');
      if (typeof this.buildDimensionLines === 'function') this.buildDimensionLines();
      this._truckWalls.forEach(w => { w.material.opacity = 0.25; });

      this.camera.position.set(cx + 28, 22, cz + 22);
      lookAt(cx, 2.5, cz);
      await takeShot('09-measured-iso.png');

      // 10. MEASUREMENTS — top down
      this.camera.position.set(cx + 0.01, 30, cz);
      lookAt(cx, 0, cz);
      await takeShot('10-measured-topdown.png');

      UI.showDimensions = origDims;
      document.body.classList.toggle('ruler-on', origDims);

      // 11. Generate summary text document
      const summary = this._generatePortfolioSummary();
      folder.file('layout-summary.txt', summary);

      // 12. Generate equipment list CSV
      const csv = this._generatePortfolioCSV();
      folder.file('equipment-list.csv', csv);

      // 13. Export layout JSON for import later
      const layout = JSON.stringify(this.serialize(), null, 2);
      folder.file('layout-data.json', layout);

      // Restore original state
      this.camera.position.copy(origCamPos);
      this.controls.target.copy(origTarget);
      this.wallVisibility = origWallVis;
      this.showRoof = origRoof;
      if (this._ceilingMesh) this._ceilingMesh.visible = origRoof;
      this.controls.update();

      // Generate and download ZIP
      const blob = await zip.generateAsync({ type: 'blob' });
      const a = document.createElement('a');
      const safeName = (document.getElementById('internal-notes')?.value || 'truck-layout')
        .split('\n')[0].slice(0, 30).replace(/[^a-z0-9]/gi, '-').toLowerCase() || 'truck-layout';
      a.href = URL.createObjectURL(blob);
      a.download = `brofab-portfolio-${safeName}-${new Date().toISOString().slice(0,10)}.zip`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);

      UI.showToast('Portfolio ZIP downloaded — 10 shots + summary + CSV + layout', 'success');

    } catch (e) {
      console.error('Portfolio generation failed:', e);
      UI.showToast('Portfolio failed: ' + e.message, 'error');
      // Restore state on error
      this.camera.position.copy(origCamPos);
      this.controls.target.copy(origTarget);
      this.wallVisibility = origWallVis;
      this.showRoof = origRoof;
      if (this._ceilingMesh) this._ceilingMesh.visible = origRoof;
      this.controls.update();
    }
  },

  _generatePortfolioSummary() {
    const lines = [];
    lines.push('═══════════════════════════════════════');
    lines.push('  BROTHERS FABRICATION — TRUCK LAYOUT');
    lines.push('═══════════════════════════════════════');
    lines.push('');
    lines.push(`Date: ${new Date().toLocaleDateString()}`);
    lines.push(`Chassis: ${this.truckType}`);
    lines.push(`Dimensions: ${this.truckLengthFt}ft × ${this.truckWidthFt}ft`);
    lines.push(`Ceiling: ${this._getCeilingHeight().toFixed(1)}ft`);
    lines.push(`Total items: ${this.placedItems.length}`);
    lines.push('');

    // Equipment list
    lines.push('─── EQUIPMENT ───');
    const counts = {};
    let totalCost = 0;
    this.placedItems.forEach(item => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
      if (!def) return;
      if (!counts[def.name]) counts[def.name] = { count: 0, cost: def.cost || 0 };
      counts[def.name].count++;
      totalCost += def.cost || 0;
    });
    for (const [name, info] of Object.entries(counts)) {
      lines.push(`  ${info.count}× ${name}  —  $${(info.count * info.cost).toLocaleString()}`);
    }
    lines.push('');
    lines.push(`Equipment subtotal: $${totalCost.toLocaleString()}`);
    lines.push(`Labor (est. 25%):   $${Math.round(totalCost * 0.25).toLocaleString()}`);
    lines.push(`Materials (est. 15%): $${Math.round(totalCost * 0.15).toLocaleString()}`);
    lines.push(`─────────────────`);
    lines.push(`ESTIMATE TOTAL:     $${Math.round(totalCost * 1.4).toLocaleString()}`);
    lines.push('');

    // Power
    let totalW = 0, supplyW = 0, freshGal = 0, greyGal = 0;
    this.placedItems.forEach(item => {
      const id = item.userData.equipId;
      const def = EQUIPMENT_CATALOG.find(e => e.id === id);
      if (UI._powerConsumption[id]) totalW += UI._powerConsumption[id];
      if (def && def.provides_power) supplyW += def.provides_power;
      if (def && def.freshWaterGal) freshGal += def.freshWaterGal;
      if (def && def.greyWaterGal) greyGal += def.greyWaterGal;
    });
    lines.push('─── UTILITIES ───');
    lines.push(`  Power load: ${totalW.toLocaleString()}W (peak ${Math.round(totalW * 1.25).toLocaleString()}W)`);
    lines.push(`  Generator:  ${supplyW.toLocaleString()}W`);
    lines.push(`  Fresh water: ${freshGal} gal`);
    lines.push(`  Grey water:  ${greyGal} gal`);
    lines.push('');

    // Notes
    const notes = document.getElementById('internal-notes')?.value;
    if (notes) {
      lines.push('─── NOTES ───');
      lines.push(notes);
      lines.push('');
    }

    lines.push('═══════════════════════════════════════');
    lines.push('  Generated by Brothers Fabrication');
    lines.push('  Truck Configurator + Builder');
    lines.push('  brothersfabrication.ca');
    lines.push('═══════════════════════════════════════');
    return lines.join('\n');
  },

  _generatePortfolioCSV() {
    let csv = 'Qty,Item,Category,Width ft,Depth ft,Height ft,Unit Cost,Line Total,Description\n';
    const counts = {};
    this.placedItems.forEach(item => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
      if (!def) return;
      if (!counts[def.id]) counts[def.id] = { def, count: 0 };
      counts[def.id].count++;
    });
    for (const { def, count } of Object.values(counts)) {
      csv += `${count},"${def.name}","${def.category}",${def.widthCells/2},${def.depthCells/2},${def.heightCells/2},${def.cost || 0},${(def.cost || 0) * count},"${(def.description || '').replace(/"/g, '""')}"\n`;
    }
    return csv;
  },

  // ---- Render Loop ----
  animate() {
    requestAnimationFrame(() => this.animate());

    // Smooth ghost translation toward target
    if (this.ghostMesh && this.ghostTarget) {
      this.ghostMesh.position.lerp(this.ghostTarget, 0.4);

      // Run validity check — wall-mounted items always valid (they snap to walls)
      const data = this.ghostMesh.userData;
      const def = EQUIPMENT_CATALOG.find(e => e.id === data.equipId);
      const isWM = def && def.wallMount;
      let valid;
      if (isWM) {
        valid = true; // wall items always placeable
      } else {
        const snapped = this.snapToGrid(this.ghostTarget, data.widthCells, data.depthCells, this.ghostRotation);
        valid = this.isPlacementValid(snapped.x, snapped.z, snapped.effW, snapped.effD, null);
      }
      if (valid !== this.ghostValid) {
        this.ghostValid = valid;
        const goodColor = 0x7fdbca;
        const badColor = 0xff5555;
        this.ghostMesh.traverse((child) => {
          if (child.isMesh && child.material) {
            if (child.material.color) child.material.color.setHex(valid ? goodColor : badColor);
            if (child.material.emissive) child.material.emissive.setHex(valid ? goodColor : badColor);
          } else if (child.isLine && child.material && child.material.color) {
            child.material.color.setHex(valid ? goodColor : badColor);
          }
        });
        UI.setStatus(valid ? '✓ Click to place here' : '✗ Cannot place — overlaps or out of bounds');
      }
    }

    this.controls.update();
    this.updateHeightAdjustVisibility();

    // Dynamic wall transparency based on camera position
    this.updateWallTransparency();

    this.renderer.render(this.scene, this.camera);

    // Update dimension overlays if enabled
    if (UI.showDimensions) UI.updateDimensionOverlays();
  },

  wheelWellPosition: 0.72,
  wheelWellSize: 'standard',
  rearDoorType: 'double',   // double, single, roll-up, none
  rearDoorOpen: false,
  manDoorType: 'slide',     // slide, swing, none
  manDoorSize: 'standard',
  manDoorWall: 'front',  // front, left-rear, left-front, right-rear, right-front
  manDoorOpen: false,

  // ---- Screenshot & Video Export ----
  saveScreenshot(format) {
    try {
      // Force a clean render frame
      this.renderer.render(this.scene, this.camera);
      const canvas = this.renderer.domElement;
      const mime = format === 'jpg' ? 'image/jpeg' : 'image/png';
      const dataUrl = canvas.toDataURL(mime, 0.92);
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = `brofab-layout-${Date.now()}.${format}`;
      a.click();
      UI.showToast(`Saved ${format.toUpperCase()} screenshot`, 'success');
    } catch (e) {
      console.error('Screenshot failed:', e);
      UI.showToast('Screenshot failed: ' + e.message, 'error');
    }
  },

  async recordRotationVideo() {
    if (this._isRecording) {
      UI.showToast('Already recording', 'info');
      return;
    }
    if (typeof MediaRecorder === 'undefined') {
      UI.showToast('MediaRecorder not supported in this browser', 'error');
      return;
    }
    this._isRecording = true;

    const canvas = this.renderer.domElement;
    const stream = canvas.captureStream(30); // 30 fps

    // Try codecs in order of preference
    let mimeType = 'video/webm;codecs=vp9';
    if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = 'video/webm;codecs=vp8';
    if (!MediaRecorder.isTypeSupported(mimeType)) mimeType = 'video/webm';

    const chunks = [];
    const recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 6000000 });
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

    const finish = () => {
      const blob = new Blob(chunks, { type: 'video/webm' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `brofab-rotation-${Date.now()}.webm`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      UI.showToast('Video saved', 'success');
      this._isRecording = false;
    };
    recorder.onstop = finish;

    // Save original camera state
    const origPos = this.camera.position.clone();
    const origTarget = this.controls.target.clone();

    // Compute orbit center + radius — include cab in the framing
    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;
    const cx = truckW / 2 - 2.5;
    const cz = truckD / 2;
    const cy = 4;
    const totalLen = truckW + 5; // box body + cab
    const radius = Math.max(totalLen, truckD) * 1.8 + 20;
    const elev = radius * 0.55;

    this.controls.target.set(cx, 2, cz);

    recorder.start();
    UI.showToast('Recording 360° rotation...', 'info');

    const duration = 6000; // 6 seconds
    const startTime = performance.now();

    return new Promise((resolve) => {
      const step = () => {
        const t = (performance.now() - startTime) / duration;
        if (t >= 1) {
          // Restore camera
          this.camera.position.copy(origPos);
          this.controls.target.copy(origTarget);
          this.controls.update();
          recorder.stop();
          resolve();
          return;
        }
        const angle = t * Math.PI * 2;
        this.camera.position.set(
          cx + Math.cos(angle) * radius,
          cy + elev,
          cz + Math.sin(angle) * radius
        );
        this.camera.lookAt(cx, 3, cz);
        this.controls.update();
        this.renderer.render(this.scene, this.camera);
        requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  },

  // Get wheel well positions/sizes based on truck chassis type
  // Real wheel wells intrude far into the interior — usually 36-48" long, 20-28" deep
  getWheelWellConfig() {
    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;

    // Size multipliers: small (compact van), standard, large (heavy duty), dually (wide dual tires)
    const sizeScale = {
      small:    { w: 0.7, d: 0.7, h: 0.6 },
      standard: { w: 1.0, d: 1.0, h: 1.0 },
      large:    { w: 1.3, d: 1.2, h: 1.2 },
      dually:   { w: 1.5, d: 1.5, h: 1.0 }
    };
    const sc = sizeScale[this.wheelWellSize] || sizeScale.standard;

    const makeWells = (baseW, baseD, baseH) => {
      const ww = baseW * sc.w;
      const wd = baseD * sc.d;
      const wh = baseH * sc.h;
      return [
        { x: truckW * this.wheelWellPosition, z: wd / 2, w: ww, d: wd, h: wh },
        { x: truckW * this.wheelWellPosition, z: truckD - wd / 2, w: ww, d: wd, h: wh }
      ];
    };

    switch (this.truckType) {
      case 'box-truck':    return makeWells(4.5, 2.2, 0.85);
      case 'ups-style':    return makeWells(3.2, 2.5, 1.0);
      case 'flatbed':      return makeWells(3.0, 1.8, 0.68);
      case 'step-van':
      default:             return makeWells(3.5, 2.0, 0.85);
    }
  },

  // ---- Dynamic Wall Transparency ----
  updateWallTransparency() {
    if (!this._truckWalls || this._truckWalls.length === 0) return;

    // When placing a wall-mounted item, force all walls to semi-transparent minimum
    const placingWallItem = this.ghostMesh && this._isWallMount(this.ghostMesh.userData.equipId);
    if (placingWallItem) {
      this._truckWalls.forEach(wall => {
        wall.material.visible = true;
        wall.material.opacity = Math.max(wall.material.opacity, 0.3);
        if (wall.material.opacity > 0.5) wall.material.opacity = 0.3;
      });
      return;
    }

    const mode = this.wallVisibility;

    // Fixed modes: all walls get the same opacity
    if (mode !== 'auto') {
      let fixed, edgeOp;
      if (mode === 'off') { fixed = 0; edgeOp = 0.15; }
      else if (mode === 'low') { fixed = 0.25; edgeOp = 0.4; }
      else { fixed = 0.95; edgeOp = 0.9; } // full
      this._truckWalls.forEach(wall => {
        wall.material.opacity = fixed;
        wall.material.visible = fixed > 0;
        if (wall.edges) { wall.edges.visible = edgeOp > 0; }
        if (wall.edgeMaterial) { wall.edgeMaterial.opacity = edgeOp; }
      });
      return;
    }

    // Auto mode: only the 1-2 walls closest to the camera fade out
    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;
    const truckCenter = new THREE.Vector3(truckW / 2, 0, truckD / 2);
    const camDir = new THREE.Vector3().subVectors(this.camera.position, truckCenter).normalize();
    camDir.y = 0; // ignore vertical tilt
    camDir.normalize();

    const cutawayOp = this.frontWallOpacity;
    const solidOp = 0.95;

    // Compute facing score for each wall (0 = behind, 1 = fully facing camera)
    const scores = this._truckWalls.map(wall => {
      const n = wall.normal.clone();
      n.y = 0;
      n.normalize();
      return Math.max(0, n.dot(camDir)); // only positive = facing camera
    });

    // Find max for relative blending so at least one wall is most transparent
    const maxScore = Math.max(...scores, 0.01);

    this._truckWalls.forEach((wall, i) => {
      wall.material.visible = true;
      const s = scores[i];
      const t = s > 0.3 ? Math.min(1, (s - 0.3) / 0.4) : 0;
      wall.material.opacity = solidOp + (cutawayOp - solidOp) * t;
      if (wall.edges) wall.edges.visible = true;
      if (wall.edgeMaterial) wall.edgeMaterial.opacity = Math.max(0.2, 0.9 + (0.2 - 0.9) * t);
    });
  },

  // ---- Dimension Lines (DIMS mode) ----
  // Architectural style: |-----| with thick end caps and extension lines
  buildDimensionLines() {
    if (this._dimensionGroup) {
      this.scene.remove(this._dimensionGroup);
      this._dimensionGroup = null;
    }
    if (!UI.showDimensions) return;

    const group = new THREE.Group();
    group.name = 'dimension-lines';

    // Color palette — different colors for different dim types
    const COLOR_LENGTH = 0x00ffe5; // cyan — overall truck length
    const COLOR_WIDTH = 0xff5599;  // magenta — overall truck width
    const COLOR_ITEM_W = 0xffdd44; // yellow — per-item width
    const COLOR_ITEM_D = 0x66ff66; // green — per-item depth

    // Helper: draw a dimension line in a given color
    const makeDimLine = (start, end, offsetDir, offsetDist, tickLength, color) => {
      tickLength = tickLength || 0.25;
      const lineMat = new THREE.LineBasicMaterial({ color, transparent: false, opacity: 1, depthTest: false });
      const extMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.55, depthTest: false });

      const offset = offsetDir.clone().multiplyScalar(offsetDist);
      const a = start.clone().add(offset);
      const b = end.clone().add(offset);

      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([a, b]), lineMat));

      const perp = new THREE.Vector3(-offsetDir.z, 0, offsetDir.x).normalize();
      const tickVec = perp.clone().multiplyScalar(tickLength / 2);
      const verticalTick = new THREE.Vector3(0, tickLength / 2, 0);

      // End caps with cross shape
      [a, b].forEach(pt => {
        group.add(new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([pt.clone().sub(tickVec), pt.clone().add(tickVec)]),
          lineMat
        ));
        group.add(new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([pt.clone().sub(verticalTick), pt.clone().add(verticalTick)]),
          lineMat
        ));
      });

      // Extension lines
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([start, a]), extMat));
      group.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([end, b]), extMat));
    };

    const truckW = this.gridCellsX * CELL_SIZE;
    const truckD = this.gridCellsZ * CELL_SIZE;

    // Truck LENGTH (cyan)
    makeDimLine(
      new THREE.Vector3(0, 0.02, 0),
      new THREE.Vector3(truckW, 0.02, 0),
      new THREE.Vector3(0, 0, -1), 1.4, 0.5,
      COLOR_LENGTH
    );

    // Truck WIDTH (magenta)
    makeDimLine(
      new THREE.Vector3(0, 0.02, 0),
      new THREE.Vector3(0, 0.02, truckD),
      new THREE.Vector3(-1, 0, 0), 1.4, 0.5,
      COLOR_WIDTH
    );

    // Per-item dimensions — stagger offsets to avoid overlap
    // Sort items by X position so consecutive items get progressively offset
    const sortedItems = this.placedItems
      .filter(i => !i.userData.elevated)
      .slice()
      .sort((a, b) => a.position.x - b.position.x);

    const usedOffsets = []; // {x1, x2, offset} for front edge
    sortedItems.forEach(item => {
      const data = item.userData;
      const effW = data.effW * CELL_SIZE;
      const effD = data.effD * CELL_SIZE;
      const x = item.position.x;
      const z = item.position.z;
      const x1 = x - effW / 2;
      const x2 = x + effW / 2;
      const z2 = z + effD / 2;

      // Find a non-overlapping offset (stagger in 0.35 increments)
      let offset = 0.4;
      let tries = 0;
      while (tries < 10) {
        const conflict = usedOffsets.some(u =>
          Math.abs(u.offset - offset) < 0.2 &&
          !(x2 < u.x1 - 0.1 || x1 > u.x2 + 0.1)
        );
        if (!conflict) break;
        offset += 0.45;
        tries++;
      }
      usedOffsets.push({ x1, x2, offset });

      // Width dimension (yellow) in front of the item
      makeDimLine(
        new THREE.Vector3(x1, 0.015, z2),
        new THREE.Vector3(x2, 0.015, z2),
        new THREE.Vector3(0, 0, 1), offset, 0.18,
        COLOR_ITEM_W
      );
    });

    // Render dim lines on top of everything
    group.traverse(c => {
      if (c.material) c.renderOrder = 999;
    });
    this.scene.add(group);
    this._dimensionGroup = group;
  },

  // ---- Resize Handler ----
  handleResize() {
    const container = document.getElementById('viewport');
    const width = container.clientWidth;
    const height = container.clientHeight;

    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();

    this.renderer.setSize(width, height);
  }
};

// Expose to window for debugging and UI module access
window.app = app;

// ---- Friendly Error System ----

// Reusable friendly error display (used by init and global handler)
app._showFriendlyError = function(title, technical, suggestion) {
  try {
    const overlay = document.getElementById('error-overlay');
    const msgEl = document.getElementById('error-msg');
    const titleEl = document.querySelector('.error-title');
    if (overlay && msgEl) {
      if (titleEl) titleEl.textContent = title || 'Something went wrong';
      msgEl.innerHTML = (suggestion ? '<p style="margin-bottom:8px;">' + suggestion + '</p>' : '') +
        '<details style="margin-top:8px;"><summary style="cursor:pointer;font-size:10px;color:#9aa0a6;">Technical details</summary><pre style="margin-top:6px;white-space:pre-wrap;font-size:10px;">' +
        (technical || 'No details available') + '</pre></details>';
      overlay.classList.remove('hidden');
    }
    const loader = document.getElementById('loader');
    if (loader) loader.classList.add('hidden');
  } catch (e) {
    console.error('Error overlay failed:', e);
  }
};

function showFatalError(msg) {
  app._showFriendlyError(
    'Hit a snag',
    msg,
    'Something broke unexpectedly. Try hitting Reload — your layout is auto-saved so nothing should be lost.'
  );
}

window.addEventListener('error', (e) => {
  console.error('Uncaught error:', e.error || e.message);
  if (e.error && e.error.message && /undefined|null|cannot read|not a function/i.test(e.error.message)) {
    if (!window._errorShown) {
      window._errorShown = true;
      showFatalError(e.error.message);
    }
  }
});

window.addEventListener('unhandledrejection', (e) => {
  console.error('Unhandled promise:', e.reason);
});

document.addEventListener('DOMContentLoaded', () => {
  const reload = document.getElementById('error-reload');
  if (reload) reload.addEventListener('click', () => window.location.reload());
});

// ---- Boot ----
window.addEventListener('DOMContentLoaded', () => {
  try {
    app.init();
  } catch (e) {
    console.error('App init failed:', e);
    showFatalError('Failed to initialize: ' + (e.message || e));
  }
});
