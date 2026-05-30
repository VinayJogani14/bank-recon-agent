"use client";

import { Box } from "@mui/material";
import { JsonView, allExpanded, defaultStyles } from "react-json-view-lite";
import "react-json-view-lite/dist/index.css";

export function JsonViewer({ data }: { data: unknown }) {
  return (
    <Box
      sx={{
        fontFamily: "monospace",
        fontSize: 12,
        bgcolor: "#f8f8f8",
        border: "1px solid #e0e0e0",
        borderRadius: 1,
        p: 1,
        mt: 0.5,
        maxHeight: 300,
        overflow: "auto",
      }}
    >
      <JsonView data={data as object} shouldExpandNode={allExpanded} style={defaultStyles} />
    </Box>
  );
}
