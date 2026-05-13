export const id = "MINI_STORE_BITS_IN_VARIABLE";
export const name = "Variable: Store Bits in Variable";
export const fields = [
    {
      key: "vectorX",
      type: "variable",
      defaultValue: "LAST_VARIABLE"
    },
    {
      key: "bit1",
      label: "Bit 1",
      type: "checkbox",
      width: "50%",
      defaultValue: false
    },
    {
      key: "bit2",
      label: "Bit 2",
      type: "checkbox",
      width: "50%",
      defaultValue: false
    },
    {
      key: "bit3",
      label: "Bit 3",
      type: "checkbox",
      width: "50%",
      defaultValue: false
    },
    {
      key: "bit4",
      label: "Bit 4",
      type: "checkbox",
      width: "50%",
      defaultValue: false
    },
    {
      key: "bit5",
      label: "Bit 5",
      type: "checkbox",
      width: "50%",
      defaultValue: false
    },
    {
      key: "bit6",
      label: "Bit 6",
      type: "checkbox",
      width: "50%",
      defaultValue: false
    },
    {
      key: "bit7",
      label: "Bit 7",
      type: "checkbox",
      width: "50%",
      defaultValue: false
    },
    {
      key: "bit8",
      label: "Bit 8",
      type: "checkbox",
      width: "50%",
      defaultValue: false
    },
    {
      key: "vectorY",
      type: "variable",
      defaultValue: "LAST_VARIABLE"
    }
];
export const compile = (input, helpers) => {
    const { variableSetToValue, variableCopy, variablesMod, ifVariableValue, variablesAdd, variablesDiv } = helpers;
    const { vectorX, bit1, bit2, bit3, bit4, bit5, bit6, bit7, bit8, vectorY } = input;
    const tmp3 = "tmp3";
    variableCopy(tmp3, vectorX);
    variableSetToValue(vectorY, 0);
    const tmp1 = "tmp1";
    const tmp2 = "tmp2";
    var i = 0;
    [bit1, bit2, bit3, bit4, bit5, bit6, bit7, bit8].forEach((e,idx)=>{
      if (e) {
        variableCopy(tmp1, tmp3);
        variableSetToValue(tmp2, 2**idx);
        variablesDiv(tmp1, tmp2);
        variableSetToValue(tmp2, 2);
        variablesMod(tmp1, tmp2);
        variableSetToValue(tmp2, 2**i);
        ifVariableValue(tmp1, "==", 1, ()=>{variablesAdd(vectorY, tmp2);}, []);
        i++;
      }
    });
};