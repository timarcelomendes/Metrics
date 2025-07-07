# pages/4_🔬_Análise_Dinâmica.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid, json, os
from jira_connector import *
from metrics_calculator import *
from config import *
from sklearn.linear_model import LinearRegression

st.set_page_config(page_title="Análise Dinâmica", page_icon="🔬", layout="wide")

DASHBOARD_LAYOUT_FILE = 'dashboard_layout.json'

def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def on_project_change():
    st.session_state.dashboard_items = load_config(DASHBOARD_LAYOUT_FILE, [])
    if 'dynamic_df' in st.session_state: st.session_state['dynamic_df'] = None

# ===== FUNÇÃO DE RENDERIZAÇÃO CORRIGIDA =====
def render_chart(chart_config, df):
    chart_type = chart_config.get('type'); fig = None; template = "plotly_white"
    try:
        title = chart_config.get('title', 'Gráfico sem título')

        if chart_type in ['dispersão', 'linha']:
            fig = px.scatter(df, x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", title="", hover_name="Issue", template=template) if chart_type == 'dispersão' else px.line(df.sort_values(by=chart_config['x']), x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", markers=True, title="", hover_name="Issue", template=template)
        
        # CORREÇÃO: Trata o caso da 'tabela' primeiro e separadamente
        elif chart_type == 'tabela':
            columns_to_show = chart_config.get('columns', [])
            if columns_to_show:
                st.dataframe(df[columns_to_show], use_container_width=True)
            else:
                st.info("Nenhuma coluna selecionada para esta tabela.")
            return # Sai da função, pois a tabela não usa o objeto 'fig'

        elif chart_type in ['barra', 'pizza', 'treemap', 'funil']:
            measure, dimension, agg = chart_config['measure'], chart_config['dimension'], chart_config.get('agg')
            if measure == 'Contagem de Issues':
                grouped_df = df.groupby(dimension).size().reset_index(name='Contagem'); y_axis, values_col = 'Contagem', 'Contagem'
            else:
                agg_func = 'sum' if agg == 'Soma' else 'mean'; grouped_df = df.groupby(dimension)[measure].agg(agg_func).reset_index(); y_axis = values_col = measure
            
            if chart_type == 'barra': fig = px.bar(grouped_df, x=dimension, y=y_axis, color=dimension, title="", template=template)
            elif chart_type == 'pizza': fig = px.pie(grouped_df, names=dimension, values=values_col, title="", template=template)
            elif chart_type == 'treemap': fig = px.treemap(grouped_df, path=[px.Constant("Todos"), dimension], values=values_col, color=y_axis, title="", color_continuous_scale='Blues', template=template)
            elif chart_type == 'funil': fig = px.funnel(grouped_df, x=y_axis, y=dimension, title="", template=template)
                
        elif chart_type == 'indicator':
            # ... (código completo do indicador, como na versão anterior)
            pass

        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

    except KeyError as e:
        st.error(f"Erro de configuração: o campo '{e}' não foi encontrado nos dados para o gráfico '{title}'.")
    except Exception as e:
        st.error(f"Erro ao gerar a visualização '{title}': {e}")


if st.session_state.get('jira_client'):
    st.caption(f"Conectado como: {st.session_state.get('email', '')}")
    
st.header("🔬 Análise Dinâmica e Construtor de Dashboards")
if 'jira_client' not in st.session_state or st.session_state.jira_client is None:
    st.warning("⚠️ **Acesso Negado: Conexão com o Jira não encontrada!**"); st.page_link("1_⚙️_Configurações.py", label="Ir para a página de Configuração", icon="⚙️"); st.stop()
if 'available_standard_fields' not in st.session_state:
    st.warning("Configuração de campos não encontrada."); st.page_link("1_⚙️_Configurações.py", label="Ir para Configurações", icon="⚙️"); st.stop()
if 'dashboard_items' not in st.session_state or st.session_state.dashboard_items is None: st.session_state.dashboard_items = load_config(DASHBOARD_LAYOUT_FILE, [])

