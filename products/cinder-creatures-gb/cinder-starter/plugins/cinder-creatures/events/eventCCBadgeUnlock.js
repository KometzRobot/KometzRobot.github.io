// Cinder Creatures — Badge Unlock dialogue
// Shows the standard "leader hands you the X BADGE" dialogue card.
// Bitfield math (setting the bit in VAR_CC_BADGES) is done in the
// scene script with raw EVENT_VARIABLE_MATH events, gated by a
// per-badge flag — this event is the cosmetic half only.
//
// Bit layout (for reference): 1=LOGIC, 2=MEM, 4=PROC, 8=DATA, 16=CORE.

const id = "EVENT_CC_BADGE_UNLOCK";
const name = "Cinder: gym badge award (dialogue)";
const groups = ["EVENT_GROUP_DIALOGUE"];
const subGroups = {
  EVENT_GROUP_DIALOGUE: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: ${fetchArg("leaderName")} awards ${fetchArg("badge")} BADGE`;
};

const fields = [
  {
    key: "badge",
    label: "Badge",
    type: "select",
    defaultValue: "LOGIC",
    options: [
      ["LOGIC", "LOGIC"],
      ["MEM", "MEM"],
      ["PROC", "PROC"],
      ["DATA", "DATA"],
      ["CORE", "CORE"],
    ],
  },
  {
    key: "leaderName",
    label: "Leader name (for award text)",
    type: "text",
    defaultValue: "AUDITOR PYRE",
  },
];

const compile = (input, helpers) => {
  const { textDialogue } = helpers;
  const badge = input.badge || "LOGIC";
  const leader = (input.leaderName || "GYM LEADER").toUpperCase();
  if (textDialogue) {
    textDialogue([
      `${leader} hands you the\n${badge} BADGE.`,
      `JOURNAL updated.\nCompanion app will\nunlock a new panel.`,
    ]);
  }
};

module.exports = {
  id,
  name,
  description:
    "Cinder Creatures: dialogue card for awarding a gym badge. Pair with EVENT_VARIABLE_MATH events on VAR_CC_BADGES (gated by a per-badge flag) to set the bit; companion app reads the bitfield out of the save header.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
