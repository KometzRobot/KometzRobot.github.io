// Cinder Creatures — Player Name Entry
// Wraps GB Studio's built-in EVENT_TEXT_INPUT into the Cinder Creatures group.
// Player types their name into a 7-char variable (Pokemon-RBY length).
// On Cinder USB, the companion app pre-seeds VAR_PLAYER_NAME from the user
// profile before the ROM boots, so most players just press START to confirm.

const id = "EVENT_CC_NAME_ENTRY";
const name = "Cinder: player name entry";
const groups = ["EVENT_GROUP_INPUT"];
const subGroups = {
  EVENT_GROUP_INPUT: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: name entry -> ${fetchArg("variable")} (max ${fetchArg("maxLength")})`;
};

const fields = [
  {
    key: "variable",
    label: "Variable to store name (string)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "maxLength",
    label: "Max length",
    type: "number",
    min: 1,
    max: 16,
    defaultValue: 7,
  },
  {
    key: "prompt",
    label: "Prompt text",
    type: "text",
    defaultValue: "WHAT IS\\nYOUR NAME?",
  },
];

const compile = (input, helpers) => {
  const { textDialogue, variableSetToString, textInput } = helpers;
  const prompt = input.prompt ?? "WHAT IS\\nYOUR NAME?";
  const maxLen = Math.max(1, Math.min(16, parseInt(input.maxLength, 10) || 7));

  // Show the prompt, then collect input into the chosen variable.
  textDialogue(prompt);
  if (typeof textInput === "function") {
    textInput(input.variable, maxLen);
  } else {
    // Fallback for older GBS: emit the raw text-input command.
    helpers._addCmd("EVENT_TEXT_INPUT", {
      text: prompt,
      variable: input.variable,
      maxLength: maxLen,
    });
  }
};

module.exports = {
  id,
  name,
  description:
    "Cinder Creatures: prompt for the player's name and store it in a variable. " +
    "On Cinder USB, the companion app pre-seeds the variable so START confirms instantly.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
