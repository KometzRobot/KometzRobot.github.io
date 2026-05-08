// Cinder Creatures — Show Creature Name
// Reads a creature ID variable (1..12) and shows the matching name in a
// dialogue box. Falls back to "???" for any other value.

const SPECIES = [
  "FORKLING", "DAEMONET", "KERNITE", "RECURSE",
  "MUTEXEL",  "BYTEFLY",  "SEMAFOX", "REGEXEL",
  "SCOPEWVR", "ALLOCROC", "NULLPUP", "CACHEBIT",
];

const id = "EVENT_CC_SHOW_NAME";
const groups = ["EVENT_GROUP_CINDER_CREATURES"];

const autoLabel = (fetchArg) => {
  return `Cinder: show name from ${fetchArg("variable")}`;
};

const fields = [
  {
    key: "variable",
    label: "Variable holding creature ID (1-12)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "prefix",
    label: "Prefix (optional)",
    type: "text",
    defaultValue: "A wild ",
  },
  {
    key: "suffix",
    label: "Suffix (optional)",
    type: "text",
    defaultValue: " appeared!",
  },
];

const compile = (input, helpers) => {
  const { caseVariableConstValue } = helpers;
  const prefix = input.prefix ?? "";
  const suffix = input.suffix ?? "";

  const cases = SPECIES.map((name, i) => ({
    value: { type: "number", value: i + 1 },
    branch: [
      {
        command: "EVENT_TEXT",
        args: { text: `${prefix}${name}${suffix}` },
      },
    ],
  }));

  const elseBranch = [
    { command: "EVENT_TEXT", args: { text: `${prefix}???${suffix}` } },
  ];

  caseVariableConstValue(input.variable, cases, elseBranch);
};

module.exports = {
  id,
  description:
    "Cinder Creatures: show the creature name matching a creature ID variable.",
  autoLabel,
  groups,
  fields,
  compile,
};
