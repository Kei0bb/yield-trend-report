import plotlyModule from "react-plotly.js";

// react-plotly.js uses a CJS default export; Vite may wrap it in an extra .default
const Plot = (plotlyModule as typeof plotlyModule & { default?: typeof plotlyModule }).default ?? plotlyModule;
export default Plot;
