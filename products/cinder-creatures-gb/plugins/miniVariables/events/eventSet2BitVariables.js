export const id = "MINI_SET_TWO_BIT_VARIABLES";
export const name = "Variable: Set 2-Bit Variables";
export const fields = [
    {
      key: "vectorX",
      type: "variable",
      defaultValue: "LAST_VARIABLE"
    },
    {
      key: "value1",
      label: "2-Bit Variable 1",
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
      width: "50%",
    },
    {
      key: "value2",
      label: "2-Bit Variable 2",
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
      width: "50%",
    },
    {
      key: "value3",
      label: "2-Bit Variable 3",
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
      width: "50%",
    },
    {
      key: "value4",
      label: "2-Bit Variable 4",
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
      width: "50%",
    },
    {
      label: "Note: Using 2-bit variables over 3 will not work correctly.",
    }
];
export const compile = (input, helpers) => {
    const { variableSetToValue, variableCopy, variablesMul, variablesAdd, variableFromUnion, temporaryEntityVariable } = helpers;
    const { vectorX, value1, value2, value3, value4} = input;
    if (value1.type === "number" && value2.type === "number" && value3.type === "number" && value4.type === "number") {
      variableSetToValue(vectorX, value4.value * 64 + value3.value * 16 + value2.value * 4 + value1.value);
    } else {
      const tmp1 = variableFromUnion(value1, temporaryEntityVariable(0));
      const tmp2 = variableFromUnion(value2, temporaryEntityVariable(1));
      const tmp3 = variableFromUnion(value3, temporaryEntityVariable(2));
      const tmp4 = variableFromUnion(value4, temporaryEntityVariable(3));
      const tmp5 = "tmp5";
      const tmp6 = "tmp6";
      variableCopy(tmp6, tmp1);
      const tmp7 = "tmp7";
      variableCopy(tmp7, tmp2);
      const tmp8 = "tmp8";
      variableCopy(tmp8, tmp3);
      const tmp9 = "tmp9";
      variableCopy(tmp9, tmp4);
      variableSetToValue(tmp5, 64);
      variablesMul(tmp9, tmp5);
      variableSetToValue(tmp5, 16);
      variablesMul(tmp8, tmp5);
      variableSetToValue(tmp5, 4);
      variablesMul(tmp7, tmp5);
      variablesAdd(tmp6, tmp7);
      variablesAdd(tmp6, tmp8);
      variablesAdd(tmp6, tmp9);
      variableCopy(vectorX, tmp6)
    }
};