// Cinder Creatures - Random Encounter
// Picks a random creature ID in [min..max] and stores it in the chosen variable.
// Default range 1..12 (the named starter pool); raise max to 56 for the full roster.

const id = "EVENT_CC_RANDOM_ENCOUNTER";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: random encounter ${fetchArg("min")}..${fetchArg("max")} into ${fetchArg("variable")}`;
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
    label: "Min creature ID (1-56)",
    type: "number",
    min: 1,
    max: 56,
    defaultValue: 1,
  },
  {
    key: "max",
    label: "Max creature ID (1-56)",
    type: "number",
    min: 1,
    max: 56,
    defaultValue: 12,
  },
];

const compile = (input, helpers) => {
  const { variableSetToRandom } = helpers;
  const lo = Math.max(1,  Math.min(56, Number(input.min ?? 1)));
  const hi = Math.max(lo, Math.min(56, Number(input.max ?? 12)));
  const range = hi - lo + 1;
  variableSetToRandom(input.variable, lo, range);
};

module.exports = {
  id,
  description: "Cinder Creatures: pick a random creature ID in [min..max] and store it.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
