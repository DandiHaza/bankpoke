import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "BankPoke",
  description: "Category trend focused personal finance dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body
        style={{
          fontFamily: "sans-serif",
          margin: 0,
          padding: 24,
          background: "linear-gradient(180deg, #f4f8ff 0%, #eef7f2 100%)",
          color: "#1f2a44",
          minHeight: "100vh",
        }}
      >
        {children}
      </body>
    </html>
  );
}
