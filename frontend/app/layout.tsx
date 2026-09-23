import type { Metadata } from "next";
import type { ReactNode } from "react";

import { NavShell } from "@/components/NavShell";

import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mini NMS",
  description: "Network Monitoring System",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <NavShell>{children}</NavShell>
        </Providers>
      </body>
    </html>
  );
}
