// Cinder Creatures - Heal Party
// Restores HP variable for each provided party-member HP variable up to its max.
// Use after visiting a "Cinder Center" tile.

const id = "EVENT_CC_HEAL_PARTY";
const name = "Cinder: heal party";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: heal party (set HPs to max)`;
};

const fields = [
  { key: "hp1", label: "Slot 1 HP var", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "max1", label: "Slot 1 max HP var", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "hp2", label: "Slot 2 HP var", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "max2", label: "Slot 2 max HP var", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "hp3", label: "Slot 3 HP var", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "max3", label: "Slot 3 max HP var", type: "variable", defaultValue: "LAST_VARIABLE" },
];

const compile = (input, helpers) => {
  const { variableCopy } = helpers;
  variableCopy(input.hp1, input.max1);
  variableCopy(input.hp2, input.max2);
  variableCopy(input.hp3, input.max3);
};

module.exports = { id,
  name, groups, subGroups, autoLabel, fields, compile };
