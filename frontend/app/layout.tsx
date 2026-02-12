import "./globals.css";
import type { ReactNode } from "react";
import { Navbar } from "../components/Navbar";
import { ToastProvider } from "../components/ToastProvider";

export const metadata = {
  title: "CodePilot – Engineering-grade AI",
  description: "Production-ready frontend for the CodePilot autonomous coding agent."
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-[#0f172a] text-slate-100 antialiased gradient-bg">
        <ToastProvider>
          <Navbar />
          <div className="mx-auto max-w-4xl px-4 pb-10 pt-6">{children}</div>
        </ToastProvider>
      </body>
    </html>
  );
}

