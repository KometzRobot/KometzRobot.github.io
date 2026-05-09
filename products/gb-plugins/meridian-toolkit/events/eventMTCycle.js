// Meridian Toolkit — Variable Cycle
// Increments a variable by `step`. If it goes above `max`, wraps to `min`.
// If it goes below `min` (negative step), wraps to `max`. Use for menu
// indexes, NPC dialogue rotations, idle-animation frames.

const id = "EVENT_MT_CYCLE";
const name = "Meridian: cycle variable";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const step = input?.step ?? 1;
  const min = input?.min ?? 0;
  const max = input?.max ?? 3;
  return `Meridian: cycle ${fetchArg("variable")} +${step} [${min}..${max}]`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to cycle",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "step",
    label: "Step (use -1 to count down)",
    type: "number",
    min: -100,
    max: 100,
    defaultValue: 1,
    width: "33%",
  },
  {
    key: "min",
    label: "Min",
    type: "number",
    min: 0,
    max: 65535,
    defaultValue: 0,
    width: "33%",
  },
  {
    key: "max",
    label: "Max",
    type: "number",
    min: 0,
    max: 65535,
    defaultValue: 3,
    width: "34%",
  },
];

const compile = (input, helpers) => {
  const { variablesOperation, ifVariableValue, variableSetToValue } = helpers;
  const step = Number(input.step ?? 1);
  const min = Number(input.min ?? 0);
  const max = Number(input.max ?? 3);
  if (step >= 0) {
    variablesOperation(input.variable, ".ADD", Math.abs(step), true);
    ifVariableValue(input.variable, ">", max, () => {
      variableSetToValue(input.variable, min);
    }, () => {});
  } else {
    ifVariableValue(input.variable, "<=", min, () => {
      variableSetToValue(input.variable, max);
    }, () => {
      variablesOperation(input.variable, ".SUB", Math.abs(step), true);
    });
  }
};

module.exports = {
  id,
  name,
  description: "Increment/decrement a variable, wrapping at min/max bounds.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
