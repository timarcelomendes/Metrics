export type JiraConnection = {
  id: string;
  name: string;
  jira_url: string;
  jira_email: string;
  active: boolean;
};

export type JiraProject = {
  name: string;
  key: string;
};

export type ChartFilter = {
  field: string;
  operator: string;
  value: unknown;
};

export type ChartConfig = {
  id?: string;
  title?: string;
  creator_type: 'Gráfico X-Y' | 'Gráfico Agregado' | 'Indicador (KPI)' | 'Tabela Dinâmica' | 'Gráfico de Tendência';
  type?: string;
  x?: string;
  y?: string;
  dimension?: string;
  measure?: string;
  measure_selection?: string;
  agg?: string;
  columns?: string[];
  filters?: ChartFilter[];
  color_by?: string;
  size_by?: string;
  source_type?: 'visual' | 'jql';
  jql_a?: string;
  jql_b?: string;
  formula?: string;
};

export type ChartPreview = {
  title?: string;
  kind: 'plotly' | 'table' | 'kpi' | 'empty';
  plotly_json?: { data: unknown[]; layout: Record<string, unknown> };
  table?: Record<string, unknown>[];
  kpi?: Record<string, unknown>;
  row_count: number;
};
