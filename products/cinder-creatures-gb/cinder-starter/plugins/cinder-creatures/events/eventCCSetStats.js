// Cinder Creatures — Set Creature Stats
// Reads a creature ID variable (1..56) and writes HP / ATK / DEF
// values into three target variables for use in a battle scene.

const STATS = [
  { hp: 18, atk: 6,  def: 4 },  // 1  FORKLING
  { hp: 22, atk: 5,  def: 5 },  // 2  DAEMONET
  { hp: 30, atk: 4,  def: 8 },  // 3  KERNITE
  { hp: 16, atk: 9,  def: 3 },  // 4  RECURSE
  { hp: 20, atk: 6,  def: 6 },  // 5  MUTEXEL
  { hp: 12, atk: 4,  def: 2 },  // 6  BYTEFLY
  { hp: 19, atk: 7,  def: 4 },  // 7  SEMAFOX
  { hp: 17, atk: 7,  def: 3 },  // 8  REGEXEL
  { hp: 21, atk: 5,  def: 6 },  // 9  SCOPEWVR
  { hp: 28, atk: 8,  def: 5 },  // 10 ALLOCROC
  { hp: 14, atk: 3,  def: 2 },  // 11 NULLPUP
  { hp: 16, atk: 5,  def: 4 },  // 12 CACHEBIT
  { hp: 17, atk: 6,  def: 3 },  // 13 THREDLE
  { hp: 24, atk: 6,  def: 4 },  // 14 ZYBORG
  { hp: 19, atk: 5,  def: 4 },  // 15 PIDGON
  { hp: 22, atk: 7,  def: 3 },  // 16 SIGNAUR
  { hp: 14, atk: 5,  def: 3 },  // 17 NICEKIT
  { hp: 20, atk: 6,  def: 5 },  // 18 SCHEDOG
  { hp: 28, atk: 5,  def: 7 },  // 19 ARMOTE
  { hp: 25, atk: 5,  def: 7 },  // 20 RISKIT
  { hp: 32, atk: 4,  def: 9 },  // 21 CISCOTL
  { hp: 26, atk: 6,  def: 6 },  // 22 PIPELYNX
  { hp: 30, atk: 5,  def: 8 },  // 23 CYCLOOM
  { hp: 18, atk: 8,  def: 4 },  // 24 NANDORE
  { hp: 17, atk: 7,  def: 5 },  // 25 NORWEN
  { hp: 16, atk: 9,  def: 3 },  // 26 XORHARE
  { hp: 19, atk: 6,  def: 5 },  // 27 ANDOWL
  { hp: 18, atk: 7,  def: 4 },  // 28 BOOLEM
  { hp: 17, atk: 6,  def: 4 },  // 29 IFFROG
  { hp: 19, atk: 7,  def: 3 },  // 30 ELSEEL
  { hp: 21, atk: 6,  def: 5 },  // 31 SWITCRAB
  { hp: 14, atk: 5,  def: 3 },  // 32 JSONIA
  { hp: 13, atk: 4,  def: 2 },  // 33 CSVOLE
  { hp: 15, atk: 4,  def: 3 },  // 34 YAMOLE
  { hp: 14, atk: 5,  def: 3 },  // 35 TOMLT
  { hp: 18, atk: 5,  def: 4 },  // 36 INTGAR
  { hp: 13, atk: 6,  def: 2 },  // 37 FLOATFIN
  { hp: 16, atk: 5,  def: 3 },  // 38 STRTERM
  { hp: 12, atk: 4,  def: 2 },  // 39 BOOLBIRD
  { hp: 22, atk: 5,  def: 6 },  // 40 STACKAT
  { hp: 27, atk: 4,  def: 8 },  // 41 HEAPYR
  { hp: 24, atk: 7,  def: 5 },  // 42 MALLOCK
  { hp: 18, atk: 5,  def: 4 },  // 43 FREEDA
  { hp: 20, atk: 4,  def: 6 },  // 44 PAGYL
  { hp: 19, atk: 5,  def: 5 },  // 45 CACHEY
  { hp: 22, atk: 5,  def: 6 },  // 46 BUFFROG
  { hp: 15, atk: 6,  def: 3 },  // 47 LINKAR
  { hp: 18, atk: 5,  def: 5 },  // 48 NODILLO
  { hp: 17, atk: 6,  def: 4 },  // 49 TREEKIN
  { hp: 19, atk: 5,  def: 5 },  // 50 GRAFTLE
  { hp: 14, atk: 8,  def: 2 },  // 51 HASHARE
  { hp: 18, atk: 5,  def: 5 },  // 52 QUEUL
  { hp: 19, atk: 5,  def: 5 },  // 53 DEQUEEL
  { hp: 16, atk: 6,  def: 4 },  // 54 SETTER
  { hp: 17, atk: 7,  def: 4 },  // 55 ITERATX
  { hp: 18, atk: 7,  def: 3 },  // 56 PARSEY
];

const id = "EVENT_CC_SET_STATS";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: set stats from ${fetchArg("idVar")}`;
};

const fields = [
  {
    key: "idVar",
    label: "Creature ID variable (1-56)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "hpVar",
    label: "Target variable: HP",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "atkVar",
    label: "Target variable: ATK",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "defVar",
    label: "Target variable: DEF",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
];

const compile = (input, helpers) => {
  const { caseVariableConstValue } = helpers;

  const setVarEvent = (variableId, value) => ({
    command: "EVENT_SET_VALUE",
    args: {
      variable: variableId,
      value: { type: "number", value },
    },
  });

  const cases = STATS.map((s, i) => ({
    value: { type: "number", value: i + 1 },
    branch: [
      setVarEvent(input.hpVar, s.hp),
      setVarEvent(input.atkVar, s.atk),
      setVarEvent(input.defVar, s.def),
    ],
  }));

  const elseBranch = [
    setVarEvent(input.hpVar, 1),
    setVarEvent(input.atkVar, 1),
    setVarEvent(input.defVar, 1),
  ];

  caseVariableConstValue(input.idVar, cases, elseBranch);
};

module.exports = {
  id,
  description:
    "Cinder Creatures: set HP/ATK/DEF variables from a creature ID (1..56).",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
