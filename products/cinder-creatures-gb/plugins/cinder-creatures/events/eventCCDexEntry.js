// Cinder Creatures — Show Pokedex-style Dex Entry
// Reads a creature ID variable (1..56) and displays the matching dex entry:
// "#NN NAME / TYPE / flavor text". Use after Cinder: encounter to show
// the Pokedex-style readout for a captured or seen creature.

const SPECIES = [
  { name: "FORKLING", type: "PROC",  note: "cleaves into two on hit" },
  { name: "DAEMONET", type: "PROC",  note: "runs in the background" },
  { name: "KERNITE",  type: "CORE",  note: "hard-headed, low EXP" },
  { name: "RECURSE",  type: "LOGIC", note: "calls itself, can stack" },
  { name: "MUTEXEL",  type: "LOGIC", note: "locks one move per turn" },
  { name: "BYTEFLY",  type: "DATA",  note: "swarms in tall grass" },
  { name: "SEMAFOX",  type: "LOGIC", note: "signals before striking" },
  { name: "REGEXEL",  type: "DATA",  note: "matches your pattern" },
  { name: "SCOPEWVR", type: "MEM",   note: "weaves a closure" },
  { name: "ALLOCROC", type: "MEM",   note: "opens its jaws wide" },
  { name: "NULLPUP",  type: "MEM",   note: "a pointer to nothing" },
  { name: "CACHEBIT", type: "DATA",  note: "remembers your last move" },
  { name: "THREDLE",  type: "PROC",  note: "spawns more of itself" },
  { name: "ZYBORG",   type: "PROC",  note: "won't stay dead" },
  { name: "PIDGON",   type: "PROC",  note: "carries a process ID" },
  { name: "SIGNAUR",  type: "PROC",  note: "sends signals on contact" },
  { name: "NICEKIT",  type: "PROC",  note: "lowers its priority" },
  { name: "SCHEDOG",  type: "PROC",  note: "takes turns" },
  { name: "ARMOTE",   type: "CORE",  note: "low power, long stamina" },
  { name: "RISKIT",   type: "CORE",  note: "reduced instruction set" },
  { name: "CISCOTL",  type: "CORE",  note: "every instruction in one body" },
  { name: "PIPELYNX", type: "CORE",  note: "moves in stages" },
  { name: "CYCLOOM",  type: "CORE",  note: "the loom of cycles" },
  { name: "NANDORE",  type: "LOGIC", note: "negates everything" },
  { name: "NORWEN",   type: "LOGIC", note: "either way, no" },
  { name: "XORHARE",  type: "LOGIC", note: "one or the other" },
  { name: "ANDOWL",   type: "LOGIC", note: "needs both" },
  { name: "BOOLEM",   type: "LOGIC", note: "true or false" },
  { name: "IFFROG",   type: "LOGIC", note: "leaps when condition met" },
  { name: "ELSEEL",   type: "LOGIC", note: "always the other path" },
  { name: "SWITCRAB", type: "LOGIC", note: "many cases, one shell" },
  { name: "JSONIA",   type: "DATA",  note: "wrapped in braces" },
  { name: "CSVOLE",   type: "DATA",  note: "rows of teeth, comma-spaced" },
  { name: "YAMOLE",   type: "DATA",  note: "indented mole" },
  { name: "TOMLT",    type: "DATA",  note: "table of contents" },
  { name: "INTGAR",   type: "DATA",  note: "rounded down, never up" },
  { name: "FLOATFIN", type: "DATA",  note: "drifts on decimals" },
  { name: "STRTERM",  type: "DATA",  note: "ends in null" },
  { name: "BOOLBIRD", type: "DATA",  note: "either bit" },
  { name: "STACKAT",  type: "MEM",   note: "last in, first out" },
  { name: "HEAPYR",   type: "MEM",   note: "grows from below" },
  { name: "MALLOCK",  type: "MEM",   note: "claims a region" },
  { name: "FREEDA",   type: "MEM",   note: "lets go cleanly" },
  { name: "PAGYL",    type: "MEM",   note: "swaps in and out" },
  { name: "CACHEY",   type: "MEM",   note: "holds the recent" },
  { name: "BUFFROG",  type: "MEM",   note: "queues up the rest" },
  { name: "LINKAR",   type: "DATA",  note: "next pointer in tow" },
  { name: "NODILLO",  type: "DATA",  note: "armored at every hop" },
  { name: "TREEKIN",  type: "DATA",  note: "branches grow on call" },
  { name: "GRAFTLE",  type: "DATA",  note: "merges two lineages" },
  { name: "HASHARE",  type: "DATA",  note: "hops to its own bucket" },
  { name: "QUEUL",    type: "MEM",   note: "first in, first out" },
  { name: "DEQUEEL",  type: "MEM",   note: "two-headed, both ways" },
  { name: "SETTER",   type: "DATA",  note: "no doubles, no order" },
  { name: "ITERATX",  type: "PROC",  note: "yields one at a time" },
  { name: "PARSEY",   type: "DATA",  note: "breaks input into tokens" },
];

const id = "EVENT_CC_DEX_ENTRY";
const name = "Cinder: show dex entry";
const groups = ["EVENT_GROUP_DIALOGUE"];
const subGroups = {
  EVENT_GROUP_DIALOGUE: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: dex entry from ${fetchArg("variable")}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable holding creature ID (1-56)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "showFlavor",
    label: "Show flavor text on second screen",
    type: "checkbox",
    defaultValue: true,
  },
];

const pad = (n) => (n < 10 ? `0${n}` : `${n}`);

const compile = (input, helpers) => {
  const { caseVariableConstValue } = helpers;
  const showFlavor = input.showFlavor !== false;

  const cases = SPECIES.map((sp, i) => {
    const num = i + 1;
    const header = `#${pad(num)} ${sp.name}\nTYPE: ${sp.type}`;
    const branch = [{ command: "EVENT_TEXT", args: { text: header } }];
    if (showFlavor) {
      branch.push({ command: "EVENT_TEXT", args: { text: sp.note } });
    }
    return { value: { type: "number", value: num }, branch };
  });

  const elseBranch = [
    { command: "EVENT_TEXT", args: { text: "#?? UNKNOWN\nNo data on file." } },
  ];

  caseVariableConstValue(input.variable, cases, elseBranch);
};

module.exports = {
  id,
  name,
  description:
    "Cinder Creatures: show a Pokedex-style entry (number + name + type, optional flavor text) from a creature ID variable.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
