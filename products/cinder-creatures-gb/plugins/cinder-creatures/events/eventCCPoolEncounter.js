// Cinder Creatures - Pool Encounter
// Joel directive (Loop 9710): catching/collecting must be a core function tied
// to the consistent loop of using the Cinder USB.
//
// Picks one of 16 pool slots at random and copies that slot's creature ID to
// the result variable. The companion app pre-seeds the 16 slot variables
// based on the user's USB activity (see scripts/cc-encounter-pool.py); the
// ROM never reads the pool file directly — it just reads its own variables.
//
// Default variable names match the convention written by the companion app's
// save-syncer: $cc_pool_0 ... $cc_pool_15. Override per-call if needed.

const id = "EVENT_CC_POOL_ENCOUNTER";
const name = "Cinder: pool encounter (USB-driven)";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: pool encounter -> ${fetchArg("resultVar")}`;
};

const POOL_SIZE = 16;

const slotFields = Array.from({ length: POOL_SIZE }, (_, i) => ({
  key: `slot${i}`,
  label: `Pool slot ${i}`,
  type: "variable",
  defaultValue: "LAST_VARIABLE",
  width: "50%",
}));

const fields = [
  {
    type: "label",
    label:
      "Picks one of 16 pool slots at random; copies that slot's creature ID to the result. " +
      "Companion app pre-seeds the slots from USB activity (chats, journal, vault, streak).",
  },
  {
    key: "resultVar",
    label: "Result variable (creature ID)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "indexVar",
    label: "Temp index variable (0..15)",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  ...slotFields,
];

const compile = (input, helpers) => {
  const { variableSetToRandom, variableCopy, caseVariableConstValue } = helpers;

  // Pick random slot index 0..15
  variableSetToRandom(input.indexVar, 0, POOL_SIZE);

  // Switch on index, copy that slot's variable to result
  const cases = Array.from({ length: POOL_SIZE }, (_, i) => ({
    value: { type: "number", value: i },
    branch: [
      {
        command: "EVENT_VARIABLE_COPY",
        args: {
          vectorX: input.resultVar,
          vectorY: input[`slot${i}`],
        },
      },
    ],
  }));

  // Fallback: if index somehow out of range, use slot 0
  const elseBranch = [
    {
      command: "EVENT_VARIABLE_COPY",
      args: {
        vectorX: input.resultVar,
        vectorY: input.slot0,
      },
    },
  ];

  caseVariableConstValue(input.indexVar, cases, elseBranch);
};

module.exports = {
  id,
  name,
  description:
    "Cinder Creatures: pick a random creature from the 16-slot USB-driven pool. The companion app seeds the slots based on chats, journal entries, vault saves, and streak.",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
