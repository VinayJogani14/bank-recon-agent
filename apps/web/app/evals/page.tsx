"use client";

import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import { useState } from "react";
import useSWR from "swr";
import { api, type EvalResult } from "../../lib/api";

function pct(v: number | null) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

export default function EvalsPage() {
  const { data: results = [], mutate } = useSWR("eval-results", api.getEvalResults, {
    refreshInterval: 10000,
  });
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRunEvals() {
    setRunning(true);
    setError(null);
    try {
      await api.triggerEvals();
      await mutate();
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <Box>
      <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
        <Typography variant="h5" fontWeight={700}>
          Eval Harness
        </Typography>
        <Button
          variant="contained"
          startIcon={running ? <CircularProgress size={16} color="inherit" /> : <PlayArrowIcon />}
          disabled={running}
          onClick={handleRunEvals}
        >
          {running ? "Running…" : "Run Evals"}
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <TableContainer component={Paper} elevation={1}>
        <Table size="small">
          <TableHead>
            <TableRow sx={{ "& th": { fontWeight: 700, bgcolor: "#f5f5f5" } }}>
              <TableCell>Ran At</TableCell>
              <TableCell align="right">Cases</TableCell>
              <TableCell align="right">Passed</TableCell>
              <TableCell align="right">Accuracy</TableCell>
              <TableCell align="right">Precision</TableCell>
              <TableCell align="right">Recall</TableCell>
              <TableCell align="right">F1</TableCell>
              <TableCell align="right">Avg Cost</TableCell>
              <TableCell align="right">P95 Latency</TableCell>
              <TableCell>Regressions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {results.length === 0 && (
              <TableRow>
                <TableCell colSpan={10} align="center" sx={{ color: "text.secondary", py: 4 }}>
                  No eval runs yet.
                </TableCell>
              </TableRow>
            )}
            {results.map((r: EvalResult) => (
              <TableRow key={r.id} hover>
                <TableCell sx={{ fontSize: 12 }}>
                  {new Date(r.ran_at).toLocaleString()}
                </TableCell>
                <TableCell align="right">{r.total_cases}</TableCell>
                <TableCell align="right">
                  <Chip
                    label={`${r.passed}/${r.total_cases}`}
                    color={r.passed === r.total_cases ? "success" : "warning"}
                    size="small"
                  />
                </TableCell>
                <TableCell align="right">{pct(r.accuracy)}</TableCell>
                <TableCell align="right">{pct(r.precision_score)}</TableCell>
                <TableCell align="right">{pct(r.recall_score)}</TableCell>
                <TableCell align="right">{pct(r.f1_score)}</TableCell>
                <TableCell align="right">
                  {r.avg_cost_usd != null ? `$${r.avg_cost_usd.toFixed(5)}` : "—"}
                </TableCell>
                <TableCell align="right">
                  {r.p95_latency_ms != null ? `${r.p95_latency_ms}ms` : "—"}
                </TableCell>
                <TableCell>
                  {(r.regressions ?? []).length > 0 ? (
                    <Chip label={`${r.regressions!.length} regressions`} color="error" size="small" />
                  ) : (
                    <Chip label="clean" color="success" size="small" variant="outlined" />
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
