import "@/lib/react-compat";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Outlaw Forge | Local 3D Print Workbench",
  description:
    "Local-first desktop software for mesh inspection, repair, print-readiness analysis, preparation, and export.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark h-full">
      <body className="h-full bg-neutral-950 text-neutral-100 font-sans antialiased overflow-hidden flex flex-col">
        {children}
      </body>
    </html>
  );
}
