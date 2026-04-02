import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Civora AI — AI-Powered Civil Engineering Design Platform",
  description:
    "Engineering-grade civil site planning with coordinated layouts, grading, drainage, utilities, profiles, and deliverables.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
