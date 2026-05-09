// Meridian Toolkit — Save Point
// Convenience wrapper: shows a "Game saved." dialogue, plays a confirm sound,
// then writes to the chosen save slot. Drop on top of save-statue actors so
// you don't have to wire the same three nodes per scene.

const id = "EVENT_MT_SAVE_POINT";
const name = "Meridian: save point";
const groups = ["EVENT_GROUP_SAVE_DATA"];
const subGroups = {
  EVENT_GROUP_SAVE_DATA: "Meridian Toolkit",
};

const autoLabel = (fetchArg, input) => {
  const slot = input?.slot ?? 0;
  return `Meridian: save to slot ${slot}`;
};

const fields = [
  {
    key: "slot",
    label: "Save slot (0-2)",
    type: "number",
    min: 0,
    max: 2,
    defaultValue: 0,
  },
  {
    key: "message",
    label: "Confirmation message",
    type: "text",
    defaultValue: "Game saved.",
  },
  {
    key: "play_sound",
    label: "Play confirm beep",
    type: "checkbox",
    defaultValue: true,
  },
];

const compile = (input, helpers) => {
  const { textDialogue, dataSave, soundPlayBeep } = helpers;
  if (input.play_sound) {
    soundPlayBeep(4);
  }
  textDialogue(input.message || "Game saved.");
  dataSave(Number(input.slot ?? 0));
};

module.exports = {
  id,
  name,
  description: "One-step save point: optional beep + dialogue + write to slot.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
