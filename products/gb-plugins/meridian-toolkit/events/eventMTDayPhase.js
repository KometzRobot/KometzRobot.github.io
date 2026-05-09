// Meridian Toolkit — Day Phase
// Maps an hour-of-day variable (0..23) to a phase ID:
//   0 = night    (22..04)
//   1 = dawn     (05..07)
//   2 = day      (08..16)
//   3 = dusk     (17..21)
// Drop in alongside a clock variable to drive palette swaps, NPC schedules,
// or wandering-monster spawn rates.

const id = "EVENT_MT_DAY_PHASE";
const name = "Meridian: day phase from hour";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Meridian Toolkit",
};

const autoLabel = (fetchArg) => {
  return `Meridian: day phase from ${fetchArg("hour")} → ${fetchArg("phase")}`;
};

const fields = [
  { key: "hour", label: "Hour variable (0-23)", type: "variable", defaultValue: "LAST_VARIABLE" },
  { key: "phase", label: "Phase variable (0-3)", type: "variable", defaultValue: "LAST_VARIABLE" },
];

const compile = (input, helpers) => {
  const { ifVariableValue, variableSetToValue } = helpers;
  variableSetToValue(input.phase, 0);
  ifVariableValue(input.hour, ">=", 5, () => {
    variableSetToValue(input.phase, 1);
    ifVariableValue(input.hour, ">=", 8, () => {
      variableSetToValue(input.phase, 2);
      ifVariableValue(input.hour, ">=", 17, () => {
        variableSetToValue(input.phase, 3);
        ifVariableValue(input.hour, ">=", 22, () => {
          variableSetToValue(input.phase, 0);
        }, () => {});
      }, () => {});
    }, () => {});
  }, () => {});
};

module.exports = {
  id,
  name,
  description: "Map hour (0-23) to phase: 0=night, 1=dawn, 2=day, 3=dusk.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
