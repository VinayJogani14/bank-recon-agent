"use client";

import { AppBar, Box, CssBaseline, ThemeProvider, Toolbar, Typography, createTheme } from "@mui/material";
import Link from "next/link";
import type { ReactNode } from "react";

const theme = createTheme({
  palette: { mode: "light", primary: { main: "#1a237e" } },
  typography: { fontFamily: "'Inter', 'Roboto', sans-serif" },
});

const NAV = [
  { label: "Runs", href: "/" },
  { label: "Upload", href: "/upload" },
  { label: "Evals", href: "/evals" },
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <AppBar position="static" color="primary" elevation={0}>
            <Toolbar variant="dense">
              <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: 1, mr: 4 }}>
                ReconAgent
              </Typography>
              {NAV.map((n) => (
                <Link key={n.href} href={n.href} style={{ color: "#fff", marginRight: 24, textDecoration: "none", fontSize: 14 }}>
                  {n.label}
                </Link>
              ))}
            </Toolbar>
          </AppBar>
          <Box sx={{ p: 3 }}>{children}</Box>
        </ThemeProvider>
      </body>
    </html>
  );
}
