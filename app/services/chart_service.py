from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import plotly.express as px

from app.models.schemas import ChartConfig, ChartPreviewResponse
from app.services.jira_service import get_jql_issue_count


def apply_filters(df: pd.DataFrame, filters: list[Any]) -> pd.DataFrame:
    output = df.copy()
    for item in filters or []:
        field = item.field
        operator = item.operator
        value = item.value
        if field not in output.columns:
            continue
        if operator == "está em":
            values = value if isinstance(value, list) else [value]
            output = output[output[field].isin(values)]
        elif operator == "não está em":
            values = value if isinstance(value, list) else [value]
            output = output[~output[field].isin(values)]
        elif operator == "é igual a":
            output = output[output[field] == value]
        elif operator == "não é igual a":
            output = output[output[field] != value]
        elif operator == "maior que":
            output = output[pd.to_numeric(output[field], errors="coerce") > float(value)]
        elif operator == "menor que":
            output = output[pd.to_numeric(output[field], errors="coerce") < float(value)]
        elif operator == "entre" and isinstance(value, (list, tuple)) and len(value) == 2:
            numeric = pd.to_numeric(output[field], errors="coerce")
            output = output[(numeric >= float(value[0])) & (numeric <= float(value[1]))]
        elif operator == "Períodos Relativos":
            days = int(str(value).replace("Últimos", "").replace("dias", "").strip() or 30)
            series = pd.to_datetime(output[field], errors="coerce")
            output = output[series >= pd.Timestamp(datetime.utcnow() - timedelta(days=days))]
    return output


def aggregate(df: pd.DataFrame, dimension: str, measure: str | None, agg: str | None) -> pd.DataFrame:
    if not measure or measure == "Contagem de Issues":
        return df.groupby(dimension, dropna=False).size().reset_index(name="Contagem de Issues")
    if agg == "Média":
        return df.groupby(dimension, dropna=False)[measure].mean(numeric_only=True).reset_index()
    if agg == "Contagem Distinta":
        return df.groupby(dimension, dropna=False)[measure].nunique().reset_index()
    if agg == "Contagem":
        return df.groupby(dimension, dropna=False)[measure].count().reset_index()
    return df.groupby(dimension, dropna=False)[measure].sum(numeric_only=True).reset_index()


def build_chart_preview(rows: list[dict[str, Any]], config: ChartConfig, jira_client: Any | None = None) -> ChartPreviewResponse:
    df = pd.DataFrame(rows or [])
    df = apply_filters(df, config.filters)

    if config.creator_type == "Indicador (KPI)" and config.source_type == "jql":
        if jira_client is None:
            raise ValueError("jira_client é obrigatório para KPI por JQL.")
        a = get_jql_issue_count(jira_client, config.jql_a or "")
        value = float(a)
        return ChartPreviewResponse(title=config.title, kind="kpi", kpi={"value": round(value, config.kpi_decimal_places), "a": a}, row_count=len(df))

    if config.creator_type == "Indicador (KPI)":
        measure = config.measure or config.measure_selection or "Contagem de Issues"
        if measure == "Contagem de Issues" or measure not in df.columns:
            value = len(df)
        else:
            value = pd.to_numeric(df[measure], errors="coerce").sum()
        return ChartPreviewResponse(title=config.title, kind="kpi", kpi={"value": round(float(value), config.kpi_decimal_places)}, row_count=len(df))

    if config.creator_type == "Tabela Dinâmica":
        columns = [col for col in config.columns if col in df.columns]
        table = df[columns].fillna("").to_dict("records") if columns else df.fillna("").to_dict("records")
        return ChartPreviewResponse(title=config.title, kind="table", table=table[:500], row_count=len(df))

    if config.creator_type == "Gráfico Agregado":
        dimension = config.dimension
        measure = config.measure or config.measure_selection or "Contagem de Issues"
        if not dimension or dimension not in df.columns:
            return ChartPreviewResponse(title=config.title, kind="empty", row_count=len(df))
        grouped = aggregate(df, dimension, None if measure == "Contagem de Issues" else measure, config.agg)
        y_col = measure if measure in grouped.columns else "Contagem de Issues"
        chart_type = config.type or "barra"
        if chart_type == "barra_horizontal":
            fig = px.bar(grouped, x=y_col, y=dimension, orientation="h", title=config.title)
        elif chart_type == "linha_agregada":
            fig = px.line(grouped, x=dimension, y=y_col, title=config.title)
        elif chart_type == "pizza":
            fig = px.pie(grouped, names=dimension, values=y_col, title=config.title)
        elif chart_type == "treemap":
            fig = px.treemap(grouped, path=[dimension], values=y_col, title=config.title)
        elif chart_type == "funil":
            fig = px.funnel(grouped, x=y_col, y=dimension, title=config.title)
        elif chart_type == "tabela":
            return ChartPreviewResponse(title=config.title, kind="table", table=grouped.fillna("").to_dict("records"), row_count=len(df))
        else:
            fig = px.bar(grouped, x=dimension, y=y_col, title=config.title)
        return ChartPreviewResponse(title=config.title, kind="plotly", plotly_json=fig.to_dict(), row_count=len(df))

    if config.creator_type in {"Gráfico X-Y", "Gráfico de Tendência"}:
        if not config.x or not config.y or config.x not in df.columns or config.y not in df.columns:
            return ChartPreviewResponse(title=config.title, kind="empty", row_count=len(df))
        if config.creator_type == "Gráfico de Tendência" or config.type == "linha":
            fig = px.line(df, x=config.x, y=config.y, title=config.title)
        else:
            fig = px.scatter(df, x=config.x, y=config.y, title=config.title)
        return ChartPreviewResponse(title=config.title, kind="plotly", plotly_json=fig.to_dict(), row_count=len(df))

    return ChartPreviewResponse(title=config.title, kind="empty", row_count=len(df))
