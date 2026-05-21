import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Darts Tournament Platform",
  description: "Participate in darts tournaments and track your statistics",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
