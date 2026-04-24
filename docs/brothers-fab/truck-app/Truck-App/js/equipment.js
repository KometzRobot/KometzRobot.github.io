// ============================================
// Equipment Catalog — Food Truck Layout Builder
// ============================================
// All dimensions in grid cells (1 cell = 6 inches)
// So 2 cells = 1 foot

const CELL_SIZE = 0.5; // Each cell is 0.5 units in 3D space (6 inches real)
const CELLS_PER_FOOT = 2;

const EQUIPMENT_CATALOG = [
  // --- Cooking ---
  {
    id: 'flat-top-griddle',
    name: 'Flat Top Griddle',
    category: 'cooking',
    widthCells: 6,   // 3 ft
    depthCells: 5,   // 2.5 ft
    heightCells: 7,  // 3.5 ft — counter height
    cost: 2800,
    color: 0xcccccc, accent: 0xff6b35, icon: '🔥',
    description: '36" commercial flat top griddle'
  },
  {
    id: 'deep-fryer',
    name: 'Deep Fryer',
    category: 'cooking',
    widthCells: 4,   // 2 ft
    depthCells: 5,   // 2.5 ft
    heightCells: 7,  // 3.5 ft — counter height
    cost: 1900,
    color: 0xcccccc, accent: 0xff4444, icon: '🍟',
    description: 'Double basket deep fryer'
  },
  {
    id: 'range-oven',
    name: 'Range / Oven',
    category: 'cooking',
    widthCells: 6,   // 3 ft
    depthCells: 5,   // 2.5 ft
    heightCells: 8,  // 4ft — taller with backsplash/controls
    cost: 3500,
    color: 0xcccccc, accent: 0xff8800, icon: '♨️',
    description: '4-burner range with oven'
  },
  {
    id: 'charbroiler',
    name: 'Charbroiler',
    category: 'cooking',
    widthCells: 6,
    depthCells: 5,
    heightCells: 7,  // 3.5 ft counter
    cost: 2400,
    color: 0xcccccc, accent: 0xcc3300, icon: '🥩',
    description: '36" radiant charbroiler'
  },
  {
    id: 'steam-table',
    name: 'Steam Table',
    category: 'cooking',
    widthCells: 8,   // 4 ft
    depthCells: 4,   // 2 ft
    heightCells: 7,  // counter height
    cost: 1800,
    color: 0xcccccc, accent: 0x66aaff, icon: '♨️',
    description: '4-well electric steam table'
  },

  // --- Prep ---
  {
    id: 'prep-table-4ft',
    name: 'Prep Table 4ft',
    category: 'prep',
    widthCells: 8, depthCells: 5, heightCells: 6,
    cost: 800,
    color: 0xd8d8d8, accent: 0x88cc88, icon: '🔪',
    description: '48" stainless prep table — 36" work surface'
  },
  {
    id: 'prep-table-6ft',
    name: 'Prep Table 6ft',
    category: 'prep',
    widthCells: 12, depthCells: 5, heightCells: 6,
    cost: 1100,
    color: 0xd8d8d8, accent: 0x88cc88, icon: '🔪',
    description: '72" stainless prep table — 36" work surface'
  },

  // --- Sinks ---
  {
    id: '3-comp-sink',
    name: '3-Comp Sink',
    category: 'plumbing',
    widthCells: 8, depthCells: 4, heightCells: 7,
    cost: 1400,
    color: 0xd0d0d0, accent: 0x4488ff, icon: '🚿',
    description: '3-compartment wash sink'
  },
  {
    id: 'hand-wash-sink',
    name: 'Hand Wash Sink',
    category: 'plumbing',
    widthCells: 3, depthCells: 3, heightCells: 6,
    cost: 450,
    color: 0xd0d0d0, accent: 0x44aaff, icon: '🧼',
    description: 'Hand washing station — 34" height'
  },

  // --- Ventilation ---
  {
    id: 'hood-exhaust',
    name: 'Hood / Exhaust',
    category: 'ventilation',
    widthCells: 8, depthCells: 5, heightCells: 2,
    cost: 3800,
    color: 0xaaaaaa, accent: 0x999999, icon: '💨',
    description: '4ft exhaust hood — bottom at 4.5ft, 18" above 3ft counter equipment',
    elevated: true, elevationCells: 9 // 4.5ft — clears counter equipment by 18"
  },
  {
    id: 'roof-vent',
    name: 'Roof Vent',
    category: 'ventilation',
    widthCells: 3, depthCells: 3, heightCells: 2,
    roofTop: true,
    cost: 280,
    color: 0xd0d0d0, accent: 0x888888, icon: '🌀',
    description: 'Passive roof vent — sits on roof',
    elevated: true, elevationCells: 12
  },
  {
    id: 'exhaust-fan',
    name: 'Exhaust Fan',
    category: 'ventilation',
    widthCells: 4, depthCells: 4, heightCells: 3,
    roofTop: true,
    cost: 650,
    color: 0xcccccc, accent: 0x777777, icon: '🌀',
    description: 'Powered roof exhaust fan',
    elevated: true, elevationCells: 12
  },
  {
    id: 'ac-unit',
    name: 'AC Unit',
    category: 'ventilation',
    widthCells: 6, depthCells: 5, heightCells: 3,
    roofTop: true,
    cost: 2200,
    color: 0xcccccc, accent: 0x4499dd, icon: '❄️',
    description: 'Rooftop AC unit',
    elevated: true, elevationCells: 12
  },
  {
    id: 'hood-fan',
    name: 'Hood Exhaust Fan',
    category: 'ventilation',
    widthCells: 4, depthCells: 4, heightCells: 3,
    cost: 1200,
    roofTop: true,
    color: 0xaaaaaa, accent: 0x777777, icon: '💨',
    description: 'Roof-mounted hood exhaust fan — required above hood system. Draws grease-laden air up and out.',
    elevated: true, elevationCells: 12
  },

  // --- Lighting ---
  {
    id: 'led-panel',
    name: 'LED Panel Light',
    category: 'lighting',
    widthCells: 4, depthCells: 2, heightCells: 1,
    cost: 120,
    color: 0xf5f5f5, accent: 0xffffaa, icon: '💡',
    description: '2x4 LED ceiling panel — flush mount',
    elevated: true, elevationCells: 12
  },
  {
    id: 'led-strip',
    name: 'LED Strip',
    category: 'lighting',
    widthCells: 8, depthCells: 1, heightCells: 1,
    cost: 80,
    color: 0xf0f0f0, accent: 0xffffdd, icon: '💡',
    description: '4ft LED strip light — flush mount',
    elevated: true, elevationCells: 12
  },
  {
    id: 'work-light',
    name: 'Work Light',
    category: 'lighting',
    widthCells: 2, depthCells: 2, heightCells: 2,
    cost: 65,
    color: 0xe8e8e8, accent: 0xffeecc, icon: '💡',
    description: 'Task/work light — ceiling mount',
    elevated: true, elevationCells: 11
  },

  // --- Wall Mounted ---
  {
    id: 'wall-shelf-4ft',
    name: 'Wall Shelf 4ft',
    category: 'storage',
    widthCells: 8, depthCells: 2, heightCells: 2,
    cost: 180,
    color: 0xdedede, accent: 0xaa8866, icon: '🗄️',
    description: '4ft wall shelf — above backsplash, below head height',
    elevated: true, elevationCells: 8 // 4ft — above counter + backsplash
  },
  {
    id: 'wall-shelf-2ft',
    name: 'Wall Shelf 2ft',
    category: 'storage',
    widthCells: 4, depthCells: 2, heightCells: 2,
    cost: 110,
    color: 0xdedede, accent: 0xaa8866, icon: '🗄️',
    description: '2ft wall-mounted shelf',
    elevated: true, elevationCells: 8
  },
  {
    id: 'control-panel',
    name: 'Control Panel',
    category: 'electrical',
    widthCells: 3, depthCells: 1, heightCells: 5,
    cost: 850,
    color: 0xcccccc, accent: 0xff9900, icon: '🎛️',
    description: 'Main electrical breaker panel',
    elevated: true, elevationCells: 8
  },
  {
    id: 'switch-panel',
    name: 'Switch Panel',
    category: 'electrical',
    widthCells: 2, depthCells: 1, heightCells: 2,
    cost: 120,
    color: 0xe8e8e8, accent: 0x44ddff, icon: '🎚️',
    description: 'Light/power switch panel',
    elevated: true, elevationCells: 8
  },
  {
    id: 'outlet-strip',
    name: 'Outlet Strip',
    category: 'electrical',
    widthCells: 4, depthCells: 1, heightCells: 1,
    cost: 95,
    color: 0xe8e8e8, accent: 0x66ccff, icon: '🔌',
    description: 'GFCI outlet strip',
    elevated: true, elevationCells: 7
  },
  {
    id: 'menu-board',
    name: 'Menu Board',
    category: 'service',
    widthCells: 6, depthCells: 1, heightCells: 5,
    cost: 450,
    color: 0xdedede, accent: 0xff6600, icon: '📋',
    description: 'Overhead menu display',
    elevated: true, elevationCells: 10
  },

  // --- Cold Storage ---
  {
    id: 'refrigerator',
    name: 'Refrigerator',
    category: 'storage',
    widthCells: 5, depthCells: 5, heightCells: 11, // 5.5ft — compact food truck reach-in
    cost: 2600,
    color: 0xe0e0e0, accent: 0x66ccff, icon: '❄️',
    description: 'Single-door reach-in fridge'
  },
  {
    id: 'freezer',
    name: 'Freezer',
    category: 'storage',
    widthCells: 5, depthCells: 5, heightCells: 11, // 5.5ft — compact food truck reach-in
    cost: 2900,
    color: 0xe0e0e0, accent: 0x3399ff, icon: '🧊',
    description: 'Reach-in freezer'
  },
  {
    id: 'under-counter-fridge',
    name: 'Under-Counter Fridge',
    category: 'storage',
    widthCells: 5, depthCells: 4, heightCells: 6,
    cost: 1300,
    color: 0xe0e0e0, accent: 0x88ddff, icon: '❄️',
    description: 'Under-counter refrigerator'
  },
  {
    id: 'sandwich-prep',
    name: 'Sandwich Prep Table',
    category: 'storage',
    widthCells: 10, depthCells: 5, heightCells: 7,
    cost: 2200,
    color: 0xe0e0e0, accent: 0x66bbdd, icon: '🥪',
    description: 'Refrigerated sandwich/salad prep'
  },
  {
    id: 'glass-door-cooler',
    name: 'Glass Door Cooler',
    category: 'storage',
    widthCells: 5, depthCells: 5, heightCells: 11, // 5.5ft — compact glass door reach-in
    cost: 2400,
    color: 0xe8e8e8, accent: 0x88ccee, icon: '🥤',
    description: 'Glass door beverage cooler'
  },
  {
    id: 'chest-freezer',
    name: 'Chest Freezer',
    category: 'storage',
    widthCells: 8, depthCells: 5, heightCells: 6, // lower — chest style
    cost: 1200,
    color: 0xe0e0e0, accent: 0x4499cc, icon: '🧊',
    description: 'Chest-style deep freezer'
  },
  {
    id: 'ice-machine',
    name: 'Ice Machine',
    category: 'storage',
    widthCells: 5, depthCells: 5, heightCells: 8, // ~4 ft
    cost: 3200,
    color: 0xe8e8e8, accent: 0x66ccee, icon: '🧊',
    description: 'Commercial ice machine'
  },
  {
    id: 'kegerator',
    name: 'Kegerator',
    category: 'storage',
    widthCells: 5, depthCells: 5, heightCells: 7, // counter height
    cost: 1700,
    color: 0xe0e0e0, accent: 0xcc8844, icon: '🍺',
    description: 'Beverage/keg cooler'
  },

  // --- Service ---
  {
    id: 'serving-window',
    name: 'Swing-Up Window (4ft)',
    category: 'service',
    widthCells: 8, depthCells: 1, heightCells: 4,
    cost: 1500,
    elevated: true, elevationCells: 6,
    wallMount: true,
    isWindow: true,
    color: 0xbbbbbb, accent: 0xffcc00, icon: '🪟',
    description: '4ft wide × 2ft tall — sill at 2.5ft, top at 4.5ft. Standard serving window.'
  },
  {
    id: 'serving-window-6ft',
    name: 'Swing-Up Window (5ft)',
    category: 'service',
    widthCells: 10, depthCells: 1, heightCells: 4,
    cost: 1900,
    elevated: true, elevationCells: 6,
    wallMount: true,
    isWindow: true,
    color: 0xbbbbbb, accent: 0xffcc00, icon: '🪟',
    description: '5ft wide × 2ft tall — larger serving window for high-volume service.'
  },
  {
    id: 'pickup-window',
    name: 'Pickup Window',
    category: 'service',
    widthCells: 4, depthCells: 1, heightCells: 3,
    cost: 900,
    elevated: true, elevationCells: 6,
    wallMount: true,
    isWindow: true,
    color: 0xbbbbbb, accent: 0xffaa00, icon: '🪟',
    description: '2ft wide × 1.5ft tall — small order pickup window.'
  },
  {
    id: 'side-window',
    name: 'Side Window',
    category: 'service',
    widthCells: 4, depthCells: 1, heightCells: 3,
    cost: 600,
    elevated: true, elevationCells: 6,
    wallMount: true,
    isWindow: true,
    color: 0xbbbbbb, accent: 0xcccccc, icon: '🪟',
    description: '2ft × 1.5ft fixed observation window. Does not open.'
  },
  {
    id: 'swing-serving-window',
    name: 'Swing-Up Window (6ft)',
    category: 'service',
    widthCells: 12, depthCells: 1, heightCells: 4,
    cost: 2400,
    elevated: true, elevationCells: 6,
    wallMount: true,
    isWindow: true,
    color: 0xbbbbbb, accent: 0xffcc00, icon: '🪟',
    description: '6ft swing-up hinged food truck window',
    wallMount: true
  },
  {
    id: 'condiment-stand',
    name: 'Condiment Stand',
    category: 'service',
    widthCells: 4, depthCells: 3, heightCells: 5,
    cost: 320,
    color: 0xd8d8d8, accent: 0xdd9944, icon: '🍯',
    description: 'Customer condiment/napkin station'
  },
  {
    id: 'cash-register',
    name: 'Cash Register',
    category: 'service',
    widthCells: 3, depthCells: 3, heightCells: 5, // 1.5'×1.5'×2.5' — POS on small counter
    cost: 800,
    color: 0xd8d8d8, accent: 0x44dd44, icon: '💰',
    description: 'POS / cash register station'
  },

  // --- Storage ---
  {
    id: 'storage-shelf',
    name: 'Storage Shelf',
    category: 'storage',
    widthCells: 8, depthCells: 3, heightCells: 11, // 5.5ft wire shelving — leaves headroom
    cost: 350,
    color: 0xc8c8c8, accent: 0xaa8866, icon: '📦',
    description: '4ft wire shelving unit'
  },

  // --- Misc ---
  {
    id: 'propane-tank',
    name: 'Propane Tank (20lb)',
    category: 'misc',
    widthCells: 3, depthCells: 3, heightCells: 4, // 2ft — 20lb tank (interior safe)
    cost: 400,
    color: 0xd0d0d0, accent: 0xff6600, icon: '⛽',
    description: 'Propane tank mount area',
    primaryShape: 'cylinder'
  },
  {
    id: 'fire-suppression',
    name: 'Fire Suppression',
    category: 'misc',
    widthCells: 2, depthCells: 2, heightCells: 6, // 3ft — Ansul tank
    cost: 1200,
    color: 0xdd0000, accent: 0xff0000, icon: '🧯',
    description: 'Fire suppression system',
    primaryShape: 'cylinder'
  },
  {
    id: 'water-heater',
    name: 'Water Heater',
    category: 'plumbing',
    widthCells: 4, depthCells: 4, heightCells: 9, // 4.5ft — compact tankless or 20gal unit
    cost: 900,
    color: 0xd8d8d8, accent: 0xff4444, icon: '🔥',
    description: '40 gal tank water heater — required if 3-comp sink needs hot water (2\' × 2\' × 6\')',
    primaryShape: 'cylinder',
    power: 200
  },
  {
    id: 'fresh-water-tank',
    name: 'Fresh Water Tank (30gal)',
    category: 'plumbing',
    widthCells: 5, depthCells: 4, heightCells: 7,
    cost: 250,
    color: 0xd8d8d8, accent: 0x4488ff, icon: '💧',
    description: '30 gal fresh — meets min. for most health dept. permits (2.5\' × 2\' × 3.5\')',
    freshWaterGal: 30
  },
  {
    id: 'fresh-water-tank-lg',
    name: 'Fresh Water Tank (60gal)',
    category: 'plumbing',
    widthCells: 6, depthCells: 5, heightCells: 8,
    cost: 420,
    color: 0xd8d8d8, accent: 0x4488ff, icon: '💧',
    description: '60 gal fresh — full-day capacity for high-volume ops (3\' × 2.5\' × 4\')',
    freshWaterGal: 60
  },
  {
    id: 'grey-water-tank',
    name: 'Grey Water Tank (40gal)',
    category: 'plumbing',
    widthCells: 5, depthCells: 4, heightCells: 7,
    cost: 280,
    color: 0xb8b8b8, accent: 0x888888, icon: '💧',
    description: '40 gal grey — must be ≥ fresh tank capacity per health code (2.5\' × 2\' × 3.5\')',
    greyWaterGal: 40
  },
  {
    id: 'grey-water-tank-lg',
    name: 'Grey Water Tank (80gal)',
    category: 'plumbing',
    widthCells: 6, depthCells: 5, heightCells: 8,
    cost: 450,
    color: 0xb8b8b8, accent: 0x888888, icon: '💧',
    description: '80 gal grey — pairs with 60 gal fresh, exceeds 1:1 ratio (3\' × 2.5\' × 4\')',
    greyWaterGal: 80
  },
  {
    id: 'generator-7kw',
    name: 'Generator 7kW (ext.)',
    category: 'electrical',
    widthCells: 5, depthCells: 3, heightCells: 5,
    cost: 2200,
    color: 0xc8c8c8, accent: 0xffaa00, icon: '⚡',
    description: 'Rear deck platform with cage/cover. No interior space lost. Bolts to frame behind rear axle.',
    provides_power: 7000
  },
  {
    id: 'generator-12kw',
    name: 'Generator 12kW (bay)',
    category: 'electrical',
    widthCells: 6, depthCells: 4, heightCells: 6,
    cost: 3400,
    color: 0xc8c8c8, accent: 0xffaa00, icon: '⚡',
    description: 'Rear deck platform or internal bay. If internal: faux wall shortens interior ~2ft, needs exhaust louvers + access panel.',
    provides_power: 12000,
    generatorBay: true, bayDepthFt: 2
  },
  {
    id: 'generator-20kw',
    name: 'Generator 20kW (bay)',
    category: 'electrical',
    widthCells: 7, depthCells: 5, heightCells: 7,
    cost: 5800,
    color: 0xc8c8c8, accent: 0xffaa00, icon: '⚡',
    description: 'Rear deck platform with steel cage, or large internal bay. If internal: faux wall shortens interior ~3ft, needs dual vent louvers + access door.',
    provides_power: 20000,
    generatorBay: true, bayDepthFt: 3
  },

  // --- Extras / Exterior / A/V ---
  {
    id: 'speaker-system',
    name: 'Speaker System',
    category: 'extras',
    widthCells: 2, depthCells: 2, heightCells: 2,
    cost: 320,
    color: 0xcccccc, accent: 0xaa00ff, icon: '🔊',
    description: 'Bluetooth PA speaker system — ceiling mount',
    elevated: true, elevationCells: 10
  },
  {
    id: 'amp-head',
    name: 'Amplifier',
    category: 'extras',
    widthCells: 3, depthCells: 3, heightCells: 2,
    cost: 280,
    color: 0xc0c0c0, accent: 0x9933cc, icon: '🎵',
    description: 'Audio amplifier / mixer'
  },
  {
    id: 'backup-camera',
    name: 'Backup Camera System',
    category: 'extras',
    widthCells: 1, depthCells: 1, heightCells: 1,
    cost: 450,
    color: 0x333333, accent: 0x44aaff, icon: '📷',
    description: 'Rear-mount camera + 7" dash monitor + wiring. No interior space needed — mounts externally.',
    nonPhysical: true
  },
  {
    id: 'radio-system',
    name: 'Radio / Audio System',
    category: 'extras',
    widthCells: 1, depthCells: 1, heightCells: 1,
    cost: 350,
    color: 0x333333, accent: 0x9933cc, icon: '📻',
    description: 'AM/FM/BT head unit + 2 interior speakers + antenna. Mounts in dash area — no kitchen space used.',
    nonPhysical: true
  },
  {
    id: 'led-trim',
    name: 'LED Trim Light',
    category: 'extras',
    widthCells: 10, depthCells: 1, heightCells: 1,
    cost: 180,
    color: 0xe8e8e8, accent: 0x00ffcc, icon: '✨',
    description: '10ft color-changing LED trim — ceiling edge',
    elevated: true, elevationCells: 12
  },
  {
    id: 'rooftop-sign',
    name: 'Rooftop Sign (Hydraulic)',
    category: 'extras',
    widthCells: 10, depthCells: 3, heightCells: 6,
    roofTop: true,
    cost: 3400,
    color: 0xdddddd, accent: 0xffaa00, icon: '🪧',
    description: 'Hydraulic lift rooftop sign — sits on roof',
    elevated: true, elevationCells: 13
  },
  {
    id: 'outdoor-menu-board',
    name: 'Outdoor Menu Board',
    category: 'extras',
    widthCells: 6, depthCells: 1, heightCells: 8,
    cost: 650,
    color: 0xcccccc, accent: 0xff6600, icon: '📋',
    description: 'Exterior illuminated menu board',
    wallMount: true
  },
  {
    id: 'outdoor-signage',
    name: 'Exterior Signage',
    category: 'extras',
    widthCells: 8, depthCells: 1, heightCells: 6,
    cost: 480,
    color: 0xcccccc, accent: 0xff8800, icon: '🏷️',
    description: 'Branded exterior signage panel'
  },
  {
    id: 'folding-counter',
    name: 'Folding Counter',
    category: 'extras',
    widthCells: 8, depthCells: 3, heightCells: 1,
    cost: 520,
    color: 0xd8d8d8, accent: 0x66aa44, icon: '🪑',
    description: 'Fold-down counter — 5ft from ground (3ft + truck floor height)',
    elevated: true, elevationCells: 6, // 3ft from truck floor = ~5ft from ground
    wallMount: true
  },
  {
    id: 'folding-shelf',
    name: 'Folding Shelf (ext.)',
    category: 'extras',
    widthCells: 6, depthCells: 2, heightCells: 1,
    cost: 220,
    color: 0xdedede, accent: 0x66aa44, icon: '🗄️',
    description: 'Exterior fold-up condiment shelf — mounts below serving window',
    elevated: true, elevationCells: 5,
    wallMount: true
  },
  {
    id: 'folding-shelf-int',
    name: 'Folding Shelf (int.)',
    category: 'prep',
    widthCells: 6, depthCells: 2, heightCells: 1,
    cost: 180,
    color: 0xdedede, accent: 0x88aa66, icon: '🗄️',
    description: 'Interior wall-mounted fold-down shelf — extra prep or storage surface',
    elevated: true, elevationCells: 7,
    wallMount: true
  },
  {
    id: 'guest-rail',
    name: 'Guest Rail',
    category: 'extras',
    widthCells: 10, depthCells: 1, heightCells: 3,
    cost: 340,
    color: 0xc0c0c0, accent: 0x888888, icon: '🚧',
    description: 'Guest rail — 4.5ft from ground (elbow height for leaning)',
    elevated: true, elevationCells: 5, // 2.5ft from truck floor = ~4.5ft from ground
    wallMount: true
  },
  {
    id: 'awning',
    name: 'Awning',
    category: 'extras',
    widthCells: 12, depthCells: 6, heightCells: 2,
    cost: 850,
    color: 0xdddddd, accent: 0xdd4444, icon: '⛱️',
    description: 'Awning — mounts just above window top edge',
    elevated: true, elevationCells: 10 // 5ft — clears the top of a 3ft+2ft window
  }
];

