// Cinder Creatures — Trainer Challenge
// Pokemon-RBY style "TRAINER X wants to fight!" intro. Pair with one of
// the cc_trainer_*.png backgrounds (elder/rival/prof/nurse) on the scene
// the actor is in.

const id = "EVENT_CC_TRAINER_CHALLENGE";
const name = "Cinder: trainer challenge intro";
const groups = ["EVENT_GROUP_DIALOGUE"];
const subGroups = {
  EVENT_GROUP_DIALOGUE: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: ${fetchArg("title")} ${fetchArg("trainer")} challenges you`;
};

const fields = [
  {
    key: "title",
    label: "Trainer title",
    type: "select",
    defaultValue: "TRAINER",
    options: [
      ["TRAINER", "TRAINER"],
      ["ELDER", "ELDER"],
      ["PROF", "PROF"],
      ["NURSE", "NURSE"],
      ["RIVAL", "RIVAL"],
      ["DOCTOR", "DOCTOR"],
      ["HACKER", "HACKER"],
      ["CISO", "CISO"],
    ],
  },
  {
    key: "trainer",
    label: "Trainer name",
    type: "text",
    defaultValue: "RED",
  },
  {
    key: "intro",
    label: "Intro line",
    type: "text",
    defaultValue: "wants to battle!",
  },
  {
    key: "boast",
    label: "Boast line",
    type: "text",
    defaultValue: "I won't lose to you!",
  },
];

const compile = (input, helpers) => {
  const { textDialogue } = helpers;
  const title = (input.title || "TRAINER").toUpperCase();
  const trainerName = (input.trainer || "RED").toUpperCase();
  const intro = input.intro || "wants to battle!";
  const boast = input.boast || "I won't lose to you!";

  if (textDialogue) {
    textDialogue([
      `${title} ${trainerName}\n${intro}`,
      `${title} ${trainerName}: ${boast}`,
    ]);
  }
};

module.exports = {
  id,
  name,
  description:
    "Cinder Creatures: Pokemon-RBY style trainer challenge intro. Pair with cc_trainer_* backgrounds to recreate the trainer-card moment.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
