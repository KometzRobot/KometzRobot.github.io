// Stock photo picker — Unsplash deterministic URLs, themed by build phase.
// Each call returns the same image for the same key (jobId + index), so the
// shop floor doesn't see a fresh photo every render.
//
// Curated for Brothers Fab: heavy on welding, metal shop, food trucks, stainless.
// No staged corporate / generic office shots.

const STOCK_POOLS = {
  // Welding, frame, fabrication — sparks, MIG, TIG, structural
  frame: [
    'photo-1565043589221-1a6fd9ae45c7', // welder with sparks
    'photo-1504917595217-d4dc5ebe6122', // metal fab shop
    'photo-1581094288338-2314dddb7ece', // sparks close-up
    'photo-1530124566582-a618bc2615dc', // grinder
    'photo-1567789884554-0b844b597180', // weld bead close-up
    'photo-1578255321055-ac95caaa1b87', // square tube cuts
    'photo-1574087452805-d97e75ce7c1b', // mig welding
    'photo-1518709268805-4e9042af9f23', // sparks atmosphere wide
    'photo-1581094794329-c8112a89af12', // pipe & metalwork
    'photo-1559867986-d09c10dca5e2',    // welder helmet on
    'photo-1582408921715-18e7806365c1', // tig welding hand
    'photo-1591115765373-5207764f72e7', // welding helmet w/ sparks
    'photo-1504307651254-35680f356dfd', // angle grinder w/ sparks
    'photo-1611288875785-22b3e4e83a76', // structural steel weld
    'photo-1591105327764-90874f25cb3a', // welder portrait
  ],
  // Plumbing & gas — copper, valves, gas line
  plumbing: [
    'photo-1581094794329-c8112a89af12', // pipe fitting
    'photo-1558618666-fcd25c85cd64',    // copper plumbing
    'photo-1607400201515-c2c41c07d307', // gas valve
    'photo-1581092160562-40aa08e78837', // tools on workbench
    'photo-1585704032915-c3400ca199e7', // valves & gauges
    'photo-1574675783029-9f5e22ad9e2e', // black iron pipe
  ],
  // Electrical — panels, conduit, wiring
  electrical: [
    'photo-1621905251918-48416bd8575a', // electrical panel
    'photo-1558618047-3c8c76ca7d13',    // wiring
    'photo-1573164713988-8665fc963095', // wire spools
    'photo-1597328894111-0aa68aaff89e', // breakers close
    'photo-1581092918056-0c4c3acd3789', // multimeter on panel
    'photo-1605152276897-4f618f831968', // conduit run
  ],
  // Stainless interior, commercial kitchen
  interior: [
    'photo-1556909114-f6e7ad7d3136',    // stainless prep table
    'photo-1565895405138-6c3a1555da6a', // commercial kitchen
    'photo-1581349437783-8a3a7e8d4d4c', // stainless counter
    'photo-1574484284002-952d92456975', // brushed metal
    'photo-1590846406792-0adc7f938f1d', // stainless hood
    'photo-1583874483540-8e7df59a1e7c', // commercial kitchen line
    'photo-1556910103-1c02745aae4d',    // stainless detail
    'photo-1593618998160-e34014e67546', // food truck interior stainless
  ],
  // Food truck exterior, delivery, on-site
  truck: [
    'photo-1565299585323-38d6b0865b47', // food truck exterior
    'photo-1567521464027-f127ff144326', // taco truck
    'photo-1571091655789-405eb7a3a3a8', // food truck side
    'photo-1593538312308-d4c29d8dc7f8', // truck at event
    'photo-1568901346375-23c9450c58cd', // food truck row
    'photo-1567129937968-cdad8f07e2f8', // food truck window service
    'photo-1565299507177-b0ac66763828', // food truck open at night
    'photo-1551782450-a2132b4ba21d',    // food truck close-up
    'photo-1605522561233-768ad7a8fabf', // converted truck side
    'photo-1532635241-17e820acc59f',    // truck rear
  ],
  // Sign, blade sign, backlit
  sign: [
    'photo-1567446537708-ac4aa75c9c28', // backlit sign
    'photo-1517649763962-0c623066013b', // metal sign
    'photo-1573164574572-cb89e39749b4', // neon sign workshop
    'photo-1572731073979-6a1b58b1ea54', // metal letters
    'photo-1572931089572-26716b2c1bcc', // sign fabrication
  ],
  // Shop floor / generic — wide context shots, racks, layout
  shop: [
    'photo-1504917595217-d4dc5ebe6122', // metal shop wide
    'photo-1565043666747-69f6646db940', // shop floor
    'photo-1518709268805-4e9042af9f23', // sparks atmosphere
    'photo-1581092580497-e0d23cbdf1dc', // workbench tools
    'photo-1599696848652-f0ff52cf7d99', // metal shop layout
    'photo-1605152276897-4f618f831968', // shop overview
    'photo-1567789884554-0b844b597180', // welding bay
    'photo-1530124566582-a618bc2615dc', // grinding station
    'photo-1530541930197-ff16ac917b0e', // shop interior wide
    'photo-1581094794329-c8112a89af12', // workshop detail
  ],
  // Materials / sourcing — steel stock, racks, cutoffs
  materials: [
    'photo-1565043666747-69f6646db940', // material rack
    'photo-1530124566582-a618bc2615dc', // metal stock
    'photo-1574484284002-952d92456975', // brushed metal stack
    'photo-1582719188393-bb71ca45dbb9', // sheet metal stack
    'photo-1610137146135-3d61c5af5ba9', // steel bar stock
    'photo-1582719471384-894fbb16e074', // tube/pipe rack
    'photo-1560179707-f14e90ef3623',    // raw materials shelf
  ],
  // Quote / lead — drawings, planning, measuring
  quote: [
    'photo-1581092160562-40aa08e78837', // tools + plans
    'photo-1503387762-592deb58ef4e',    // sketch / plan
    'photo-1581092918056-0c4c3acd3789', // tape measure & plans
    'photo-1581094794329-c8112a89af12', // shop notebook
    'photo-1581092580497-e0d23cbdf1dc', // worksheet on bench
  ],
  // Crew — people working, hands, faces
  crew: [
    'photo-1559867986-d09c10dca5e2',    // welder portrait
    'photo-1591105327764-90874f25cb3a', // helmet on
    'photo-1582408921715-18e7806365c1', // gloved hands tig
    'photo-1574087452805-d97e75ce7c1b', // welder bent over
    'photo-1504307651254-35680f356dfd', // grinder hands
    'photo-1611288875785-22b3e4e83a76', // shop worker
  ],
};

