// Cinder Creatures - Capture Roll
// Rolls a capture chance based on current foe HP and a base capture rate.
// Formula: chance = baseRate + (maxHp - currHp) * 2  (clamped 1..255)
// Sets caught=1 if rnd(0..255) < chance, else 0.

const id = "EVENT_CC_CAPTURE_ROLL";
const name = "Cinder: capture roll";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: capture roll baseRate=${fetchArg("baseRate")} curr=${fetchArg("currHp")} max=${fetchArg("maxHp")} -> ${fetchArg("caught")}`;
};

const fields = [
  { key: "baseRate", label: "Base capture rate (0..255)", type: "number", defaultValue: 30, min: 0, max: 255 },
  { key: "currHp", label: "Foe current HP variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "maxHp", label: "Foe max HP variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "caught", label: "Caught flag (out)", type: "variable", defaultValue: "LAST_VARIABLE" },
];

const compile = (input, helpers) => {
  const { variableSetToValue, variableSetToVariable, variableMath, variableRandom, ifVariableValue, temporaryEntityVariable } = helpers;
  const tmpChance = temporaryEntityVariable ? temporaryEntityVariable(0) : input.caught;
  const tmpRoll = temporaryEntityVariable ? temporaryEntityVariable(1) : input.caught;
  // chance = (maxHp - currHp) * 2 + baseRate
  variableSetToVariable(tmpChance, input.maxHp);
  variableMath(tmpChance, "-", input.currHp);
  variableMath(tmpChance, "*", 2);
  variableMath(tmpChance, "+", input.baseRate);
  // roll 0..255
  variableRandom(tmpRoll, 0, 255);
  variableSetToValue(input.caught, 0);
  ifVariableValue(tmpRoll, "<", tmpChance, () => {
    variableSetToValue(input.caught, 1);
  });
};

module.exports = { id,
  name, groups, subGroups, autoLabel, fields, compile };
