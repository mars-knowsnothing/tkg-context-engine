import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TKG Context Engine",
  description: "Time-aware Knowledge Graph Context Management System",
  keywords: ["knowledge graph", "AI", "context management", "temporal", "graphiti"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} antialiased gradient-bg min-h-screen`}>
        {children}
      </body>
    </html>
  );
}
