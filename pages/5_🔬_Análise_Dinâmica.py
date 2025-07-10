# pages/3_🔬_Análise_Dinâmica.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid, json, os
from jira_connector import *
from metrics_calculator import *
from config import *
from utils import *
from security import *
from pathlib import Path

st.set_page_config(page_title="Análise Dinâmica", page_icon="🔬", layout="wide")

st.markdown("""<style> button[data-testid="stButton"][kind="primary"] span svg { fill: white; } </style>""", unsafe_allow_html=True)

def on_project_change():
    if 'dynamic_df' in st.session_state: del st.session_state['dynamic_df']
    if 'chart_to_edit' in st.session_state: del st.session_state['chart_to_edit']

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑"); st.stop()

with st.sidebar:
    # Constrói o caminho para da logo a partir da raiz do projeto
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(
            logo_path, 
            size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 

    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    default_index = project_names.index(st.session_state.get('project_name')) if st.session_state.get('project_name') in project_names else None
    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_creator", index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]; st.session_state.project_name = selected_project_name
        is_data_loaded = 'dynamic_df' in st.session_state and st.session_state.dynamic_df is not None and not st.session_state.dynamic_df.empty
        with st.expander("Carregar Dados", expanded=not is_data_loaded):
            if st.button("Carregar / Atualizar Dados", use_container_width=True, type="primary"):
                with st.spinner("Buscando e preparando dados..."):
                    issues = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key)
                    data = []; global_configs = get_global_configs(); user_data = find_user(st.session_state['email']);
                    selected_standard_fields = user_data.get('standard_fields', []); custom_fields_to_fetch = global_configs.get('custom_fields', [])
                    for i in issues:
                        completion_date = find_completion_date(i)
                        issue_data = {'Issue': i.key, 'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),'Data de Conclusão': completion_date, 'Mês de Conclusão': completion_date.strftime('%Y-%m') if completion_date else None, 'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i), 'Tipo de Issue': i.fields.issuetype.name, 'Responsável': i.fields.assignee.displayName if i.fields.assignee else 'Não atribuído', 'Criado por': i.fields.reporter.displayName if i.fields.reporter else 'N/A', 'Status': i.fields.status.name, 'Prioridade': i.fields.priority.name if i.fields.priority else 'N/A', 'Labels': ', '.join(i.fields.labels) if i.fields.labels else 'Nenhum'}
                        for field in custom_fields_to_fetch:
                            field_name, field_id = field['name'], field['id']; value = getattr(i.fields, field_id, None)
                            if hasattr(value, 'displayName'): issue_data[field_name] = value.displayName
                            elif hasattr(value, 'value'): issue_data[field_name] = value.value
                            elif value is not None: issue_data[field_name] = value
                            else: issue_data[field_name] = None
                        data.append(issue_data)
                    st.session_state.dynamic_df = pd.DataFrame(data); st.rerun()
                    
                    st.divider()
    
        if st.button("Logout", use_container_width=True):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.switch_page("1_🔑_Login.py")
        

editing_mode = 'chart_to_edit' in st.session_state and st.session_state.chart_to_edit is not None
chart_data = st.session_state.get('chart_to_edit', {})
if editing_mode: st.header(f"✏️ Editando: {chart_data.get('title', 'Visualização')}")
else: st.header("🔬 Laboratório de Criação de Visualizações")
df = st.session_state.get('dynamic_df')
if df is None or df.empty:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Carregar / Atualizar Dados' para começar."); st.stop()
st.caption(f"Utilizando dados do projeto: **{st.session_state.project_name}**")
with st.expander("Filtros Globais (afetam a pré-visualização)", expanded=False):
    filter_cols = st.columns(4); tipos = sorted(df['Tipo de Issue'].unique()); resp = sorted(df['Responsável'].unique()); stats = sorted(df['Status'].unique()); prios = sorted(df['Prioridade'].unique())
    tipos_selecionados = filter_cols[0].multiselect("Filtrar por Tipo", options=tipos); responsaveis_selecionados = filter_cols[1].multiselect("Filtrar por Responsável", options=resp)
    status_selecionados = filter_cols[2].multiselect("Filtrar por Status", options=stats); prioridades_selecionadas = filter_cols[3].multiselect("Filtrar por Prioridade", options=prios)
    filtered_df = df.copy()
    if tipos_selecionados: filtered_df = filtered_df[filtered_df['Tipo de Issue'].isin(tipos_selecionados)]
    if responsaveis_selecionados: filtered_df = filtered_df[filtered_df['Responsável'].isin(responsaveis_selecionados)]
    if status_selecionados: filtered_df = filtered_df[filtered_df['Status'].isin(status_selecionados)]
    if prioridades_selecionadas: filtered_df = filtered_df[filtered_df['Prioridade'].isin(prioridades_selecionadas)]
