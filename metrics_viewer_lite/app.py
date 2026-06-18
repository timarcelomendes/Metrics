from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).parent
SAMPLE_DATA = APP_DIR / "data" / "sample_metrics.csv"
REQUIRED_COLUMNS = {"date", "value"}
OPTIONAL_DEFAULTS = {
    "project": "Projeto único",
    "owner": "Responsável não informado",
    "metric": "Valor",
}


st.set_page_config(
    page_title="Metrics Viewer Lite",
    page_icon="📊",
    layout="wide",
)


@st.cache_data(show_spinner=False)
def load_csv(file_source) -> pd.DataFrame:
    """Load metrics data from an uploaded file or local sample CSV."""
    return pd.read_csv(file_source)


def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize the minimum schema required for charts."""
    normalized = df.copy()
    normalized.columns = [column.strip().lower() for column in normalized.columns]

    missing = REQUIRED_COLUMNS.difference(normalized.columns)
    if missing:
        missing_columns = ", ".join(sorted(missing))
        raise ValueError(f"Colunas obrigatórias ausentes: {missing_columns}")

    for column, default_value in OPTIONAL_DEFAULTS.items():
        if column not in normalized.columns:
            normalized[column] = default_value

    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    normalized["value"] = pd.to_numeric(normalized["value"], errors="coerce")
    normalized = normalized.dropna(subset=["date", "value"])

    if normalized.empty:
        raise ValueError("Nenhum registro válido foi encontrado após normalizar datas e valores.")

    return normalized.sort_values("date")


def filter_data(df: pd.DataFrame) -> pd.DataFrame:
    """Render sidebar filters and return the filtered dataset."""
    st.sidebar.header("Filtros")

    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    selected_range = st.sidebar.date_input(
        "Período",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    projects = st.sidebar.multiselect(
        "Projetos",
        options=sorted(df["project"].dropna().unique()),
        default=sorted(df["project"].dropna().unique()),
    )
    owners = st.sidebar.multiselect(
        "Responsáveis",
        options=sorted(df["owner"].dropna().unique()),
        default=sorted(df["owner"].dropna().unique()),
    )
    metrics = st.sidebar.multiselect(
        "Métricas",
        options=sorted(df["metric"].dropna().unique()),
        default=sorted(df["metric"].dropna().unique()),
    )

    if len(selected_range) != 2:
        st.sidebar.warning("Selecione uma data inicial e uma data final.")
        return df.iloc[0:0]

    start_date, end_date = selected_range
    return df[
        (df["date"].dt.date >= start_date)
        & (df["date"].dt.date <= end_date)
        & (df["project"].isin(projects))
        & (df["owner"].isin(owners))
        & (df["metric"].isin(metrics))
    ]


def render_kpis(df: pd.DataFrame) -> None:
    """Show simple indicators for the current selection."""
    total_value = df["value"].sum()
    average_value = df["value"].mean()
    records = len(df)
    active_projects = df["project"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valor total", f"{total_value:,.0f}".replace(",", "."))
    col2.metric("Média", f"{average_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    col3.metric("Registros", records)
    col4.metric("Projetos", active_projects)


def render_charts(df: pd.DataFrame) -> None:
    """Render the main visualization area."""
    time_series = (
        df.groupby([pd.Grouper(key="date", freq="W"), "metric"], as_index=False)["value"]
        .sum()
        .sort_values("date")
    )
    by_project = df.groupby(["project", "metric"], as_index=False)["value"].sum()
    by_owner = df.groupby(["owner", "metric"], as_index=False)["value"].mean()

    st.subheader("Evolução semanal")
    st.plotly_chart(
        px.line(time_series, x="date", y="value", color="metric", markers=True),
        use_container_width=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Total por projeto")
        st.plotly_chart(
            px.bar(by_project, x="project", y="value", color="metric", barmode="group"),
            use_container_width=True,
        )
    with col2:
        st.subheader("Média por responsável")
        st.plotly_chart(
            px.bar(by_owner, x="owner", y="value", color="metric", barmode="group"),
            use_container_width=True,
        )


def main() -> None:
    st.title("📊 Metrics Viewer Lite")
    st.caption("Projeto paralelo focado somente em visualização de dados.")

    uploaded_file = st.sidebar.file_uploader("Carregar CSV", type=["csv"])
    source = uploaded_file if uploaded_file is not None else SAMPLE_DATA

    try:
        data = normalize_data(load_csv(source))
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    filtered = filter_data(data)
    if filtered.empty:
        st.warning("Nenhum dado encontrado para os filtros selecionados.")
        st.stop()

    render_kpis(filtered)
    render_charts(filtered)

    with st.expander("Ver dados filtrados"):
        st.dataframe(filtered, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
