import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Performance AI",
  description: "AI-assisted civil site planning for concept layouts, grading, drainage, and utilities.",
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
