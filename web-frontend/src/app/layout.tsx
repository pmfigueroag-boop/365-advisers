import type { Metadata } from "next";
import { Inter, Playfair_Display, Geist_Mono } from "next/font/google";
import "./globals.css";
import "./print.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const playfair = Playfair_Display({
  variable: "--font-playfair",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "365 Advisers",
  description: "Institutional-grade multi-agent investment intelligence terminal. AI-powered analysis, portfolio construction, and risk management.",
  keywords: ["investment", "analysis", "portfolio", "AI", "institutional", "365 Advisers"],
  icons: {
    icon: "/favicon.png",
    apple: "/logo-100.png",
  },
  manifest: "/manifest.json",
  openGraph: {
    title: "365 Advisers — Investment Intelligence Terminal",
    description: "Institutional-grade multi-agent investment intelligence terminal.",
    siteName: "365 Advisers",
    images: [{ url: "/logo-200.jpg", width: 200, height: 200 }],
    type: "website",
  },
  twitter: {
    card: "summary",
    title: "365 Advisers",
    description: "Institutional-grade investment intelligence terminal.",
    images: ["/logo-200.jpg"],
  },
  other: {
    "theme-color": "#060913",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${inter.variable} ${playfair.variable} ${geistMono.variable} font-sans antialiased`}
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
