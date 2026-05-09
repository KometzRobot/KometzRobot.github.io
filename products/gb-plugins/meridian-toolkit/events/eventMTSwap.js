// Meridian Toolkit — Variable Swap
// Swap the values of two variables. Without a helper this needs a temp var
// and three set-statements every time. One drop-in node here.

const id = "EVENT_MT_SWAP";
const name = "Meridian: swap variables";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Meridian Toolkit",
};

const autoLabel = (fetchArg) => {
  return `Meridian: swap ${fetchArg("a")} <-> ${fetchArg("b")}`;
};

const fields = [
  {
    key: "a",
    label: "Variable A",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
    width: "50%",
  },
  {
    key: "b",
    label: "Variable B",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
    width: "50%",
  },
];

const compile = (input, helpers) => {
  const { variableCopy, temporaryEntityVariable } = helpers;
  const tmp = temporaryEntityVariable(0);
  variableCopy(tmp, input.a);
  variableCopy(input.a, input.b);
  variableCopy(input.b, tmp);
};

module.exports = {
  id,
  name,
  description: "Swap the values of two variables in one step.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