st.divider()
creator_type_options = ["Gráfico X-Y", "Gráfico Agregado", "Indicador (KPI)"]; default_creator_index = 0
if editing_mode:
    type_map = {'dispersão':'Gráfico X-Y', 'linha':'Gráfico X-Y', 'barra':'Gráfico Agregado', 'linha_agregada':'Gráfico Agregado', 'pizza':'Gráfico Agregado', 'treemap':'Gráfico Agregado', 'funil':'Gráfico Agregado', 'tabela':'Gráfico Agregado', 'indicator':'Indicador (KPI)'}
    creator_type_from_data = type_map.get(chart_data.get('type'))
    if creator_type_from_data in creator_type_options: default_creator_index = creator_type_options.index(creator_type_from_data)
chart_creator_type = st.radio("Selecione o tipo de visualização:", creator_type_options, key="creator_type", horizontal=True, index=default_creator_index)
config_container = st.container(border=True); chart_config = {}
global_configs = get_global_configs(); user_data = find_user(st.session_state['email'])
active_standard_fields = user_data.get('standard_fields', []); active_custom_fields = [f['name'] for f in global_configs.get('custom_fields', [])]
base_numeric_cols = ['Lead Time (dias)', 'Cycle Time (dias)']; base_date_cols = ['Data de Criação', 'Data de Conclusão', 'Mês de Conclusão']; base_categorical_cols = ['Tipo de Issue', 'Responsável', 'Status', 'Prioridade', 'Criado por', 'Labels']
configured_date_cols = [f for f in active_standard_fields if 'Data' in f]; configured_categorical_cols = [f for f in active_standard_fields if 'Data' not in f]
numeric_cols = sorted(list(set(base_numeric_cols + [f['name'] for f in global_configs.get('custom_fields', []) if f['type'] == 'Número']))); date_cols = sorted(list(set(base_date_cols + configured_date_cols)))
categorical_cols = sorted(list(set(base_categorical_cols + configured_categorical_cols + [f['name'] for f in global_configs.get('custom_fields', []) if f['type'] == 'Texto'])))
measure_options = ["Contagem de Issues"] + numeric_cols + categorical_cols; all_cols_for_table = sorted(list(set(date_cols + categorical_cols + numeric_cols)))
all_cols_for_table = sorted(list(set(date_cols + categorical_cols + numeric_cols)))