// ---- GLTF Model Pipeline ----
// Models go in /models/{id}.glb — if present, used instead of procedural geometry
// Falls back to procedural boxes if no model file found
const _modelCache = {};  // id → THREE.Group (cloned per use)
const _modelFailed = {}; // id → true (don't retry 404s)
const _gltfLoader = typeof THREE.GLTFLoader !== 'undefined' ? new THREE.GLTFLoader() : null;

function loadEquipmentModel(equipId) {
  return new Promise((resolve) => {
    if (_modelFailed[equipId]) { resolve(null); return; }
    if (_modelCache[equipId]) { resolve(_modelCache[equipId].clone()); return; }
    if (!_gltfLoader) { resolve(null); return; }

    _gltfLoader.load(
      `models/${equipId}.glb`,
      (gltf) => {
        const model = gltf.scene;
        model.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
          }
        });
        _modelCache[equipId] = model;
        resolve(model.clone());
      },
      undefined,
      () => {
        _modelFailed[equipId] = true;
        resolve(null);
      }
    );
  });
}

// Try to swap a procedural mesh for a GLTF model after placement
function tryUpgradeToModel(group, equipDef) {
  loadEquipmentModel(equipDef.id).then((model) => {
    if (!model) return;
    // Scale model to fit the equipment dimensions
    const w = equipDef.widthCells * CELL_SIZE;
    const d = equipDef.depthCells * CELL_SIZE;
    const h = equipDef.heightCells * CELL_SIZE;
    const box = new THREE.Box3().setFromObject(model);
    const size = new THREE.Vector3();
    box.getSize(size);
    if (size.x > 0 && size.y > 0 && size.z > 0) {
      model.scale.set(w / size.x, h / size.y, d / size.z);
    }
    // Center model
    const center = new THREE.Vector3();
    new THREE.Box3().setFromObject(model).getCenter(center);
    model.position.sub(center);
    model.position.y += h / 2;

    // Remove procedural children, add model
    while (group.children.length > 0) group.remove(group.children[0]);
    group.add(model);
  });
}

