'use client';

import dynamic from 'next/dynamic';
import type { ChartPreview } from '@/types';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export function ChartRenderer({ preview }: { preview: ChartPreview | null }) {
  if (!preview) {
    return <div className="empty">Carregue dados e clique em pré-visualizar.</div>;
  }

  if (preview.kind === 'kpi') {
    return (
      <div className="kpi-card">
        <span>{preview.title ?? 'Indicador'}</span>
        <strong>{String(preview.kpi?.value ?? 0)}</strong>
        <small>{preview.row_count} linhas consideradas</small>
      </div>
    );
  }

  if (preview.kind === 'table') {
    const rows = preview.table ?? [];
    const columns = rows.length ? Object.keys(rows[0]) : [];
    return (
      <div className="table-wrap">
        <table>
          <thead>
            <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
          </thead>
          <tbody>
            {rows.slice(0, 100).map((row, index) => (
              <tr key={index}>{columns.map((column) => <td key={column}>{String(row[column] ?? '')}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (preview.kind === 'plotly' && preview.plotly_json) {
    return <Plot data={preview.plotly_json.data as never[]} layout={preview.plotly_json.layout} style={{ width: '100%', height: '560px' }} useResizeHandler />;
  }

  return <div className="empty">Configuração incompleta para gerar gráfico.</div>;
}
