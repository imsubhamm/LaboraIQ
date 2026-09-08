export type HealthScore = { score: number; status: string; reasons: string[] };

export type AnalyzerDashboardRow = {
  analyzer_id: string;
  code: string;
  vendor: string;
  model: string;
  branch_id: string;
  branch_code: string;
  branch_name: string;
  time_zone: string;
  configuration_status: string;
  connectivity: string;
  health: HealthScore;
  uptime_percent: number | null;
  orders: number;
  order_success_percent: number | null;
  avg_latency_ms: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  queue_depth: number;
  last_seen_at: string | null;
  last_successful_connection_at: string | null;
  failed_orders: number;
  retry_rate: number | null;
  current_error: string | null;
  timeout_rate: number | null;
  avg_order_duration_seconds: number | null;
  avg_result_turnaround_seconds: number | null;
  work_items: number;
  completed_items: number;
  pending_items: number;
  failed_items: number;
  cancelled_items: number;
  results_received: number;
  technically_reviewed: number;
  validated: number;
  released: number;
  tests_per_hour: number | null;
  inbound_messages: number;
  outbound_messages: number;
};

export type AnalyzerTrendPoint = {
  bucket: string;
  label: string;
  availability_percent: number | null;
  failure_rate: number | null;
  avg_latency_ms: number | null;
  throughput: number | null;
  queue_depth: number | null;
};

export type AnalyzerAlert = {
  analyzer_id: string;
  analyzer_code: string;
  type: string;
  severity: string;
  message: string;
};

export type AnalyzerHealthEvent = {
  occurred_at: string;
  event_type: string;
  success: boolean;
  latency_ms: number | null;
  message: string;
};

export type AnalyzerHealthAttempt = {
  created_at: string;
  attempt_no: number;
  state: string;
  error: string | null;
};

export type AnalyzerDashboardDetail = {
  analyzer_id: string;
  connectivity: string;
  health: HealthScore;
  last_heartbeat_at: string | null;
  last_successful_connection_at: string | null;
  current_latency_ms: number | null;
  queue_depth: number;
  current_error: string | null;
  uptime_seconds: number;
  downtime_seconds: number;
  connection_failures: number;
  failed_orders: number;
  retry_rate: number | null;
  timeout_rate: number | null;
  avg_latency_ms: number | null;
  p50_latency_ms: number | null;
  p95_latency_ms: number | null;
  avg_order_duration_seconds: number | null;
  avg_result_turnaround_seconds: number | null;
  orders_received: number;
  completed_orders: number;
  results_received: number;
  tests_processed: number;
  tests_per_hour: number | null;
  inbound_messages: number;
  outbound_messages: number;
  ack_messages: number;
  connection_events: AnalyzerHealthEvent[];
  failed_attempts: AnalyzerHealthAttempt[];
  hourly_trends: AnalyzerTrendPoint[];
};

export type AnalyzerDashboard = {
  window_start: string;
  window_end: string;
  summary: {
    total_analyzers: number;
    online: number;
    degraded: number;
    offline: number;
    overall_uptime_percent: number | null;
    order_success_percent: number | null;
    result_success_percent: number | null;
    open_alerts: number;
  };
  analyzers: AnalyzerDashboardRow[];
  trends: AnalyzerTrendPoint[];
  alerts: AnalyzerAlert[];
  detail: AnalyzerDashboardDetail | null;
};

export function formatPercent(value: number | null | undefined): string {
  return value == null ? "—" : `${value.toFixed(1)}%`;
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  return value == null ? "—" : value.toFixed(digits);
}

export function formatWhen(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : parsed.toLocaleString();
}
