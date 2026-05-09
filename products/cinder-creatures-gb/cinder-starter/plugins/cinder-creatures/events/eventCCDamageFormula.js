// Cinder Creatures - Damage Formula
// Computes damage = ATK + rnd(0..variance) - DEF (clamped >= 0) into dmgVar.
// Use after Cinder: set stats so you have ATK/DEF in variables.

const id = "EVENT_CC_DAMAGE_FORMULA";
const groups = ["EVENT_GROUP_VARIABLES"];
const subGroups = {
  EVENT_GROUP_VARIABLES: "Cinder Creatures",
};

const autoLabel = (fetchArg) => {
  return `Cinder: damage = ${fetchArg("atkVar")} + rnd(0..${fetchArg("variance")}) - ${fetchArg("defVar")} -> ${fetchArg("dmgVar")}`;
};

const fields = [
  {
    key: "atkVar",
    label: "Attacker ATK variable",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "defVar",
    label: "Defender DEF variable",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
  {
    key: "variance",
    label: "Random variance (0..N)",
    type: "number",
    min: 0, max: 16, defaultValue: 4,
  },
  {
    key: "dmgVar",
    label: "Output damage variable",
    type: "variable",
    defaultValue: "LAST_VARIABLE",
  },
];

const compile = (input, helpers) => {
  const { variableSetToRandom, variablesOperation } = helpers;
  const variance = Math.max(0, Math.min(16, Number(input.variance ?? 4)));

  // dmg = rnd(0..variance)
  variableSetToRandom(input.dmgVar, 0, variance + 1);
  // dmg += atk
  variablesOperation(input.dmgVar, ".ADD", input.atkVar, false);
  // dmg -= def (clamped to 0 so we don't underflow)
  variablesOperation(input.dmgVar, ".SUB", input.defVar, true);
};

module.exports = {
  id,
  description: "Cinder Creatures: compute damage = ATK + rnd(0..variance) - DEF (clamped >= 0).",
  autoLabel,
  groups,
  subGroups,
  fields,
  compile,
};
