from prometheus_client import Counter, Gauge, Histogram

STEP_LATENCY = Histogram(
    "recon_step_latency_seconds",
    "Step execution latency",
    ["step"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

RETRY_COUNT = Counter(
    "recon_retry_total",
    "Number of step retries",
    ["step"],
)

INVARIANT_VIOLATIONS = Counter(
    "recon_invariant_violations_total",
    "Invariant violations per step",
    ["step"],
)

ESCALATION_RATE = Gauge(
    "recon_escalation_rate",
    "Fraction of transactions escalated to review queue",
)

EVAL_ACCURACY = Gauge(
    "recon_eval_accuracy",
    "Latest eval harness accuracy",
)
