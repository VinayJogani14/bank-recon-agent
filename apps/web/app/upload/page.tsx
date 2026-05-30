"use client";

import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Paper,
  Typography,
} from "@mui/material";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_AGENT_API_URL ?? "http://localhost:8000";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  async function handleSubmit() {
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${BASE}/runs`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      router.push(`/runs/${data.run_id}`);
    } catch (e) {
      setError(String(e));
      setLoading(false);
    }
  }

  return (
    <Box maxWidth={500}>
      <Typography variant="h5" fontWeight={700} mb={3}>
        Upload Bank Statement
      </Typography>
      <Paper
        variant="outlined"
        sx={{
          p: 4,
          textAlign: "center",
          border: "2px dashed #bdbdbd",
          cursor: "pointer",
          "&:hover": { borderColor: "#1a237e" },
        }}
        onClick={() => inputRef.current?.click()}
      >
        <UploadFileIcon sx={{ fontSize: 48, color: "text.secondary", mb: 1 }} />
        <Typography color="text.secondary" mb={1}>
          {file ? file.name : "Click to select a CSV file"}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Required columns: date, amount, description, account
        </Typography>
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          style={{ display: "none" }}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}

      <Button
        variant="contained"
        size="large"
        fullWidth
        sx={{ mt: 2 }}
        disabled={!file || loading}
        onClick={handleSubmit}
        startIcon={loading ? <CircularProgress size={18} color="inherit" /> : <UploadFileIcon />}
      >
        {loading ? "Uploading…" : "Start Reconciliation"}
      </Button>
    </Box>
  );
}
