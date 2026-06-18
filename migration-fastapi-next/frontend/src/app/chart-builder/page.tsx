'use client';

import { useEffect, useMemo, useState } from 'react';
import { ChartRenderer } from '@/components/ChartRenderer';
import { apiFetch } from '@/lib/api';
import type { ChartConfig, ChartPreview, JiraProject } from '@/types';

const creatorTypes = ['Gráfico X-Y', 'Gráfico Agregado', 'Indicador (KPI)', 'Tabela Dinâmica', 'Gráfico de Tendência'] as const;

export default function ChartBuilderPage() {
  const [projects, setProjects] = useState<JiraProject[]>([]);
  const [projectKey, setProjectKey] = useState('');
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [preview, setPreview] = useState<ChartPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<ChartConfig>({
    creator_type: 'Gráfico Agregado',
    type: 'barra',
    agg: 'Contagem',
    measure_selection: 'Contagem de Issues',
    source_type: 'visual',
    columns: [],
    filters: [],
  });

  const columns = useMemo(() => (rows.length ? Object.keys(rows[0]) : []), [rows]);

  useEffect(() => {
    apiFetch<JiraProject[]>('/api/jira/projects')
      .then(setProjects)
      .catch((err) => setError(err.message));
  }, []);

  async function loadProjectData() {
    setError(null);
    const data = await apiFetch<{ rows: Record<string, unknown>[]; total: number }>('/api/jira/project-data', {
      method: 'POST',
      body: JSON.stringify({ project_key: projectKey }),
    });
    setRows(data.rows);
  }

  async function previewChart() {
    setError(null);
    const data = await apiFetch<ChartPreview>('/api/charts/preview', {
      method: 'POST',
      body: JSON.stringify({ project_key: projectKey, rows, config }),
    });
    setPreview(data);
  }

  async function saveChart() {
    setError(null);
    await apiFetch('/api/charts/save', {
      method: 'POST',
      body: JSON.stringify({ project_key: projectKey, config }),
    });
    alert('Gráfico salvo com sucesso.');
  }

  return (
    <div className="stack">
      <section className="card stack">
        <h1>Construir Gráficos</h1>
        <p>Construtor visual migrado para Next.js, consumindo dados do Jira via FastAPI.</p>
        {error && <strong>{error}</strong>}
        <div className="row">
          <select value={projectKey} onChange={(event) => setProjectKey(event.target.value)}>
            <option value="">Selecione um projeto</option>
            {projects.map((project) => <option key={project.key} value={project.key}>{project.name} ({project.key})</option>)}
          </select>
          <button onClick={loadProjectData} disabled={!projectKey}>Carregar dados Jira</button>
          <span>{rows.length} issues carregadas</span>
        </div>
      </section>

      <section className="card stack">
        <h2>Configuração da Visualização</h2>
        <div className="grid">
          <label className="stack">
            Tipo de visualização
            <select value={config.creator_type} onChange={(event) => setConfig({ ...config, creator_type: event.target.value as ChartConfig['creator_type'] })}>
              {creatorTypes.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
          <label className="stack">
            Título
            <input value={config.title ?? ''} onChange={(event) => setConfig({ ...config, title: event.target.value })} placeholder="Título do gráfico" />
          </label>

          {config.creator_type === 'Gráfico X-Y' && (
            <>
              <label className="stack">Eixo X<select value={config.x ?? ''} onChange={(event) => setConfig({ ...config, x: event.target.value })}><option />{columns.map((c) => <option key={c}>{c}</option>)}</select></label>
              <label className="stack">Eixo Y<select value={config.y ?? ''} onChange={(event) => setConfig({ ...config, y: event.target.value })}><option />{columns.map((c) => <option key={c}>{c}</option>)}</select></label>
              <label className="stack">Formato<select value={config.type ?? 'dispersão'} onChange={(event) => setConfig({ ...config, type: event.target.value })}><option value="dispersão">Dispersão</option><option value="linha">Linha</option></select></label>
            </>
          )}

          {config.creator_type === 'Gráfico Agregado' && (
            <>
              <label className="stack">Dimensão<select value={config.dimension ?? ''} onChange={(event) => setConfig({ ...config, dimension: event.target.value })}><option />{columns.map((c) => <option key={c}>{c}</option>)}</select></label>
              <label className="stack">Medida<select value={config.measure_selection ?? 'Contagem de Issues'} onChange={(event) => setConfig({ ...config, measure_selection: event.target.value, measure: event.target.value })}><option>Contagem de Issues</option>{columns.map((c) => <option key={c}>{c}</option>)}</select></label>
              <label className="stack">Cálculo<select value={config.agg ?? 'Contagem'} onChange={(event) => setConfig({ ...config, agg: event.target.value })}><option>Contagem</option><option>Soma</option><option>Média</option><option>Contagem Distinta</option></select></label>
              <label className="stack">Formato<select value={config.type ?? 'barra'} onChange={(event) => setConfig({ ...config, type: event.target.value })}><option value="barra">Barras</option><option value="barra_horizontal">Barras Horizontais</option><option value="linha_agregada">Linhas</option><option value="pizza">Pizza</option><option value="treemap">Treemap</option><option value="funil">Funil</option><option value="tabela">Tabela</option></select></label>
            </>
          )}

          {config.creator_type === 'Indicador (KPI)' && (
            <>
              <label className="stack">Fonte<select value={config.source_type ?? 'visual'} onChange={(event) => setConfig({ ...config, source_type: event.target.value as 'visual' | 'jql' })}><option value="visual">Dados carregados</option><option value="jql">Consulta JQL</option></select></label>
              {config.source_type === 'jql' ? <label className="stack">JQL A<textarea value={config.jql_a ?? ''} onChange={(event) => setConfig({ ...config, jql_a: event.target.value })} /></label> : <label className="stack">Medida<select value={config.measure_selection ?? 'Contagem de Issues'} onChange={(event) => setConfig({ ...config, measure_selection: event.target.value, measure: event.target.value })}><option>Contagem de Issues</option>{columns.map((c) => <option key={c}>{c}</option>)}</select></label>}
            </>
          )}
        </div>
        <div className="row">
          <button onClick={previewChart} disabled={!projectKey}>Pré-visualizar</button>
          <button onClick={saveChart} disabled={!projectKey} className="secondary">Salvar no dashboard</button>
        </div>
      </section>

      <section className="card stack">
        <h2>Pré-visualização</h2>
        <ChartRenderer preview={preview} />
      </section>
    </div>
  );
}
