import type { Metadata, Viewport } from "next";
import { SpeedInsights } from "@vercel/speed-insights/next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://civoraai.com"),
  title: "Civora AI — Civil Site Planning Review",
  description:
    "Civil site planning workspace for traceable concepts, review-required engineering signals, and engineer-review packages.",
  applicationName: "Civora",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon.png", type: "image/png", sizes: "512x512" },
    ],
    apple: [{ url: "/apple-icon.png", sizes: "180x180", type: "image/png" }],
  },
  openGraph: {
    title: "Civora AI — Civil Site Planning Review",
    description:
      "Civil site planning workspace for traceable concepts, review-required engineering signals, and engineer-review packages.",
    siteName: "Civora",
    type: "website",
    images: [
      {
        url: "/brand/civora-primary-mark.png",
        width: 1254,
        height: 1254,
        alt: "Civora",
      },
    ],
  },
  twitter: {
    card: "summary",
    title: "Civora AI — Civil Site Planning Review",
    description:
      "Civil site planning workspace for traceable concepts, review-required engineering signals, and engineer-review packages.",
    images: ["/brand/civora-primary-mark.png"],
  },
};

export const viewport: Viewport = {
  themeColor: "#f6f7f9",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const enableSpeedInsights = Boolean(process.env.VERCEL);

  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        {children}
        {enableSpeedInsights ? <SpeedInsights /> : null}
      </body>
    </html>
  );
}
