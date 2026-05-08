// Cinder Creatures — Set Creature Stats
// Reads a creature ID variable (1..12) and writes HP / ATK / DEF
// values into three target variables for use in a battle scene.

const STATS = [
  { hp: 18, atk: 6, def: 4 },  // 1 FORKLING
  { hp: 22, atk: 5, def: 5 },  // 2 DAEMONET
  { hp: 30, atk: 4, def: 8 },  // 3 KERNITE
  { hp: 16, atk: 9, def: 3 },  // 4 RECURSE
  { hp: 20, atk: 6, def: 6 },  // 5 MUTEXEL
  { hp: 12, atk: 4, def: 2 },  // 6 BYTEFLY
  { hp: 19, atk: 7, def: 4 },  // 7 SEMAFOX
  { hp: 17, atk: 7, def: 3 },  // 8 REGEXEL
  { hp: 21, atk: 5, def: 6 },  // 9 SCOPEWVR
  { hp: 28, atk: 8, def: 5 },  // 10 ALLOCROC
  { hp: 14, atk: 3, def: 2 },  // 11 NULLPUP
  { hp: 16, atk: 5, def: 4 },  // 12 CACHEBIT
];

const id = "EVENT_CC_SET_STATS";
const groups = ["EVENT_GROUP_CINDER_CREATURES"];

const autoLabel = (fetchArg) => {
  return `Cinder: set stats from ${fetchArg("idVar")}`;
};

const fields = [
  {
    key: "idVar",
    label: "Creature ID variable (1-12)",
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
    "Cinder Creatures: set HP/ATK/DEF variables from a creature ID (1..12).",
  autoLabel,
  groups,
  fields,
  compile,
};
