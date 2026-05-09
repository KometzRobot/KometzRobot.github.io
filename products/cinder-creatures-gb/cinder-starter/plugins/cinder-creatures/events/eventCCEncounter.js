// Cinder Creatures - One-shot encounter
// Picks a random creature ID + immediately shows "A wild XXXX appeared!"
// Equivalent to running random encounter + show name back-to-back.

const SPECIES = [
  "FORKLING", "DAEMONET", "KERNITE",  "RECURSE",
  "MUTEXEL",  "BYTEFLY",  "SEMAFOX",  "REGEXEL",
  "SCOPEWVR", "ALLOCROC", "NULLPUP",  "CACHEBIT",
  "THREDLE",  "ZYBORG",   "PIDGON",   "SIGNAUR",
  "NICEKIT",  "SCHEDOG",  "ARMOTE",   "RISKIT",
  "CISCOTL",  "PIPELYNX", "CYCLOOM",  "NANDORE",
  "NORWEN",   "XORHARE",  "ANDOWL",   "BOOLEM",
  "IFFROG",   "ELSEEL",   "SWITCRAB", "JSONIA",
  "CSVOLE",   "YAMOLE",   "TOMLT",    "INTGAR",
  "FLOATFIN", "STRTERM",  "BOOLBIRD", "STACKAT",
  "HEAPYR",   "MALLOCK",  "FREEDA",   "PAGYL",
  "CACHEY",   "BUFFROG",  "LINKAR",   "NODILLO",
  "TREEKIN",  "GRAFTLE",  "HASHARE",  "QUEUL",
  "DEQUEEL",  "SETTER",   "ITERATX",  "PARSEY",
];

const id = "EVENT_CC_ENCOUNTER";
const groups = ["EVENT_GROUP_DIALOGUE"];
const subGroups = {
  EVENT_GROUP_DIALOGUE: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: encounter ${fetchArg("min")}..${fetchArg("max")} -> ${fetchArg("variable")}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to receive creature ID",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "min",
    label: "Min ID (1-56)",
    type: "number",
    min: 1, max: 56, defaultValue: 1,
    width: "50%",
  },
  {
    key: "max",
    label: "Max ID (1-56)",
    type: "number",
    min: 1, max: 56, defaultValue: 12,
    width: "50%",
  },
  {
    key: "prefix",
    label: "Prefix",
    type: "text",
    defaultValue: "A wild ",
  },
  {
    key: "suffix",
    label: "Suffix",
    type: "text",
    defaultValue: " appeared!",
  },
];

const compile = (input, helpers) => {
  const { variableSetToRandom, caseVariableConstValue } = helpers;
  const lo = Math.max(1, Math.min(56, Number(input.min ?? 1)));
  const hi = Math.max(lo, Math.min(56, Number(input.max ?? 12)));
  const range = hi - lo + 1;

  variableSetToRandom(input.variable, lo, range);

  const prefix = input.prefix ?? "";
  const suffix = input.suffix ?? "";
  const cases = SPECIES.slice(lo - 1, hi).map((name, idx) => ({
    value: { type: "number", value: lo + idx },
    branch: [
      { command: "EVENT_TEXT", args: { text: `${prefix}${name}${suffix}` } },
    ],
  }));
  const elseBranch = [
    { command: "EVENT_TEXT", args: { text: `${prefix}???${suffix}` } },
  ];
  caseVariableConstValue(input.variable, cases, elseBranch);
};

module.exports = {
  id,
  description: "Cinder Creatures: roll a random encounter and show the creature name in one step.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
