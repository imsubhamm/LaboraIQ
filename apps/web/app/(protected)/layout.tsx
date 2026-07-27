import { Shell } from "@/components/shell";
export default function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return <Shell>{children}</Shell>;
}

