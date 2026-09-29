import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OUTLAW FORGE | Precision 3D Mesh Engine & CAD Workbench",
  description: "Next-generation high-performance 3D CAD modeler, mesh repair, and additive manufacturing slicing workbench.",
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
