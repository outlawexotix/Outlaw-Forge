import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Outlaw Forge | Local 3D Print Workbench",
  description:
    "Local-first 3D-print preparation workbench for mesh inspection, printer-aware checks, deterministic repair and preparation, and export through a local geometry service.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark h-full" suppressHydrationWarning>
      <body className="h-full bg-neutral-950 text-neutral-100 font-sans antialiased overflow-hidden flex flex-col">
        {children}
      </body>
    </html>
  );
}
