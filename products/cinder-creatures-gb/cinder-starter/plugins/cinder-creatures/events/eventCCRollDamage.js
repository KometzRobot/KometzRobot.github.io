// Cinder Creatures — Roll Damage
// Picks a random damage value in [min..max] and writes it to a variable.
// Designed for quick combat prototyping without a full formula yet.

const id = "EVENT_CC_ROLL_DAMAGE";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Cinder Creatures",
};

const autoLabel = (fetchArg, input) => {
  const min = input?.min ?? 1;
  const max = input?.max ?? 6;
  return `Cinder: roll ${min}..${max} damage into ${fetchArg("dmgVar")}`;
};

const fields = [
  {
    key: "dmgVar",
    label: "Variable to receive damage",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "min",
    label: "Min damage",
    type: "number",
    min: 0,
    max: 255,
    defaultValue: 1,
    width: "50%",
  },
  {
    key: "max",
    label: "Max damage",
    type: "number",
    min: 0,
    max: 255,
    defaultValue: 6,
    width: "50%",
  },
];

const compile = (input, helpers) => {
  const { variableSetToRandom } = helpers;
  const min = typeof input.min === "number" ? input.min : 1;
  const max = typeof input.max === "number" ? input.max : 6;
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  const range = hi - lo + 1;
  variableSetToRandom(input.dmgVar, lo, range);
};

module.exports = {
  id,
  description:
    "Cinder Creatures: roll a random damage value into a variable (min..max).",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
