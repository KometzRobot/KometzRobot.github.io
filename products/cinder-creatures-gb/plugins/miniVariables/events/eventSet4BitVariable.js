export const id = "MINI_SET_FOUR_BIT_VARIABLE";
export const name = "Variable: Set 4-Bit Variable";
export const fields = [
    {
      key: "vectorX",
      type: "variable",
      defaultValue: "LAST_VARIABLE"
    },
    {
      key: "mini",
      options: [
          ["v1", "4-Bit Variable 1"],
          ["v2", "4-Bit Variable 2"]
      ],
      type: "select",
      defaultValue: "v1"
    },
    {
      key: "value",
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
    },
    {
      label: "Note: Using 4-bit variables over 15 will not work correctly.",
    }
];
export const compile = (input, helpers) => {
    const { variableSetToValue, variablesDiv, variablesMod, variablesMul, variablesAdd, variableFromUnion, temporaryEntityVariable, variableCopy } = helpers;
    const { vectorX, mini, value } = input;
    const tmp1 = "tmp1";
    const tmp3 = "tmp3";
    variableSetToValue(tmp1, 16);
    if (value.type == "number") {
      variableSetToValue(tmp3, value.value);
    } else {
      const tmp2 = variableFromUnion(value, temporaryEntityVariable(0));
      variableCopy(tmp3, tmp2);
    }
    switch (mini) {
        case "v2":
            variablesMod(vectorX, tmp1);
            variablesMul(tmp3, tmp1);
            variablesAdd(vectorX, tmp3);
            break;
        case "v1":
        default:
            variablesDiv(vectorX, tmp1);
            variablesMul(vectorX, tmp1);
            variablesAdd(vectorX, tmp3);
            break;
    }
};