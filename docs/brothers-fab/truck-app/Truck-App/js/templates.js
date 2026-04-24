// ============================================
// Built-in Template Layouts
// ============================================
// gridX/gridZ = CENTER position in world units (1 world unit = 1 ft)
// Truck floor: X axis = length (0=rear), Z axis = width (0=left wall)
// CELL_SIZE=0.5, so item world width = widthCells * 0.5
//
// Layout convention:
//   Left wall (Z low):  cooking line, cold storage
//   Right wall (Z high): prep, service, windows
//   Center: aisle (~2.5-3ft clear)
//   Front/rear corners: utilities, tanks, generator

const BUILTIN_TEMPLATES = [
  // ============================
  // 1. CLASSIC TACO TRUCK — 20ft x 8ft
  // ============================
  {
    id: 'taco-truck',
    name: 'Classic Taco Truck',
    description: 'Traditional taqueria — griddle, charbroiler, prep, serving window. Full compliance.',
    truck_length_ft: 20,
    truck_width_ft: 8,
    items: [
      // LEFT WALL — cooking line (Z=1.25 for 2.5ft deep items)
      { equipmentId: 'refrigerator',      gridX: 1.25,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'prep-table-4ft',    gridX: 4.5,   gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'flat-top-griddle',  gridX: 8.0,   gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'charbroiler',       gridX: 11.0,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'steam-table',       gridX: 14.5,  gridZ: 1.0,  rotation: 0, variant: 0 }, // D=2ft, Z=1.0

      // RIGHT WALL — service side
      { equipmentId: '3-comp-sink',       gridX: 2.0,   gridZ: 7.0,  rotation: 0, variant: 0 }, // D=2ft
      { equipmentId: 'hand-wash-sink',    gridX: 4.75,  gridZ: 7.25, rotation: 0, variant: 0 }, // D=1.5ft
      { equipmentId: 'sandwich-prep',     gridX: 8.0,   gridZ: 6.75, rotation: 0, variant: 1 }, // D=2.5ft
      { equipmentId: 'cash-register',     gridX: 11.5,  gridZ: 7.0,  rotation: 0, variant: 0 }, // D=2ft
      { equipmentId: 'serving-window',    gridX: 14.5,  gridZ: 7.5,  rotation: 0, variant: 0 }, // D=1ft

      // ELEVATED — hood over cooking, ceiling light
      { equipmentId: 'hood-exhaust',      gridX: 9.5,   gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'led-panel',         gridX: 10.0,  gridZ: 4.0,  rotation: 0, variant: 0 },

      // UTILITIES — front area (X 16.5–20)
      { equipmentId: 'fire-suppression',  gridX: 17.0,  gridZ: 0.5,  rotation: 0, variant: 0 },
      { equipmentId: 'propane-tank',      gridX: 18.25, gridZ: 0.75, rotation: 0, variant: 0 },
      { equipmentId: 'generator-12kw',    gridX: 18.5,  gridZ: 2.5,  rotation: 0, variant: 0 },
      { equipmentId: 'fresh-water-tank',  gridX: 18.25, gridZ: 4.5,  rotation: 0, variant: 0 },
      { equipmentId: 'grey-water-tank',   gridX: 18.25, gridZ: 6.5,  rotation: 0, variant: 0 },
      { equipmentId: 'control-panel',     gridX: 0.75,  gridZ: 3.75, rotation: 0, variant: 0 }
    ]
  },

  // ============================
  // 2. COFFEE & ESPRESSO — 16ft x 7ft
  // ============================
  {
    id: 'coffee-cart',
    name: 'Coffee & Espresso',
    description: 'Compact coffee truck — espresso station, cold drinks, pastry display, grab-and-go.',
    truck_length_ft: 16,
    truck_width_ft: 7,
    items: [
      // LEFT WALL (Z=1.25 for 2.5ft deep, Z=1.0 for 2ft deep)
      { equipmentId: 'under-counter-fridge', gridX: 1.25, gridZ: 1.0,  rotation: 0, variant: 0 }, // D=2ft
      { equipmentId: 'prep-table-4ft',       gridX: 4.5,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'range-oven',           gridX: 8.0,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'glass-door-cooler',    gridX: 10.75,gridZ: 1.25, rotation: 0, variant: 2 },
      { equipmentId: 'ice-machine',          gridX: 13.25,gridZ: 1.25, rotation: 0, variant: 0 },

      // RIGHT WALL (7ft truck: Z=6.0 for D=2ft, Z=5.75 for D=2.5ft)
      { equipmentId: '3-comp-sink',       gridX: 2.0,  gridZ: 6.0,  rotation: 0, variant: 0 },
      { equipmentId: 'hand-wash-sink',    gridX: 4.75, gridZ: 6.25, rotation: 0, variant: 0 },
      { equipmentId: 'sandwich-prep',     gridX: 8.0,  gridZ: 5.75, rotation: 0, variant: 1 },
      { equipmentId: 'cash-register',     gridX: 11.5, gridZ: 6.0,  rotation: 0, variant: 0 },
      { equipmentId: 'pickup-window',     gridX: 13.5, gridZ: 6.5,  rotation: 0, variant: 0 },

      // ELEVATED
      { equipmentId: 'led-panel',         gridX: 8.0,  gridZ: 3.5,  rotation: 0, variant: 0 },

      // UTILITIES
      { equipmentId: 'fresh-water-tank',  gridX: 1.25, gridZ: 3.5,  rotation: 0, variant: 0 },
      { equipmentId: 'generator-7kw',     gridX: 15.0, gridZ: 3.5,  rotation: 0, variant: 0 },
      { equipmentId: 'fire-suppression',  gridX: 15.5, gridZ: 1.25, rotation: 0, variant: 0 }
    ]
  },

  // ============================
  // 3. BURGER JOINT — 22ft x 8ft
  // ============================
  {
    id: 'burger-joint',
    name: 'Burger Joint',
    description: 'Full burger operation — flat top, deep fryer, cold storage, big serving window.',
    truck_length_ft: 22,
    truck_width_ft: 8,
    items: [
      // LEFT WALL
      { equipmentId: 'refrigerator',      gridX: 1.25,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'freezer',           gridX: 3.75,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'prep-table-4ft',    gridX: 7.0,   gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'flat-top-griddle',  gridX: 10.5,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'deep-fryer',        gridX: 13.0,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'range-oven',        gridX: 15.5,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'steam-table',       gridX: 19.0,  gridZ: 1.0,  rotation: 0, variant: 0 },

      // RIGHT WALL
      { equipmentId: '3-comp-sink',       gridX: 2.0,   gridZ: 7.0,  rotation: 0, variant: 0 },
      { equipmentId: 'hand-wash-sink',    gridX: 4.75,  gridZ: 7.25, rotation: 0, variant: 0 },
      { equipmentId: 'sandwich-prep',     gridX: 8.0,   gridZ: 6.75, rotation: 0, variant: 1 },
      { equipmentId: 'ice-machine',       gridX: 11.75, gridZ: 6.75, rotation: 0, variant: 0 },
      { equipmentId: 'cash-register',     gridX: 14.0,  gridZ: 7.0,  rotation: 0, variant: 0 },
      { equipmentId: 'serving-window',    gridX: 17.0,  gridZ: 7.5,  rotation: 0, variant: 0 },

      // ELEVATED
      { equipmentId: 'hood-exhaust',      gridX: 12.0,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'ac-unit',           gridX: 12.0,  gridZ: 4.0,  rotation: 0, variant: 0 },
      { equipmentId: 'led-panel',         gridX: 8.0,   gridZ: 4.0,  rotation: 0, variant: 0 },

      // UTILITIES — front area (X 19–22)
      { equipmentId: 'fire-suppression',  gridX: 21.5,  gridZ: 0.5,  rotation: 0, variant: 0 },
      { equipmentId: 'propane-tank',      gridX: 21.25, gridZ: 1.75, rotation: 0, variant: 0 },
      { equipmentId: 'generator-20kw',    gridX: 20.25, gridZ: 4.0,  rotation: 0, variant: 0 },
      { equipmentId: 'fresh-water-tank-lg', gridX: 20.5, gridZ: 6.5, rotation: 0, variant: 0 },
      { equipmentId: 'grey-water-tank-lg',  gridX: 20.5, gridZ: 2.75,rotation: 0, variant: 0 },
      { equipmentId: 'control-panel',     gridX: 0.75,  gridZ: 4.0,  rotation: 0, variant: 0 }
    ]
  },

  // ============================
  // 4. BBQ SMOKER — 22ft x 8ft
  // ============================
  {
    id: 'bbq-smoker',
    name: 'BBQ Smoker',
    description: 'BBQ and smokehouse — charbroiler, ovens, big prep area, 6ft serving window.',
    truck_length_ft: 22,
    truck_width_ft: 8,
    items: [
      // LEFT WALL
      { equipmentId: 'refrigerator',      gridX: 1.25,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'freezer',           gridX: 3.75,  gridZ: 1.25, rotation: 0, variant: 1 },
      { equipmentId: 'prep-table-6ft',    gridX: 8.0,   gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'charbroiler',       gridX: 12.0,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'range-oven',        gridX: 14.5,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'steam-table',       gridX: 18.0,  gridZ: 1.0,  rotation: 0, variant: 0 },

      // RIGHT WALL
      { equipmentId: '3-comp-sink',       gridX: 2.0,   gridZ: 7.0,  rotation: 0, variant: 0 },
      { equipmentId: 'hand-wash-sink',    gridX: 4.75,  gridZ: 7.25, rotation: 0, variant: 0 },
      { equipmentId: 'prep-table-4ft',    gridX: 7.5,   gridZ: 6.75, rotation: 0, variant: 0 },
      { equipmentId: 'cash-register',     gridX: 10.5,  gridZ: 7.0,  rotation: 0, variant: 0 },
      { equipmentId: 'serving-window-6ft',gridX: 14.0,  gridZ: 7.5,  rotation: 0, variant: 0 },

      // ELEVATED
      { equipmentId: 'hood-exhaust',      gridX: 13.0,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'led-panel',         gridX: 10.0,  gridZ: 4.0,  rotation: 0, variant: 0 },

      // UTILITIES
      { equipmentId: 'propane-tank',      gridX: 21.25, gridZ: 0.75, rotation: 0, variant: 0 },
      { equipmentId: 'fire-suppression',  gridX: 21.5,  gridZ: 2.0,  rotation: 0, variant: 0 },
      { equipmentId: 'control-panel',     gridX: 0.75,  gridZ: 4.0,  rotation: 0, variant: 0 },
      { equipmentId: 'fresh-water-tank',  gridX: 20.75, gridZ: 4.0,  rotation: 0, variant: 0 },
      { equipmentId: 'grey-water-tank',   gridX: 20.75, gridZ: 6.0,  rotation: 0, variant: 0 },
      { equipmentId: 'generator-12kw',    gridX: 20.5,  gridZ: 7.5,  rotation: 0, variant: 0 }
    ]
  },

  // ============================
  // 5. ICE CREAM & DESSERTS — 16ft x 7ft
  // ============================
  {
    id: 'ice-cream-truck',
    name: 'Ice Cream & Desserts',
    description: 'Frozen treats — chest freezer, dipping cabinet, toppings station, compact layout.',
    truck_length_ft: 16,
    truck_width_ft: 7,
    items: [
      // LEFT WALL
      { equipmentId: 'chest-freezer',        gridX: 2.0,  gridZ: 1.25, rotation: 0, variant: 2 },
      { equipmentId: 'freezer',              gridX: 6.0,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'under-counter-fridge', gridX: 8.5,  gridZ: 1.0,  rotation: 0, variant: 0 },
      { equipmentId: 'ice-machine',          gridX: 11.0, gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'glass-door-cooler',    gridX: 13.5, gridZ: 1.25, rotation: 0, variant: 2 },

      // RIGHT WALL (7ft truck)
      { equipmentId: '3-comp-sink',       gridX: 2.0,  gridZ: 6.0,  rotation: 0, variant: 0 },
      { equipmentId: 'hand-wash-sink',    gridX: 4.75, gridZ: 6.25, rotation: 0, variant: 0 },
      { equipmentId: 'prep-table-4ft',    gridX: 7.5,  gridZ: 5.75, rotation: 0, variant: 0 },
      { equipmentId: 'cash-register',     gridX: 10.5, gridZ: 6.0,  rotation: 0, variant: 0 },
      { equipmentId: 'pickup-window',     gridX: 12.5, gridZ: 6.5,  rotation: 0, variant: 0 },

      // ELEVATED
      { equipmentId: 'led-panel',         gridX: 8.0,  gridZ: 3.5,  rotation: 0, variant: 0 },

      // UTILITIES
      { equipmentId: 'fresh-water-tank',  gridX: 1.25, gridZ: 3.5,  rotation: 0, variant: 0 },
      { equipmentId: 'generator-7kw',     gridX: 15.0, gridZ: 3.5,  rotation: 0, variant: 0 }
    ]
  },

  // ============================
  // 6. PIZZA WAGON — 20ft x 8ft
  // ============================
  {
    id: 'pizza-wagon',
    name: 'Pizza Wagon',
    description: 'Pizza operation — dual ovens, big prep area, cold storage, dough-to-door flow.',
    truck_length_ft: 20,
    truck_width_ft: 8,
    items: [
      // LEFT WALL
      { equipmentId: 'refrigerator',      gridX: 1.25,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'sandwich-prep',     gridX: 5.0,   gridZ: 1.25, rotation: 0, variant: 1 },
      { equipmentId: 'prep-table-6ft',    gridX: 10.5,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'range-oven',        gridX: 15.0,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'range-oven',        gridX: 18.0,  gridZ: 1.25, rotation: 0, variant: 0 },

      // RIGHT WALL
      { equipmentId: '3-comp-sink',       gridX: 2.0,   gridZ: 7.0,  rotation: 0, variant: 0 },
      { equipmentId: 'hand-wash-sink',    gridX: 4.75,  gridZ: 7.25, rotation: 0, variant: 0 },
      { equipmentId: 'under-counter-fridge', gridX: 6.75, gridZ: 7.0, rotation: 0, variant: 0 },
      { equipmentId: 'ice-machine',       gridX: 9.25,  gridZ: 6.75, rotation: 0, variant: 0 },
      { equipmentId: 'cash-register',     gridX: 12.5,  gridZ: 7.0,  rotation: 0, variant: 0 },
      { equipmentId: 'serving-window',    gridX: 15.5,  gridZ: 7.5,  rotation: 0, variant: 0 },

      // ELEVATED
      { equipmentId: 'hood-exhaust',      gridX: 16.5,  gridZ: 1.25, rotation: 0, variant: 0 },
      { equipmentId: 'led-panel',         gridX: 10.0,  gridZ: 4.0,  rotation: 0, variant: 0 },

      // UTILITIES
      { equipmentId: 'propane-tank',      gridX: 19.25, gridZ: 4.0,  rotation: 0, variant: 0 },
      { equipmentId: 'fire-suppression',  gridX: 19.5,  gridZ: 5.5,  rotation: 0, variant: 0 },
      { equipmentId: 'control-panel',     gridX: 0.75,  gridZ: 4.0,  rotation: 0, variant: 0 },
      { equipmentId: 'fresh-water-tank',  gridX: 18.75, gridZ: 6.5,  rotation: 0, variant: 0 },
      { equipmentId: 'generator-12kw',    gridX: 19.0,  gridZ: 2.5,  rotation: 0, variant: 0 },
      { equipmentId: 'ac-unit',           gridX: 16.5,  gridZ: 4.0,  rotation: 0, variant: 0 }
    ]
  }
];

window.BUILTIN_TEMPLATES = BUILTIN_TEMPLATES;
