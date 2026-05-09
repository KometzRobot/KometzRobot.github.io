// Cinder Creatures - Party Add
// Adds a creature ID to the next empty party slot (slots 1..6).
// Party slot variables are PARTY_1..PARTY_6 by convention; the script
// stops at the first slot that equals 0 (empty).

const id = "EVENT_CC_PARTY_ADD";
const name = "Cinder: party add";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: add ${fetchArg("creatureVar")} to party (slots ${fetchArg("slot1")}..${fetchArg("slot6")})`;
};

const fields = [
  { key: "creatureVar", label: "Creature ID variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "slot1", label: "Party slot 1 variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "slot2", label: "Party slot 2 variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "slot3", label: "Party slot 3 variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "slot4", label: "Party slot 4 variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "slot5", label: "Party slot 5 variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "slot6", label: "Party slot 6 variable", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "addedFlag", label: "Added flag (1 if added, 0 if full)", type: "variable", defaultValue: "LAST_VARIABLE" },
];

const compile = (input, helpers) => {
  const { variableSetToValue, variableCopy, ifVariableValue } = helpers;
  variableSetToValue(input.addedFlag, 0);
  const slots = [input.slot1, input.slot2, input.slot3, input.slot4, input.slot5, input.slot6];
  for (const slot of slots) {
    ifVariableValue(slot, "==", 0, () => {
      ifVariableValue(input.addedFlag, "==", 0, () => {
        variableCopy(slot, input.creatureVar);
        variableSetToValue(input.addedFlag, 1);
      });
    });
  }
};

module.exports = { id,
  name, groups, subGroups, autoLabel, fields, compile };
