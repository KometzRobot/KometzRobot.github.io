// Cinder Creatures - Boss Encounter (CINDER)
// Hardcodes the CINDER boss stats and shows the boss intro line.

const id = "EVENT_CC_BOSS";
const groups = ["EVENT_GROUP_DIALOGUE"];
const subGroups = {
  EVENT_GROUP_DIALOGUE: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: BOSS encounter -> ${fetchArg("hpVar")} ${fetchArg("atkVar")} ${fetchArg("defVar")}`;
};

const fields = [
  {
    key: "hpVar",
    label: "HP variable",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "atkVar",
    label: "ATK variable",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "defVar",
    label: "DEF variable",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "introText",
    label: "Boss intro line",
    type: "text",
    defaultValue: "CINDER turns around.",
  },
];

const compile = (input, helpers) => {
  const { variableSetToValue, textDialogue } = helpers;
  variableSetToValue(input.hpVar, 80);
  variableSetToValue(input.atkVar, 12);
  variableSetToValue(input.defVar, 8);
  if (textDialogue) {
    textDialogue([input.introText ?? "CINDER turns around."]);
  }
};

module.exports = {
  id,
  description: "Cinder Creatures: set CINDER boss stats (HP 80 / ATK 12 / DEF 8) and show intro line.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
