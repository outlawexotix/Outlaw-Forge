import "@/lib/react-compat";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OUTLAW FORGE | Precision 3D Mesh Engine & CAD Workbench",
  description:
    "A practical 3D-print preparation workbench for mesh inspection, repair, transformation, arrangement, and printer-aware export.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark h-full">
      <body className="h-full bg-[#090d16] text-slate-100 antialiased overflow-hidden flex flex-col">
        {children}
      </body>
    </html>
  );
}
