-- Enable UUID extension
create extension if not exists "uuid-ossp";

-- ============================================================
-- RUNS
-- ============================================================
create table runs (
  id            uuid primary key default uuid_generate_v4(),
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  status        text not null default 'pending'
                  check (status in ('pending','running','completed','failed')),
  csv_filename  text not null,
  total_rows    int,
  matched       int,
  escalated     int,
  total_cost_usd numeric(10,6)
);

create index idx_runs_status on runs(status);
create index idx_runs_started_at on runs(started_at desc);

-- ============================================================
-- BANK TRANSACTIONS
-- ============================================================
create table bank_transactions (
  id                  uuid primary key default uuid_generate_v4(),
  run_id              uuid not null references runs(id) on delete cascade,
  date                date not null,
  amount_cents        bigint not null,
  description         text not null,
  normalized_merchant text,
  account             text not null,
  raw_row             jsonb not null,
  created_at          timestamptz not null default now()
);

create index idx_bank_transactions_run_id on bank_transactions(run_id);
create index idx_bank_transactions_date on bank_transactions(date);
create index idx_bank_transactions_amount on bank_transactions(amount_cents);
create index idx_bank_transactions_merchant on bank_transactions(normalized_merchant);

-- ============================================================
-- INVOICES
-- ============================================================
create table invoices (
  id                uuid primary key default uuid_generate_v4(),
  vendor            text not null,
  normalized_vendor text not null,
  amount_cents      bigint not null,
  issued_date       date not null,
  due_date          date not null,
  status            text not null default 'open'
                      check (status in ('open','matched','partial','void')),
  created_at        timestamptz not null default now()
);

create index idx_invoices_status on invoices(status);
create index idx_invoices_amount on invoices(amount_cents);
create index idx_invoices_normalized_vendor on invoices(normalized_vendor);
create index idx_invoices_issued_date on invoices(issued_date);

-- ============================================================
-- LEDGER ENTRIES
-- ============================================================
create table ledger_entries (
  id                uuid primary key default uuid_generate_v4(),
  transaction_id    uuid not null references bank_transactions(id),
  invoice_id        uuid not null references invoices(id),
  amount_cents      bigint not null,
  posted_at         timestamptz not null default now(),
  confidence        numeric(4,3) not null check (confidence between 0 and 1),
  created_by_run_id uuid not null references runs(id),
  created_at        timestamptz not null default now()
);

create index idx_ledger_entries_transaction on ledger_entries(transaction_id);
create index idx_ledger_entries_invoice on ledger_entries(invoice_id);
create index idx_ledger_entries_run on ledger_entries(created_by_run_id);
-- prevent same invoice matched twice in same run
create unique index idx_ledger_entries_invoice_run on ledger_entries(invoice_id, created_by_run_id);

-- ============================================================
-- STEP TRACES
-- ============================================================
create table step_traces (
  id                uuid primary key default uuid_generate_v4(),
  run_id            uuid not null references runs(id) on delete cascade,
  step_name         text not null,
  attempt           int not null default 1,
  input_json        jsonb not null,
  output_json       jsonb,
  latency_ms        int,
  tokens_in         int,
  tokens_out        int,
  cost_usd          numeric(10,6),
  status            text not null check (status in ('success','retry','failure','escalated')),
  invariant_results jsonb,
  llm_provider      text,
  llm_model         text,
  created_at        timestamptz not null default now()
);

create index idx_step_traces_run_id on step_traces(run_id);
create index idx_step_traces_step on step_traces(step_name);
create index idx_step_traces_status on step_traces(status);

-- ============================================================
-- REVIEW QUEUE
-- ============================================================
create table review_queue (
  id             uuid primary key default uuid_generate_v4(),
  transaction_id uuid not null references bank_transactions(id),
  reason         text not null,
  candidates     jsonb,
  resolved       boolean not null default false,
  created_at     timestamptz not null default now(),
  resolved_at    timestamptz
);

create index idx_review_queue_transaction on review_queue(transaction_id);
create index idx_review_queue_resolved on review_queue(resolved);

-- ============================================================
-- EVAL TABLES
-- ============================================================
create table golden_cases (
  id                   uuid primary key default uuid_generate_v4(),
  name                 text not null unique,
  input_csv            text not null,
  expected_matches     jsonb not null,
  expected_escalations jsonb not null,
  created_at           timestamptz not null default now()
);

create table evals_results (
  id              uuid primary key default uuid_generate_v4(),
  ran_at          timestamptz not null default now(),
  total_cases     int not null,
  passed          int not null,
  accuracy        numeric(5,4),
  precision_score numeric(5,4),
  recall_score    numeric(5,4),
  f1_score        numeric(5,4),
  avg_cost_usd    numeric(10,6),
  p95_latency_ms  int,
  regressions     jsonb
);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
alter table runs              enable row level security;
alter table bank_transactions enable row level security;
alter table invoices          enable row level security;
alter table ledger_entries    enable row level security;
alter table step_traces       enable row level security;
alter table review_queue      enable row level security;
alter table golden_cases      enable row level security;
alter table evals_results     enable row level security;

-- Permissive policies for service role (bypasses RLS) and authenticated users
-- In production: scope to org/tenant via JWT claims
create policy "service_role_all" on runs              for all using (true) with check (true);
create policy "service_role_all" on bank_transactions for all using (true) with check (true);
create policy "service_role_all" on invoices          for all using (true) with check (true);
create policy "service_role_all" on ledger_entries    for all using (true) with check (true);
create policy "service_role_all" on step_traces       for all using (true) with check (true);
create policy "service_role_all" on review_queue      for all using (true) with check (true);
create policy "service_role_all" on golden_cases      for all using (true) with check (true);
create policy "service_role_all" on evals_results     for all using (true) with check (true);
