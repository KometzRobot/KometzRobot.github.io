// Meridian Toolkit — Coin Flip
// Sets a variable to 0 (tails) or 1 (heads) with optional bias toward heads.

const id = "EVENT_MT_COIN_FLIP";
const name = "Meridian: coin flip";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const pct = input?.heads_pct ?? 50;
  return `Meridian: coin flip (${pct}% heads) into ${fetchArg("variable")}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to receive 0/1",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "heads_pct",
    label: "Heads chance (%)",
    type: "number",
    min: 1,
    max: 99,
    defaultValue: 50,
  },
];

const compile = (input, helpers) => {
  const { variableSetToRandom, variableSetToValue, ifVariableValue, temporaryEntityVariable } = helpers;
  const pct = Math.max(1, Math.min(99, Number(input.heads_pct ?? 50)));
  const tmp = temporaryEntityVariable(0);
  variableSetToRandom(tmp, 1, 100);
  variableSetToValue(input.variable, 0);
  ifVariableValue(
    tmp,
    "<=",
    pct,
    () => { variableSetToValue(input.variable, 1); },
    () => {}
  );
};

module.exports = {
  id,
  name,
  description: "Coin flip — variable becomes 0 (tails) or 1 (heads).",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