with st.sidebar:
    st.image("images/gauge-logo.png", width=150)
    st.divider(); projects = st.session_state.get('projects', {})
    st.markdown("#### 1. Selecione o Projeto"); project_name = st.selectbox("Selecione um Projeto", options=list(projects.keys()), key="project_selector_dynamic", on_change=on_project_change, index=None, placeholder="Escolha um projeto...", label_visibility="collapsed")
    if project_name:
        st.session_state.project_key = projects.get(project_name); st.session_state.project_name = project_name
        with st.expander("2. Fonte de Dados", expanded=True):
            st.info("Esta visão analisa todos os dados do projeto.")
            if st.button("Carregar e Analisar Dados", use_container_width=True, type="primary"):
                with st.spinner("Buscando e preparando dados..."):
                    issues = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key)
                    data = []; custom_fields = load_config(CUSTOM_FIELDS_FILE, []); selected_standard = load_config(STANDARD_FIELDS_FILE, [])
                    AVAILABLE_STANDARD_FIELDS_LOCAL = st.session_state.get('available_standard_fields', {})
                    for i in issues:
                        completion_date = find_completion_date(i)
                        issue_data = {'Issue': i.key, 'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),'Data de Conclusão': completion_date, 'Mês de Conclusão': completion_date.strftime('%Y-%m') if completion_date else None, 'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i), 'Tipo de Issue': i.fields.issuetype.name, 'Responsável': i.fields.assignee.displayName if i.fields.assignee else 'Não atribuído', 'Criado por': i.fields.reporter.displayName if i.fields.reporter else 'N/A', 'Status': i.fields.status.name, 'Prioridade': i.fields.priority.name if i.fields.priority else 'N/A', 'Story Points': getattr(i.fields, STORY_POINTS_FIELD_ID, 0) or 0, 'Labels': ', '.join(i.fields.labels) if i.fields.labels else 'Nenhum'}
                        for field_name in selected_standard:
                            field_id = AVAILABLE_STANDARD_FIELDS_LOCAL.get(field_name)
                            if field_id:
                                value = getattr(i.fields, field_id, None)
                                if isinstance(value, list): issue_data[field_name] = ', '.join([getattr(v, 'name', str(v)) for v in value]) if value else 'Nenhum'
                                elif hasattr(value, 'name'): issue_data[field_name] = value.name
                                elif value: issue_data[field_name] = str(value).split('T')[0]
                                else: issue_data[field_name] = 'N/A'
                        for field in custom_fields:
                            field_name, field_id = field['name'], field['id']
                            value = getattr(i.fields, field_id, None)
                            if hasattr(value, 'displayName'): issue_data[field_name] = value.displayName
                            elif hasattr(value, 'value'): issue_data[field_name] = value.value
                            elif value is not None: issue_data[field_name] = str(value)
                            else: issue_data[field_name] = 'N/A'
                        data.append(issue_data)
                    st.session_state.dynamic_df = pd.DataFrame(data); st.rerun()

df = st.session_state.get('dynamic_df')
if df is None: st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Carregar Dados' para começar."); st.stop()
if df.empty: st.warning("A busca não retornou nenhuma issue para este projeto."); st.stop()

with st.expander("Filtros Globais", expanded=False):
    filter_cols = st.columns(4); tipos = sorted(df['Tipo de Issue'].unique()); resp = sorted(df['Responsável'].unique()); stats = sorted(df['Status'].unique()); prios = sorted(df['Prioridade'].unique())
    tipos_selecionados = filter_cols[0].multiselect("Tipo de Issue", options=tipos); responsaveis_selecionados = filter_cols[1].multiselect("Responsável", options=resp)
    status_selecionados = filter_cols[2].multiselect("Status", options=stats); prioridades_selecionadas = filter_cols[3].multiselect("Prioridade", options=prios)
    filtered_df = df.copy()
    if tipos_selecionados: filtered_df = filtered_df[filtered_df['Tipo de Issue'].isin(tipos_selecionados)]
    if responsaveis_selecionados: filtered_df = filtered_df[filtered_df['Responsável'].isin(responsaveis_selecionados)]
    if status_selecionados: filtered_df = filtered_df[filtered_df['Status'].isin(status_selecionados)]
    if prioridades_selecionadas: filtered_df = filtered_df[filtered_df['Prioridade'].isin(prioridades_selecionadas)]
    st.metric("Issues na Análise (Após Filtros)", f"{len(filtered_df)} de {len(df)}")

