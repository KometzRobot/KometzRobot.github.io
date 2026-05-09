// Meridian Toolkit — Manhattan Distance
// Computes |ax-bx| + |ay-by| between two coordinate pairs and stores in a
// variable. Cheap proxy for "is the player near X" checks without needing
// sqrt. Use for trigger zones, AI sight lines, sound proximity.

const id = "EVENT_MT_DISTANCE";
const name = "Meridian: manhattan distance";
const groups = ["EVENT_GROUP_VARIABLES", "EVENT_GROUP_MATH"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Meridian Toolkit",
  EVENT_GROUP_MATH: "Meridian Toolkit",
};

const autoLabel = (fetchArg) => {
  return `Meridian: distance (${fetchArg("ax")},${fetchArg("ay")})↔(${fetchArg("bx")},${fetchArg("by")}) → ${fetchArg("out")}`;
};

const fields = [
  { key: "out", label: "Variable to receive distance", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "ax", label: "A: X", type: "variable", defaultValue: "LAST_VARIABLE", width: "50%" },
  { key: "ay", label: "A: Y", type: "variable", defaultValue: "LAST_VARIABLE", width: "50%" },
  { key: "bx", label: "B: X", type: "variable", defaultValue: "LAST_VARIABLE", width: "50%" },
  { key: "by", label: "B: Y", type: "variable", defaultValue: "LAST_VARIABLE", width: "50%" },
];

const compile = (input, helpers) => {
  const { variableCopy, variablesOperation, ifVariableCompare, variableSetToValue, temporaryEntityVariable } = helpers;
  const dx = temporaryEntityVariable(0);
  const dy = temporaryEntityVariable(1);
  const zero = temporaryEntityVariable(2);
  variableSetToValue(zero, 0);

  variableCopy(dx, input.ax);
  variablesOperation(dx, ".SUB", input.bx, false);
  ifVariableCompare(dx, "<", zero, () => {
    variablesOperation(dx, ".MUL", -1, true);
  }, () => {});

  variableCopy(dy, input.ay);
  variablesOperation(dy, ".SUB", input.by, false);
  ifVariableCompare(dy, "<", zero, () => {
    variablesOperation(dy, ".MUL", -1, true);
  }, () => {});

  variableCopy(input.out, dx);
  variablesOperation(input.out, ".ADD", dy, false);
};

module.exports = {
  id,
  name,
  description: "Manhattan distance |ax-bx|+|ay-by| stored in a variable.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