// Create 3D mesh for an equipment item
// variant: 0, 1, or 2 — selects one of three visual styles for the item
function createEquipmentMesh(equipDef, isGhost, variant) {
  if (variant === undefined || variant === null) {
    variant = 0;
  }
  const w = equipDef.widthCells * CELL_SIZE;
  const d = equipDef.depthCells * CELL_SIZE;
  const h = equipDef.heightCells * CELL_SIZE;

  const group = new THREE.Group();

  // Non-physical items (cameras, radio) — tiny marker, not a real 3D object
  if (equipDef.nonPhysical) {
    const marker = new THREE.Mesh(
      new THREE.SphereGeometry(0.15, 12, 8),
      isGhost
        ? new THREE.MeshPhongMaterial({ color: 0x7fdbca, emissive: 0x7fdbca, emissiveIntensity: 0.5, transparent: true, opacity: 0.7 })
        : new THREE.MeshStandardMaterial({ color: equipDef.accent || 0x44aaff, roughness: 0.4, metalness: 0.2 })
    );
    marker.position.y = 0.15;
    marker.castShadow = true;
    group.add(marker);
    // Label ring
    if (!isGhost) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(0.2, 0.02, 8, 24),
        new THREE.MeshBasicMaterial({ color: equipDef.accent || 0x44aaff })
      );
      ring.rotation.x = Math.PI / 2;
      ring.position.y = 0.01;
      group.add(ring);
    }
    group.userData = {
      equipId: equipDef.id, widthCells: equipDef.widthCells, depthCells: equipDef.depthCells,
      heightCells: equipDef.heightCells, elevated: false, elevationCells: 0,
      name: equipDef.name, variant: 0, isGhost: isGhost
    };
    return group;
  }

  // Primary body geometry — box or cylinder
  let bodyGeo;
  if (equipDef.primaryShape === 'cylinder') {
    const radius = Math.min(w, d) / 2;
    bodyGeo = new THREE.CylinderGeometry(radius, radius, h, 32);
  } else {
    bodyGeo = new THREE.BoxGeometry(w, h, d, 2, 2, 2);
  }

  // Color tinting: when enabled, mix body color with accent
  let bodyColor = 0xf0f0f0;
  if (!isGhost && window.UI && window.UI.colorTint) {
    const accent = new THREE.Color(equipDef.accent);
    const white = new THREE.Color(0xf0f0f0);
    bodyColor = white.lerp(accent, 0.2).getHex();
  }
  const bodyMat = isGhost
    ? new THREE.MeshPhongMaterial({
        color: 0x7fdbca,
        emissive: 0x7fdbca,
        emissiveIntensity: 0.5,
        transparent: true,
        opacity: 0.7
      })
    : new THREE.MeshStandardMaterial({
        color: bodyColor,
        roughness: 0.38,
        metalness: 0.2
      });
  const bodyMesh = new THREE.Mesh(bodyGeo, bodyMat);
  bodyMesh.position.y = h / 2;
  bodyMesh.castShadow = true;
  bodyMesh.receiveShadow = true;
  group.add(bodyMesh);

  // Front arrow marker — small triangle on the floor at the front of the item
  // Always visible so users can see the orientation when rotating
  {
    const arrowHeight = 0.01;
    const arrowW = Math.min(w, d) * 0.4;
    const arrowD = arrowW * 0.5;
    const arrowGeo = new THREE.BufferGeometry();
    const arrowVerts = new Float32Array([
      0, arrowHeight, arrowD / 2,
      -arrowW / 2, arrowHeight, -arrowD / 2,
      arrowW / 2, arrowHeight, -arrowD / 2
    ]);
    arrowGeo.setAttribute('position', new THREE.BufferAttribute(arrowVerts, 3));
    arrowGeo.computeVertexNormals();
    const arrowMat = new THREE.MeshBasicMaterial({
      color: isGhost ? 0x44dd88 : 0x4ab5a3,
      transparent: true,
      opacity: isGhost ? 0.8 : 0.6,
      side: THREE.DoubleSide
    });
    const arrow = new THREE.Mesh(arrowGeo, arrowMat);
    arrow.position.set(0, 0, d / 2 + arrowD * 0.6);
    group.add(arrow);
  }

  // Category surface indicator — a bright, prominent colored cap covering the top of the item
  if (!isGhost && window.UI && window.UI.colorIndicators) {
    const capH = 0.08;
    const capGeo = new THREE.BoxGeometry(w * 1.02, capH, d * 1.02);
    const capMat = new THREE.MeshBasicMaterial({
      color: equipDef.accent,
      transparent: true,
      opacity: 0.92
    });
    const cap = new THREE.Mesh(capGeo, capMat);
    cap.position.set(0, h + capH / 2 + 0.01, 0);
    group.add(cap);
  }

  // Add subtle details based on type and variant
  if (!isGhost) {
    addEquipmentDetails(group, equipDef, w, h, d, variant);
  }

  // Store metadata
  group.userData = {
    equipId: equipDef.id,
    widthCells: equipDef.widthCells,
    depthCells: equipDef.depthCells,
    heightCells: equipDef.heightCells,
    elevated: equipDef.elevated || false,
    elevationCells: equipDef.elevationCells || 0,
    name: equipDef.name,
    variant: variant,
    isGhost: isGhost
  };

  // Elevation handled by placement code (onMouseMove / loadLayout)
  // Don't set here — causes double-offset bugs

  return group;
}

