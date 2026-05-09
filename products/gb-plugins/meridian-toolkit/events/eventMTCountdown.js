// Meridian Toolkit — Countdown Timer
// Decrements a variable by 1 each frame for `frames` frames (60 = 1 second
// at GBC speed) until the variable hits 0 OR the duration elapses. Stops
// early if the variable already reached 0. Use for fight timers, charging
// attacks, hold-button-to-skip prompts.

const id = "EVENT_MT_COUNTDOWN";
const name = "Meridian: countdown wait";
const groups = ["EVENT_GROUP_TIMER"];
const subGroups = {
  EVENT_GROUP_TIMER: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const start = input?.start ?? 60;
  return `Meridian: countdown ${fetchArg("variable")} from ${start}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to decrement (0 = done)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "start",
    label: "Starting value",
    type: "number",
    min: 1,
    max: 65535,
    defaultValue: 60,
  },
  {
    key: "frames_per_tick",
    label: "Frames per decrement",
    type: "number",
    min: 1,
    max: 600,
    defaultValue: 1,
  },
];

const compile = (input, helpers) => {
  const { variableSetToValue, variablesOperation, wait, ifVariableValue, temporaryEntityVariable } = helpers;
  const start = Math.max(1, Number(input.start ?? 60));
  const fpt = Math.max(1, Number(input.frames_per_tick ?? 1));
  variableSetToValue(input.variable, start);
  for (let i = 0; i < start; i++) {
    ifVariableValue(input.variable, ">", 0, () => {
      wait(fpt);
      variablesOperation(input.variable, ".SUB", 1, true);
    }, () => {});
  }
};

module.exports = {
  id,
  name,
  description: "Set variable to N then count down each frame until 0.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
