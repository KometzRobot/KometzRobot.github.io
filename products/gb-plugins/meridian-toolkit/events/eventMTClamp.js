// Meridian Toolkit — Clamp Variable
// Constrains a variable to [min..max]. Useful for HP bars, stat caps, scroll
// positions — any time a variable shouldn't drift outside known bounds.

const id = "EVENT_MT_CLAMP";
const name = "Meridian: clamp variable";
const groups = ["EVENT_GROUP_VARIABLES", "EVENT_GROUP_MATH"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Meridian Toolkit",
  EVENT_GROUP_MATH: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const lo = input?.min ?? 0;
  const hi = input?.max ?? 100;
  return `Meridian: clamp ${fetchArg("variable")} to ${lo}..${hi}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to clamp",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "min",
    label: "Minimum",
    type: "number",
    min: 0,
    max: 65535,
    defaultValue: 0,
    width: "50%",
  },
  {
    key: "max",
    label: "Maximum",
    type: "number",
    min: 0,
    max: 65535,
    defaultValue: 100,
    width: "50%",
  },
];

const compile = (input, helpers) => {
  const { ifVariableValue, variableSetToValue } = helpers;
  const lo = Number(input.min ?? 0);
  const hi = Number(input.max ?? 100);
  ifVariableValue(input.variable, "<", lo, () => {
    variableSetToValue(input.variable, lo);
  }, () => {});
  ifVariableValue(input.variable, ">", hi, () => {
    variableSetToValue(input.variable, hi);
  }, () => {});
};

module.exports = {
  id,
  name,
  description: "Clamp a variable into [min..max].",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
