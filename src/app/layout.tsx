import type { Metadata } from 'next';
import Link from 'next/link';
import './styles.css';

export const metadata: Metadata = {
  title: 'Gauge Metrics',
  description: 'Gauge Metrics Web',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>
        <aside className="sidebar">
          <strong>Gauge Metrics</strong>
          <Link href="/">Dashboard</Link>
          <Link href="/jira-connections">Conexões Jira</Link>
          <Link href="/chart-builder">Construir Gráficos</Link>
        </aside>
        <main className="content">{children}</main>
      </body>
    </html>
  );
}
