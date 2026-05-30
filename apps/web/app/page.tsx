import {
  Box,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import Link from "next/link";
import { api, type Run } from "../lib/api";

const STATUS_COLOR: Record<Run["status"], "default" | "warning" | "success" | "error"> = {
  pending: "default",
  running: "warning",
  completed: "success",
  failed: "error",
};

function fmtDate(d: string | null) {
  if (!d) return "—";
  return new Date(d).toLocaleString();
}

function fmtCost(v: number | null) {
  if (v == null) return "—";
  return `$${v.toFixed(4)}`;
}

export default async function RunsPage() {
  let runs: Run[] = [];
  try {
    runs = await api.getRuns();
  } catch {
    // no runs yet or API unavailable
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={2}>
        Reconciliation Runs
      </Typography>
      <TableContainer component={Paper} elevation={1}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ "& th": { fontWeight: 700, bgcolor: "#f5f5f5" } }}>
              <TableCell>Run ID</TableCell>
              <TableCell>File</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="right">Rows</TableCell>
              <TableCell align="right">Matched</TableCell>
              <TableCell align="right">Escalated</TableCell>
              <TableCell align="right">Cost</TableCell>
              <TableCell>Started</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {runs.length === 0 && (
              <TableRow>
                <TableCell colSpan={8} align="center" sx={{ color: "text.secondary", py: 4 }}>
                  No runs yet. Upload a CSV to get started.
                </TableCell>
              </TableRow>
            )}
            {runs.map((run) => (
              <TableRow key={run.id} hover>
                <TableCell>
                  <Link
                    href={`/runs/${run.id}`}
                    style={{ fontFamily: "monospace", fontSize: 12, color: "#1a237e" }}
                  >
                    {run.id.slice(0, 8)}…
                  </Link>
                </TableCell>
                <TableCell sx={{ fontSize: 13 }}>{run.csv_filename}</TableCell>
                <TableCell>
                  <Chip
                    label={run.status}
                    color={STATUS_COLOR[run.status]}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">{run.total_rows ?? "—"}</TableCell>
                <TableCell align="right">{run.matched ?? "—"}</TableCell>
                <TableCell align="right">{run.escalated ?? "—"}</TableCell>
                <TableCell align="right">{fmtCost(run.total_cost_usd)}</TableCell>
                <TableCell sx={{ fontSize: 12 }}>{fmtDate(run.started_at)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
