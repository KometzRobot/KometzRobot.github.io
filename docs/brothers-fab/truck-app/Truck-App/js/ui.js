// ============================================
// UI Module — Food Truck Layout Builder
// ============================================

const UI = {
  mode: 'customer', // 'customer' or 'internal'
  colorAccents: false,  // legacy — now split into colorTint + colorIndicators
  colorTint: false,
  colorIndicators: false,
  showDimensions: false,
  _searchFilter: '',

  // Power consumption (watts) for items — used for generator sizing
  _powerConsumption: {
    'flat-top-griddle': 4500,
    'deep-fryer': 5000,
    'range-oven': 6000,
    'charbroiler': 4000,
    'steam-table': 2500,
    'refrigerator': 450,
    'freezer': 550,
    'under-counter-fridge': 300,
    'sandwich-prep': 500,
    'glass-door-cooler': 400,
    'chest-freezer': 500,
    'ice-machine': 600,
    'kegerator': 350,
    'hood-exhaust': 1200,
    'exhaust-fan': 400,
    'ac-unit': 2500,
    'led-panel': 40,
    'led-strip': 15,
    'work-light': 60,
    'cash-register': 100,
    'switch-panel': 0,
    'outlet-strip': 0,
    'menu-board': 80,
    'water-heater': 200,
    'speaker-system': 150,
    'amp-head': 250,
    'led-trim': 80,
    'rooftop-sign': 400,
    'outdoor-menu-board': 120,
    'outdoor-signage': 60
  },

  // Which utilities each equipment type needs (for line estimation)
  _utilityRequirements: {
    'flat-top-griddle': ['gas', 'electrical'],
    'deep-fryer': ['gas', 'electrical'],
    'range-oven': ['gas', 'electrical'],
    'charbroiler': ['gas'],
    'steam-table': ['electrical', 'water'],
    '3-comp-sink': ['water'],
    'hand-wash-sink': ['water'],
    'hood-exhaust': ['electrical'],
    'roof-vent': [],
    'exhaust-fan': ['electrical'],
    'ac-unit': ['electrical'],
    'led-panel': ['electrical'],
    'led-strip': ['electrical'],
    'work-light': ['electrical'],
    'refrigerator': ['electrical'],
    'freezer': ['electrical'],
    'under-counter-fridge': ['electrical'],
    'sandwich-prep': ['electrical'],
    'glass-door-cooler': ['electrical'],
    'chest-freezer': ['electrical'],
    'ice-machine': ['electrical', 'water'],
    'kegerator': ['electrical'],
    'cash-register': ['electrical'],
    'control-panel': [],
    'switch-panel': ['electrical'],
    'outlet-strip': ['electrical'],
    'menu-board': ['electrical'],
    'water-heater': ['water', 'gas'],
    'propane-tank': [],
    'fire-suppression': []
  },

  // Source items for each utility (line endpoint)
  _utilitySources: {
    'electrical': ['control-panel'],
    'water': ['water-heater'],
    'gas': ['propane-tank']
  },

  // Map equipment IDs to Material Symbol names (all verified to exist)
  _iconMap: {
    'flat-top-griddle': 'cooking',
    'deep-fryer': 'fastfood',
    'range-oven': 'microwave',
    'charbroiler': 'outdoor_grill',
    'steam-table': 'soup_kitchen',
    'prep-table-4ft': 'table_restaurant',
    'prep-table-6ft': 'table_restaurant',
    '3-comp-sink': 'water_drop',
    'hand-wash-sink': 'wash',
    'hood-exhaust': 'mode_fan',
    'roof-vent': 'air',
    'exhaust-fan': 'mode_fan',
    'ac-unit': 'ac_unit',
    'led-panel': 'light',
    'led-strip': 'wb_iridescent',
    'work-light': 'lightbulb',
    'wall-shelf-4ft': 'shelves',
    'wall-shelf-2ft': 'shelves',
    'control-panel': 'electrical_services',
    'switch-panel': 'toggle_on',
    'outlet-strip': 'power',
    'menu-board': 'menu_book',
    'refrigerator': 'kitchen',
    'freezer': 'ac_unit',
    'under-counter-fridge': 'kitchen',
    'sandwich-prep': 'lunch_dining',
    'glass-door-cooler': 'local_drink',
    'chest-freezer': 'inventory_2',
    'ice-machine': 'water_drop',
    'kegerator': 'sports_bar',
    'serving-window': 'window',
    'serving-window-6ft': 'window',
    'pickup-window': 'window',
    'side-window': 'window',
    'swing-serving-window': 'window',
    'condiment-stand': 'restaurant',
    'cash-register': 'point_of_sale',
    'storage-shelf': 'shelves',
    'propane-tank': 'propane',
    'fire-suppression': 'fire_extinguisher',
    'water-heater': 'whatshot',
    'fresh-water-tank': 'water_drop',
    'fresh-water-tank-lg': 'water_drop',
    'grey-water-tank': 'water',
    'grey-water-tank-lg': 'water',
    'generator-7kw': 'bolt',
    'generator-12kw': 'bolt',
    'generator-20kw': 'bolt',
    'speaker-system': 'speaker',
    'amp-head': 'speaker_group',
    'led-trim': 'auto_awesome',
    'rooftop-sign': 'emergency',
    'outdoor-menu-board': 'storefront',
    'outdoor-signage': 'campaign',
    'folding-counter': 'table_bar',
    'folding-shelf': 'shelves',
    'guest-rail': 'horizontal_rule',
    'awning': 'roofing'
  },

  getEquipmentIconHTML(equip) {
    const name = this._iconMap[equip.id] || 'inventory_2';
    return `<span class="material-symbols-outlined">${name}</span>`;
  },

  // Track which category sections are collapsed
  _collapsedCategories: new Set([
    'cooking', 'prep', 'storage', 'plumbing', 'ventilation',
    'service', 'lighting', 'electrical', 'extras', 'misc'
  ]),

  // Category display order and labels
  _categoryOrder: [
    { key: 'cooking', label: 'Cooking', icon: 'mi-local_fire_department' },
    { key: 'prep', label: 'Prep', icon: 'mi-countertops' },
    { key: 'storage', label: 'Cold Storage', icon: 'mi-kitchen' },
    { key: 'plumbing', label: 'Plumbing', icon: 'mi-water_drop' },
    { key: 'ventilation', label: 'Ventilation', icon: 'mi-air' },
    { key: 'service', label: 'Windows', icon: 'mi-storefront' },
    { key: 'lighting', label: 'Lighting', icon: 'mi-lightbulb' },
    { key: 'electrical', label: 'Electrical', icon: 'mi-bolt' },
    { key: 'extras', label: 'Exterior', icon: 'mi-deck' },
    { key: 'misc', label: 'Safety', icon: 'mi-health_and_safety' }
  ],

  // ---- Equipment Sidebar ----
  populateEquipmentList() {
    const list = document.getElementById('equipment-list');
    list.innerHTML = '';

    const filter = this._searchFilter ? this._searchFilter.toLowerCase() : '';

    // Group items by category
    const grouped = {};
    EQUIPMENT_CATALOG.forEach(equip => {
      if (filter) {
        if (!equip.name.toLowerCase().includes(filter) &&
            !equip.category.toLowerCase().includes(filter) &&
            !(equip.description || '').toLowerCase().includes(filter)) return;
      }
      if (!grouped[equip.category]) grouped[equip.category] = [];
      grouped[equip.category].push(equip);
    });

    // Render each category that has items
    this._categoryOrder.forEach(({ key, label, icon }) => {
      const items = grouped[key];
      if (!items || items.length === 0) return;

      const section = document.createElement('div');
      section.className = 'eq-category';
      // When searching, auto-expand all; otherwise respect collapsed state
      const isCollapsed = !filter && this._collapsedCategories.has(key);
      if (isCollapsed) section.classList.add('collapsed');

      const header = document.createElement('div');
      header.className = 'eq-category-header';
      header.innerHTML = `
        <span class="eq-cat-arrow">▼</span>
        <span class="eq-cat-icon">${icon && icon.startsWith('mi-') ? '<span class="material-symbols-outlined">' + icon.slice(3) + '</span>' : (icon || '')}</span>
        <span class="eq-cat-label">${label}</span>
        <span class="eq-cat-count">${items.length}</span>
      `;
      header.addEventListener('click', () => {
        if (this._collapsedCategories.has(key)) {
          this._collapsedCategories.delete(key);
          section.classList.remove('collapsed');
        } else {
          this._collapsedCategories.add(key);
          section.classList.add('collapsed');
        }
      });
      section.appendChild(header);

      const cardsContainer = document.createElement('div');
      cardsContainer.className = 'eq-category-items';

      items.forEach(equip => {
        const card = document.createElement('div');
        card.className = 'equipment-card';
        card.dataset.equipId = equip.id;
        card.draggable = true;
        card.title = equip.description || equip.name;

        const iconBg = this.colorIndicators || this.colorTint
          ? hexToCssColor(equip.accent) + '22'
          : '#e8eaed';
        const iconColor = this.colorIndicators || this.colorTint
          ? hexToCssColor(equip.accent)
          : '#5f6368';

        card.innerHTML = `
          <div class="eq-icon" style="background: ${iconBg}; color: ${iconColor}">
            ${this.getEquipmentIconHTML(equip)}
          </div>
          <div class="eq-info">
            <div class="eq-name">${equip.name}</div>
            <div class="eq-dims">${getFormattedDims(equip)}${equip.cost ? ' · $' + equip.cost.toLocaleString() : ''}</div>
          </div>
        `;

        card.addEventListener('click', () => {
          if (window.app) app.deselectItem();
          document.querySelectorAll('.equipment-card').forEach(c => c.classList.remove('active'));
          if (window.app && app.activeEquipId === equip.id) {
            app.cancelPlacement();
            return;
          }
          card.classList.add('active');
          if (window.app) app.startPlacement(equip.id);
        });

        card.addEventListener('dragstart', (e) => {
          e.dataTransfer.effectAllowed = 'copy';
          e.dataTransfer.setData('text/equip-id', equip.id);
          card.classList.add('dragging');
          if (window.app) {
            document.querySelectorAll('.equipment-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            app.startPlacement(equip.id);
          }
        });

        card.addEventListener('dragend', () => {
          card.classList.remove('dragging');
        });

        cardsContainer.appendChild(card);
      });

      section.appendChild(cardsContainer);
      list.appendChild(section);
    });

    // Bind canvas drop only once
    if (!this._canvasDropBound) {
      const canvas = document.getElementById('canvas');
      canvas.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        if (window.app && app.ghostMesh) {
          app.onMouseMove(e);
        }
      });
      canvas.addEventListener('drop', (e) => {
        e.preventDefault();
        if (window.app && app.ghostMesh) {
          // Update ghost position and re-validate at drop location
          app.onMouseMove(e);
          if (app.ghostTarget) {
            app.ghostMesh.position.copy(app.ghostTarget);
            const data = app.ghostMesh.userData;
            const snapped = app.snapToGrid(app.ghostTarget, data.widthCells, data.depthCells, app.ghostRotation);
            app.ghostValid = app.isPlacementValid(snapped.x, snapped.z, snapped.effW, snapped.effD, null);
          }
          if (app.ghostValid) {
            app.placeEquipment();
          } else {
            UI.showToast('Cannot drop here — collision or out of bounds', 'error');
          }
        }
      });
      this._canvasDropBound = true;
    }
  },

  clearActiveEquipment() {
    document.querySelectorAll('.equipment-card').forEach(c => c.classList.remove('active'));
  },

  // ---- Collapsible headers ----
  initCollapsibles() {
    const storageKey = 'truck-builder-collapsed-v1';
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch(e) {}

    document.querySelectorAll('.collapsible-header').forEach(h => {
      const id = h.dataset.collapse || h.textContent.trim();
      if (saved[id]) h.classList.add('collapsed');

      h.addEventListener('click', () => {
        h.classList.toggle('collapsed');
        try {
          const current = JSON.parse(localStorage.getItem(storageKey) || '{}');
          if (h.classList.contains('collapsed')) current[id] = true;
          else delete current[id];
          localStorage.setItem(storageKey, JSON.stringify(current));
        } catch(e) {}
      });
    });
  },

  // ---- Search Filter ----
  initSearch() {
    const input = document.getElementById('equip-search');
    if (!input) return;
    input.addEventListener('input', () => {
      this._searchFilter = input.value.trim();
      this.populateEquipmentList();
    });
  },

  // ---- Properties Panel ----
  showProperties(item) {
    document.getElementById('properties-panel').style.display = 'block';
    document.getElementById('no-selection').style.display = 'none';

    const data = item.userData;
    const def = EQUIPMENT_CATALOG.find(e => e.id === data.equipId);

    document.getElementById('prop-name').textContent = def ? def.name : data.name;

    const gridX = Math.round(item.position.x / CELL_SIZE);
    const gridZ = Math.round(item.position.z / CELL_SIZE);
    document.getElementById('prop-position').textContent = `(${gridX}, ${gridZ})`;

    const wFt = data.widthCells / CELLS_PER_FOOT;
    const dFt = data.depthCells / CELLS_PER_FOOT;
    const hFt = data.heightCells / CELLS_PER_FOOT;
    document.getElementById('prop-size').textContent = `${wFt}' x ${dFt}' x ${hFt}'h`;

    const rotDeg = Math.round(THREE.MathUtils.radToDeg(item.rotation.y)) % 360;
    document.getElementById('prop-rotation').textContent = `${rotDeg < 0 ? rotDeg + 360 : rotDeg}\u00B0`;

    const variantEl = document.getElementById('prop-variant');
    if (variantEl) variantEl.textContent = `${(data.variant || 0) + 1}/3`;

    const costEl = document.getElementById('prop-cost');
    if (costEl && def) costEl.textContent = def.cost ? `$${def.cost.toLocaleString()}` : '—';
  },

  hideProperties() {
    document.getElementById('properties-panel').style.display = 'none';
    document.getElementById('no-selection').style.display = 'block';
  },

  // ---- Status ----
  setStatus(text) {
    document.getElementById('status-text').textContent = text;
  },

  setItemCount(count) {
    document.getElementById('item-count').textContent = `Items: ${count}`;
    const statItems = document.getElementById('stat-items');
    if (statItems) statItems.textContent = count;
  },

  setDimensionsInfo(text) {
    const el = document.getElementById('dimensions-info');
    if (el) el.textContent = text;
  },

  // ---- Toasts — discreet, don't stack up ----
  showToast(message, type) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    // Limit to 3 stacked toasts max
    while (container.children.length >= 3) {
      container.firstChild.remove();
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type || 'info'}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 2100);
  },

  // ---- Layout Summary ----
  updateSummary(placedItems) {
    const container = document.getElementById('layout-summary');

    if (placedItems.length === 0) {
      container.innerHTML = '<p class="muted">Place equipment to see summary</p>';
    } else {
      const counts = {};
      placedItems.forEach(item => {
        const name = item.userData.name;
        counts[name] = (counts[name] || 0) + 1;
      });
      let html = '';
      for (const [name, count] of Object.entries(counts)) {
        html += `<div class="summary-item"><span>${name}</span><span class="count">x${count}</span></div>`;
      }
      container.innerHTML = html;
    }

    // Stats
    this.setItemCount(placedItems.length);

    // Floor usage percentage
    if (window.app) {
      const totalCells = app.gridCellsX * app.gridCellsZ;
      let usedCells = 0;
      placedItems.forEach(item => {
        if (item.userData.elevated) return;
        usedCells += (item.userData.effW || item.userData.widthCells) *
                     (item.userData.effD || item.userData.depthCells);
      });
      const pct = totalCells > 0 ? Math.min(100, Math.round((usedCells / totalCells) * 100)) : 0;
      const statFloor = document.getElementById('stat-floor');
      if (statFloor) statFloor.textContent = `${pct}%`;

      // Cubic feet: equipment volume vs total usable volume
      const ceilHt = 8; // 8ft ceiling
      const totalVolFt3 = app.truckLengthFt * app.truckWidthFt * ceilHt;
      let usedVolFt3 = 0;
      placedItems.forEach(item => {
        const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
        if (!def) return;
        const wFt = def.widthCells / 2;
        const dFt = def.depthCells / 2;
        const hFt = def.heightCells / 2;
        usedVolFt3 += wFt * dFt * hFt;
      });
      usedVolFt3 = Math.round(usedVolFt3);
      const remainVolFt3 = Math.round(totalVolFt3 - usedVolFt3);
      const statVol = document.getElementById('stat-volume');
      if (statVol) statVol.textContent = `${usedVolFt3} / ${totalVolFt3} ft³`;
      const statRemain = document.getElementById('stat-remaining');
      if (statRemain) statRemain.textContent = `${remainVolFt3} ft³`;
    }

    // Total cost (internal)
    let totalCost = 0;
    const costByItem = {};
    placedItems.forEach(item => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === item.userData.equipId);
      if (def && def.cost) {
        totalCost += def.cost;
        if (!costByItem[def.name]) costByItem[def.name] = { count: 0, unit: def.cost, total: 0 };
        costByItem[def.name].count++;
        costByItem[def.name].total += def.cost;
      }
    });
    const statCost = document.getElementById('stat-cost');
    if (statCost) statCost.textContent = `$${totalCost.toLocaleString()}`;

    // Cost breakdown (internal)
    const breakdown = document.getElementById('cost-breakdown');
    if (breakdown) {
      if (Object.keys(costByItem).length === 0) {
        breakdown.innerHTML = '<p class="muted">Place items to see cost breakdown</p>';
      } else {
        let html = '';
        for (const [name, info] of Object.entries(costByItem)) {
          html += `<div class="cost-item"><span>${info.count}× ${name}</span><span class="amt">$${info.total.toLocaleString()}</span></div>`;
        }
        breakdown.innerHTML = html;
      }
    }
    const labor = Math.round(totalCost * 0.25);
    const materials = Math.round(totalCost * 0.15);
    const quoteTotal = totalCost + labor + materials;
    const setText = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = '$' + val.toLocaleString();
    };
    setText('cost-equipment', totalCost);
    setText('cost-labor', labor);
    setText('cost-materials', materials);
    setText('cost-total', quoteTotal);

    // Compliance checks
    const check = (id, cond) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.classList.toggle('ok', cond);
      el.querySelector('.check-icon').textContent = cond ? '✓' : '○';
    };
    const hasItem = (id) => placedItems.some(i => i.userData.equipId === id);
    const hasCategory = (cat) => placedItems.some(i => {
      const def = EQUIPMENT_CATALOG.find(e => e.id === i.userData.equipId);
      return def && def.category === cat;
    });
    check('check-handwash', hasItem('hand-wash-sink'));
    check('check-3comp', hasItem('3-comp-sink'));
    check('check-hood', hasItem('hood-exhaust'));
    check('check-fire', hasItem('fire-suppression'));
    check('check-fridge', placedItems.some(i => ['refrigerator', 'freezer', 'under-counter-fridge', 'sandwich-prep', 'chest-freezer', 'glass-door-cooler'].includes(i.userData.equipId)));
    check('check-service', placedItems.some(i => i.userData.equipId.includes('window') || i.userData.equipId === 'cash-register'));

    // ---- Power load calculation ----
    let totalWatts = 0;
    let supplyWatts = 0;
    let freshWater = 0;
    let greyWater = 0;
    placedItems.forEach(item => {
      const id = item.userData.equipId;
      if (this._powerConsumption[id]) totalWatts += this._powerConsumption[id];
      const def = EQUIPMENT_CATALOG.find(e => e.id === id);
      if (def && def.provides_power) supplyWatts += def.provides_power;

      if (id === 'fresh-water-tank') freshWater += 30;
      if (id === 'fresh-water-tank-lg') freshWater += 60;
      if (id === 'grey-water-tank') greyWater += 40;
      if (id === 'grey-water-tank-lg') greyWater += 80;
    });
    const peakWatts = Math.round(totalWatts * 1.25);
    const setT = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };
    setT('power-load', totalWatts.toLocaleString() + ' W');
    setT('power-peak', peakWatts.toLocaleString() + ' W');
    setT('power-supply', supplyWatts.toLocaleString() + ' W');
    // Power usage bar — fill % of supply (or 100% if over)
    const barFill = document.getElementById('power-bar-fill');
    if (barFill) {
      let pct = 0;
      if (supplyWatts > 0) pct = Math.min(100, (peakWatts / supplyWatts) * 100);
      else if (peakWatts > 0) pct = 100;
      barFill.style.width = pct + '%';
    }
    const statusEl = document.getElementById('power-status');
    if (statusEl) {
      statusEl.classList.remove('ok', 'over', 'none');
      if (supplyWatts === 0) {
        statusEl.textContent = 'NO GENERATOR';
        statusEl.classList.add('none');
      } else if (supplyWatts >= peakWatts) {
        const headroom = Math.round(((supplyWatts - peakWatts) / supplyWatts) * 100);
        statusEl.textContent = `OK (+${headroom}%)`;
        statusEl.classList.add('ok');
      } else {
        const needMore = peakWatts - supplyWatts;
        statusEl.textContent = `-${needMore.toLocaleString()} W`;
        statusEl.classList.add('over');
      }
    }
    setT('water-fresh', freshWater + ' gal');
    setT('water-grey', greyWater + ' gal');

    // ---- Line length estimates (Manhattan distance to nearest source) ----
    const estimateLines = (type) => {
      const sourceIds = this._utilitySources[type] || [];
      const sources = placedItems.filter(i => sourceIds.includes(i.userData.equipId));
      const consumers = placedItems.filter(i => {
        const needs = this._utilityRequirements[i.userData.equipId] || [];
        return needs.includes(type) && !sourceIds.includes(i.userData.equipId);
      });
      let total = 0;
      consumers.forEach(c => {
        let minDist = Infinity;
        if (sources.length === 0) {
          // Virtual source = center of truck
          if (window.app) {
            minDist = Math.abs(c.position.x - app.gridCellsX * CELL_SIZE * 0.5) +
                      Math.abs(c.position.z - app.gridCellsZ * CELL_SIZE * 0.5);
          }
        } else {
          sources.forEach(s => {
            const d = Math.abs(c.position.x - s.position.x) + Math.abs(c.position.z - s.position.z);
            if (d < minDist) minDist = d;
          });
        }
        if (minDist !== Infinity) total += minDist;
      });
      // Convert units → feet (1 unit = 2 ft since CELL_SIZE=0.5, 2 cells/ft)
      return Math.round(total * 2);
    };
    setT('wire-est', estimateLines('electrical') + ' ft');
    setT('pex-est', estimateLines('water') + ' ft');
    setT('gas-est', estimateLines('gas') + ' ft');

    // ---- Wall & floor surface area ----
    if (window.app) {
      const lenFt = app.truckLengthFt;
      const widFt = app.truckWidthFt;
      const wallHeightFt = 8;
      const wallSqFt = Math.round(2 * (lenFt + widFt) * wallHeightFt);
      const floorSqFt = Math.round(lenFt * widFt);
      setT('wall-sqft', wallSqFt + ' sq ft');
      setT('floor-sqft', floorSqFt + ' sq ft');
    }

    // Update build checklist
    if (window.app && typeof app.renderBuildChecklist === 'function') {
      app.renderBuildChecklist();
    }

    // Bill of Materials
    const bomEl = document.getElementById('bom-list');
    if (bomEl) {
      if (placedItems.length === 0) {
        bomEl.innerHTML = '<p class="muted">Place items to generate BOM</p>';
      } else {
        let html = '';
        for (const [name, info] of Object.entries(costByItem)) {
          html += `<div class="bom-item"><span>${info.count}× ${name}</span><span>$${info.unit}</span></div>`;
        }
        bomEl.innerHTML = html;
      }
    }
  },

  // ---- Mode Switching ----
  setMode(mode) {
    this.mode = mode;
    document.body.setAttribute('data-mode', mode);
    document.querySelectorAll('.mode-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.mode === mode);
    });
    this.showToast(`Switched to ${mode} mode`, 'info');
  },

  initModeSwitcher() {
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.setMode(btn.dataset.mode);
      });
    });
  },

  // ---- Custom Tooltips ----
  initTooltips() {
    // Create tooltip element
    const tooltip = document.createElement('div');
    tooltip.className = 'tooltip';
    document.body.appendChild(tooltip);

    let hoverTimer = null;
    let currentTarget = null;

    const show = (el, text) => {
      tooltip.textContent = text;
      const rect = el.getBoundingClientRect();
      // Position below the element
      const top = rect.bottom + 10;
      const left = rect.left + rect.width / 2;
      tooltip.style.left = left + 'px';
      tooltip.style.top = top + 'px';
      tooltip.style.transform = 'translate(-50%, 0)';
      tooltip.classList.add('visible');
      // Keep within viewport
      const tt = tooltip.getBoundingClientRect();
      if (tt.right > window.innerWidth - 8) {
        tooltip.style.left = (window.innerWidth - tt.width / 2 - 8) + 'px';
      }
      if (tt.left < 8) {
        tooltip.style.left = (tt.width / 2 + 8) + 'px';
      }
      // If it would overflow bottom, show above instead
      if (tt.bottom > window.innerHeight - 8) {
        tooltip.style.top = (rect.top - tt.height - 10) + 'px';
      }
    };

    const hide = () => {
      tooltip.classList.remove('visible');
      currentTarget = null;
      if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
    };

    document.addEventListener('mouseover', (e) => {
      const el = e.target.closest('[data-tip], [title]');
      if (!el || el === currentTarget) return;
      const text = el.getAttribute('data-tip') || el.getAttribute('title');
      if (!text) return;

      // Stash the title so the native tooltip doesn't also show
      if (el.hasAttribute('title')) {
        el.setAttribute('data-tip', el.getAttribute('title'));
        el.removeAttribute('title');
      }

      currentTarget = el;
      if (hoverTimer) clearTimeout(hoverTimer);
      hoverTimer = setTimeout(() => show(el, text), 700);
    });

    document.addEventListener('mouseout', (e) => {
      if (currentTarget && !currentTarget.contains(e.relatedTarget)) {
        hide();
      }
    });

    // Hide on click/scroll
    document.addEventListener('click', hide);
    document.addEventListener('scroll', hide, true);
  },

  // ---- Mobile Drawers ----
  initMobileDrawers() {
    const sidebar = document.getElementById('sidebar');
    const panel = document.getElementById('panel');
    const backdrop = document.getElementById('mobile-backdrop');
    const toggleSidebar = document.getElementById('btn-toggle-sidebar');
    const togglePanel = document.getElementById('btn-toggle-panel');

    const closeAll = () => {
      sidebar?.classList.remove('open');
      panel?.classList.remove('open');
      document.body.classList.remove('drawer-open');
    };

    if (toggleSidebar) toggleSidebar.addEventListener('click', () => {
      const isOpen = sidebar.classList.contains('open');
      closeAll();
      if (!isOpen) {
        sidebar.classList.add('open');
        document.body.classList.add('drawer-open');
      }
    });

    if (togglePanel) togglePanel.addEventListener('click', () => {
      const isOpen = panel.classList.contains('open');
      closeAll();
      if (!isOpen) {
        panel.classList.add('open');
        document.body.classList.add('drawer-open');
      }
    });

    if (backdrop) backdrop.addEventListener('click', closeAll);

    // Close drawers on Esc
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && document.body.classList.contains('drawer-open')) {
        closeAll();
      }
    });

    // Close sidebar after picking an equipment card (mobile)
    document.getElementById('equipment-list').addEventListener('click', (e) => {
      if (window.innerWidth <= 900 && e.target.closest('.equipment-card')) {
        closeAll();
      }
    });
  },

  // ---- Visual Toggles ----
  toggleColor() {
    const newState = !this.colorTint;
    this.colorTint = newState;
    this.colorIndicators = newState;
    this.colorAccents = newState;
    const btn = document.getElementById('btn-color-toggle');
    if (btn) btn.classList.toggle('active', newState);
    if (window.app) app.rebuildAllItems();
    this.populateEquipmentList();
    this.showToast(`Color ${newState ? 'ON' : 'OFF'}`, 'info');
  },

  initColorToggle() {
    const colorBtn = document.getElementById('btn-color-toggle');
    if (colorBtn) colorBtn.addEventListener('click', () => this.toggleColor());
    const dimsBtn = document.getElementById('btn-dims-toggle');
    if (dimsBtn) dimsBtn.addEventListener('click', () => this.toggleDimensions());
  },

  toggleDimensions() {
    this.showDimensions = !this.showDimensions;
    const btn = document.getElementById('btn-dims-toggle');
    if (btn) btn.classList.toggle('active', this.showDimensions);
    document.body.classList.toggle('ruler-on', this.showDimensions);
    if (!this.showDimensions) {
      const overlay = document.getElementById('dim-overlay');
      if (overlay) overlay.innerHTML = '';
    } else {
      this.buildRulers();
    }
    if (window.app && typeof app.buildDimensionLines === 'function') {
      app.buildDimensionLines();
    }
    this.showToast(`Ruler ${this.showDimensions ? 'ON' : 'OFF'}`, 'info');
  },

  // Persistent guide lines stored as world positions
  _guideLinesX: [], // x positions in world units
  _guideLinesZ: [], // z positions

  // ---- Photoshop-style Rulers with draggable guides ----
  buildRulers() {
    const top = document.getElementById('ruler-top');
    const left = document.getElementById('ruler-left');
    if (!top || !left || !window.app) return;

    const canvas = app.renderer.domElement;
    const rect = canvas.getBoundingClientRect();

    // Truck dimensions in feet
    const truckLenFt = app.truckLengthFt;
    const truckWidFt = app.truckWidthFt;

    // Project truck edges to screen to compute pixels-per-foot
    const leftPt = new THREE.Vector3(0, 0, 0);
    const rightPt = new THREE.Vector3(app.gridCellsX * CELL_SIZE, 0, 0);
    leftPt.project(app.camera);
    rightPt.project(app.camera);
    const leftScreenX = (leftPt.x * 0.5 + 0.5) * rect.width;
    const rightScreenX = (rightPt.x * 0.5 + 0.5) * rect.width;
    const pxPerFtX = Math.abs(rightScreenX - leftScreenX) / truckLenFt;

    const frontPt = new THREE.Vector3(0, 0, 0);
    const backPt = new THREE.Vector3(0, 0, app.gridCellsZ * CELL_SIZE);
    frontPt.project(app.camera);
    backPt.project(app.camera);
    const frontScreenY = (-frontPt.y * 0.5 + 0.5) * rect.height;
    const backScreenY = (-backPt.y * 0.5 + 0.5) * rect.height;
    const pxPerFtY = Math.abs(backScreenY - frontScreenY) / truckWidFt;

    // Build tick HTML for top ruler
    let topHtml = '';
    const rulerWidth = rect.width - 22;
    const topStart = leftScreenX - 22;
    for (let ft = 0; ft <= truckLenFt; ft++) {
      const x = topStart + ft * pxPerFtX;
      if (x < 0 || x > rulerWidth) continue;
      const isMajor = ft % 5 === 0;
      topHtml += `<div class="ruler-tick ${isMajor ? 'major' : 'minor'}" style="left:${x}px"></div>`;
      if (isMajor) topHtml += `<div class="ruler-label" style="left:${x}px">${ft}</div>`;
    }
    top.innerHTML = topHtml;

    // Build tick HTML for left ruler
    let leftHtml = '';
    const rulerHeight = rect.height - 22;
    const leftStart = frontScreenY - 22;
    for (let ft = 0; ft <= truckWidFt; ft++) {
      const y = leftStart + ft * pxPerFtY;
      if (y < 0 || y > rulerHeight) continue;
      const isMajor = ft % 5 === 0 || ft === 0;
      leftHtml += `<div class="ruler-tick ${isMajor ? 'major' : 'minor'}" style="top:${y}px"></div>`;
      if (isMajor) leftHtml += `<div class="ruler-label" style="top:${y}px">${ft}</div>`;
    }
    left.innerHTML = leftHtml;

    // Drag-from-ruler to create guide lines
    if (!this._rulerDragBound) {
      this._setupRulerDrag(top, left, canvas);
      this._rulerDragBound = true;
    }

    // Refresh existing guide lines display
    this._renderGuideLines();
  },

  _setupRulerDrag(topRuler, leftRuler, canvas) {
    let dragging = null; // 'x' or 'z'
    let previewLine = null;

    const startDrag = (axis) => (e) => {
      if (!this.showDimensions) return;
      e.preventDefault();
      dragging = axis;
      // Create a preview line element
      previewLine = document.createElement('div');
      previewLine.style.cssText = `
        position: absolute;
        background: rgba(255, 102, 68, 0.8);
        pointer-events: none;
        z-index: 11;
        box-shadow: 0 0 4px rgba(255, 102, 68, 0.5);
      `;
      const r = canvas.getBoundingClientRect();
      if (axis === 'x') {
        previewLine.style.left = (e.clientX - r.left) + 'px';
        previewLine.style.top = '22px';
        previewLine.style.width = '2px';
        previewLine.style.bottom = '0';
      } else {
        previewLine.style.top = (e.clientY - r.top) + 'px';
        previewLine.style.left = '22px';
        previewLine.style.height = '2px';
        previewLine.style.right = '0';
      }
      document.getElementById('viewport').appendChild(previewLine);
    };

    topRuler.addEventListener('mousedown', startDrag('x'));
    leftRuler.addEventListener('mousedown', startDrag('z'));

    window.addEventListener('mousemove', (e) => {
      if (!dragging || !previewLine) return;
      const r = canvas.getBoundingClientRect();
      if (dragging === 'x') {
        previewLine.style.left = (e.clientX - r.left) + 'px';
      } else {
        previewLine.style.top = (e.clientY - r.top) + 'px';
      }
    });

    window.addEventListener('mouseup', (e) => {
      if (!dragging || !previewLine) return;
      const r = canvas.getBoundingClientRect();
      // Reverse-project from screen to world position
      const ndcX = ((e.clientX - r.left) / r.width) * 2 - 1;
      const ndcY = -((e.clientY - r.top) / r.height) * 2 + 1;
      const raycaster = new THREE.Raycaster();
      raycaster.setFromCamera({ x: ndcX, y: ndcY }, app.camera);
      const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
      const hit = new THREE.Vector3();
      raycaster.ray.intersectPlane(floorPlane, hit);

      if (hit) {
        if (dragging === 'x') {
          this._guideLinesX.push(hit.x);
        } else {
          this._guideLinesZ.push(hit.z);
        }
        this._renderGuideLines();
        if (window.app && typeof app.buildDimensionLines === 'function') {
          app.buildDimensionLines();
        }
        this._renderGuideLines();
        this.showToast('Guide line added', 'info');
      }

      previewLine.remove();
      previewLine = null;
      dragging = null;
    });
  },

  _guideGroup: null,

  _renderGuideLines() {
    if (!window.app) return;

    // Remove old guide group
    if (this._guideGroup) {
      app.scene.remove(this._guideGroup);
      this._guideGroup = null;
    }

    if (this._guideLinesX.length === 0 && this._guideLinesZ.length === 0) return;

    this._guideGroup = new THREE.Group();
    this._guideGroup.name = 'guide-lines';

    const truckW = app.gridCellsX * CELL_SIZE;
    const truckD = app.gridCellsZ * CELL_SIZE;
    const ceilH = app._getCeilingHeight ? app._getCeilingHeight() : 3.25;

    const guideMat = new THREE.LineBasicMaterial({
      color: 0xff6644, transparent: true, opacity: 0.6, depthTest: false
    });
    const labelMat = new THREE.LineBasicMaterial({
      color: 0xff6644, transparent: true, opacity: 0.35, depthTest: false
    });

    this._guideLinesX.forEach(x => {
      // Floor line
      const floorGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x, 0.05, -0.3),
        new THREE.Vector3(x, 0.05, truckD + 0.3)
      ]);
      this._guideGroup.add(new THREE.Line(floorGeo, guideMat));
      // Vertical line up to ceiling
      const vertGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x, 0.05, 0),
        new THREE.Vector3(x, ceilH, 0)
      ]);
      this._guideGroup.add(new THREE.Line(vertGeo, labelMat));
    });

    this._guideLinesZ.forEach(z => {
      const floorGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(-0.3, 0.05, z),
        new THREE.Vector3(truckW + 0.3, 0.05, z)
      ]);
      this._guideGroup.add(new THREE.Line(floorGeo, guideMat));
      const vertGeo = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(0, 0.05, z),
        new THREE.Vector3(0, ceilH, z)
      ]);
      this._guideGroup.add(new THREE.Line(vertGeo, labelMat));
    });

    app.scene.add(this._guideGroup);
  },

  clearGuideLines() {
    this._guideLinesX = [];
    this._guideLinesZ = [];
    this._renderGuideLines();
    this.showToast('Guides cleared', 'info');
  },

  // Format feet value as "4'6" (1.37m)" with both imperial and metric
  formatDimension(feet) {
    const ft = Math.floor(feet);
    const inchesRaw = Math.round((feet - ft) * 12);
    let imperial;
    if (inchesRaw === 0) imperial = `${ft}'`;
    else if (inchesRaw === 12) imperial = `${ft + 1}'`;
    else imperial = `${ft}'${inchesRaw}"`;
    const meters = (feet * 0.3048).toFixed(2);
    return `${imperial} (${meters}m)`;
  },

  // Update dimension label overlays (called every frame)
  updateDimensionOverlays() {
    if (!this.showDimensions || !window.app) return;
    const overlay = document.getElementById('dim-overlay');
    if (!overlay) return;

    const canvas = app.renderer.domElement;
    const rect = canvas.getBoundingClientRect();
    const labels = [];

    // Per-item labels — W×D in feet/inches + metric
    app.placedItems.forEach(item => {
      const data = item.userData;
      const wFt = (data.effW || data.widthCells) / CELLS_PER_FOOT;
      const dFt = (data.effD || data.depthCells) / CELLS_PER_FOOT;
      const pos = new THREE.Vector3(
        item.position.x,
        (data.elevated ? (data.elevationCells || 0) * CELL_SIZE : 0) + data.heightCells * CELL_SIZE * 0.5,
        item.position.z
      );
      pos.project(app.camera);
      if (pos.z < 1) {
        labels.push({
          text: `${this.formatDimension(wFt)}<br>× ${this.formatDimension(dFt)}`,
          x: (pos.x * 0.5 + 0.5) * rect.width,
          y: (-pos.y * 0.5 + 0.5) * rect.height,
          truck: false
        });
      }
    });

    // Truck LENGTH label (centered over the dim line behind the truck)
    const truckW = app.gridCellsX * CELL_SIZE;
    const truckD = app.gridCellsZ * CELL_SIZE;
    const truckLabelPos = new THREE.Vector3(truckW / 2, 0.15, -1.3);
    truckLabelPos.project(app.camera);
    if (truckLabelPos.z < 1) {
      labels.push({
        text: this.formatDimension(app.truckLengthFt),
        x: (truckLabelPos.x * 0.5 + 0.5) * rect.width,
        y: (-truckLabelPos.y * 0.5 + 0.5) * rect.height,
        truck: true
      });
    }
    // Truck WIDTH label
    const widthLabelPos = new THREE.Vector3(-1.3, 0.15, truckD / 2);
    widthLabelPos.project(app.camera);
    if (widthLabelPos.z < 1) {
      labels.push({
        text: this.formatDimension(app.truckWidthFt),
        x: (widthLabelPos.x * 0.5 + 0.5) * rect.width,
        y: (-widthLabelPos.y * 0.5 + 0.5) * rect.height,
        truck: true
      });
    }

    overlay.innerHTML = labels.map(l =>
      `<div class="dim-label ${l.truck ? 'truck' : ''}" style="left:${l.x}px;top:${l.y}px">${l.text}</div>`
    ).join('');
  },

  // ---- Fullscreen ----
  initFullscreen() {
    const btn = document.getElementById('btn-fullscreen');
    if (!btn) return;
    btn.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen();
      }
    });
  },

  // ---- Slide-in Quote Panel ----
  initQuotePanel(onSubmit) {
    const overlay = document.getElementById('quote-overlay');
    const openBtn = document.getElementById('btn-quote');
    const closeBtn = document.getElementById('btn-close-quote');
    const backdrop = document.getElementById('quote-backdrop');
    const form = document.getElementById('quote-form');

    const open = () => {
      overlay.classList.remove('hidden');
      // Populate layout preview
      this.updateQuoteLayoutPreview();
    };
    const close = () => overlay.classList.add('hidden');

    openBtn.addEventListener('click', open);
    closeBtn.addEventListener('click', close);
    backdrop.addEventListener('click', close);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !overlay.classList.contains('hidden')) close();
    });

    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const data = {
        name: document.getElementById('q-name').value,
        email: document.getElementById('q-email').value,
        phone: document.getElementById('q-phone').value,
        truckLength: document.getElementById('q-truck-length').value,
        timeline: document.getElementById('q-timeline').value,
        budget: document.getElementById('q-budget').value,
        notes: document.getElementById('q-notes').value
      };
      onSubmit(data).then((ok) => {
        if (ok) {
          form.reset();
          close();
        }
      });
    });
  },

  updateQuoteLayoutPreview() {
    const container = document.getElementById('quote-layout-items');
    if (!container || !window.app) return;

    const items = app.placedItems;
    if (items.length === 0) {
      container.innerHTML = '<p class="muted">No items placed yet</p>';
      return;
    }

    const counts = {};
    items.forEach(i => {
      counts[i.userData.name] = (counts[i.userData.name] || 0) + 1;
    });

    let html = '';
    for (const [name, count] of Object.entries(counts)) {
      html += `<div class="qli"><span>${name}</span><span class="count">x${count}</span></div>`;
    }
    container.innerHTML = html;
  },

  // ---- Save/Load Panel ----
  initSaveLoadPanel(onSave, onLoad, onLoadList, onDelete) {
    const overlay = document.getElementById('saveload-overlay');
    const title = document.getElementById('saveload-title');
    const saveSec = document.getElementById('save-section');
    const loadSec = document.getElementById('load-section');
    const closeBtn = document.getElementById('btn-close-saveload');
    const backdrop = document.getElementById('saveload-backdrop');

    const openSave = () => {
      title.textContent = 'SAVE LAYOUT';
      saveSec.style.display = 'block';
      loadSec.style.display = 'none';
      overlay.classList.remove('hidden');
    };

    const openLoad = async () => {
      title.textContent = 'LOAD LAYOUT';
      saveSec.style.display = 'none';
      loadSec.style.display = 'block';
      overlay.classList.remove('hidden');
      const list = document.getElementById('load-list');
      list.innerHTML = '<p class="muted">Loading...</p>';

      // Show autosave entry if one exists
      const autoKey = 'truck-builder-autosave-v1';
      let autoHtml = '';
      try {
        const autoRaw = localStorage.getItem(autoKey);
        if (autoRaw) {
          const autoState = JSON.parse(autoRaw);
          if (autoState.items && autoState.items.length > 0) {
            const ageMin = Math.round((Date.now() - (autoState.savedAt || 0)) / 60000);
            const ageText = ageMin < 1 ? 'just now' :
                            ageMin < 60 ? `${ageMin} min ago` :
                            `${Math.floor(ageMin / 60)} hr ago`;
            autoHtml = `<div class="load-item" id="autosave-entry" style="border-left:3px solid var(--accent);">
              <div class="load-item-name">Auto-Save (last session)</div>
              <div class="load-item-meta">
                <span>${autoState.items.length} items · ${autoState.truckLengthFt || 20}ft</span>
                <span>${ageText}</span>
              </div>
            </div>`;
          }
        }
      } catch(e) {}

      const layouts = await onLoadList();
      if ((!layouts || layouts.length === 0) && !autoHtml) {
        list.innerHTML = '<p class="muted">No saved layouts yet</p>';
        return;
      }
      list.innerHTML = autoHtml;

      // Wire up autosave click
      const autoEntry = document.getElementById('autosave-entry');
      if (autoEntry) {
        autoEntry.addEventListener('click', () => {
          try {
            const autoState = JSON.parse(localStorage.getItem(autoKey));
            if (autoState && window.app) {
              window.app.deserialize(autoState);
              this.showToast('Restored auto-save', 'success');
              overlay.classList.add('hidden');
            }
          } catch(e) { this.showToast('Failed to restore', 'error'); }
        });
      }

      if (!layouts) return;
      layouts.forEach(l => {
        const div = document.createElement('div');
        div.className = 'load-item';
        div.innerHTML = `
          <div class="load-item-name">${escapeHtml(l.name)}</div>
          <div class="load-item-meta">
            <span>${l.item_count} items · ${l.truck_length_ft}ft</span>
            <span>${new Date(l.created_at).toLocaleDateString()}</span>
          </div>
          ${l.tags ? `<div class="load-item-meta"><span>${escapeHtml(l.tags)}</span></div>` : ''}
          <button class="load-item-delete" data-id="${l.id}">Delete</button>
        `;
        div.addEventListener('click', async (e) => {
          if (e.target.classList.contains('load-item-delete')) {
            e.stopPropagation();
            if (confirm('Delete this saved layout?')) {
              await onDelete(l.id);
              openLoad();
            }
            return;
          }
          await onLoad(l);
          overlay.classList.add('hidden');
        });
        list.appendChild(div);
      });
    };

    const close = () => overlay.classList.add('hidden');

    const saveBtn = document.getElementById('btn-save');
    const loadBtn = document.getElementById('btn-load');
    if (saveBtn) saveBtn.addEventListener('click', openSave);
    if (loadBtn) loadBtn.addEventListener('click', openLoad);
    if (closeBtn) closeBtn.addEventListener('click', close);
    if (backdrop) backdrop.addEventListener('click', close);

    const doSaveBtn = document.getElementById('btn-do-save');
    if (!doSaveBtn) return;
    doSaveBtn.addEventListener('click', async () => {
      const nameEl = document.getElementById('save-name');
      const tagsEl = document.getElementById('save-tags');
      const name = nameEl ? nameEl.value.trim() : '';
      const tags = tagsEl ? tagsEl.value.trim() : '';
      const isTemplate = document.getElementById('save-as-template')?.checked || false;
      if (!name) {
        this.showToast('Please enter a layout name', 'error');
        return;
      }
      const ok = await onSave(name, tags, isTemplate);
      if (ok) {
        if (nameEl) nameEl.value = '';
        if (tagsEl) tagsEl.value = '';
        if (document.getElementById('save-as-template')) {
          document.getElementById('save-as-template').checked = false;
        }
        close();
      }
    });
  },

  // ---- Internal Controls ----
  initInternalControls(onTruckResize) {
    const lenSel = document.getElementById('truck-length-select');
    const widSel = document.getElementById('truck-width-select');
    const typeSel = document.getElementById('truck-type-select');
    const wheelToggle = document.getElementById('wheel-wells-toggle');

    const update = () => {
      const len = parseFloat(lenSel.value);
      const wid = parseFloat(widSel.value);
      onTruckResize(len, wid);
    };

    if (lenSel) lenSel.addEventListener('change', update);
    if (widSel) widSel.addEventListener('change', update);
    if (typeSel) typeSel.addEventListener('change', () => {
      if (window.app) {
        app.truckType = typeSel.value;
        app.buildTruck();
        app.buildGridOverlay();
        this.showToast('Chassis: ' + typeSel.value, 'info');
      }
    });
    if (wheelToggle) wheelToggle.addEventListener('change', () => {
      if (window.app) {
        app.showWheelWells = wheelToggle.checked;
        app.buildTruck();
        app.buildGridOverlay();
      }
    });

    const wheelAdjust = document.getElementById('wheel-well-adjust');
    const wheelSliderWrap = document.getElementById('wheel-well-slider-wrap');
    const wheelPosSlider = document.getElementById('wheel-well-pos');
    const wheelPosLabel = document.getElementById('wheel-well-pos-label');
    if (wheelAdjust && wheelSliderWrap) {
      wheelAdjust.addEventListener('change', () => {
        wheelSliderWrap.style.display = wheelAdjust.checked ? 'block' : 'none';
      });
    }
    if (wheelPosSlider) {
      wheelPosSlider.addEventListener('input', () => {
        const pct = parseInt(wheelPosSlider.value);
        if (wheelPosLabel) wheelPosLabel.textContent = pct + '%';
        if (window.app) {
          app.wheelWellPosition = pct / 100;
          app.buildTruck();
          app.buildGridOverlay();
        }
      });
    }
    // Well size stepper
    const wellSizeSel = document.getElementById('wheel-well-size');
    const wellSizeLabel = document.getElementById('well-size-label');
    const stepSize = (dir) => {
      if (!wellSizeSel) return;
      const len = wellSizeSel.options.length;
      const newIdx = (wellSizeSel.selectedIndex + dir + len) % len;
      wellSizeSel.selectedIndex = newIdx;
      if (wellSizeLabel) wellSizeLabel.textContent = wellSizeSel.options[newIdx].text;
      wellSizeSel.dispatchEvent(new Event('change'));
    };
    const szPrev = document.getElementById('well-size-prev');
    const szNext = document.getElementById('well-size-next');
    if (szPrev) szPrev.addEventListener('click', () => stepSize(-1));
    if (szNext) szNext.addEventListener('click', () => stepSize(1));
    if (wellSizeSel) {
      wellSizeSel.addEventListener('change', () => {
        if (window.app) {
          app.wheelWellSize = wellSizeSel.value;
          app.buildTruck();
          app.buildGridOverlay();
        }
      });
    }

    // Door steppers
    const wireStepper = (prevId, nextId, selId, labelId, prop) => {
      const sel = document.getElementById(selId);
      const lbl = document.getElementById(labelId);
      const step = (dir) => {
        if (!sel) return;
        const len = sel.options.length;
        sel.selectedIndex = (sel.selectedIndex + dir + len) % len;
        if (lbl) lbl.textContent = sel.options[sel.selectedIndex].text;
        if (window.app) {
          app[prop] = sel.value;
          if (prop === 'rearDoorOpen') app.rearDoorOpen = sel.value === 'open';
          app.buildTruck();
          app.buildGridOverlay();
        }
      };
      const p = document.getElementById(prevId);
      const n = document.getElementById(nextId);
      if (p) p.addEventListener('click', () => step(-1));
      if (n) n.addEventListener('click', () => step(1));
    };
    wireStepper('rear-door-prev', 'rear-door-next', 'rear-door-type', 'rear-door-label', 'rearDoorType');
    const doorsToggle = document.getElementById('doors-open-toggle');
    const doorsLabel = document.getElementById('doors-state');
    if (doorsToggle) {
      doorsToggle.addEventListener('change', () => {
        const open = doorsToggle.checked;
        if (doorsLabel) doorsLabel.textContent = open ? 'Doors open' : 'Doors shut';
        if (window.app) {
          app.rearDoorOpen = open;
          app.manDoorOpen = open;
          app.buildTruck();
          app.buildGridOverlay();
        }
      });
    }
    wireStepper('man-door-prev', 'man-door-next', 'man-door-type', 'man-door-label', 'manDoorType');
    wireStepper('man-door-size-prev', 'man-door-size-next', 'man-door-size', 'man-door-size-label', 'manDoorSize');
    wireStepper('man-door-wall-prev', 'man-door-wall-next', 'man-door-wall', 'man-door-wall-label', 'manDoorWall');

    const wellColorSel = document.getElementById('wheel-well-color');
    const wellColorLabel = document.getElementById('well-color-label');
    const stepColor = (dir) => {
      if (!wellColorSel) return;
      const len = wellColorSel.options.length;
      const newIdx = (wellColorSel.selectedIndex + dir + len) % len;
      wellColorSel.selectedIndex = newIdx;
      if (wellColorLabel) wellColorLabel.textContent = wellColorSel.options[newIdx].text;
      wellColorSel.dispatchEvent(new Event('change'));
    };
    const prevBtn = document.getElementById('well-color-prev');
    const nextBtn = document.getElementById('well-color-next');
    if (prevBtn) prevBtn.addEventListener('click', () => stepColor(-1));
    if (nextBtn) nextBtn.addEventListener('click', () => stepColor(1));
    if (wellColorSel) {
      wellColorSel.addEventListener('change', () => {
        if (window.app) {
          app.buildTruck();
          app.buildGridOverlay();
        }
      });
    }
  },

  // ---- View presets ----
  initViewPresets() {
    // Only camera preset buttons (ones with data-view) toggle each other
    const cameraBtns = document.querySelectorAll('.view-btn[data-view]');
    cameraBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        cameraBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (window.app) app.setViewPreset(btn.dataset.view);
      });
    });
  },

  // ---- New (clear) ----
  initNewButton(onNew) {
    const btn = document.getElementById('btn-new');
    if (btn) btn.addEventListener('click', () => {
      if (confirm('Clear all placed items?')) {
        onNew();
      }
    });
  },

  // ---- Export ----
  initExportButton(onExport) {
    const btn = document.getElementById('btn-export');
    if (btn) btn.addEventListener('click', onExport);
  },

  // ---- Import ----
  initImportButton(onImport) {
    const btn = document.getElementById('btn-import');
    if (!btn) return;

    // Hidden file input
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json,application/json';
    input.style.display = 'none';
    document.body.appendChild(input);

    btn.addEventListener('click', () => input.click());

    input.addEventListener('change', () => {
      const file = input.files && input.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const parsed = JSON.parse(reader.result);
          onImport(parsed);
        } catch (e) {
          UI.showToast('Invalid JSON file', 'error');
        }
      };
      reader.readAsText(file);
      input.value = ''; // Reset so same file can be re-picked
    });
  },

  // ---- Templates Panel ----
  initTemplatesPanel(onLoadTemplate, onListUserTemplates) {
    const overlay = document.getElementById('templates-overlay');
    const openBtn = document.getElementById('btn-templates');
    const closeBtn = document.getElementById('btn-close-templates');
    const backdrop = document.getElementById('templates-backdrop');
    const builtinList = document.getElementById('builtin-templates-list');
    const userList = document.getElementById('user-templates-list');

    if (!overlay || !openBtn) return;

    const renderBuiltins = () => {
      if (!builtinList || !window.BUILTIN_TEMPLATES) return;
      builtinList.innerHTML = '';
      BUILTIN_TEMPLATES.forEach(tpl => {
        const card = document.createElement('div');
        card.className = 'template-card';
        card.innerHTML = `
          <div class="template-name">${escapeHtml(tpl.name)}</div>
          <div class="template-desc">${escapeHtml(tpl.description || '')}</div>
          <div class="template-meta">
            <span class="accent">${tpl.items.length} items</span>
            <span>${tpl.truck_length_ft}' × ${tpl.truck_width_ft}'</span>
          </div>
        `;
        card.addEventListener('click', () => {
          if (!confirm(`Load "${tpl.name}"? This will replace your current layout.`)) return;
          onLoadTemplate(tpl);
          overlay.classList.add('hidden');
        });
        builtinList.appendChild(card);
      });
    };

    const renderUserTemplates = async () => {
      if (!userList) return;
      userList.innerHTML = '<p class="muted">Loading...</p>';
      const layouts = await onListUserTemplates();
      if (!layouts || layouts.length === 0) {
        userList.innerHTML = '<p class="muted">No user templates yet. Save a layout and check "Save as template" to add one.</p>';
        return;
      }
      userList.innerHTML = '';
      layouts.forEach(l => {
        const card = document.createElement('div');
        card.className = 'template-card';
        card.innerHTML = `
          <div class="template-name">${escapeHtml(l.name)}</div>
          <div class="template-desc">${escapeHtml(l.tags || 'Saved template')}</div>
          <div class="template-meta">
            <span class="accent">${l.item_count} items</span>
            <span>${l.truck_length_ft}' × ${l.truck_width_ft}'</span>
            <span>${new Date(l.created_at).toLocaleDateString()}</span>
          </div>
        `;
        card.addEventListener('click', () => {
          if (!confirm(`Load "${l.name}"? This will replace your current layout.`)) return;
          // Convert saved_layouts row to the format loadLayout expects
          if (window.app) app.loadLayout(l);
          overlay.classList.add('hidden');
        });
        userList.appendChild(card);
      });
    };

    const open = () => {
      overlay.classList.remove('hidden');
      renderBuiltins();
      renderUserTemplates();
    };
    const close = () => overlay.classList.add('hidden');

    openBtn.addEventListener('click', open);
    if (closeBtn) closeBtn.addEventListener('click', close);
    if (backdrop) backdrop.addEventListener('click', close);
  }
};

// Expose to window
window.UI = UI;

// Helpers
function hexToCssColor(hex) {
  return '#' + hex.toString(16).padStart(6, '0');
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}
