// Cinder Creatures - Item Give
// Adds N of an item ID to a bag-slot count variable (cap 99).

const id = "EVENT_CC_ITEM_GIVE";
const name = "Cinder: item give";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: give ${fetchArg("amount")} of item -> ${fetchArg("countVar")}`;
};

const fields = [
  { key: "amount", label: "Amount to give", type: "number", defaultValue: 1, min: 1, max: 99 },
  { key: "countVar", label: "Item count variable (in/out)", type: "variable", defaultValue: "LAST_VARIABLE" },
];

const compile = (input, helpers) => {
  const { variableMath, ifVariableValue, variableSetToValue } = helpers;
  variableMath(input.countVar, "+", input.amount);
  ifVariableValue(input.countVar, ">", 99, () => {
    variableSetToValue(input.countVar, 99);
  });
};

module.exports = { id,
  name, groups, subGroups, autoLabel, fields, compile };
