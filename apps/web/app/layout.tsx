import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "LaboraIQ Control Centre", template: "%s · LaboraIQ" },
  description: "Secure laboratory operations foundation and configuration control.",
  applicationName: "LaboraIQ",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