// ---- Detail helpers — soft shading, no outlines ----

function darkMat() {
  return new THREE.MeshStandardMaterial({ color: 0x444444, roughness: 0.7, metalness: 0.1 });
}
function midMat() {
  return new THREE.MeshStandardMaterial({ color: 0x909090, roughness: 0.6, metalness: 0.1 });
}
function lightMat() {
  return new THREE.MeshStandardMaterial({ color: 0xdedede, roughness: 0.5, metalness: 0.05 });
}
function steelMat() {
  return new THREE.MeshStandardMaterial({ color: 0xc8c8c8, roughness: 0.28, metalness: 0.4 });
}

// Recessed inset panel — slightly darker than body, implies depth through shadow
function addInsetPanel(group, w, h, position, rotation) {
  const geo = new THREE.BoxGeometry(w, h, 0.02);
  const mat = new THREE.MeshStandardMaterial({ color: 0xdadada, roughness: 0.6, metalness: 0.05 });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.copy(position);
  if (rotation) mesh.rotation.copy(rotation);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  group.add(mesh);
  return mesh;
}

// Add a small box handle — rounded cylinder for softer look
function addHandle(group, length, position, vertical) {
  const geo = new THREE.CylinderGeometry(0.015, 0.015, length, 8);
  if (vertical) {
    // default cylinder is vertical
  } else {
    geo.rotateZ(Math.PI / 2);
  }
  const mesh = new THREE.Mesh(geo, steelMat());
  mesh.position.copy(position);
  mesh.castShadow = true;
  group.add(mesh);
  return mesh;
}

// Add 4 legs to an item — radius scales with equipment size
function addLegs(group, w, h, d, legHeight) {
  const lh = legHeight || 0.15;
  const legMat = steelMat();
  const minDim = Math.min(w, d);
  const legR = Math.max(0.015, minDim * 0.03);
  const positions = [
    [-w * 0.42, -d * 0.38],
    [w * 0.42, -d * 0.38],
    [-w * 0.42, d * 0.38],
    [w * 0.42, d * 0.38]
  ];
  positions.forEach(([lx, lz]) => {
    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(legR, legR * 1.2, lh, 8),
      legMat
    );
    leg.position.set(lx, lh / 2, lz);
    leg.castShadow = true;
    group.add(leg);
  });
}

// Backsplash — raised back guard, no outline
function addBacksplash(group, w, h, d, splashHeight) {
  const sh = splashHeight || h * 0.25;
  const splash = new THREE.Mesh(
    new THREE.BoxGeometry(w * 0.98, sh, 0.035),
    new THREE.MeshStandardMaterial({ color: 0xe2e2e2, roughness: 0.32, metalness: 0.25 })
  );
  splash.position.set(0, h + sh / 2, -d / 2 - 0.018);
  splash.castShadow = true;
  splash.receiveShadow = true;
  group.add(splash);
  return splash;
}

