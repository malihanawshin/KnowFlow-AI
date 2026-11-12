import type { Metadata } from "next";
import "@fontsource-variable/inter/wght.css";
import "@fontsource/instrument-serif/400.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "KnowFlow AI",
  description: "Ask questions about your PDFs and trace answers to the source.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