with config_container:
    if chart_creator_type == "Gráfico X-Y":
        c1, c2, c3 = st.columns(3); x_options = date_cols+numeric_cols; y_options = numeric_cols; type_options = ["Dispersão", "Linha"]
        x_idx = x_options.index(chart_data.get('x')) if editing_mode and chart_data.get('x') in x_options else 0
        y_idx = y_options.index(chart_data.get('y')) if editing_mode and chart_data.get('y') in y_options else 0
        type_idx = type_options.index(chart_data.get('type', 'dispersão').capitalize()) if editing_mode and chart_data.get('type','').capitalize() in type_options else 0
        x = c1.selectbox("Eixo X", x_options, index=x_idx); y = c2.selectbox("Eixo Y", y_options, index=y_idx)
        chart_type = c3.radio("Formato", type_options, index=type_idx, horizontal=True).lower()
        chart_config = {'id': str(uuid.uuid4()), 'type': chart_type, 'x': x, 'y': y, 'title': f"{y} vs {x}", 'creator_type': chart_creator_type}

    elif chart_creator_type == "Gráfico Agregado":
        format_options = ["Barras", "Linhas", "Pizza", "Treemap", "Funil", "Tabela"]; type_map_inv = {'barra': 'Barras', 'linha_agregada': 'Linhas', 'pizza': 'Pizza', 'treemap': 'Treemap', 'funil': 'Funil', 'tabela':'Tabela'}
        dim_idx = categorical_cols.index(chart_data.get('dimension')) if editing_mode and chart_data.get('dimension') in categorical_cols else 0
        measure_idx = measure_options.index(chart_data.get('measure')) if editing_mode and chart_data.get('measure') in measure_options else 0
        agg_options = ["Soma", "Média"]; agg_idx = agg_options.index(chart_data.get('agg', 'Soma')) if editing_mode and chart_data.get('measure') != 'Contagem de Issues' and chart_data.get('agg') in agg_options else 0
        type_from_data = type_map_inv.get(chart_data.get('type', 'barra')); type_idx = format_options.index(type_from_data) if editing_mode and type_from_data in format_options else 0
        c1, c2, c3, c4 = st.columns([2, 2, 1, 2]); dim = c1.selectbox("Dimensão", categorical_cols, index=dim_idx); measure = c2.selectbox("Medida", measure_options, index=measure_idx)
        if measure != 'Contagem de Issues': agg = c3.radio("Cálculo", agg_options, index=agg_idx, horizontal=True)
        else: agg = 'Contagem'; c3.write(""); c3.info("Contagem")
        chart_type_str = c4.radio("Formato", format_options, index=type_idx, horizontal=True)
        chart_type = chart_type_str.lower().replace("s", "").replace("á", "a")
        if chart_type == 'tabela':
            selected_cols = st.multiselect("Selecione as colunas para a tabela", options=all_cols_for_table, default=chart_data.get('columns', []))
            chart_config = {'id': str(uuid.uuid4()), 'type': chart_type, 'columns': selected_cols, 'title': f"Tabela: {', '.join(selected_cols)}", 'creator_type': chart_creator_type}
        else:
            chart_config = {'id': str(uuid.uuid4()), 'type': 'linha_agregada' if chart_type == 'linha' else chart_type, 'dimension': dim, 'measure': measure, 'agg': agg, 'title': f"Análise de '{measure}' por '{dim}'", 'creator_type': chart_creator_type}

    elif chart_creator_type == "Indicador (KPI)":
        c1, c2 = st.columns([3, 1]); kpi_title = c1.text_input("Título do Indicador", value=chart_data.get('title', '')); kpi_icon = c2.text_input("Ícone", value=chart_data.get('icon', '🚀'))
        st.markdown("**Valor Principal (Numerador)**"); c1, c2 = st.columns(2); num_field_opts = ['Issues'] + numeric_cols + categorical_cols; num_field_idx = num_field_opts.index(chart_data.get('num_field')) if editing_mode and chart_data.get('num_field') in num_field_opts else 0
        num_field = c2.selectbox("Campo", num_field_opts, key='kpi_num_field', index=num_field_idx)
        if num_field == 'Issues': num_op = 'Contagem'; c1.text_input("Operação", value="Contagem", disabled=True)
        else:
            num_op_opts = ["Soma", "Média", "Contagem"]; num_op_idx = num_op_opts.index(chart_data.get('num_op')) if editing_mode and chart_data.get('num_op') in num_op_opts else 0
            num_op = c1.selectbox("Operação", num_op_opts, key='kpi_num_op', index=num_op_idx)
        use_den = st.checkbox("Adicionar Denominador (para rácio)?", value=chart_data.get('use_den', False)); den_op, den_field = (None, None)
        if use_den:
            st.markdown("**Denominador**"); c3, c4 = st.columns(2); den_field_opts = ['Issues'] + numeric_cols + categorical_cols; den_field_idx = den_field_opts.index(chart_data.get('den_field')) if editing_mode and chart_data.get('den_field') in den_field_opts else 0
            den_field = c4.selectbox("Campo ", den_field_opts, key='kpi_den_field', index=den_field_idx)
            if den_field == 'Issues': den_op = 'Contagem'; c3.text_input("Operação ", value="Contagem", disabled=True)
            else:
                den_op_opts = ["Soma", "Média", "Contagem"]; den_op_idx = den_op_opts.index(chart_data.get('den_op')) if editing_mode and chart_data.get('den_op') in den_op_opts else 0
                den_op = c3.selectbox("Operação ", den_op_opts, key='kpi_den_op', index=den_op_idx)
        st.divider(); kpi_style_opts = ["Número Grande", "Medidor (Gauge)"]; style_idx = kpi_style_opts.index(chart_data.get('style')) if editing_mode and chart_data.get('style') in kpi_style_opts else 0
        kpi_style = st.selectbox("Estilo de Exibição", kpi_style_opts, index=style_idx)
        target_type, target_op, target_field, gauge_min, gauge_max_static, bar_color, target_color = ('Fixo', None, None, 0, 100, '#1f77b4', '#d62728')
        if kpi_style == 'Medidor (Gauge)':
            c1,c2 = st.columns(2); target_type_opts = ["Valor Fixo", "Valor Dinâmico"]; target_type_idx = target_type_opts.index(chart_data.get('target_type', 'Fixo')) if editing_mode else 0
            with c1: target_type = st.radio("Definir Meta como:", target_type_opts, horizontal=True, index=target_type_idx)
            if target_type == "Valor Fixo": gauge_max_static = c2.number_input("Valor da Meta", value=chart_data.get('gauge_max_static', 100))
            else:
                c3, c4 = st.columns(2); target_field_opts = ['Issues'] + numeric_cols + categorical_cols; target_field_idx = target_field_opts.index(chart_data.get('target_field')) if editing_mode and chart_data.get('target_field') in target_field_opts else 0
                target_field = c4.selectbox("Campo da Meta", target_field_opts, key='kpi_target_field', index=target_field_idx)
                if target_field == 'Issues': target_op = 'Contagem'; c3.text_input("Operação da Meta", value="Contagem", disabled=True)
                else:
                    target_op_opts = ["Soma", "Média", "Contagem"]; target_op_idx = target_op_opts.index(chart_data.get('target_op')) if editing_mode and chart_data.get('target_op') in target_op_opts else 0
                    target_op = c3.selectbox("Operação da Meta", target_op_opts, key='kpi_target_op', index=target_op_idx)
            cc1, cc2 = st.columns(2); bar_color = cc1.color_picker('Cor da Barra', chart_data.get('gauge_bar_color', '#1f77b4')); target_color = cc2.color_picker('Cor da Meta', chart_data.get('gauge_target_color', '#d62728'))
        show_delta = st.toggle("Mostrar variação vs. média?", value=chart_data.get('show_delta', False)) if kpi_style == 'Número Grande' and num_op != 'Contagem' else False
        chart_config = {'id': str(uuid.uuid4()), 'type': 'indicator', 'title': kpi_title, 'icon': kpi_icon, 'num_op': num_op, 'num_field': num_field, 'use_den': use_den, 'den_op': den_op, 'den_field': den_field, 'style': kpi_style, 'gauge_min': gauge_min, 'gauge_max_static': gauge_max_static, 'target_type': target_type, 'target_op': target_op, 'target_field': target_field, 'show_delta': show_delta, 'gauge_bar_color': bar_color, 'gauge_target_color': target_color, 'creator_type': chart_creator_type}