// Add subtle detail geometry to equipment
// variant (0-2) produces three different visual styles per item
function addEquipmentDetails(group, def, w, h, d, variant) {
  variant = variant || 0;
  switch (def.id) {
    case 'flat-top-griddle': {
      // Legs
      addLegs(group, w, h, d);
      // Backsplash (rear guard)
      addBacksplash(group, w, h, d, h * 0.4);
      // Dark griddle surface recessed slightly
      const surface = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.92, 0.04, d * 0.88),
        darkMat()
      );
      surface.position.set(0, h + 0.015, 0);
      group.add(surface);
      // Raised edge around griddle
      const edgeThickness = 0.025;
      const edgeBack = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.92, 0.04, edgeThickness),
        midMat()
      );
      edgeBack.position.set(0, h + 0.035, -d * 0.43);
      group.add(edgeBack);
      // Grease trough in front
      const trough = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.85, 0.03, 0.04),
        darkMat()
      );
      trough.position.set(0, h + 0.015, d * 0.48);
      group.add(trough);
      // 4 control knobs on front apron
      for (let i = 0; i < 4; i++) {
        const knob = new THREE.Mesh(
          new THREE.CylinderGeometry(0.04, 0.04, 0.05, 12),
          darkMat()
        );
        knob.rotation.x = Math.PI / 2;
        knob.position.set(-w*0.35 + i * (w*0.23), h * 0.18, d/2 + 0.03);
        group.add(knob);
      }
      // Front panel line
      addInsetPanel(group, w * 0.98, h * 0.3, new THREE.Vector3(0, h * 0.15, d/2 + 0.005));
      break;
    }
    case 'charbroiler': {
      // Grate lines on top
      for (let i = -3; i <= 3; i++) {
        const bar = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.88, 0.02, 0.025),
          darkMat()
        );
        bar.position.set(0, h + 0.015, i * d * 0.12);
        group.add(bar);
      }
      // Knobs
      for (let i = 0; i < 3; i++) {
        const knob = new THREE.Mesh(
          new THREE.CylinderGeometry(0.035, 0.035, 0.04, 12),
          darkMat()
        );
        knob.rotation.x = Math.PI / 2;
        knob.position.set(-w*0.3 + i * (w*0.3), h * 0.15, d/2 + 0.02);
        group.add(knob);
      }
      break;
    }
    case 'deep-fryer': {
      // Legs
      addLegs(group, w, h, d);
      // Two fryer wells (deeply recessed — use dark boxes to simulate depth)
      for (let i = -1; i <= 1; i += 2) {
        const wellRim = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.42, 0.03, d * 0.6),
          midMat()
        );
        wellRim.position.set(i * w * 0.22, h + 0.015, 0);
        group.add(wellRim);
        const well = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.36, 0.08, d * 0.54),
          darkMat()
        );
        well.position.set(i * w * 0.22, h - 0.04, 0);
        group.add(well);
        // Basket with handle sticking up
        const basket = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.32, 0.015, d * 0.45),
          midMat()
        );
        basket.position.set(i * w * 0.22, h - 0.06, 0);
        group.add(basket);
        // Long handle
        const handleRod = new THREE.Mesh(
          new THREE.CylinderGeometry(0.015, 0.015, 0.35, 8),
          midMat()
        );
        handleRod.position.set(i * w * 0.22, h + 0.15, -d * 0.3);
        group.add(handleRod);
        const handleGrip = new THREE.Mesh(
          new THREE.CylinderGeometry(0.022, 0.022, 0.1, 8),
          darkMat()
        );
        handleGrip.position.set(i * w * 0.22, h + 0.32, -d * 0.3);
        group.add(handleGrip);
      }
      // Front control panel
      addInsetPanel(group, w * 0.98, h * 0.3, new THREE.Vector3(0, h * 0.15, d/2 + 0.005));
      // Control knobs
      for (let i = 0; i < 2; i++) {
        const knob = new THREE.Mesh(
          new THREE.CylinderGeometry(0.035, 0.035, 0.04, 10),
          darkMat()
        );
        knob.rotation.x = Math.PI / 2;
        knob.position.set(-w * 0.15 + i * w * 0.3, h * 0.15, d/2 + 0.03);
        group.add(knob);
      }
      // Temperature display
      const display = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.25, h * 0.08, 0.02),
        new THREE.MeshStandardMaterial({ color: 0x2a4a2a, roughness: 0.6, metalness: 0.05 })
      );
      display.position.set(0, h * 0.25, d/2 + 0.015);
      group.add(display);
      break;
    }
    case 'range-oven': {
      // Commercial range — NO legs (sits flat), backsplash, 4-6 burners, big oven door
      // Small kick plate at bottom (4" high)
      const kick = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.98, 0.1, 0.02),
        darkMat()
      );
      kick.position.set(0, 0.05, d/2 + 0.005);
      group.add(kick);

      // Low backsplash with control panel
      const splashH = h * 0.2;
      const splash = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.98, splashH, 0.05),
        new THREE.MeshStandardMaterial({ color: 0xe2e2e2, roughness: 0.5, metalness: 0.08 })
      );
      splash.position.set(0, h + splashH / 2, -d / 2 - 0.025);
      group.add(splash);

      // Stove top — dark recessed
      const stovetop = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.96, 0.03, d * 0.92),
        new THREE.MeshStandardMaterial({ color: 0x2a2a2a, roughness: 0.8, metalness: 0.05 })
      );
      stovetop.position.set(0, h + 0.015, 0);
      group.add(stovetop);

      // 6 burners in a 3x2 grid (standard commercial range)
      const cols = 3, rows = 2;
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          const bx = -w * 0.32 + c * (w * 0.32);
          const bz = -d * 0.2 + r * (d * 0.4);
          // Outer grate
          const grate = new THREE.Mesh(
            new THREE.TorusGeometry(0.09, 0.02, 8, 20),
            darkMat()
          );
          grate.rotation.x = -Math.PI / 2;
          grate.position.set(bx, h + 0.035, bz);
          group.add(grate);
          // Inner burner ring
          const inner = new THREE.Mesh(
            new THREE.CylinderGeometry(0.05, 0.05, 0.02, 14),
            darkMat()
          );
          inner.position.set(bx, h + 0.025, bz);
          group.add(inner);
          // Center cap
          const cap = new THREE.Mesh(
            new THREE.CylinderGeometry(0.025, 0.025, 0.015, 10),
            midMat()
          );
          cap.position.set(bx, h + 0.04, bz);
          group.add(cap);
        }
      }

      // Big oven door — takes up most of the front below stovetop
      const doorH = h * 0.75;
      const doorY = h * 0.42;
      const doorOffset = 0.025;
      const door = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.92, doorH, 0.02),
        new THREE.MeshStandardMaterial({ color: 0xe2e2e2, roughness: 0.5, metalness: 0.08 })
      );
      door.position.set(0, doorY, d/2 + doorOffset);
      group.add(door);

      // Oven window — large, dark
      const win = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.78, doorH * 0.55, 0.015),
        new THREE.MeshStandardMaterial({ color: 0x0a0a0a, transparent: true, opacity: 0.9, roughness: 0.2, metalness: 0.1 })
      );
      win.position.set(0, doorY + doorH * 0.1, d/2 + doorOffset + 0.015);
      group.add(win);

      // Thick horizontal handle bar at top of door
      const handle = new THREE.Mesh(
        new THREE.CylinderGeometry(0.028, 0.028, w * 0.75, 8),
        steelMat()
      );
      handle.rotation.z = Math.PI / 2;
      handle.position.set(0, doorY + doorH * 0.42, d/2 + doorOffset + 0.06);
      group.add(handle);
      for (let side of [-1, 1]) {
        const bracket = new THREE.Mesh(
          new THREE.BoxGeometry(0.03, 0.04, 0.07),
          darkMat()
        );
        bracket.position.set(side * w * 0.35, doorY + doorH * 0.42, d/2 + doorOffset + 0.035);
        group.add(bracket);
      }

      // Row of control knobs on the backsplash face
      for (let i = 0; i < 6; i++) {
        const knob = new THREE.Mesh(
          new THREE.CylinderGeometry(0.03, 0.03, 0.045, 10),
          darkMat()
        );
        knob.rotation.x = Math.PI / 2;
        knob.position.set(-w * 0.4 + i * (w * 0.16), h + splashH * 0.5, -d/2 - 0.05);
        group.add(knob);
      }
      break;
    }
    case 'steam-table': {
      // 4 wells
      for (let i = 0; i < 4; i++) {
        const well = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.2, 0.04, d * 0.75),
          darkMat()
        );
        well.position.set(-w * 0.37 + i * w * 0.25, h + 0.02, 0);
        group.add(well);
      }
      break;
    }
    case 'prep-table-4ft':
    case 'prep-table-6ft': {
      // Legs
      addLegs(group, w, h, d);
      // Small backsplash
      addBacksplash(group, w, h, d, h * 0.18);
      // Stainless top with raised edge
      const top = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.98, 0.03, d * 0.98),
        new THREE.MeshStandardMaterial({ color: 0xdadada, roughness: 0.5, metalness: 0.05 })
      );
      top.position.set(0, h + 0.015, 0);
      group.add(top);

      if (variant === 0) {
        // Drawers only (no doors)
        const drawers = def.widthCells > 10 ? 4 : 3;
        for (let i = 0; i < drawers; i++) {
          const dx = -w/2 + (w/drawers) * (i + 0.5);
          addHandle(group, w * 0.6 / drawers, new THREE.Vector3(dx, h * 0.65, d/2 + 0.025), false);
          // Drawer outline
          const line = new THREE.Mesh(
            new THREE.BoxGeometry(0.01, h * 0.9, 0.01),
            darkMat()
          );
          line.position.set(-w/2 + (w/drawers) * (i + 1), h * 0.5, d/2 + 0.005);
          if (i < drawers - 1) group.add(line);
        }
      } else if (variant === 1) {
        // Cabinet doors
        const cabinets = def.widthCells > 10 ? 3 : 2;
        for (let i = 0; i < cabinets; i++) {
          const dx = -w/2 + (w/cabinets) * (i + 0.5);
          addHandle(group, 0.06, new THREE.Vector3(dx + w/cabinets * 0.3, h * 0.5, d/2 + 0.025), true);
          const line = new THREE.Mesh(
            new THREE.BoxGeometry(0.01, h * 0.85, 0.01),
            darkMat()
          );
          line.position.set(-w/2 + (w/cabinets) * (i + 1), h * 0.5, d/2 + 0.005);
          if (i < cabinets - 1) group.add(line);
        }
      } else {
        // Open shelving — just two cross bars + lower shelf
        const shelf1 = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.95, 0.02, d * 0.9),
          new THREE.MeshStandardMaterial({ color: 0xdadada, roughness: 0.5, metalness: 0.05 })
        );
        shelf1.position.set(0, h * 0.15, 0);
        group.add(shelf1);
        // Legs visible at corners via extra dark verticals
        for (const [sx, sz] of [[-1,-1],[-1,1],[1,-1],[1,1]]) {
          const leg = new THREE.Mesh(
            new THREE.BoxGeometry(0.03, h, 0.03),
            darkMat()
          );
          leg.position.set(sx * w * 0.46, h / 2, sz * d * 0.44);
          group.add(leg);
        }
      }
      break;
    }
    case '3-comp-sink': {
      // Legs
      addLegs(group, w, h, d);
      // Backsplash
      addBacksplash(group, w, h, d, h * 0.45);
      // Three recessed basins with rim
      for (let i = -1; i <= 1; i++) {
        const rim = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.3, 0.03, d * 0.75),
          midMat()
        );
        rim.position.set(i * w * 0.3, h + 0.015, 0);
        group.add(rim);
        const basin = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.26, 0.1, d * 0.68),
          darkMat()
        );
        basin.position.set(i * w * 0.3, h - 0.04, 0);
        group.add(basin);
      }
      // Drain boards on the sides (flat extensions)
      // Faucets rising from back
      for (let i = -1; i <= 1; i++) {
        const faucetBase = new THREE.Mesh(
          new THREE.CylinderGeometry(0.02, 0.02, 0.12, 8),
          midMat()
        );
        faucetBase.position.set(i * w * 0.3, h + 0.1, -d * 0.35);
        group.add(faucetBase);
        // Curved spout (approximate with a tilted cylinder)
        const spout = new THREE.Mesh(
          new THREE.CylinderGeometry(0.015, 0.015, 0.12, 8),
          midMat()
        );
        spout.rotation.x = Math.PI / 3;
        spout.position.set(i * w * 0.3, h + 0.18, -d * 0.25);
        group.add(spout);
        // Handle
        const handle = new THREE.Mesh(
          new THREE.BoxGeometry(0.05, 0.015, 0.015),
          midMat()
        );
        handle.position.set(i * w * 0.3, h + 0.15, -d * 0.35);
        group.add(handle);
      }
      // Front apron outline
      addInsetPanel(group, w * 0.98, h * 0.3, new THREE.Vector3(0, h * 0.15, d/2 + 0.005));
      break;
    }
    case 'hand-wash-sink': {
      // Single basin
      const basin = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.7, 0.04, d * 0.65),
        darkMat()
      );
      basin.position.set(0, h + 0.02, 0);
      group.add(basin);
      // Faucet
      const faucet = new THREE.Mesh(
        new THREE.CylinderGeometry(0.018, 0.018, 0.15, 8),
        midMat()
      );
      faucet.position.set(0, h + 0.1, -d * 0.3);
      group.add(faucet);
      // Spout curve
      const spout = new THREE.Mesh(
        new THREE.BoxGeometry(0.08, 0.02, 0.02),
        midMat()
      );
      spout.position.set(0, h + 0.17, -d * 0.25);
      group.add(spout);
      break;
    }
    case 'refrigerator': {
      // Compressor housing on top
      const compressor = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.95, h * 0.08, d * 0.95),
        new THREE.MeshStandardMaterial({ color: 0xd8d8d8, roughness: 0.5, metalness: 0.08 })
      );
      compressor.position.set(0, h - h * 0.04 + 0.01, 0);
      group.add(compressor);
      // Ventilation grille on top compressor
      for (let i = -3; i <= 3; i++) {
        const slat = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.6, 0.008, 0.008),
          darkMat()
        );
        slat.position.set(0, h - h * 0.04 + 0.02, i * d * 0.08);
        group.add(slat);
      }
      // Kick plate at bottom
      const kick = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.95, h * 0.06, 0.02),
        new THREE.MeshStandardMaterial({ color: 0xc4c4c4, roughness: 0.5, metalness: 0.1 })
      );
      kick.position.set(0, h * 0.03, d/2 + 0.005);
      group.add(kick);

      // Main door area (below compressor, above kick)
      const doorYCenter = h * 0.48;
      const doorH = h * 0.85;

      if (variant === 0) {
        // Single door with vertical chrome handle
        // Inset door panel (slightly recessed)
        const door = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.88, doorH, 0.02),
          new THREE.MeshStandardMaterial({ color: 0xe8e8e8, roughness: 0.5, metalness: 0.05 })
        );
        door.position.set(0, doorYCenter, d/2 + 0.011);
        group.add(door);
        // Chrome handle
        const handle = new THREE.Mesh(
          new THREE.CylinderGeometry(0.022, 0.022, doorH * 0.7, 8),
          steelMat()
        );
        handle.position.set(w * 0.36, doorYCenter, d/2 + 0.05);
        group.add(handle);
        // Handle brackets
        for (let side of [-1, 1]) {
          const bracket = new THREE.Mesh(
            new THREE.BoxGeometry(0.03, 0.04, 0.05),
            darkMat()
          );
          bracket.position.set(w * 0.36, doorYCenter + side * doorH * 0.32, d/2 + 0.03);
          group.add(bracket);
        }
        // Hinge markers on opposite side
        for (let hy of [-1, 1]) {
          const hinge = new THREE.Mesh(
            new THREE.BoxGeometry(0.03, 0.04, 0.04),
            midMat()
          );
          hinge.position.set(-w * 0.44, doorYCenter + hy * doorH * 0.35, d/2 + 0.01);
          group.add(hinge);
        }
      } else if (variant === 1) {
        // Two-door split
        for (let half of [0, 1]) {
          const hy = half === 0 ? doorYCenter + doorH * 0.22 : doorYCenter - doorH * 0.22;
          const hh = doorH * 0.44;
          const door = new THREE.Mesh(
            new THREE.BoxGeometry(w * 0.88, hh, 0.02),
            new THREE.MeshStandardMaterial({ color: 0xe8e8e8, roughness: 0.5, metalness: 0.05 })
          );
          door.position.set(0, hy, d/2 + 0.011);
          group.add(door);
          // Handle per door
          const handle = new THREE.Mesh(
            new THREE.CylinderGeometry(0.02, 0.02, hh * 0.6, 8),
            steelMat()
          );
          handle.position.set(w * 0.36, hy, d/2 + 0.05);
          group.add(handle);
        }
      } else {
        // Glass door variant — dark tinted glass
        const glass = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.82, doorH * 0.85, 0.015),
          new THREE.MeshStandardMaterial({ color: 0x1a2028, transparent: true, opacity: 0.85, roughness: 0.15, metalness: 0.1 })
        );
        glass.position.set(0, doorYCenter, d/2 + 0.015);
        group.add(glass);
        addInsetPanel(group, w * 0.88, doorH * 0.9, new THREE.Vector3(0, doorYCenter, d/2 + 0.025));
        // Interior shelves visible through glass
        for (let i = 1; i <= 4; i++) {
          const shelf = new THREE.Mesh(
            new THREE.BoxGeometry(w * 0.78, 0.01, d * 0.7),
            midMat()
          );
          shelf.position.set(0, h * 0.15 + i * doorH * 0.18, 0);
          group.add(shelf);
        }
        // Horizontal handle
        addHandle(group, w * 0.5, new THREE.Vector3(0, doorYCenter + doorH * 0.35, d/2 + 0.03), false);
      }
      break;
    }
    case 'freezer': {
      // Compressor housing on top
      const comp = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.95, h * 0.08, d * 0.95),
        new THREE.MeshStandardMaterial({ color: 0xd8d8d8, roughness: 0.5, metalness: 0.08 })
      );
      comp.position.set(0, h - h * 0.04 + 0.01, 0);
      group.add(comp);
      // Kick plate
      const kick = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.95, h * 0.06, 0.02),
        new THREE.MeshStandardMaterial({ color: 0xc4c4c4, roughness: 0.5, metalness: 0.1 })
      );
      kick.position.set(0, h * 0.03, d/2 + 0.005);
      group.add(kick);

      if (variant === 0) {
        // Single tall door with inset panel
        const door = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.88, h * 0.82, 0.02),
          new THREE.MeshStandardMaterial({ color: 0xe8e8e8, roughness: 0.5, metalness: 0.05 })
        );
        door.position.set(0, h * 0.47, d/2 + 0.011);
        group.add(door);
        // Chrome handle
        const handle = new THREE.Mesh(
          new THREE.CylinderGeometry(0.022, 0.022, h * 0.55, 8),
          steelMat()
        );
        handle.position.set(w * 0.36, h * 0.47, d/2 + 0.05);
        group.add(handle);
      } else if (variant === 1) {
        // Two doors top/bottom
        addHandle(group, h * 0.15, new THREE.Vector3(w * 0.35, h * 0.75, d/2 + 0.025), true);
        addHandle(group, h * 0.25, new THREE.Vector3(w * 0.35, h * 0.35, d/2 + 0.025), true);
        const divLine = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.9, 0.01, 0.01),
          darkMat()
        );
        divLine.position.set(0, h * 0.55, d/2 + 0.005);
        group.add(divLine);
        addInsetPanel(group, w * 0.9, h * 0.35, new THREE.Vector3(0, h * 0.75, d/2 + 0.005));
        addInsetPanel(group, w * 0.9, h * 0.48, new THREE.Vector3(0, h * 0.3, d/2 + 0.005));
      } else {
        // 3-drawer style (pulls)
        for (let i = 0; i < 3; i++) {
          const y = h * (0.25 + i * 0.2);
          addHandle(group, w * 0.5, new THREE.Vector3(0, y + 0.05, d/2 + 0.025), false);
          const line = new THREE.Mesh(
            new THREE.BoxGeometry(w * 0.9, 0.01, 0.008),
            darkMat()
          );
          line.position.set(0, y - 0.04, d/2 + 0.005);
          group.add(line);
        }
      }
      break;
    }
    case 'sandwich-prep': {
      // Refrigerated base
      addInsetPanel(group, w * 0.95, h * 0.5, new THREE.Vector3(0, h * 0.25, d/2 + 0.005));
      // Two doors
      const divLine = new THREE.Mesh(
        new THREE.BoxGeometry(0.01, h * 0.5, 0.01),
        darkMat()
      );
      divLine.position.set(0, h * 0.25, d/2 + 0.005);
      group.add(divLine);
      addHandle(group, 0.08, new THREE.Vector3(-w * 0.2, h * 0.25, d/2 + 0.025), true);
      addHandle(group, 0.08, new THREE.Vector3(w * 0.2, h * 0.25, d/2 + 0.025), true);
      // Pan inserts on top (ingredient wells)
      const wells = variant === 0 ? 4 : variant === 1 ? 6 : 5;
      for (let i = 0; i < wells; i++) {
        const well = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.85 / wells, 0.03, d * 0.45),
          darkMat()
        );
        well.position.set(
          -w * 0.42 + (i + 0.5) * (w * 0.85 / wells),
          h + 0.015,
          -d * 0.15
        );
        group.add(well);
      }
      // Cutting board strip — light grey, same palette
      const board = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.9, 0.02, d * 0.25),
        new THREE.MeshStandardMaterial({ color: 0xd4d4d4, roughness: 0.5, metalness: 0.05 })
      );
      board.position.set(0, h + 0.01, d * 0.28);
      group.add(board);
      break;
    }
    case 'glass-door-cooler': {
      // Dark tinted glass
      const glass = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.85, h * 0.75, 0.015),
        new THREE.MeshStandardMaterial({
          color: 0x1a2028,
          transparent: true,
          opacity: 0.85,
          roughness: 0.15,
          metalness: 0.1
        })
      );
      glass.position.set(0, h * 0.5, d/2);
      group.add(glass);
      addInsetPanel(group, w * 0.88, h * 0.78, new THREE.Vector3(0, h * 0.5, d/2 + 0.015));
      // Interior shelves visible through glass
      for (let i = 1; i <= 4; i++) {
        const shelf = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.8, 0.015, d * 0.7),
          new THREE.MeshStandardMaterial({ color: 0xe2e2e2, roughness: 0.5, metalness: 0.05 })
        );
        shelf.position.set(0, (h * 0.85 / 5) * i, 0);
        group.add(shelf);
      }
      // Handle (variant dependent)
      if (variant === 0) {
        addHandle(group, h * 0.4, new THREE.Vector3(w * 0.36, h * 0.5, d/2 + 0.03), true);
      } else if (variant === 1) {
        addHandle(group, h * 0.2, new THREE.Vector3(-w * 0.36, h * 0.6, d/2 + 0.03), true);
        addHandle(group, h * 0.2, new THREE.Vector3(w * 0.36, h * 0.6, d/2 + 0.03), true);
      } else {
        addHandle(group, w * 0.55, new THREE.Vector3(0, h * 0.88, d/2 + 0.03), false);
      }
      break;
    }
    case 'chest-freezer': {
      // Low chest shape — lid on top
      const lid = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.95, 0.04, d * 0.95),
        new THREE.MeshStandardMaterial({ color: 0xe2e2e2, roughness: 0.5, metalness: 0.05 })
      );
      lid.position.set(0, h + 0.02, 0);
      group.add(lid);
      // Lid handle
      addHandle(group, w * 0.4, new THREE.Vector3(0, h + 0.05, -d * 0.3), false);
      // Variant 2: viewing window lid (dark glass)
      if (variant === 2) {
        const glass = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.7, 0.01, d * 0.6),
          new THREE.MeshStandardMaterial({
            color: 0x1a2028,
            transparent: true,
            opacity: 0.85,
            roughness: 0.15,
            metalness: 0.1
          })
        );
        glass.position.set(0, h + 0.045, 0);
        group.add(glass);
      }
      break;
    }
    case 'ice-machine': {
      // Ice bin at bottom with slot
      const slot = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.6, h * 0.12, 0.02),
        darkMat()
      );
      slot.position.set(0, h * 0.3, d/2 + 0.005);
      group.add(slot);
      // Top section divider
      const divider = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.9, 0.012, 0.01),
        darkMat()
      );
      divider.position.set(0, h * 0.5, d/2 + 0.005);
      group.add(divider);
      // Grille pattern on top half
      for (let i = 0; i < 5; i++) {
        const slat = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.8, 0.008, 0.008),
          darkMat()
        );
        slat.position.set(0, h * (0.6 + i * 0.07), d/2 + 0.005);
        group.add(slat);
      }
      addInsetPanel(group, w * 0.9, h * 0.88, new THREE.Vector3(0, h * 0.5, d/2 + 0.005));
      break;
    }
    case 'kegerator': {
      // Tap tower on top
      const tower = new THREE.Mesh(
        new THREE.CylinderGeometry(0.04, 0.04, 0.2, 8),
        midMat()
      );
      tower.position.set(0, h + 0.1, 0);
      group.add(tower);
      // Taps (1, 2, or 3 based on variant)
      const numTaps = variant + 1;
      for (let i = 0; i < numTaps; i++) {
        const tap = new THREE.Mesh(
          new THREE.BoxGeometry(0.03, 0.04, 0.08),
          darkMat()
        );
        const angle = (i - (numTaps - 1) / 2) * 0.25;
        tap.position.set(Math.sin(angle) * 0.04, h + 0.13, 0.05 + Math.cos(angle) * 0.04);
        group.add(tap);
      }
      addHandle(group, h * 0.3, new THREE.Vector3(w * 0.35, h * 0.5, d/2 + 0.025), true);
      addInsetPanel(group, w * 0.9, h * 0.85, new THREE.Vector3(0, h * 0.48, d/2 + 0.005));
      break;
    }
    case 'under-counter-fridge': {
      addHandle(group, w * 0.4, new THREE.Vector3(0, h * 0.75, d/2 + 0.025), false);
      addInsetPanel(group, w * 0.9, h * 0.85, new THREE.Vector3(0, h * 0.5, d/2 + 0.005));
      break;
    }
    case 'serving-window':
    case 'serving-window-6ft':
    case 'pickup-window':
    case 'swing-serving-window': {
      // Hide the solid body
      const body = group.children[0];
      body.visible = false;
      body.castShadow = false;
      body.receiveShadow = false;

      // Dark transparent opening — visible from both sides as a "hole"
      const punchMat = new THREE.MeshBasicMaterial({
        color: 0x1a1e28,
        transparent: true,
        opacity: 0.15,
        side: THREE.DoubleSide,
        depthWrite: true
      });
      const punchGeo = new THREE.BoxGeometry(w * 0.94, h * 0.94, 0.6);
      const punch = new THREE.Mesh(punchGeo, punchMat);
      punch.position.set(0, h / 2, 0);
      punch.renderOrder = -1;
      group.add(punch);

      // Steel frame
      const fMat = steelMat();
      const ft = 0.08;
      const fd = 0.3;

      // Top header
      const fTop = new THREE.Mesh(new THREE.BoxGeometry(w + ft, ft, fd), fMat);
      fTop.position.set(0, h + ft/2, 0);
      fTop.castShadow = true; group.add(fTop);

      // Bottom sill
      const fBot = new THREE.Mesh(new THREE.BoxGeometry(w + ft, ft * 1.5, fd), fMat);
      fBot.position.set(0, -ft * 0.25, 0);
      fBot.castShadow = true; group.add(fBot);

      // Left jamb
      const fL = new THREE.Mesh(new THREE.BoxGeometry(ft, h + ft, fd), fMat);
      fL.position.set(-w/2 - ft/2, h/2, 0);
      fL.castShadow = true; group.add(fL);

      // Right jamb
      const fR = new THREE.Mesh(new THREE.BoxGeometry(ft, h + ft, fd), fMat);
      fR.position.set(w/2 + ft/2, h/2, 0);
      fR.castShadow = true; group.add(fR);

      // Counter ledge
      const ledge = new THREE.Mesh(
        new THREE.BoxGeometry(w + ft * 2 + 0.2, 0.04, 0.6),
        lightMat()
      );
      ledge.position.set(0, -ft * 0.5, 0.35);
      ledge.castShadow = true; group.add(ledge);

      break;
    }
    case 'cash-register': {
      // POS screen
      const screen = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.55, h * 0.25, 0.03),
        new THREE.MeshStandardMaterial({ color: 0x1a1a1a, roughness: 0.8, metalness: 0.05 })
      );
      screen.position.set(0, h + 0.15, 0);
      screen.rotation.x = -0.2;
      group.add(screen);
      // Stand
      const stand = new THREE.Mesh(
        new THREE.BoxGeometry(0.04, 0.12, 0.04),
        darkMat()
      );
      stand.position.set(0, h + 0.06, 0);
      group.add(stand);
      // Drawer line on front
      addInsetPanel(group, w * 0.85, h * 0.25, new THREE.Vector3(0, h * 0.4, d/2 + 0.005));
      break;
    }
    case 'hood-exhaust': {
      // Vent slats on underside (facing down)
      for (let i = -3; i <= 3; i++) {
        const slat = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.85, 0.015, 0.02),
          darkMat()
        );
        slat.position.set(0, -0.01, i * d * 0.12);
        group.add(slat);
      }
      // Filter rectangles visible
      addInsetPanel(group, w * 0.9, d * 0.85,
        new THREE.Vector3(0, -0.02, 0),
        new THREE.Euler(-Math.PI / 2, 0, 0)
      );
      break;
    }
    case 'storage-shelf': {
      // Horizontal shelves (visible through open sides)
      for (let i = 1; i <= 4; i++) {
        const shelf = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.95, 0.02, d * 0.95),
          new THREE.MeshStandardMaterial({ color: 0xdadada, roughness: 0.5, metalness: 0.05 })
        );
        shelf.position.set(0, (h / 5) * i, 0);
        group.add(shelf);
      }
      break;
    }
    case 'propane-tank': {
      // Top valve on the cylinder body (already cylinder-shaped)
      const valve = new THREE.Mesh(
        new THREE.CylinderGeometry(0.04, 0.04, 0.08, 8),
        darkMat()
      );
      valve.position.set(0, h + 0.04, 0);
      group.add(valve);
      // Top cap line
      const cap = new THREE.Mesh(
        new THREE.TorusGeometry(Math.min(w, d) * 0.35, 0.01, 6, 20),
        darkMat()
      );
      cap.rotation.x = -Math.PI / 2;
      cap.position.y = h * 0.9;
      group.add(cap);
      break;
    }
    case 'fire-suppression': {
      // Valve top on cylinder
      const valve = new THREE.Mesh(
        new THREE.BoxGeometry(0.1, 0.06, 0.1),
        darkMat()
      );
      valve.position.set(0, h + 0.03, 0);
      group.add(valve);
      // Pressure gauge circle
      const gauge = new THREE.Mesh(
        new THREE.CylinderGeometry(0.04, 0.04, 0.01, 12),
        darkMat()
      );
      gauge.rotation.x = Math.PI / 2;
      gauge.position.set(0, h * 0.8, Math.min(w, d) * 0.35);
      group.add(gauge);
      break;
    }
    case 'water-heater': {
      // Control panel on cylinder side
      const panel = new THREE.Mesh(
        new THREE.BoxGeometry(0.1, 0.14, 0.02),
        darkMat()
      );
      panel.position.set(0, h * 0.5, Math.min(w, d) * 0.4 + 0.01);
      group.add(panel);
      // Pipe on top
      const pipe = new THREE.Mesh(
        new THREE.CylinderGeometry(0.025, 0.025, 0.12, 8),
        midMat()
      );
      pipe.position.set(0, h + 0.06, 0);
      group.add(pipe);
      break;
    }
    case 'roof-vent': {
      // Mushroom-cap vent
      const cap = new THREE.Mesh(
        new THREE.CylinderGeometry(w * 0.5, w * 0.4, h * 0.4, 12),
        midMat()
      );
      cap.position.set(0, h * 0.75, 0);
      group.add(cap);
      break;
    }
    case 'exhaust-fan': {
      // Grill on top with X pattern
      const frame = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.9, 0.02, d * 0.9),
        darkMat()
      );
      frame.position.set(0, h + 0.01, 0);
      group.add(frame);
      // Fan blades (crosses)
      for (let i = 0; i < 4; i++) {
        const blade = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.7, 0.015, 0.04),
          midMat()
        );
        blade.rotation.y = (i * Math.PI) / 4;
        blade.position.y = h * 0.6;
        group.add(blade);
      }
      break;
    }
    case 'ac-unit': {
      // Vent grill on front
      for (let i = -3; i <= 3; i++) {
        const slat = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.8, 0.015, 0.015),
          darkMat()
        );
        slat.position.set(0, h * 0.5 + i * 0.04, d/2 + 0.005);
        group.add(slat);
      }
      break;
    }
    case 'led-panel': {
      // Glowing emissive face
      const face = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.9, 0.01, d * 0.85),
        new THREE.MeshBasicMaterial({ color: 0xfffbcc })
      );
      face.position.set(0, -0.005, 0);
      face.userData.isLightGlow = true;
      group.add(face);
      // Downward point light — bright enough to cast visible pool on floor
      const pl = new THREE.PointLight(0xfff4d0, 12, 5, 2);
      pl.position.set(0, -0.2, 0);
      pl.userData.isEquipLight = true;
      group.add(pl);
      // Secondary wider fill
      const pl2 = new THREE.PointLight(0xfff8e0, 4, 8, 2);
      pl2.position.set(0, -0.1, 0);
      pl2.userData.isEquipLight = true;
      group.add(pl2);
      break;
    }
    case 'led-strip': {
      const strip = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.95, 0.015, d * 0.5),
        new THREE.MeshBasicMaterial({ color: 0xfff8cc })
      );
      strip.position.set(0, -0.005, 0);
      strip.userData.isLightGlow = true;
      group.add(strip);
      // Two spread lights along the strip length
      for (let i = -1; i <= 1; i += 2) {
        const sl = new THREE.PointLight(0xfff4d0, 6, 4, 2);
        sl.position.set(i * w * 0.25, -0.15, 0);
        sl.userData.isEquipLight = true;
        group.add(sl);
      }
      break;
    }
    case 'work-light': {
      const bulb = new THREE.Mesh(
        new THREE.CylinderGeometry(w * 0.25, w * 0.25, 0.03, 12),
        new THREE.MeshBasicMaterial({ color: 0xffeecc })
      );
      bulb.position.set(0, -0.01, 0);
      bulb.userData.isLightGlow = true;
      group.add(bulb);
      // Focused spot-like point light
      const wl = new THREE.PointLight(0xffe8bb, 15, 4, 2);
      wl.position.set(0, -0.1, 0);
      wl.userData.isEquipLight = true;
      group.add(wl);
      break;
    }
    case 'led-trim': {
      // Color-changing LED strip — emissive glow + light source
      const trimGlow = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.95, 0.01, d * 0.8),
        new THREE.MeshBasicMaterial({ color: 0x88ffcc })
      );
      trimGlow.position.set(0, -0.005, 0);
      trimGlow.userData.isLightGlow = true;
      group.add(trimGlow);
      // Multiple light points along the strip
      for (let i = -1; i <= 1; i++) {
        const tl = new THREE.PointLight(0x88ffcc, 4, 3, 2);
        tl.position.set(i * w * 0.3, -0.1, 0);
        tl.userData.isEquipLight = true;
        group.add(tl);
      }
      break;
    }
    case 'wall-shelf-4ft':
    case 'wall-shelf-2ft': {
      // Simple shelf slab (the body already shows this, add bracket lines)
      const bracket1 = new THREE.Mesh(
        new THREE.BoxGeometry(0.02, h * 1.2, 0.04),
        darkMat()
      );
      bracket1.position.set(-w * 0.35, -h * 0.2, -d/2 + 0.02);
      group.add(bracket1);
      const bracket2 = new THREE.Mesh(
        new THREE.BoxGeometry(0.02, h * 1.2, 0.04),
        darkMat()
      );
      bracket2.position.set(w * 0.35, -h * 0.2, -d/2 + 0.02);
      group.add(bracket2);
      break;
    }
    case 'control-panel': {
      // Panel door
      addInsetPanel(group, w * 0.85, h * 0.88, new THREE.Vector3(0, h * 0.5, d/2 + 0.005));
      // Rows of breaker switches
      for (let row = 0; row < 4; row++) {
        for (let col = -1; col <= 1; col++) {
          const sw = new THREE.Mesh(
            new THREE.BoxGeometry(w * 0.12, 0.02, 0.015),
            darkMat()
          );
          sw.position.set(col * w * 0.2, h * (0.2 + row * 0.18), d/2 + 0.01);
          group.add(sw);
        }
      }
      break;
    }
    case 'switch-panel': {
      // Switch toggles
      for (let i = -1; i <= 1; i++) {
        const sw = new THREE.Mesh(
          new THREE.BoxGeometry(w * 0.2, h * 0.3, 0.02),
          darkMat()
        );
        sw.position.set(i * w * 0.28, h * 0.5, d/2 + 0.01);
        group.add(sw);
      }
      break;
    }
    case 'outlet-strip': {
      // Outlet dots
      for (let i = 0; i < 4; i++) {
        const outlet = new THREE.Mesh(
          new THREE.BoxGeometry(0.03, h * 0.5, 0.015),
          darkMat()
        );
        outlet.position.set(-w * 0.35 + i * w * 0.23, h * 0.5, d/2 + 0.01);
        group.add(outlet);
      }
      break;
    }
    case 'menu-board': {
      // Dark board surface
      const surface = new THREE.Mesh(
        new THREE.BoxGeometry(w * 0.92, h * 0.85, 0.02),
        new THREE.MeshStandardMaterial({ color: 0x2a2a2a, roughness: 0.8, metalness: 0.05 })
      );
      surface.position.set(0, h * 0.5, d/2 + 0.005);
      group.add(surface);
      break;
    }
    case 'side-window':
    case 'drive-thru-window': {
      // Fixed glass window — frame + tinted glass + punch-through
      const swBody = group.children[0];
      swBody.visible = false;
      swBody.castShadow = false;
      swBody.receiveShadow = false;

      // Dark transparent opening
      const swPunchMat = new THREE.MeshBasicMaterial({
        color: 0x1a1e28, transparent: true, opacity: 0.15,
        side: THREE.DoubleSide, depthWrite: true
      });
      const swPunch = new THREE.Mesh(new THREE.BoxGeometry(w * 0.94, h * 0.94, 0.5), swPunchMat);
      swPunch.position.set(0, h/2, 0);
      swPunch.renderOrder = -1;
      group.add(swPunch);

      const swMat = steelMat();
      const swt = 0.06;
      const swd = 0.15;
      // Frame
      const swTop = new THREE.Mesh(new THREE.BoxGeometry(w + swt, swt, swd), swMat);
      swTop.position.set(0, h + swt/2, 0); swTop.castShadow = true; group.add(swTop);
      const swBot = new THREE.Mesh(new THREE.BoxGeometry(w + swt, swt, swd), swMat);
      swBot.position.set(0, -swt/2, 0); swBot.castShadow = true; group.add(swBot);
      const swL = new THREE.Mesh(new THREE.BoxGeometry(swt, h + swt, swd), swMat);
      swL.position.set(-w/2 - swt/2, h/2, 0); swL.castShadow = true; group.add(swL);
      const swR = new THREE.Mesh(new THREE.BoxGeometry(swt, h + swt, swd), swMat);
      swR.position.set(w/2 + swt/2, h/2, 0); swR.castShadow = true; group.add(swR);
      // Glass pane
      const glass = new THREE.Mesh(
        new THREE.BoxGeometry(w, h, 0.02),
        new THREE.MeshStandardMaterial({ color: 0x1a2028, transparent: true, opacity: 0.7, roughness: 0.1, metalness: 0.1 })
      );
      glass.position.set(0, h/2, 0); group.add(glass);
      break;
    }
    case 'condiment-stand': {
      // Dispenser holes on top
      for (let i = -1; i <= 1; i++) {
        const hole = new THREE.Mesh(
          new THREE.CylinderGeometry(0.04, 0.04, 0.04, 10),
          darkMat()
        );
        hole.position.set(i * w * 0.25, h + 0.02, 0);
        group.add(hole);
      }
      break;
    }
  }
}

// Get formatted dimensions string
function getFormattedDims(equipDef) {
  const wFt = equipDef.widthCells / CELLS_PER_FOOT;
  const dFt = equipDef.depthCells / CELLS_PER_FOOT;
  return `${wFt}' x ${dFt}'`;
}
