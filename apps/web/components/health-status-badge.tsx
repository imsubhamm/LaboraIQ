import { Activity, AlertTriangle, HeartPulse, ShieldAlert } from "lucide-react";

const ICONS = {
  healthy: HeartPulse,
  warning: AlertTriangle,
  degraded: ShieldAlert,
  critical: ShieldAlert,
  offline: Activity
} as const;

export function HealthStatusBadge({ status, score }: { status: string; score?: number }) {
  const key = status in ICONS ? (status as keyof typeof ICONS) : "offline";
  const Icon = ICONS[key];
  const label = status.replaceAll("_", " ");
  return (
    <span className={`health-badge ${status}`} role="status" aria-label={`Health ${label}${score != null ? ` ${score}` : ""}`}>
      <Icon size={14} aria-hidden="true" />
      <strong>{label}</strong>
      {score != null && <small>{score}</small>}
    </span>
  );
}