// Map fab stage → pool
const STAGE_POOL = {
  quote: 'quote',
  approved: 'shop',
  design: 'quote',
  sourcing: 'materials',
  frame: 'frame',
  plumbing: 'plumbing',
  electrical: 'electrical',
  delivered: 'truck',
};

// Map by job *type* keyword → pool — used when stage is "show the finished thing"
// (delivered, quote, approved). For in-progress stages we let the stage win so
// a food truck mid-build shows welding, not the finished restaurant.
const TYPE_POOL = [
  [/sign/i,            'sign'],
  [/truck|piaggio/i,   'truck'],
  [/coffee|seacan/i,   'truck'],
  [/kitchen|install|hood/i, 'interior'],
  [/trailer|frame/i,   'frame'],
];

// Stages where we should show the finished/branded thing instead of the build.
const TYPE_WINS_STAGES = new Set(['quote', 'approved', 'delivered']);

function pickPool({ stage, type, kind }) {
  if (kind && STOCK_POOLS[kind]) return kind;
  // For in-progress stages, stage wins — show the actual work being done.
  if (stage && STAGE_POOL[stage] && !TYPE_WINS_STAGES.has(stage)) {
    return STAGE_POOL[stage];
  }
  // For early/finished stages, type wins — show the product context.
  if (type) {
    for (const [rx, pool] of TYPE_POOL) if (rx.test(type)) return pool;
  }
  if (stage && STAGE_POOL[stage]) return STAGE_POOL[stage];
  return 'shop';
}

// Stable index from a string key.
function hashIdx(key, mod) {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = ((h * 31) + key.charCodeAt(i)) >>> 0;
  return h % mod;
}

// Public: get a stock photo URL.
// usage: stockPhoto({ jobId, idx, stage, type, kind, w, h })
function stockPhoto(opts = {}) {
  const { jobId = 'x', idx = 0, stage, type, kind, w = 800, h = 600 } = opts;
  const pool = STOCK_POOLS[pickPool({ stage, type, kind })] || STOCK_POOLS.shop;
  const photo = pool[hashIdx(`${jobId}|${idx}`, pool.length)];
  // Unsplash CDN with crop params — deterministic, no API call.
  return `https://images.unsplash.com/${photo}?auto=format&fit=crop&w=${w}&h=${h}&q=70`;
}

window.stockPhoto = stockPhoto;
window.bfStock = { STOCK_POOLS, pickPool };
