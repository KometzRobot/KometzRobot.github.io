// Meridian Toolkit — Debug Banner
// Pops a debug dialogue showing a label + variable value, then waits for a
// button press. Strip these out of release builds — they're for "why is this
// not what I expected" moments during development.

const id = "EVENT_MT_DEBUG_BANNER";
const name = "Meridian: debug banner (var)";
const groups = ["EVENT_GROUP_DIALOGUE"];
const subGroups = {
  EVENT_GROUP_DIALOGUE: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const label = input?.label || "DEBUG";
  return `Meridian: debug "${label}" = ${fetchArg("variable")}`;
};

const fields = [
  {
    key: "label",
    label: "Label (printed before value)",
    type: "text",
    defaultValue: "DEBUG",
  },
  {
    key: "variable",
    label: "Variable to show",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
];

const compile = (input, helpers) => {
  const { textDialogue } = helpers;
  const label = (input.label || "DEBUG").slice(0, 16);
  textDialogue(`${label}: $${input.variable}$`);
};

module.exports = {
  id,
  name,
  description: "Show a label + variable value in a dialogue (for debugging).",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
