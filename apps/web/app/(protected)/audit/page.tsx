import { ResourcePage } from "@/components/resource-page";
export default function Page() { return <ResourcePage title="Audit events" description="Immutable, tenant-scoped evidence for safety-critical actions." endpoint="audit-events" emptyMessage="Events are generated automatically by controlled actions." columns={[{key:"occurred_at",label:"Timestamp"},{key:"event_type",label:"Event"},{key:"entity_type",label:"Entity"},{key:"action",label:"Action"},{key:"correlation_id",label:"Correlation ID"}]}/>; }

