import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import "./industrial.css";

export const metadata: Metadata = { title: "TelemetryX | Industrial Operations", description: "Machinery monitoring and accountable maintenance workspaces" };

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