dashboard_items = st.session_state.get('dashboard_items') or []; creator_tab, dashboard_tab = st.tabs(["➕ Criar Visualização", f"🖼️ Meu Dashboard ({len(dashboard_items)})"])

with creator_tab:
    st.subheader("Laboratório de Visualizações"); chart_creator_type = st.radio("Selecione o tipo de visualização a criar:", ["Gráfico X-Y", "Gráfico Agregado", "Indicador (KPI)"], key="creator_type", horizontal=True)
    config_container = st.container(border=True); chart_config = {}
    selected_standard_fields = load_config(STANDARD_FIELDS_FILE, []); custom_fields = [field['name'] for field in load_config(CUSTOM_FIELDS_FILE, [])]
    numeric_cols = ['Lead Time (dias)', 'Cycle Time (dias)', 'Story Points']; date_cols = ['Data de Criação', 'Data de Conclusão', 'Mês de Conclusão'] + [f for f in selected_standard_fields if 'Data' in f]
    categorical_cols = ['Tipo de Issue', 'Responsável', 'Status', 'Prioridade', 'Criado por', 'Labels', 'Mês de Conclusão'] + custom_fields + [f for f in selected_standard_fields if 'Data' not in f]; measure_options = ["Contagem de Issues"] + numeric_cols
    
    if chart_creator_type == "Gráfico X-Y":
        with config_container:
            c1, c2, c3 = st.columns(3); x = c1.selectbox("Eixo X", date_cols+numeric_cols); y = c2.selectbox("Eixo Y", numeric_cols); chart_type = c3.radio("Formato", ["Dispersão", "Linha"], horizontal=True).lower()
            chart_config = {'id': str(uuid.uuid4()), 'type': chart_type, 'x': x, 'y': y, 'title': f"{y} vs {x}"}
    elif chart_creator_type == "Gráfico Agregado":
        with config_container:
            c1, c2 = st.columns(2)
            # O seletor de formato agora está no início para esta seção
            chart_type = c2.radio("Formato", ["Barras", "Pizza", "Treemap", "Funil", "Tabela"], key='creator_agg_type', horizontal=True).lower().replace("s", "").replace("á", "a")
            
            # --- LÓGICA DE UI ATUALIZADA PARA TABELA ---
            if chart_type == 'tabela':
                all_cols = numeric_cols + date_cols + categorical_cols
                selected_cols = st.multiselect("Selecione as colunas para exibir (até 4)", options=sorted(list(set(all_cols))), max_selections=4)
                chart_config = {'id': str(uuid.uuid4()), 'type': chart_type, 'columns': selected_cols, 'title': f"Tabela: {', '.join(selected_cols)}"}
            else:
                c1a, c1b = c1.columns(2)
                dim = c1a.selectbox("Dimensão", categorical_cols, key='creator_dim_agg')
                measure = c1b.selectbox("Medida", measure_options, key='creator_measure_agg')
                agg = st.radio("Cálculo", ["Soma", "Média"], key='creator_agg_agg', horizontal=True) if measure != 'Contagem de Issues' else 'Contagem'
                chart_config = {'id': str(uuid.uuid4()), 'type': chart_type, 'dimension': dim, 'measure': measure, 'agg': agg, 'title': f"Análise de '{measure}' por '{dim}'"}
    elif chart_creator_type == "Indicador (KPI)":
        with config_container:
            c1, c2 = st.columns([3, 1]); kpi_title = c1.text_input("Título do Indicador", "Ex: Taxa de Bugs"); kpi_icon = c2.text_input("Ícone", "🚀")
            st.markdown("**Valor Principal (Numerador)**"); c1, c2 = st.columns(2)
            num_field = c2.selectbox("Campo", ['Issues'] + numeric_cols + categorical_cols, key='kpi_num_field')
            if num_field == 'Issues': num_op = 'Contagem'; c1.text_input("Operação", value="Contagem", disabled=True)
            else: num_op = c1.selectbox("Operação", ["Soma", "Média", "Contagem"], key='kpi_num_op')
            use_den = st.checkbox("Adicionar Denominador (para rácio)?", key='kpi_use_den'); den_op, den_field = (None, None)
            if use_den:
                st.markdown("**Denominador**"); c3, c4 = st.columns(2); den_field = c4.selectbox("Campo ", ['Issues'] + numeric_cols + categorical_cols, key='kpi_den_field')
                if den_field == 'Issues': den_op = 'Contagem'; c3.text_input("Operação ", value="Contagem", disabled=True)
                else: den_op = c3.selectbox("Operação ", ["Soma", "Média", "Contagem"], key='kpi_den_op')
            st.divider(); kpi_style = st.selectbox("Estilo de Exibição", ["Número Grande", "Medidor (Gauge)"])
            target_type, target_op, target_field, gauge_min, gauge_max_static, bar_color, target_color = ('Fixo', None, None, 0, 100, '#1f77b4', '#d62728')
            if kpi_style == 'Medidor (Gauge)':
                c1,c2 = st.columns(2); 
                with c1: target_type = st.radio("Definir Meta como:", ["Valor Fixo", "Valor Dinâmico"], horizontal=True, key="kpi_target_type")
                if target_type == "Valor Fixo": gauge_max_static = c2.number_input("Valor da Meta", value=100)
                else:
                    c3, c4 = st.columns(2); target_field = c4.selectbox("Campo da Meta", ['Issues'] + numeric_cols + categorical_cols, key='kpi_target_field')
                    if target_field == 'Issues': target_op = 'Contagem'; c3.text_input("Operação da Meta", value="Contagem", disabled=True)
                    else: target_op = c3.selectbox("Operação da Meta", ["Soma", "Média", "Contagem"], key='kpi_target_op')
                cc1, cc2 = st.columns(2); bar_color = cc1.color_picker('Cor da Barra', '#1f77b4'); target_color = cc2.color_picker('Cor da Meta', '#d62728')
            show_delta = st.toggle("Mostrar variação vs. média?") if kpi_style == 'Número Grande' and num_op != 'Contagem' else False
            chart_config = {'id': str(uuid.uuid4()), 'type': 'indicator', 'title': kpi_title, 'icon': kpi_icon, 'num_op': num_op, 'num_field': num_field, 'use_den': use_den, 'den_op': den_op, 'den_field': den_field, 'style': kpi_style, 'gauge_min': gauge_min, 'gauge_max_static': gauge_max_static, 'target_type': target_type, 'target_op': target_op, 'target_field': target_field, 'show_delta': show_delta, 'gauge_bar_color': bar_color, 'gauge_target_color': target_color}
    
    # BOTÃO DE ADICIONAR CORRIGIDO
    if st.button("Adicionar Visualização ao Dashboard", type="primary", use_container_width=True, icon="➕"):
        if chart_config: st.session_state.dashboard_items.append(chart_config); save_config(st.session_state.dashboard_items, DASHBOARD_LAYOUT_FILE); st.success(f"Visualização '{chart_config.get('title')}' adicionada!"); st.rerun()

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
                        # LAYOUT DO CARTÃO CORRIGIDO
                        header_cols = st.columns([0.85, 0.15]); 
                        with header_cols[0]:
                            card_title = chart_to_render.get('title', 'Visualização'); card_icon = chart_to_render.get('icon', '') if chart_to_render.get('type') == 'indicator' else '📊'
                            st.markdown(f"**{card_icon} {card_title}**")
                        with header_cols[1]:
                            if st.button("❌", key=f"del_{chart_to_render['id']}", help="Remover Gráfico"):
                                st.session_state.dashboard_items = [item for item in st.session_state.dashboard_items if item['id'] != chart_to_render['id']]; save_config(st.session_state.dashboard_items, DASHBOARD_LAYOUT_FILE); st.rerun()
                        render_chart(chart_to_render, filtered_df)