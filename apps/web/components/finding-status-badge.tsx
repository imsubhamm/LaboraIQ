export function FindingStatusBadge({ status }: { status: string }) {
  const tone =
    status === "CLOSED"
      ? "healthy"
      : status === "IN_PROGRESS" || status === "CAPA_PENDING"
        ? "warning"
        : status === "SCHEDULED" || status === "DRAFT"
          ? "degraded"
          : "critical";
  return (
    <span className={`health-badge ${tone}`} role="status">
      {status.replaceAll("_", " ")}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const tone =
    severity === "CRITICAL" ? "critical" : severity === "MAJOR" ? "warning" : severity === "MINOR" ? "degraded" : "healthy";
  return (
    <span className={`health-badge ${tone}`} role="status">
      {severity}
    </span>
  );
}

export function CapaStatusBadge({ status }: { status: string }) {
  const tone = status === "CLOSED" ? "healthy" : status === "NONE" ? "degraded" : "warning";
  return (
    <span className={`health-badge ${tone}`} role="status">
      {status.replaceAll("_", " ")}
    </span>
  );
}
