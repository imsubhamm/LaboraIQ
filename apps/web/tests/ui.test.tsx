import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnalyzerAlertList } from "@/components/analyzer-alert-list";
import { AnalyzerHealthKpis } from "@/components/analyzer-health-kpis";
import { AnalyzerHealthPanel } from "@/components/analyzer-health-panel";
import { AnalyzerViewTabs } from "@/components/analyzer-view-tabs";
import { AnalyzerHealthTable } from "@/components/analyzer-health-table";
import { HealthStatusBadge } from "@/components/health-status-badge";
import { TrendChart } from "@/components/trend-chart";
import { can } from "@/lib/auth";
import { apiBaseUrl } from "@/lib/auth-cookies";
import { isSessionValid } from "@/proxy";
import { ResourcePage } from "@/components/resource-page";
import { SpecimenBarcode } from "@/components/specimen-barcode";

vi.mock("next/navigation", () => ({
  usePathname: () => "/organizations",
  useSearchParams: () => new URLSearchParams()
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: vi.fn().mockResolvedValue({items: [], total: 0, limit: 25, offset: 0}) };
});

afterEach(() => {
  cleanup();
});

describe("apiBaseUrl for server route handlers", () => {
  afterEach(() => {
    delete process.env.INTERNAL_API_URL;
    delete process.env.INTERNAL_API_ORIGIN;
    delete process.env.NEXT_PUBLIC_API_URL;
  });

  it("resolves relative NEXT_PUBLIC_API_URL against the internal origin", () => {
    process.env.NEXT_PUBLIC_API_URL = "/api/v1";
    expect(apiBaseUrl()).toBe("http://127.0.0.1:8000/api/v1");
  });

  it("prefers INTERNAL_API_URL when set", () => {
    process.env.NEXT_PUBLIC_API_URL = "/api/v1";
    process.env.INTERNAL_API_URL = "http://127.0.0.1:8000/api/v1";
    expect(apiBaseUrl()).toBe("http://127.0.0.1:8000/api/v1");
  });
});

describe("platform administration UI", () => {
  it("rejects missing and expired sessions", async () => {
    expect(await isSessionValid(undefined, 100)).toBe(false);
    expect(await isSessionValid("99", 100)).toBe(false);
    expect(await isSessionValid("101", 100)).toBe(true);
  });

  it("uses permission-aware actions", () => {
    expect(can("organization.manage", new Set(["organization.read"]))).toBe(false);
  });

  it("shows a stable empty organization state and form action", async () => {
    render(<ResourcePage title="Organizations" description="Tenant configuration" endpoint="organizations"
      emptyMessage="Create a tenant" managePermission="organization.manage"
      columns={[{key:"name",label:"Name"}]} fields={[{name:"name",label:"Organization name"}]}/>);
    expect(await screen.findByText("No records found")).toBeInTheDocument();
    expect(screen.getByRole("button", {name: /Add Organization/i})).toBeInTheDocument();
  });

  it("renders API errors", async () => {
    const { api } = await import("@/lib/api");
    vi.mocked(api).mockRejectedValueOnce(new Error("Service unavailable"));
    render(<ResourcePage title="Audit events" description="Evidence" endpoint="audit-events"
      emptyMessage="No events" columns={[{key:"action",label:"Action"}]}/>);
    expect(await screen.findByText("Service unavailable")).toBeInTheDocument();
  });

  it("renders a real Code 128 specimen barcode for the exact identifier", async () => {
    const value = "LQ0805063919C2AA0601";
    const { container } = render(<SpecimenBarcode value={value}/>);
    const barcode = await screen.findByRole("img", {name: `Code 128 specimen barcode ${value}`});
    expect(barcode).toHaveAttribute("data-barcode-value", value);
    expect(container.querySelectorAll("svg rect").length).toBeGreaterThan(10);
  });
});

const emptyDashboard = {
  window_start: "2026-09-08T00:00:00Z",
  window_end: "2026-09-08T01:00:00Z",
  summary: {
    total_analyzers: 0,
    online: 0,
    degraded: 0,
    offline: 0,
    overall_uptime_percent: null,
    order_success_percent: null,
    result_success_percent: null,
    open_alerts: 0
  },
  analyzers: [],
  trends: [],
  alerts: [],
  detail: null
};

describe("analyzer machine health UI", () => {
  it("renders KPI summary values", () => {
    render(
      <AnalyzerHealthKpis
        summary={{
          total_analyzers: 4,
          online: 2,
          degraded: 1,
          offline: 1,
          overall_uptime_percent: 91.2,
          order_success_percent: 80,
          result_success_percent: null,
          open_alerts: 3
        }}
      />
    );
    expect(screen.getByText("Total analyzers")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("91.2%")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("labels healthy, degraded, and critical states with text", () => {
    const { rerender } = render(<HealthStatusBadge status="healthy" score={96} />);
    expect(screen.getByRole("status")).toHaveTextContent(/healthy/i);
    rerender(<HealthStatusBadge status="degraded" score={67} />);
    expect(screen.getByRole("status")).toHaveTextContent(/degraded/i);
    rerender(<HealthStatusBadge status="critical" score={20} />);
    expect(screen.getByRole("status")).toHaveTextContent(/critical/i);
  });

  it("shows an empty analyzer health table", () => {
    render(
      <AnalyzerHealthTable rows={[]} emptyMessage="Configure an analyzer" onSelect={() => undefined} />
    );
    expect(screen.getByText("No analyzer health data")).toBeInTheDocument();
    expect(screen.getByText("Configure an analyzer")).toBeInTheDocument();
  });

  it("renders trend empty state and alert empty state", () => {
    render(<TrendChart title="Availability over time" points={[]} valueKey="availability_percent" emptyLabel="No availability samples." />);
    expect(screen.getByText("No availability samples.")).toBeInTheDocument();
    render(<AnalyzerAlertList alerts={[]} emptyMessage="No derived alerts in this window." />);
    expect(screen.getByText("No derived alerts in this window.")).toBeInTheDocument();
  });

  it("loads health filters and empty dashboard from the API", async () => {
    const { api } = await import("@/lib/api");
    vi.mocked(api).mockImplementation(async (path: string) => {
      if (String(path).includes("analyzer-dashboard")) {
        return emptyDashboard;
      }
      return { items: [], total: 0, limit: 25, offset: 0 };
    });
    render(<AnalyzerHealthPanel branches={[{ id: "b1", code: "KOL", name: "Kolkata" }]} />);
    expect(await screen.findByLabelText("Filter by branch")).toBeInTheDocument();
    expect(await screen.findByText("No analyzer health data")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply filters" })).toBeInTheDocument();
  });

  it("exposes Machine health as a real navigable link", () => {
    render(<AnalyzerViewTabs view="config" />);
    expect(screen.getByRole("link", { name: "Machine health" })).toHaveAttribute("href", "/analyzers?view=health");
    expect(screen.getByRole("link", { name: "Configuration" })).toHaveAttribute("href", "/analyzers");
  });
});
