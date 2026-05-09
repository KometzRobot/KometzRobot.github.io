// Meridian Toolkit — Random Direction
// Picks a random cardinal direction (up/down/left/right) and writes the
// direction code into a variable: 0=up, 1=down, 2=left, 3=right. Compatible
// with GB Studio's standard direction encoding. Use for wandering NPCs,
// random spawn facing, scatter effects.

const id = "EVENT_MT_RANDOM_DIR";
const name = "Meridian: random direction";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const mode = input?.mode ?? "4";
  return `Meridian: random ${mode}-way direction into ${fetchArg("variable")}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to receive direction (0-3 or 0-7)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "mode",
    label: "Direction mode",
    type: "select",
    options: [
      ["4", "4-way (cardinals only)"],
      ["8", "8-way (with diagonals)"],
    ],
    defaultValue: "4",
  },
];

const compile = (input, helpers) => {
  const { variableSetToRandom } = helpers;
  const sides = String(input.mode ?? "4") === "8" ? 8 : 4;
  variableSetToRandom(input.variable, 0, sides);
};

module.exports = {
  id,
  name,
  description: "Pick a random cardinal (or 8-way) direction into a variable.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
