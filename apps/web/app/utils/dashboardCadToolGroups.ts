import type { DrawCadToolGroup } from "../components/DrawCadToolsPanel";

export const DASHBOARD_CAD_TOOL_GROUPS: DrawCadToolGroup[] = [
  {
    title: "Draw",
    tools: [
      { label: "Select", tool: "select", hint: "Pick objects" },
      { label: "Pan", tool: "pan", hint: "Drag view" },
      { label: "Line", tool: "line", hint: "2+ points" },
      { label: "Polyline", tool: "polyline", hint: "Connected line" },
      { label: "Area", tool: "area", hint: "Closed polygon" },
      { label: "Box", tool: "box", hint: "Rectangle" },
      { label: "Point", tool: "point", hint: "Marker" },
      { label: "Circle", tool: "circle", hint: "Center + radius" },
      { label: "Arc", tool: "arc", hint: "Center + angles" },
      { label: "Text", tool: "text", hint: "Point + note" },
    ],
  },
  {
    title: "Modify",
    tools: [
      { label: "Move", tool: "move", hint: "Selected objects" },
      { label: "Copy", tool: "copy", hint: "Selected + vector" },
      { label: "Rotate", tool: "rotate", hint: "Selected objects" },
      { label: "Scale", tool: "scale", hint: "Selected objects" },
      { label: "Offset", tool: "offset", hint: "Selected geometry" },
      { label: "Trim", tool: "trim", hint: "Selected line" },
      { label: "Extend", tool: "extend", hint: "Selected line" },
      { label: "Fillet", tool: "fillet", hint: "Selected vertex" },
      { label: "Join", tool: "join", hint: "Selected linework" },
      { label: "Split", tool: "split", hint: "Joined object" },
      { label: "Close", tool: "close", hint: "Polyline area" },
      { label: "Open", tool: "open", hint: "Closed linework" },
      { label: "Reverse", tool: "reverse", hint: "Vertex order" },
      { label: "Delete", tool: "delete", hint: "Selected object" },
    ],
  },
  {
    title: "Annotate / Organize",
    tools: [
      { label: "Dimension", tool: "dimension", hint: "Selected geometry" },
      { label: "Measure", tool: "measure", hint: "Selected distance" },
      { label: "Hatch", tool: "hatch", hint: "Closed fill" },
      { label: "Symbol", tool: "symbol", hint: "Insert current symbol" },
      { label: "Layer", tool: "layer", hint: "Apply layer" },
      { label: "Properties", tool: "properties", hint: "Apply object props" },
      { label: "Snap", tool: "snap", hint: "Toggle snap" },
      { label: "Ortho", tool: "ortho", hint: "Toggle ortho" },
      { label: "Undo", tool: "undo", hint: "Last draft edit" },
      { label: "Redo", tool: "redo", hint: "Redo draft edit" },
      { label: "Command", tool: "command", hint: "Typed commands" },
    ],
  },
];
