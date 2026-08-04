import { ResourcePage } from "@/components/resource-page";

export default function PatientsPage() {
  return <ResourcePage
    title="Patients"
    description="Registered patient identities and laboratory visit history."
    endpoint="patients"
    emptyMessage="Registered patients will appear here after their first laboratory request."
    columns={[
      { key: "patient_number", label: "Patient ID" },
      { key: "full_name", label: "Patient name" },
      { key: "phone", label: "Phone" },
      { key: "sex", label: "Sex" },
      { key: "blood_group", label: "Blood group" },
      { key: "visit_count", label: "Visits" },
      { key: "last_visit_at", label: "Last visit" },
    ]}
  />;
}
