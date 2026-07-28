import { redirect } from "next/navigation";

export default function LegacyClientIntakePage() {
  redirect("/patients/new");
}
