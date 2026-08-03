/** Shared number-formatting helpers for the PCM/WAT summary table. Pure
 *  functions, no React — kept out of a component file so
 *  react-refresh/only-export-components has nothing to complain about. */

/** Four significant digits, so 0.4021 and 1042.6 read at the same width.
 *
 *  Mirrors Python's "%.4g" exactly — the PDF formats the same numbers
 *  server-side, and a screen/PDF mismatch on the same lot is a bug report
 *  waiting to happen. `%g`:
 *   1. rounds to the given precision (4 significant digits) FIRST,
 *   2. THEN decides plain vs. exponential from the *rounded* magnitude
 *      (exponential when the decimal exponent is < -4 or >= the precision),
 *   3. in exponential form, strips trailing mantissa zeros and pads the
 *      exponent to two digits.
 *  Rounding before branching matters: 9999.6 rounds to 10000 (5 digits),
 *  which must print as "1e+04", not the plain "10000" that a naive
 *  raw-value-first exponent check would produce. */
export function fmtValue(v: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v === 0) return "0";
  const rounded = Number(v.toPrecision(4));
  const exp = Math.floor(Math.log10(Math.abs(rounded)));
  if (exp < -4 || exp >= 4) {
    const [rawMantissa, rawExp] = rounded.toExponential(3).split("e");
    const mantissa = rawMantissa.includes(".")
      ? rawMantissa.replace(/0+$/, "").replace(/\.$/, "")
      : rawMantissa;
    const expSign = rawExp[0] === "-" ? "-" : "+";
    const expDigits = Math.abs(Number(rawExp)).toString().padStart(2, "0");
    return `${mantissa}e${expSign}${expDigits}`;
  }
  return String(rounded);
}

export function fmtCpk(cpk: number | null, state: string): string {
  if (state === "infinite") return "∞";
  if (state === "value" && cpk !== null) return cpk.toFixed(2);
  return "—";
}
