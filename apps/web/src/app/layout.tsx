import type { Metadata } from "next";
import { Fraunces, Instrument_Sans } from "next/font/google";
import { AppProviders } from "@/lib/api";
import { themeInitScript } from "@/lib/theme";
import "./globals.css";

const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces", weight: ["500", "600"] });
const instrument = Instrument_Sans({ subsets: ["latin"], variable: "--font-instrument", weight: ["400", "500", "600"] });

export const metadata: Metadata = {
  title: "Larder",
  description: "Pantry-first meal planning for your kitchen.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${fraunces.variable} ${instrument.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
