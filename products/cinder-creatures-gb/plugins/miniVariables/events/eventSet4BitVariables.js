export const id = "MINI_SET_FOUR_BIT_VARIABLES";
export const name = "Variable: Set 4-Bit Variables";
export const fields = [
    {
      key: "vectorX",
      type: "variable",
      defaultValue: "LAST_VARIABLE"
    },
    {
      key: "vectorY",
      label: "4-Bit Variable 1",
      type: "union",
      types: ["number", "variable", "property"],
      defaultType: "number",
      min: 0,
      max: 15,
      defaultValue: {
        number: 0,
        variable: "LAST_VARIABLE",
        property: "$self$:xpos"
      },
      width: "50%",
    },
    {
      key: "vectorZ",
      label: "4-Bit Variable 2",
      type: "union",
      types: ["number", "variable", "property"],
      defaultType: "number",
      min: 0,
      max: 15,
      defaultValue: {
        number: 0,
        variable: "LAST_VARIABLE",
        property: "$self$:xpos"
      },
      width: "50%",
    },
    {
      label: "Note: Using 4-bit variables over 15 will not work correctly.",
    }
];
export const compile = (input, helpers) => {
    const { variableSetToValue, variableCopy, variablesMul, variablesAdd, variableFromUnion, temporaryEntityVariable } = helpers;
    const { vectorX, vectorY, vectorZ } = input;
    if (vectorY.type === "number" && vectorZ.type === "number") {
      variableSetToValue(vectorX, vectorZ.value * 16 + vectorY.value);
    } else {
      const tmp1 = variableFromUnion(vectorY, temporaryEntityVariable(0));
      const tmp2 = variableFromUnion(vectorZ, temporaryEntityVariable(1));
      const tmp3 = "tmp3";
      variableSetToValue(tmp3, 16);
      const tmp4 = "tmp4";
      variableCopy(tmp4, tmp1);
      const tmp5 = "tmp5";
      variableCopy(tmp5, tmp2);
      variablesMul(tmp5, tmp3)
      variablesAdd(tmp5, tmp4)
      variableCopy(vectorX, tmp5);
    }
};