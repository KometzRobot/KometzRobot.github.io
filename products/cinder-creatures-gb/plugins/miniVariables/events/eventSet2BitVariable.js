export const id = "MINI_SET_TWO_BIT_VARIABLE";
export const name = "Variable: Set 2-Bit Variable";
export const fields = [
    {
      key: "vectorX",
      type: "variable",
      defaultValue: "LAST_VARIABLE"
    },
    {
      key: "mini",
      options: [
          ["v1", "2-Bit Variable 1"],
          ["v2", "2-Bit Variable 2"],
          ["v3", "2-Bit Variable 3"],
          ["v4", "2-Bit Variable 4"]
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
      max: 3,
      defaultValue: {
        number: 0,
        variable: "LAST_VARIABLE",
        property: "$self$:xpos"
      },
    },
    {
      label: "Note: Using 2-bit variables over 3 will not work correctly.",
    }
];
export const compile = (input, helpers) => {
    const { variableSetToValue, variablesDiv, variablesMod, variablesMul, variablesAdd, variableCopy, variableFromUnion, temporaryEntityVariable } = helpers;
    const { vectorX, mini, value } = input;
    const tmp1 = "tmp1";
    variableSetToValue(tmp1, 4);
    const tmp2 = "tmp2";
    const tmp4 = "tmp4";
    if (value.type == "number") {
        variableSetToValue(tmp4, value.value);
    } else {
        const tmp3 = variableFromUnion(value, temporaryEntityVariable(0));
        variableCopy(tmp4, tmp3);
    }
    switch (mini) {
        case "v2":
            variableCopy(tmp2, vectorX);
            variablesMod(tmp2, tmp1);
            variablesMul(tmp4, tmp1);
            variableSetToValue(tmp1, 16);
            variablesDiv(vectorX, tmp1);
            variablesMul(vectorX, tmp1);
            variablesAdd(vectorX, tmp4);
            variablesAdd(vectorX, tmp2);
            break;
        case "v3":
            variableSetToValue(tmp1, 64);
            variableCopy(tmp2, vectorX);
            variablesDiv(tmp2, tmp1);
            variablesMul(tmp2, tmp1);
            variableSetToValue(tmp1, 16);
            variablesMul(tmp4, tmp1);
            variablesMod(vectorX, tmp1);
            variablesAdd(vectorX, tmp4);
            variablesAdd(vectorX, tmp2);
            break;
        case "v4":
            variableSetToValue(tmp1, 64);
            variablesMod(vectorX, tmp1);
            variablesMul(tmp4, tmp1);
            variablesAdd(vectorX, tmp4);
            break;
        case "v1":
        default:
            variablesDiv(vectorX, tmp1);
            variablesMul(vectorX, tmp1);
            variablesAdd(vectorX, tmp4);
            break;
    }
};