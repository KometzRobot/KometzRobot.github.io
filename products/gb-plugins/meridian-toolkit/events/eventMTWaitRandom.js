// Meridian Toolkit — Wait Random
// Wait a random number of frames between min and max. Use for NPC idle
// animations, randomized dialogue beats, varied enemy attack timing.
// 60 frames = ~1 second on GBC.

const id = "EVENT_MT_WAIT_RANDOM";
const name = "Meridian: wait random";
const groups = ["EVENT_GROUP_TIMER"];
const subGroups = {
  EVENT_GROUP_TIMER: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const min = input?.min ?? 30;
  const max = input?.max ?? 120;
  return `Meridian: wait random ${min}-${max} frames`;
};

const fields = [
  {
    key: "min",
    label: "Min frames",
    type: "number",
    min: 1,
    max: 600,
    defaultValue: 30,
    width: "50%",
  },
  {
    key: "max",
    label: "Max frames",
    type: "number",
    min: 1,
    max: 600,
    defaultValue: 120,
    width: "50%",
  },
];

const compile = (input, helpers) => {
  const { variableSetToRandom, wait, temporaryEntityVariable, ifVariableValue } = helpers;
  const minF = Math.max(1, Number(input.min ?? 30));
  const maxF = Math.max(minF, Number(input.max ?? 120));
  const range = maxF - minF + 1;
  const tmp = temporaryEntityVariable(0);
  variableSetToRandom(tmp, minF, range);
  for (let f = minF; f <= maxF; f++) {
    ifVariableValue(tmp, "==", f, () => { wait(f); }, () => {});
  }
};

module.exports = {
  id,
  name,
  description: "Wait a random number of frames within [min..max].",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
