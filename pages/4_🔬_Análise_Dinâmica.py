import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import json
import os
from jira_connector import get_all_project_issues
from metrics_calculator import find_completion_date, calculate_lead_time, calculate_cycle_time
from sklearn.linear_model import LinearRegression

st.set_page_config(
    page_title="Análise Dinâmica",
    page_icon="🔬",
    layout="wide"
)

# --- Constantes e Funções de Configuração ---
CUSTOM_FIELDS_FILE = 'custom_fields.json'
STANDARD_FIELDS_FILE = 'standard_fields_config.json'
DASHBOARD_LAYOUT_FILE = 'dashboard_layout.json'

def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- Funções de Callback ---
def on_project_change():
    """Limpa o dataframe e o dashboard guardado ao trocar de projeto."""
    st.session_state.dashboard_items = load_config(DASHBOARD_LAYOUT_FILE, [])
    if 'dynamic_df' in st.session_state:
        st.session_state['dynamic_df'] = None

# --- Função de Renderização ---
def render_chart(chart_config, df):
    """Renderiza um único gráfico ou indicador com base na sua configuração e no dataframe filtrado."""
    chart_type = chart_config.get('type')
    fig = None 
    
    try:
        if chart_type in ['dispersão', 'linha']:
            title = f"{chart_config.get('y')} vs. {chart_config.get('x')}"
            if chart_type == 'dispersão':
                fig = px.scatter(df, x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", title=title, hover_name="Issue")
            else:
                fig = px.line(df.sort_values(by=chart_config['x']), x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", markers=True, title=title, hover_name="Issue")
        
        elif chart_type in ['barra', 'pizza', 'treemap']:
            measure, dimension, agg = chart_config['measure'], chart_config['dimension'], chart_config['agg']
            title = f"Análise de '{measure}' por '{dimension}'"
            if measure == 'Contagem de Issues':
                grouped_df = df.groupby(dimension).size().reset_index(name='Contagem')
                y_axis, values_col = 'Contagem', 'Contagem'
            else:
                agg_func = 'sum' if agg == 'Soma' else 'mean'
                grouped_df = df.groupby(dimension)[measure].agg(agg_func).reset_index()
                y_axis, values_col = measure, measure

            if chart_type == 'barra':
                fig = px.bar(grouped_df, x=dimension, y=y_axis, color=dimension, title=title)
            elif chart_type == 'pizza':
                fig = px.pie(grouped_df, names=dimension, values=values_col, title=title)
            elif chart_type == 'treemap':
                 fig = px.treemap(grouped_df, path=[px.Constant("Todos"), dimension], values=values_col, color=y_axis, title=title, color_continuous_scale='Blues')
        
        elif chart_type == 'indicator':
            title = chart_config.get('title', 'Indicador')
            
            def calculate_value(op, field, data_frame):
                if not op or not field: return 0
                if op == 'Contagem':
                    return len(data_frame.dropna(subset=[field])) if field != 'Issues' else len(data_frame)
                elif op == 'Soma':
                    return pd.to_numeric(data_frame[field], errors='coerce').sum()
                elif op == 'Média':
                    return pd.to_numeric(data_frame[field], errors='coerce').mean()
                return 0
            
            num_value = calculate_value(chart_config['num_op'], chart_config['num_field'], df)
            final_value = num_value
            if chart_config.get('use_den'):
                den_value = calculate_value(chart_config['den_op'], chart_config['den_field'], df)
                final_value = (num_value / den_value) if den_value != 0 else 0
            
            style = chart_config.get('style', 'Número Grande')
            
            with st.container(border=True):
                if style == 'Número Grande':
                    delta_value = None
                    mean_val = 0
                    if chart_config.get('show_delta'):
                        mean_val = calculate_value('Média', chart_config['num_field'], df)
                        delta_value = final_value - mean_val
                    st.metric(
                        label=f"{chart_config.get('icon', '')} {title}", value=f"{final_value:,.2f}",
                        delta=f"{delta_value:,.2f}" if delta_value is not None else None,
                        help=f"Variação em relação à média do período ({mean_val:,.2f})" if delta_value is not None else None
                    )
                elif style == 'Medidor (Gauge)':
                    target_value = 100
                    if chart_config.get('target_type') == 'Valor Fixo':
                        target_value = chart_config.get('gauge_max_static', 100)
                    else:
                        if chart_config.get('target_op') and chart_config.get('target_field'):
                            target_value = calculate_value(chart_config['target_op'], chart_config['target_field'], df)
                    fig = go.Figure(go.Indicator(
                        mode = "gauge+number", value = final_value,
                        title = {'text': f"{chart_config.get('icon', '')} {title}", 'font': {'size': 16}},
                        gauge = {
                            'axis': {'range': [chart_config.get('gauge_min', 0), target_value]},
                            'bar': {'color': "#1f77b4"},
                            'threshold': {'line': {'color': "red", 'width': 2}, 'thickness': 0.75, 'value': target_value}
                        }
                    ))
                    fig.update_layout(height=150, margin=dict(l=20, r=20, t=50, b=20))

        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Erro ao gerar a visualização '{chart_config.get('title', 'Desconhecido')}': {e}")


# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("🔬 Análise Dinâmica e Construtor de Dashboards")

if 'jira_client' not in st.session_state or st.session_state.jira_client is None:
    st.warning("⚠️ **Acesso Negado: Conexão com o Jira não encontrada!**")
    st.info("Para aceder a esta página, por favor, inicie o aplicativo pela página principal e realize a conexão.")
    st.page_link("Configurações.py", label="Ir para a página de Configuração", icon="⚙️")
    st.stop()

if 'dashboard_items' not in st.session_state or st.session_state.dashboard_items is None:
    st.session_state.dashboard_items = load_config(DASHBOARD_LAYOUT_FILE, [])

with st.sidebar:
    try: st.image("images/gauge-logo.png", width=150)
    except Exception: st.write("Gauge Metrics")
    st.divider()

    projects = st.session_state.get('projects', {})
    
    st.markdown("#### 1. Selecione o Projeto")
    project_name = st.selectbox("Selecione um Projeto", options=list(projects.keys()), key="project_selector_dynamic", on_change=on_project_change, index=None, placeholder="Escolha um projeto...", label_visibility="collapsed")
    
    if project_name:
        st.session_state.project_key = projects.get(project_name); st.session_state.project_name = project_name
        
        with st.expander("2. Fonte de Dados", expanded=True):
            st.info("Esta visão analisa todos os dados do projeto.")
            if st.button("Carregar e Analisar Dados", use_container_width=True, type="primary"):
                with st.spinner("Buscando e preparando dados..."):
                    issues = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key)
                    selected_standard_fields = load_config(STANDARD_FIELDS_FILE, [])
                    custom_fields_to_fetch = load_config(CUSTOM_FIELDS_FILE, [])
                    story_points_field = 'customfield_10016'
                    data = []
                    AVAILABLE_STANDARD_FIELDS = st.session_state.get('available_standard_fields', {})
                    for i in issues:
                        completion_date = find_completion_date(i)
                        issue_data = {
                            'Issue': i.key, 'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),'Data de Conclusão': completion_date, 'Mês de Conclusão': completion_date.strftime('%Y-%m') if completion_date else None, 
                            'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i), 
                            'Tipo de Issue': i.fields.issuetype.name, 'Responsável': i.fields.assignee.displayName if i.fields.assignee else 'Não atribuído', 
                            'Criado por': i.fields.reporter.displayName if i.fields.reporter else 'N/A', 'Status': i.fields.status.name, 
                            'Prioridade': i.fields.priority.name if i.fields.priority else 'N/A', 'Story Points': getattr(i.fields, story_points_field, 0) or 0, 
                            'Labels': ', '.join(i.fields.labels) if i.fields.labels else 'Nenhum'
                        }
                        for field_name in selected_standard_fields:
                            field_id = AVAILABLE_STANDARD_FIELDS.get(field_name)
                            if field_id:
                                value = getattr(i.fields, field_id, None)
                                if isinstance(value, list): issue_data[field_name] = ', '.join([v.name for v in value if hasattr(v, 'name')]) if value else 'Nenhum'
                                elif hasattr(value, 'name'): issue_data[field_name] = value.name
                                elif value: issue_data[field_name] = str(value).split('T')[0]
                                else: issue_data[field_name] = 'N/A'
                        for field in custom_fields_to_fetch:
                            field_name_custom, field_id_custom = field['name'], field['id']
                            field_value = getattr(i.fields, field_id_custom, None)
                            if hasattr(field_value, 'displayName'): issue_data[field_name_custom] = field_value.displayName
                            elif hasattr(field_value, 'value'): issue_data[field_name_custom] = field_value.value
                            elif field_value is not None: issue_data[field_name_custom] = str(field_value)
                            else: issue_data[field_name_custom] = 'N/A'
                        data.append(issue_data)
                    st.session_state.dynamic_df = pd.DataFrame(data)
                    st.rerun()

df = st.session_state.get('dynamic_df')
if df is None:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Carregar Dados do Projeto' para começar."); st.stop()
if df.empty:
    st.warning("A busca não retornou nenhuma issue para este projeto."); st.stop()

with st.expander("Filtros Globais (afetam todos os gráficos)", expanded=False):
    filter_cols = st.columns(4)
    tipos = sorted(df['Tipo de Issue'].unique()); resp = sorted(df['Responsável'].unique()); stats = sorted(df['Status'].unique()); prios = sorted(df['Prioridade'].unique())
    tipos_selecionados = filter_cols[0].multiselect("Tipo de Issue", options=tipos, key='filter_issue_type')
    responsaveis_selecionados = filter_cols[1].multiselect("Responsável", options=resp, key='filter_assignee')
    status_selecionados = filter_cols[2].multiselect("Status", options=stats, key='filter_status')
    prioridades_selecionadas = filter_cols[3].multiselect("Prioridade", options=prios, key='filter_priority')
    
    filtered_df = df.copy()
    if tipos_selecionados: filtered_df = filtered_df[filtered_df['Tipo de Issue'].isin(tipos_selecionados)]
    if responsaveis_selecionados: filtered_df = filtered_df[filtered_df['Responsável'].isin(responsaveis_selecionados)]
    if status_selecionados: filtered_df = filtered_df[filtered_df['Status'].isin(status_selecionados)]
    if prioridades_selecionadas: filtered_df = filtered_df[filtered_df['Prioridade'].isin(prioridades_selecionadas)]
    st.metric("Issues na Análise (Após Filtros)", f"{len(filtered_df)} de {len(df)}")

dashboard_items = st.session_state.get('dashboard_items') or []
creator_tab, dashboard_tab = st.tabs(["➕ Criar Visualização", f"🖼️ Meu Dashboard ({len(dashboard_items)})"])

with creator_tab:
    st.subheader("Laboratório de Visualizações")
    chart_creator_type = st.radio("Selecione o tipo de visualização a criar:", ["Gráfico X-Y (Dispersão/Linha)", "Gráfico Agregado (Barra/Pizza/Treemap)", "Indicador (KPI)"], key="creator_type", horizontal=True)
    
    config_container = st.container(border=True); chart_config = {}
    
    selected_standard_fields = load_config(STANDARD_FIELDS_FILE, [])
    custom_fields = [field['name'] for field in load_config(CUSTOM_FIELDS_FILE, [])]
    
    numeric_cols = ['Lead Time (dias)', 'Cycle Time (dias)', 'Story Points']
    date_cols = ['Data de Criação', 'Data de Conclusão', 'Mês de Conclusão'] + [f for f in selected_standard_fields if 'Data' in f]
    categorical_cols = ['Tipo de Issue', 'Responsável', 'Status', 'Prioridade', 'Criado por', 'Labels', 'Mês de Conclusão'] + custom_fields + [f for f in selected_standard_fields if 'Data' not in f]
    measure_options = ["Contagem de Issues"] + numeric_cols

    if chart_creator_type == "Gráfico X-Y (Dispersão/Linha)":
        with config_container:
            c1, c2, c3 = st.columns(3); x = c1.selectbox("Eixo X", date_cols+numeric_cols, key='creator_x_xy'); y = c2.selectbox("Eixo Y", numeric_cols, key='creator_y_xy'); chart_type = c3.radio("Formato", ["Dispersão", "Linha"], key='creator_xy_type', horizontal=True).lower()
            chart_config = {'id': str(uuid.uuid4()), 'type': chart_type, 'x': x, 'y': y, 'title': f"{y} vs {x}"}
    
    elif chart_creator_type == "Gráfico Agregado (Barra/Pizza/Treemap)":
        with config_container:
            c1, c2, c3, c4 = st.columns(4); dim = c1.selectbox("Dimensão (Agrupar por)", categorical_cols, key='creator_dim_agg'); measure = c2.selectbox("Medida", measure_options, key='creator_measure_agg')
            agg = c3.radio("Cálculo", ["Soma", "Média"], key='creator_agg_agg', horizontal=True) if measure != 'Contagem de Issues' else 'Contagem'; chart_type = c4.radio("Formato", ["Barras", "Pizza", "Treemap"], key='creator_agg_type', horizontal=True).lower().replace("s", "")
            chart_config = {'id': str(uuid.uuid4()), 'type': chart_type, 'dimension': dim, 'measure': measure, 'agg': agg, 'title': f"Análise de '{measure}' por '{dim}'"}
            
    elif chart_creator_type == "Indicador (KPI)":
        with config_container:
            kpi_title = st.text_input("Título do Indicador", "Ex: Média de Pontos por Issue")
            kpi_icon = st.text_input("Ícone (Opcional)", "🚀", max_chars=5)
            st.markdown("**Valor Principal (Numerador)**"); c1, c2 = st.columns(2)
            num_op = c1.selectbox("Operação N.", ["Soma", "Média", "Contagem"], key='kpi_num_op'); num_field = c2.selectbox("Campo N.", ['Issues'] + numeric_cols + categorical_cols, key='kpi_num_field')
            use_den = st.checkbox("Adicionar Denominador (para criar um rácio)?", key='kpi_use_den')
            den_op, den_field, target_type, target_op, target_field, gauge_min, gauge_max_static = (None,)*7
            if use_den:
                st.markdown("**Denominador**"); c3, c4 = st.columns(2)
                den_op = c3.selectbox("Operação D.", ["Soma", "Média", "Contagem"], key='kpi_den_op'); den_field = c4.selectbox("Campo D.", ['Issues'] + numeric_cols + categorical_cols, key='kpi_den_field')
            st.divider(); kpi_style = st.selectbox("Estilo de Exibição", ["Número Grande", "Medidor (Gauge)"])
            if kpi_style == 'Medidor (Gauge)':
                target_type = st.radio("Definir Meta como:", ["Valor Fixo", "Valor Dinâmico"], horizontal=True, key="kpi_target_type")
                if target_type == "Valor Fixo":
                    c5, c6 = st.columns(2); gauge_min = c5.number_input("Valor Mínimo", value=0); gauge_max_static = c6.number_input("Valor Máximo (Meta)", value=100)
                else:
                    st.markdown("**Configuração da Meta (Valor Máximo do Gauge)**"); c5, c6 = st.columns(2)
                    target_op = c5.selectbox("Operação da Meta", ["Soma", "Média", "Contagem"], key='kpi_target_op'); target_field = c6.selectbox("Campo da Meta", ['Issues'] + numeric_cols + categorical_cols, key='kpi_target_field')
            show_delta = st.toggle("Mostrar variação (vs. média)?", help="Compara o valor principal com a média do seu campo no período.") if kpi_style == 'Número Grande' else False
            chart_config = {'id': str(uuid.uuid4()), 'type': 'indicator', 'title': kpi_title, 'icon': kpi_icon, 'num_op': num_op, 'num_field': num_field, 'use_den': use_den, 'den_op': den_op, 'den_field': den_field, 'style': kpi_style, 'gauge_min': gauge_min, 'gauge_max_static': gauge_max_static, 'target_type': target_type, 'target_op': target_op, 'target_field': target_field, 'show_delta': show_delta}
    
    if st.button("➕ Adicionar Visualização ao Dashboard", type="primary"):
        if chart_config: st.session_state.dashboard_items.append(chart_config); save_config(st.session_state.dashboard_items, DASHBOARD_LAYOUT_FILE); st.success(f"Visualização '{chart_config.get('title')}' adicionada!"); st.rerun()
        else: st.warning("Configuração de visualização inválida.")
        
with dashboard_tab:
    st.header("Meu Dashboard Personalizado")
    if not st.session_state.dashboard_items: st.info("Seu dashboard está vazio.")
    else:
        if filtered_df.empty: st.warning("Nenhum dado para exibir com os filtros atuais.")
        else:
            cols = st.columns(2)
            for i, chart_to_render in enumerate(list(st.session_state.dashboard_items)):
                with cols[i % 2]:
                    with st.container(border=True):
                        render_chart(chart_to_render, filtered_df)
                        if st.button("Remover", key=f"del_{chart_to_render['id']}", type="secondary"):
                            st.session_state.dashboard_items = [item for item in st.session_state.dashboard_items if item['id'] != chart_to_render['id']]; save_config(st.session_state.dashboard_items, DASHBOARD_LAYOUT_FILE); st.rerun()