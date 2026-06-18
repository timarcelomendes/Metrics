from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class JiraConnectionCreate(BaseModel):
    name: str = Field(min_length=2)
    jira_url: HttpUrl
    jira_email: str
    api_token: str = Field(min_length=10)


class JiraConnectionOut(BaseModel):
    id: str
    name: str
    jira_url: str
    jira_email: str
    active: bool = False


class ActivateConnectionRequest(BaseModel):
    connection_id: str


class ProjectDataRequest(BaseModel):
    project_key: str
    jql_filter: str | None = None
    standard_fields: list[str] = []
    custom_fields: list[str] = []


class ChartFilter(BaseModel):
    field: str
    operator: str
    value: Any


class ChartConfig(BaseModel):
    id: str | None = None
    title: str | None = None
    creator_type: Literal[
        "Gráfico X-Y",
        "Gráfico Agregado",
        "Indicador (KPI)",
        "Tabela Dinâmica",
        "Gráfico de Tendência",
    ]
    type: str | None = None
    x: str | None = None
    y: str | None = None
    dimension: str | None = None
    secondary_dimension: str | None = None
    measure: str | None = None
    measure_selection: str | None = None
    agg: str | None = None
    columns: list[str] = []
    filters: list[ChartFilter] = []
    color_by: str | None = None
    size_by: str | None = None
    top_n: int | None = None
    sort_by: str | None = None
    show_as_percentage: bool = False
    show_data_labels: bool = False
    source_type: Literal["visual", "jql"] = "visual"
    jql_a: str | None = None
    jql_b: str | None = None
    jql_c: str | None = None
    formula: str | None = None
    kpi_decimal_places: int = 2
    kpi_format_as_percentage: bool = False


class ChartPreviewRequest(BaseModel):
    project_key: str
    config: ChartConfig
    rows: list[dict[str, Any]] | None = None


class ChartPreviewResponse(BaseModel):
    title: str | None
    kind: str
    plotly_json: dict[str, Any] | None = None
    table: list[dict[str, Any]] | None = None
    kpi: dict[str, Any] | None = None
    row_count: int


class DashboardChartSaveRequest(BaseModel):
    project_key: str
    dashboard_id: str = "main_dashboard"
    tab_name: str = "Geral"
    config: ChartConfig


class JqlCountRequest(BaseModel):
    jql: str
