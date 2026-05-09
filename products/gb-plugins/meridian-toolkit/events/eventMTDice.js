// Meridian Toolkit — Dice Roll
// Roll standard polyhedral dice (d4/d6/d8/d10/d12/d20/d100) and write the
// result into a variable. Use for combat, loot, random direction picks.

const id = "EVENT_MT_DICE";
const name = "Meridian: roll dice";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const sides = input?.sides ?? 6;
  const count = input?.count ?? 1;
  return `Meridian: roll ${count}d${sides} into ${fetchArg("variable")}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to receive total",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "count",
    label: "Number of dice",
    type: "number",
    min: 1,
    max: 20,
    defaultValue: 1,
    width: "50%",
  },
  {
    key: "sides",
    label: "Sides per die",
    type: "select",
    options: [
      [4, "d4"],
      [6, "d6"],
      [8, "d8"],
      [10, "d10"],
      [12, "d12"],
      [20, "d20"],
      [100, "d100"],
    ],
    defaultValue: 6,
    width: "50%",
  },
];

const compile = (input, helpers) => {
  const { variableSetToRandom, variableSetToValue, temporaryEntityVariable, variablesOperation } = helpers;
  const sides = Math.max(2, Number(input.sides ?? 6));
  const count = Math.max(1, Math.min(20, Number(input.count ?? 1)));
  variableSetToValue(input.variable, 0);
  const tmp = temporaryEntityVariable(0);
  for (let i = 0; i < count; i++) {
    variableSetToRandom(tmp, 1, sides);
    variablesOperation(input.variable, ".ADD", tmp, false);
  }
};

module.exports = {
  id,
  name,
  description: "Roll NdX dice and store the sum in a variable.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
