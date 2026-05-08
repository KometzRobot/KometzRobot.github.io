// Cinder Creatures — Random Encounter
// Picks a random creature ID (1..12) and stores it in the chosen variable.

const id = "EVENT_CC_RANDOM_ENCOUNTER";
const groups = ["EVENT_GROUP_CINDER_CREATURES"];

const autoLabel = (fetchArg) => {
  return `Cinder: random encounter into ${fetchArg("variable")}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to receive creature ID (1-12)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
];

const compile = (input, helpers) => {
  const { variableSetToScriptValue } = helpers;
  variableSetToScriptValue(input.variable, {
    type: "rnd",
    min: { type: "number", value: 1 },
    max: { type: "number", value: 12 },
  });
};

module.exports = {
  id,
  description:
    "Cinder Creatures: pick a random creature ID (1..12) and store it.",
  autoLabel,
  groups,
  fields,
  compile,
};
