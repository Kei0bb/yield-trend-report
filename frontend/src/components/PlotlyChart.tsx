import plotlyModule from "react-plotly.js";

// react-plotly.js uses CJS default export; Vite may wrap it
const Plot = (plotlyModule as any).default ?? plotlyModule;
export default Plot;
