import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "Forge SDLC",
  description: "Pipeline multiagente de SDLC",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="pt-BR">
      <body
        style={{
          fontFamily: "system-ui, sans-serif",
          margin: 0,
          background: "#0f1115",
          color: "#e6e6e6",
        }}
      >
        {children}
      </body>
    </html>
  );
}