# BOTÕES DE AÇÃO COM LÓGICA POR PROJETO
st.divider()
if editing_mode:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Salvar Alterações", type="primary", use_container_width=True, icon="💾"):
            all_dashboards = find_user(st.session_state['email']).get('dashboard_layout', {})
            current_project_key = st.session_state.get('project_key')
            project_dashboard = all_dashboards.get(current_project_key, [])
            
            item_index = next((i for i, item in enumerate(project_dashboard) if item["id"] == chart_data["id"]), None)
            
            if item_index is not None:
                new_chart_config = chart_config
                new_chart_config['id'] = chart_data['id'] # Garante que o ID original seja mantido
                project_dashboard[item_index] = new_chart_config
                all_dashboards[current_project_key] = project_dashboard
                save_user_dashboard(st.session_state['email'], all_dashboards)
                st.success("Visualização atualizada com sucesso!")
                del st.session_state['chart_to_edit']
                st.page_link("pages/2_🏠_Meu_Dashboard.py", label="Voltar ao Dashboard", icon="🏠")
            else:
                st.error("Erro ao encontrar a visualização para atualizar.")
    
    # --- BOTÃO DE CANCELAR EDIÇÃO ---
    with col2:
        if st.button("Cancelar Edição", use_container_width=True):
            del st.session_state['chart_to_edit']
            st.rerun()
else:
    # Lógica para adicionar ao dashboard do projeto correto
    all_dashboards = find_user(st.session_state['email']).get('dashboard_layout', {})
    current_project_key = st.session_state.get('project_key')
    project_dashboard = all_dashboards.get(current_project_key, [])
    
    if len(project_dashboard) >= 12:
        st.warning("Limite de 12 visualizações no dashboard deste projeto atingido.")
    else:
        if st.button("Adicionar ao Dashboard", type="primary", use_container_width=True, icon="➕"):
            if chart_config:
                project_dashboard.append(chart_config)
                all_dashboards[current_project_key] = project_dashboard
                save_user_dashboard(st.session_state['email'], all_dashboards)
                st.success(f"Visualização '{chart_config.get('title')}' adicionada ao dashboard do projeto {st.session_state.project_name}!")
            else:
                st.warning("Configuração de visualização inválida.")

st.divider()
st.subheader("Pré-visualização da Configuração Atual")
if chart_config:
    with st.container(border=True):
        render_chart(chart_config, df) # Assumindo que você usa filtered_df para a pré-visualização
else:
    st.info("Configure uma visualização acima para ver a pré-visualização.")