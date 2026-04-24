import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Market Intelligence OS",
  description: "Supplier risk and pricing intelligence MVP"
};

const nav = [
  ["/dashboard", "Dashboard"],
  ["/suppliers", "Suppliers"],
  ["/products", "Products"],
  ["/alerts", "Alerts"],
  ["/agent-runs", "Agent Runs"]
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <header className="border-b-2 border-ink bg-paper/90 backdrop-blur">
            <div className="mx-auto flex max-w-7xl flex-col gap-4 px-5 py-5 md:flex-row md:items-end md:justify-between">
              <Link href="/dashboard" className="group">
                <p className="text-xs font-black uppercase tracking-[0.28em] text-clay">AI Market Intelligence OS</p>
                <h1 className="text-3xl font-black leading-none md:text-5xl">Commercial nerve center</h1>
              </Link>
              <nav className="flex flex-wrap gap-2">
                {nav.map(([href, label]) => (
                  <Link key={href} href={href} className="border-2 border-ink bg-[#fffaf0] px-3 py-2 text-sm font-black hover:bg-brass">
                    {label}
                  </Link>
                ))}
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-5 py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}

