import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { can } from "@/lib/auth";
import { isSessionValid } from "@/proxy";
import { ResourcePage } from "@/components/resource-page";
import { SpecimenBarcode } from "@/components/specimen-barcode";

vi.mock("next/navigation", () => ({ usePathname: () => "/organizations" }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: vi.fn().mockResolvedValue({items: [], total: 0, limit: 25, offset: 0}) };
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
