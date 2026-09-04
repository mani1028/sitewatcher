import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SiteWatch",
  description: "Lightweight multi-project website monitoring with email alerts",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
