// Meridian Toolkit — Weighted Pick
// Picks one of four outcomes (1-4) based on configurable weights. Outcome ID
// lands in the chosen variable. Use for loot tables, encounter rates, NPC
// mood selection — any time you want non-uniform random.

const id = "EVENT_MT_WEIGHTED_PICK";
const name = "Meridian: weighted pick";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const w = [input?.w1 ?? 1, input?.w2 ?? 1, input?.w3 ?? 1, input?.w4 ?? 1];
  return `Meridian: weighted pick (${w.join(":")}) into ${fetchArg("variable")}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to receive outcome (1-4)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  { key: "w1", label: "Weight outcome 1", type: "number", min: 0, max: 100, defaultValue: 1, width: "50%" },
  { key: "w2", label: "Weight outcome 2", type: "number", min: 0, max: 100, defaultValue: 1, width: "50%" },
  { key: "w3", label: "Weight outcome 3", type: "number", min: 0, max: 100, defaultValue: 1, width: "50%" },
  { key: "w4", label: "Weight outcome 4", type: "number", min: 0, max: 100, defaultValue: 1, width: "50%" },
];

const compile = (input, helpers) => {
  const { variableSetToRandom, variableSetToValue, ifVariableValue, temporaryEntityVariable } = helpers;
  const w1 = Math.max(0, Number(input.w1 ?? 1));
  const w2 = Math.max(0, Number(input.w2 ?? 1));
  const w3 = Math.max(0, Number(input.w3 ?? 1));
  const w4 = Math.max(0, Number(input.w4 ?? 1));
  const total = Math.max(1, w1 + w2 + w3 + w4);
  const t1 = w1;
  const t2 = w1 + w2;
  const t3 = w1 + w2 + w3;
  const tmp = temporaryEntityVariable(0);
  variableSetToRandom(tmp, 1, total);
  variableSetToValue(input.variable, 4);
  ifVariableValue(tmp, "<=", t3, () => { variableSetToValue(input.variable, 3); }, () => {});
  ifVariableValue(tmp, "<=", t2, () => { variableSetToValue(input.variable, 2); }, () => {});
  ifVariableValue(tmp, "<=", t1, () => { variableSetToValue(input.variable, 1); }, () => {});
};

module.exports = {
  id,
  name,
  description: "Pick one of four outcomes (1-4) using configurable weights.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
