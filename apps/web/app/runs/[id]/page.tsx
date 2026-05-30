"use client";

import {
  Alert,
  Box,
  Button,
  Chip,
  Collapse,
  Divider,
  Paper,
  Stack,
  Typography,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ReplayIcon from "@mui/icons-material/Replay";
import { use, useState } from "react";
import useSWR from "swr";
import { api, type StepTrace } from "../../../lib/api";
import { JsonViewer } from "../../../components/JsonViewer";

const STEP_ORDER = ["ingest", "enrich", "match", "validate", "post"];

const STATUS_COLOR: Record<string, "success" | "warning" | "error" | "info"> = {
  success: "success",
  retry: "warning",
  failure: "error",
  escalated: "info",
};

function TraceCard({ trace }: { trace: StepTrace }) {
  const [open, setOpen] = useState(false);
  const [replayResult, setReplayResult] = useState<string | null>(null);

  async function handleReplay() {
    try {
      const r = await api.replayStep(trace.run_id, trace.step_name);
      setReplayResult(`Replay ${r.status}`);
    } catch (e) {
      setReplayResult(`Error: ${e}`);
    }
  }

  const invariants = trace.invariant_results ?? [];

  return (
    <Paper variant="outlined" sx={{ mb: 1.5, p: 2 }}>
      <Stack direction="row" alignItems="center" gap={1} sx={{ cursor: "pointer" }} onClick={() => setOpen(!open)}>
        <Typography variant="subtitle2" sx={{ fontWeight: 700, minWidth: 80 }}>
          {trace.step_name}
        </Typography>
        <Chip label={`attempt ${trace.attempt}`} size="small" />
        <Chip label={trace.status} color={STATUS_COLOR[trace.status] ?? "default"} size="small" />
        {trace.latency_ms != null && (
          <Chip label={`${trace.latency_ms}ms`} size="small" variant="outlined" />
        )}
        {trace.cost_usd != null && (
          <Chip label={`$${trace.cost_usd.toFixed(5)}`} size="small" variant="outlined" />
        )}
        {invariants.map((inv) => (
          <Chip
            key={inv.name}
            label={inv.name}
            color={inv.passed ? "success" : "error"}
            size="small"
          />
        ))}
        <Box flex={1} />
        <Button
          size="small"
          startIcon={<ReplayIcon />}
          onClick={(e) => { e.stopPropagation(); handleReplay(); }}
          variant="outlined"
          sx={{ fontSize: 11 }}
        >
          Replay
        </Button>
        <ExpandMoreIcon
          sx={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", transition: "0.2s" }}
        />
      </Stack>

      {replayResult && (
        <Alert severity="info" sx={{ mt: 1 }}>
          {replayResult}
        </Alert>
      )}

      <Collapse in={open}>
        <Divider sx={{ my: 1.5 }} />
        <Stack direction="row" gap={2} flexWrap="wrap">
          <Box flex={1} minWidth={280}>
            <Typography variant="caption" color="text.secondary" fontWeight={700}>
              INPUT
            </Typography>
            <JsonViewer data={trace.input_json} />
          </Box>
          {trace.output_json && (
            <Box flex={1} minWidth={280}>
              <Typography variant="caption" color="text.secondary" fontWeight={700}>
                OUTPUT
              </Typography>
              <JsonViewer data={trace.output_json} />
            </Box>
          )}
        </Stack>
        {invariants.some((i) => !i.passed) && (
          <Box mt={1}>
            {invariants.filter((i) => !i.passed).map((i) => (
              <Alert key={i.name} severity="error" sx={{ mb: 0.5 }}>
                <strong>{i.name}</strong>: {i.detail}
              </Alert>
            ))}
          </Box>
        )}
      </Collapse>
    </Paper>
  );
}

export default function RunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: run } = useSWR(`run-${id}`, () => api.getRun(id), { refreshInterval: 3000 });
  const { data: traces = [] } = useSWR(`traces-${id}`, () => api.getTraces(id), {
    refreshInterval: 3000,
  });

  const grouped = STEP_ORDER.reduce<Record<string, StepTrace[]>>((acc, s) => {
    acc[s] = traces.filter((t) => t.step_name === s);
    return acc;
  }, {});

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={0.5}>
        Run: <span style={{ fontFamily: "monospace", fontSize: 18 }}>{id.slice(0, 8)}…</span>
      </Typography>
      {run && (
        <Stack direction="row" gap={1} mb={3}>
          <Chip label={run.status} color={run.status === "completed" ? "success" : run.status === "failed" ? "error" : "warning"} />
          <Chip label={`${run.csv_filename}`} variant="outlined" />
          {run.total_rows != null && <Chip label={`${run.total_rows} rows`} variant="outlined" />}
          {run.matched != null && <Chip label={`${run.matched} matched`} color="success" variant="outlined" />}
          {run.escalated != null && <Chip label={`${run.escalated} escalated`} color="warning" variant="outlined" />}
        </Stack>
      )}

      {STEP_ORDER.map((step) => {
        const stepTraces = grouped[step] ?? [];
        if (stepTraces.length === 0) return null;
        return (
          <Box key={step} mb={2}>
            <Typography variant="overline" color="text.secondary">
              {step}
            </Typography>
            {stepTraces.map((t) => (
              <TraceCard key={t.id} trace={t} />
            ))}
          </Box>
        );
      })}

      {traces.length === 0 && (
        <Typography color="text.secondary">No traces yet — run is still executing.</Typography>
      )}
    </Box>
  );
}
