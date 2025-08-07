# pages/5_🏗️_Personalizar Gráficos.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid, json, os
from config import DASHBOARD_CHART_LIMIT
from jira_connector import *
from metrics_calculator import *
from config import *
from utils import *
from security import *
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(page_title="Personalizar Gráficos", page_icon="🏗️", layout="wide")

# --- CSS e Funções Auxiliares ---
st.markdown("""<style> 
    button[data-testid="stButton"][kind="primary"] span svg { fill: white; } 
    [data-testid="stHorizontalBlock"] { align-items: flex-end; }
</style>""", unsafe_allow_html=True)

def on_project_change():
    """Limpa o estado relevante ao trocar de projeto."""
    keys_to_clear = ['dynamic_df', 'chart_to_edit', 'creator_filters']
    for key in keys_to_clear:
        if key in st.session_state: st.session_state.pop(key, None)

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
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
    
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else None
    
    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_creator", index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        project_key = projects[selected_project_name]
        st.session_state.project_key = projects[selected_project_name]; 
        st.session_state.project_name = selected_project_name
        is_data_loaded = 'dynamic_df' in st.session_state and not st.session_state.dynamic_df.empty
        with st.expander("Carregar Dados", expanded=not is_data_loaded):
            if st.button("Carregar / Atualizar Dados", use_container_width=True, type="primary"):

                with st.spinner(f"A carregar e processar dados de '{selected_project_name}'..."):
                    all_issues_raw = get_all_project_issues(st.session_state.jira_client, project_key)
                    valid_issues = filter_ignored_issues(all_issues_raw)
                    
                    data = []
                    user_data = find_user(st.session_state['email'])
                    global_configs = st.session_state.get('global_configs', {})
                    project_config = get_project_config(project_key) or {}
                    
                    user_enabled_standard = user_data.get('standard_fields', [])
                    user_enabled_custom = user_data.get('enabled_custom_fields', [])
                    all_available_standard = global_configs.get('available_standard_fields', {})
                    all_available_custom = global_configs.get('custom_fields', [])
                    estimation_config = project_config.get('estimation_field', {})

                    for i in valid_issues:
                        completion_date = find_completion_date(i)
                        issue_data = {
                            'Issue': i.key,
                            'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),
                            'Data de Conclusão': completion_date,
                            'Lead Time (dias)': calculate_lead_time(i),
                            'Cycle Time (dias)': calculate_cycle_time(i),
                        }
                        
                        # --- LÓGICA DE PROCESSAMENTO UNIVERSAL CORRIGIDA ---
                        fields_to_process = []
                        for field_name in user_enabled_standard:
                            if field_name in all_available_standard:
                                fields_to_process.append({**all_available_standard[field_name], 'name': field_name})
                        for field_config in all_available_custom:
                            if field_config.get('name') in user_enabled_custom:
                                fields_to_process.append(field_config)
                        
                        for field in fields_to_process:
                            field_id, field_name = field['id'], field['name']
                            value = getattr(i.fields, field_id, None)
                            
                            # Lógica inteligente para extrair o valor correto de qualquer tipo de campo
                            if value is None:
                                issue_data[field_name] = None
                            elif hasattr(value, 'displayName'): # Para campos de Utilizador (Assignee, Reporter)
                                issue_data[field_name] = value.displayName
                            elif isinstance(value, list) and value: # Para campos de lista (Seleção Múltipla, Componentes, etc.)
                                processed_list = []
                                for item in value:
                                    if hasattr(item, 'value'): processed_list.append(item.value)
                                    elif hasattr(item, 'name'): processed_list.append(item.name)
                                    else: processed_list.append(str(item))
                                issue_data[field_name] = ', '.join(processed_list)
                            elif hasattr(value, 'value'): # Para campos de Seleção Única
                                issue_data[field_name] = value.value
                            elif hasattr(value, 'name'): # Para campos de Objeto Simples (Status, Priority)
                                issue_data[field_name] = value.name
                            else: # Para campos de texto simples, número ou data
                                issue_data[field_name] = str(value).split('T')[0]

                        # Adiciona o campo de estimativa
                        if estimation_config.get('id'):
                            issue_data[estimation_config['name']] = get_issue_estimation(i, estimation_config)
                            
                        data.append(issue_data)
                    
                    st.session_state.dynamic_df = pd.DataFrame(data)
                    st.rerun()

    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
editing_mode = 'chart_to_edit' in st.session_state and st.session_state.chart_to_edit is not None
chart_data = st.session_state.get('chart_to_edit', {})

if editing_mode: st.header(f"✏️ Editando: {chart_data.get('title', 'Visualização')}", divider='orange')
else: st.header("🏗️ Laboratório de Criação de Gráficos", divider='rainbow')

if 'jira_client' not in st.session_state:
    # Verifica se o utilizador tem alguma conexão guardada na base de dados
    user_connections = get_user_connections(st.session_state['email'])
    
    if not user_connections:
        # Cenário 1: O utilizador nunca configurou uma conexão
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌")
        st.info("Para começar, você precisa de adicionar as suas credenciais do Jira.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗")
        st.stop()
    else:
        # Cenário 2: O utilizador tem conexões, mas nenhuma está ativa
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
        st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
        st.stop()
        
df = st.session_state.get('dynamic_df')
if df is None or df.empty:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Carregar / Atualizar Dados' para começar."); st.stop()
st.caption(f"Utilizando dados do projeto: **{st.session_state.project_name}**")

# --- Lógica de construção de listas de colunas dinâmicas ---
global_configs = st.session_state.get('global_configs', {}); user_data = find_user(st.session_state['email']); project_config = get_project_config(st.session_state.project_key) or {}
user_enabled_standard_fields = user_data.get('standard_fields', []); user_enabled_custom_fields = user_data.get('enabled_custom_fields', [])
all_available_standard = global_configs.get('available_standard_fields', {}); all_available_custom = global_configs.get('custom_fields', [])
project_estimation_field = project_config.get('estimation_field', {})
master_field_list = []
for field in all_available_custom:
    if field.get('name') in user_enabled_custom_fields: master_field_list.append({'name': field['name'], 'type': field.get('type', 'Texto')})
for field_name in user_enabled_standard_fields:
    details = all_available_standard.get(field_name, {})
    if details: master_field_list.append({'name': field_name, 'type': details.get('type', 'Texto')})
if project_estimation_field and project_estimation_field.get('name') not in [f['name'] for f in master_field_list]:
    est_type = 'Numérico' if project_estimation_field.get('source') != 'standard_time' else 'Horas'
    master_field_list.append({'name': project_estimation_field['name'], 'type': est_type})
base_numeric_cols = ['Lead Time (dias)', 'Cycle Time (dias)']; base_date_cols = ['Data de Criação', 'Data de Conclusão']
base_categorical_cols = ['Issue'] # Adicione outros campos base se desejar que apareçam sempre
numeric_cols = sorted(list(set(base_numeric_cols + [f['name'] for f in master_field_list if f['type'] in ['Numérico', 'Horas']])))
date_cols = sorted(list(set(base_date_cols + [f['name'] for f in master_field_list if f['type'] == 'Data'])))
categorical_cols = sorted(list(set(base_categorical_cols + [f['name'] for f in master_field_list if f['type'] in ['Texto (Alfanumérico)', 'Texto']])))
measure_options = ["Contagem de Issues"] + numeric_cols + categorical_cols; all_cols_for_table = sorted(list(set(date_cols + categorical_cols + numeric_cols)))

# --- Filtros Dinâmicos ---
st.divider()
st.subheader("Filtros da Pré-visualização")

if 'creator_filters' not in st.session_state:
    if editing_mode:
        st.session_state.creator_filters = chart_data.get('filters', [])
    else:
        st.session_state.creator_filters = []

def add_filter():
    st.session_state.creator_filters.append({})

def remove_filter(index):
    st.session_state.creator_filters.pop(index)

filter_container = st.container()
with filter_container:
    for i, f in enumerate(st.session_state.creator_filters):
        cols = st.columns([2, 2, 3, 1])
        
        all_filterable_fields = [""] + categorical_cols + numeric_cols
        
        # --- 1. Selecionar o Campo ---
        selected_field = cols[0].selectbox("Campo", options=all_filterable_fields, key=f"filter_field_{i}", index=all_filterable_fields.index(f.get('field')) if f.get('field') in all_filterable_fields else 0)
        st.session_state.creator_filters[i]['field'] = selected_field
        
        # --- 2. Selecionar Operador e Valor ---
        if selected_field:
            field_type = 'numeric' if selected_field in numeric_cols else 'categorical'
            op_options = ['está em', 'não está em', 'é igual a', 'não é igual a'] if field_type == 'categorical' else ['maior que', 'menor que', 'entre', 'é igual a', 'não é igual a']
            
            operator = cols[1].selectbox("Operador", options=op_options, key=f"filter_op_{i}", index=op_options.index(f.get('operator')) if f.get('operator') in op_options else 0)
            st.session_state.creator_filters[i]['operator'] = operator
            
            with cols[2]:
                if operator in ['está em', 'não está em']:
                    options = sorted(df[selected_field].dropna().unique())
                    value = st.multiselect("Valores", options=options, key=f"filter_val_multi_{i}", default=f.get('value', []))
                elif operator == 'entre':
                    min_val, max_val = df[selected_field].min(), df[selected_field].max()
                    value = st.slider("Intervalo", float(min_val), float(max_val), f.get('value', [min_val, max_val]), key=f"filter_val_slider_{i}")
                else: # Inputs únicos
                    if field_type == 'categorical':
                        options = sorted(df[selected_field].dropna().unique())
                        value = st.selectbox("Valor", options=options, key=f"filter_val_single_cat_{i}", index=options.index(f.get('value')) if f.get('value') in options else 0)
                    else: # Numérico
                        value = st.number_input("Valor", key=f"filter_val_single_num_{i}", value=f.get('value', 0.0))
            st.session_state.creator_filters[i]['value'] = value

        cols[3].button("❌", key=f"remove_filter_{i}", on_click=remove_filter, args=(i,), use_container_width=True)

st.button("➕ Adicionar Filtro", on_click=add_filter, use_container_width=True)

# --- Lógica de Aplicação dos Filtros (Atualizada) ---
filtered_df = df.copy()
for f in st.session_state.creator_filters:
    field, op, val = f.get('field'), f.get('operator'), f.get('value')
    if field and op and val is not None:
        if op == 'é igual a': filtered_df = filtered_df[filtered_df[field] == val]
        elif op == 'não é igual a': filtered_df = filtered_df[filtered_df[field] != val]
        elif op == 'está em': filtered_df = filtered_df[filtered_df[field].isin(val)]
        elif op == 'não está em': filtered_df = filtered_df[~filtered_df[field].isin(val)]
        elif op == 'maior que': filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') > val]
        elif op == 'menor que': filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') < val]
        elif op == 'entre' and len(val) == 2:
            filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce').between(val[0], val[1])]
        if field in date_cols:
            if op == "Períodos Relativos":
                # --- NOVOS MAPEAMENTOS ADICIONADOS AQUI ---
                days_map = {
                    "Últimos 7 dias": 7, "Últimos 14 dias": 14, "Últimos 30 dias": 30, 
                    "Últimos 60 dias": 60, "Últimos 90 dias": 90, "Últimos 120 dias": 120, 
                    "Últimos 150 dias": 150, "Últimos 180 dias": 180
                }
                end_date = pd.to_datetime(datetime.now().date())
                start_date = end_date - timedelta(days=days_map.get(val, 0))
                filtered_df = filtered_df[(pd.to_datetime(filtered_df[field]) >= start_date) & (pd.to_datetime(filtered_df[field]) <= end_date)]
            elif op == "Período Personalizado" and len(val) == 2:
                start_date, end_date = pd.to_datetime(val[0]), pd.to_datetime(val[1])
                filtered_df = filtered_df[(pd.to_datetime(filtered_df[field]) >= start_date) & (pd.to_datetime(filtered_df[field]) <= end_date)]

st.divider()

# --- Construtor de Gráficos Unificado ---
st.subheader("Configuração da Visualização")
creation_mode = st.radio("Como deseja criar a sua visualização?", ["Construtor Visual", "Gerar com IA ✨"], horizontal=True, key="creation_mode_selector")
chart_config = {}
df_for_preview = filtered_df.copy()

if creation_mode == "Construtor Visual":
    creator_type_options = ["Gráfico X-Y", "Gráfico Agregado", "Indicador (KPI)", "Tabela Dinâmica"]
    default_creator_index = creator_type_options.index(chart_data.get('creator_type')) if editing_mode and chart_data.get('creator_type') in creator_type_options else 0
    chart_creator_type = st.radio("Selecione o tipo de visualização:", creator_type_options, key="visual_creator_type", horizontal=True, index=default_creator_index)
    
    # Define um dataframe temporário que pode ser modificado pelos construtores
    chart_config = {}
    df_for_preview = filtered_df.copy()

    with st.container(border=True):
        if chart_creator_type == "Gráfico X-Y":
            # --- Interface Principal ---
            st.markdown("###### **Configuração do Gráfico X-Y**")
            c1, c2, c3 = st.columns(3)
            x_options = date_cols + numeric_cols
            y_options = numeric_cols
            type_options = ["Dispersão", "Linha"]

            x_idx = x_options.index(chart_data.get('x')) if editing_mode and chart_data.get('x') in x_options else 0
            y_idx = y_options.index(chart_data.get('y')) if editing_mode and chart_data.get('y') in y_options else 0
            type_idx = type_options.index(chart_data.get('type', 'dispersão').capitalize()) if editing_mode and chart_data.get('type','').capitalize() in type_options else 0
            
            x = c1.selectbox("Eixo X", x_options, index=x_idx)
            y = c2.selectbox("Eixo Y", y_options, index=y_idx)
            chart_type = c3.radio("Formato", type_options, index=type_idx, horizontal=True).lower()
            
            st.divider()

            # --- Interface para Cor e Dimensão Combinada ---
            COMBINED_DIMENSION_OPTION = "— Criar Dimensão Combinada —"
            color_options = ["Nenhum", COMBINED_DIMENSION_OPTION] + categorical_cols
            color_idx = color_options.index(chart_data.get('color_by')) if editing_mode and chart_data.get('color_by') in color_options else 0
            color_selection = st.selectbox("Colorir por (Dimensão Opcional)", color_options, index=color_idx)
            
            final_color_by = color_selection
            if color_selection == COMBINED_DIMENSION_OPTION:
                with st.container(border=True):
                    final_color_by, df_for_preview = combined_dimension_ui(filtered_df, categorical_cols, date_cols, key_suffix="xy")

            # --- Título e Rótulos ---
            custom_title_input = st.text_input("Título do Gráfico:", value=chart_data.get('title', f"{y} vs {x}"), key="chart_title_input_xy")
            show_labels = st.toggle("Exibir Rótulos de Dados", key="xy_labels", value=chart_data.get('show_data_labels', False))
            chart_config = {
                'id': str(uuid.uuid4()), 'type': chart_type, 'x': x, 'y': y, 
                'title': custom_title_input.strip(),
                'creator_type': chart_creator_type, 'source_type': 'visual', 
                'color_by': final_color_by, 'filters': st.session_state.get('creator_filters', []), 
                'show_data_labels': show_labels
            }

        elif chart_creator_type == "Gráfico Agregado":
            # --- Interface Principal ---
            st.markdown("###### **Configuração do Gráfico Agregado**")
            COMBINED_DIMENSION_OPTION = "— Criar Dimensão Combinada —"
            dim_options = [COMBINED_DIMENSION_OPTION] + categorical_cols
            dim_selection = st.selectbox("Dimensão (Agrupar por)", options=dim_options, index=dim_options.index(chart_data.get('dimension')) if editing_mode and chart_data.get('dimension') in dim_options else 0)
            
            final_dimension = dim_selection
            if dim_selection == COMBINED_DIMENSION_OPTION:
                with st.container(border=True):
                    final_dimension, df_for_preview = combined_dimension_ui(filtered_df, categorical_cols, date_cols, key_suffix="agg")

            if final_dimension:
                st.divider()
                c1, c2, c3 = st.columns([2, 1, 2])
                measure = c1.selectbox("Medida (Calcular)", options=measure_options, index=measure_options.index(chart_data.get('measure')) if editing_mode and chart_data.get('measure') in measure_options else 0)
                
                if measure in categorical_cols:
                    agg = 'Contagem Distinta'; c2.info("Contagem Distinta", icon="🔢")
                elif measure in numeric_cols:
                    agg_options = ["Soma", "Média"]; agg_idx = agg_options.index(chart_data.get('agg', 'Soma')) if editing_mode and chart_data.get('agg') in agg_options else 0
                    agg = c2.radio("Cálculo", agg_options, index=agg_idx, horizontal=True)
                else: # Contagem de Issues
                    agg = 'Contagem'; c2.info("Contagem", icon="🧮")

                format_options = ["Barras", "Linhas", "Pizza", "Treemap", "Funil", "Tabela"]
                type_map_inv = {'barra': 'Barras', 'linha_agregada': 'Linhas', 'pizza': 'Pizza', 'treemap': 'Treemap', 'funil': 'Funil', 'tabela':'Tabela'}
                type_from_data = type_map_inv.get(chart_data.get('type', 'barra')); type_idx = format_options.index(type_from_data) if editing_mode and type_from_data in format_options else 0
                chart_type_str = c3.radio("Formato", format_options, index=type_idx, horizontal=True)
                chart_type = chart_type_str.lower().replace("s", "").replace("á", "a")
                
                auto_title = f"Análise de '{measure}' por '{final_dimension}'" if chart_type != 'tabela' else "Tabela de Dados"
                custom_title = st.text_input("Título do Gráfico:", value=chart_data.get('title', auto_title), key="chart_title_input_agg")
                show_labels = st.toggle("Exibir Rótulos de Dados", key="agg_labels", value=chart_data.get('show_data_labels', False))

                if chart_type == 'tabela':
                    selected_cols = st.multiselect("Selecione as colunas para a tabela", options=all_cols_for_table, default=chart_data.get('columns', []))
                    chart_config = {'id': str(uuid.uuid4()), 'type': chart_type, 'columns': selected_cols, 'title': custom_title, 'creator_type': chart_creator_type, 'source_type': 'visual', 'filters': st.session_state.get('creator_filters', [])}
                else:
                    chart_config = {'id': str(uuid.uuid4()), 'type': 'linha_agregada' if chart_type == 'linha' else chart_type, 'dimension': final_dimension, 'measure': measure, 'agg': agg, 'title': custom_title, 'creator_type': chart_creator_type, 'source_type': 'visual', 'filters': st.session_state.get('creator_filters', []), 'show_data_labels': show_labels}

        # --- CONSTRUTOR DE INDICADOR (KPI) (COMPLETO) ---
        elif chart_creator_type == "Indicador (KPI)":
            
            kpi_source_type = st.radio(
                "Como deseja criar o seu KPI?",
                ["Construtor Visual", "Avançado (com JQL)"],
                horizontal=True,
                key="kpi_source_selector"
            )
            st.divider()

            # --- MODO AVANÇADO (JQL) ---
            if kpi_source_type == "Avançado (com JQL)":
                st.info("Crie um KPI com até três consultas JQL para cálculos personalizados.", icon="💡")
                
                kpi_title = st.text_input("Título do Indicador", key="jql_kpi_title", value=chart_data.get('title', ''))
                
                st.markdown("**Consulta JQL 1 (Valor A)**")
                col1, col2 = st.columns([4, 1])
                jql_a = col1.text_area("JQL 1", placeholder='project = "PROJ" AND issuetype = Bug', value=chart_data.get('jql_a', ''), label_visibility="collapsed")
                with col2:
                    st.write("") # Espaçador
                    if st.button("Testar", key="test_jql_a", use_container_width=True):
                        with st.spinner("Testando..."): st.session_state.jql_test_result_a = get_jql_issue_count(st.session_state.jira_client, jql_a)

                if st.session_state.get('jql_test_result_a') is not None:
                    st.success(f"Resultado do Teste: **{st.session_state.jql_test_result_a}** issues encontradas.", icon="✅")
                    st.session_state.pop('jql_test_result_a', None)

                use_b = st.checkbox("Usar uma segunda consulta (Valor B)?", value=bool(chart_data.get('jql_b')))
                jql_b, operation = None, None
                
                if use_b:
                    st.markdown("**Consulta JQL 2 (Valor B)**")
                    col3, col4 = st.columns([4, 1])
                    jql_b = col3.text_area("JQL 2", placeholder='project = "PROJ"', value=chart_data.get('jql_b', ''), label_visibility="collapsed")
                    with col4:
                        st.write("")
                        if st.button("Testar", key="test_jql_b", use_container_width=True):
                            with st.spinner("Testando..."): st.session_state.jql_test_result_b = get_jql_issue_count(st.session_state.jira_client, jql_b)

                    if st.session_state.get('jql_test_result_b') is not None:
                        st.success(f"Resultado do Teste: **{st.session_state.jql_test_result_b}** issues encontradas.", icon="✅")
                        st.session_state.pop('jql_test_result_b', None)
                    
                    op_options = ['Dividir (A / B)', 'Somar (A + B)', 'Subtrair (A - B)', 'Multiplicar (A * B)']
                    op_idx = op_options.index(chart_data.get('jql_operation')) if editing_mode and chart_data.get('jql_operation') in op_options else 0
                    operation = st.selectbox("Operação Aritmética", options=op_options, index=op_idx)

                st.divider()
                use_baseline = st.checkbox("Mostrar variação contra uma linha de base (JQL C)?", value=bool(chart_data.get('jql_baseline')))
                jql_c = None
                
                if use_baseline:
                    st.markdown("**Consulta JQL da Linha de Base (Valor C)**")
                    col5, col6 = st.columns([4, 1])
                    jql_c = col5.text_area("JQL C", placeholder='project = "PROJ" AND created >= -14d AND created < -7d', value=chart_data.get('jql_baseline', ''), label_visibility="collapsed")
                    with col6:
                        st.write("")
                        if st.button("Testar", key="test_jql_c", use_container_width=True):
                            with st.spinner("Testando..."): st.session_state.jql_test_result_c = get_jql_issue_count(st.session_state.jira_client, jql_c)
                    
                    if st.session_state.get('jql_test_result_c') is not None:
                        st.success(f"Resultado do Teste: **{st.session_state.jql_test_result_c}** issues encontradas.", icon="✅")
                        st.session_state.pop('jql_test_result_c', None)

                chart_config = {
                    'id': str(uuid.uuid4()), 'type': 'indicator', 'style': 'Número Grande',
                    'title': kpi_title, 'icon': "🧮", 'source_type': 'jql',
                    'jql_a': jql_a, 'jql_b': jql_b if use_b else None,
                    'jql_operation': operation if use_b else None,
                    'jql_baseline': jql_c if use_baseline else None,
                    'creator_type': chart_creator_type,
                    'filters': st.session_state.get('creator_filters', [])
                }

            # --- MODO VISUAL (EXISTENTE) ---
            else: # Construtor Visual
                c1, c2 = st.columns([3, 1]); kpi_title = c1.text_input("Título do Indicador", value=chart_data.get('title', '')); kpi_icon = c2.text_input("Ícone", value=chart_data.get('icon', '🚀'))
                st.markdown("**Valor Principal (Numerador)**"); c1, c2 = st.columns(2); num_field_opts = ["Contagem de Issues"] + numeric_cols + categorical_cols
                num_field_idx = num_field_opts.index(chart_data.get('num_field')) if editing_mode and chart_data.get('num_field') in num_field_opts else 0
                num_field = c2.selectbox("Campo", num_field_opts, key='kpi_num_field', index=num_field_idx)
                if num_field == 'Contagem de Issues': num_op = 'Contagem'; c1.text_input("Operação", value="Contagem", disabled=True)
                else:
                    num_op_opts = ["Soma", "Média", "Contagem"]; num_op_idx = num_op_opts.index(chart_data.get('num_op')) if editing_mode and chart_data.get('num_op') in num_op_opts else 0
                    num_op = c1.selectbox("Operação", num_op_opts, key='kpi_num_op', index=num_op_idx)
                use_den = st.checkbox("Adicionar Denominador (para rácio)?", value=chart_data.get('use_den', False)); den_op, den_field = (None, None)
                if use_den:
                    st.markdown("**Denominador**"); c3, c4 = st.columns(2); den_field_opts = ["Contagem de Issues"] + numeric_cols + categorical_cols
                    den_field_idx = den_field_opts.index(chart_data.get('den_field')) if editing_mode and chart_data.get('den_field') in den_field_opts else 0
                    den_field = c4.selectbox("Campo ", den_field_opts, key='kpi_den_field', index=den_field_idx)
                    if den_field == 'Contagem de Issues': den_op = 'Contagem'; c3.text_input("Operação ", value="Contagem", disabled=True)
                    else:
                        den_op_opts = ["Soma", "Média", "Contagem"]; den_op_idx = den_op_opts.index(chart_data.get('den_op')) if editing_mode and chart_data.get('den_op') in den_op_opts else 0
                        den_op = c3.selectbox("Operação ", den_op_opts, key='kpi_den_op', index=den_op_idx)
                
                st.divider(); kpi_style_opts = ["Número Grande", "Medidor (Gauge)", "Gráfico de Bala (Bullet)"]; style_idx = kpi_style_opts.index(chart_data.get('style')) if editing_mode and chart_data.get('style') in kpi_style_opts else 0
                kpi_style = st.selectbox("Estilo de Exibição", kpi_style_opts, index=style_idx)
                
                target_type = chart_data.get('target_type', 'Fixo'); gauge_max_static = chart_data.get('gauge_max_static', 100); target_op = chart_data.get('target_op'); target_field = chart_data.get('target_field');
                gauge_poor_threshold = chart_data.get('gauge_poor_threshold', 50); gauge_good_threshold = chart_data.get('gauge_good_threshold', 80);
                bar_color = chart_data.get('gauge_bar_color', '#1f77b4'); target_color = chart_data.get('gauge_target_color', '#d62728')

                if kpi_style in ['Medidor (Gauge)', 'Gráfico de Bala (Bullet)']:
                    st.markdown("**Configurações de Medição:**")
                    c1,c2 = st.columns(2); target_type_opts = ["Valor Fixo", "Valor Dinâmico"]; target_type_idx = target_type_opts.index(chart_data.get('target_type', 'Fixo')) if editing_mode else 0
                    with c1: target_type = st.radio("Definir Meta como:", target_type_opts, horizontal=True, index=target_type_idx)
                    if target_type == "Valor Fixo": gauge_max_static = c2.number_input("Valor da Meta", value=gauge_max_static)
                    else:
                        c3, c4 = st.columns(2); target_field_opts = ['Issues'] + numeric_cols + categorical_cols; target_field_idx = target_field_opts.index(target_field) if editing_mode and target_field in target_field_opts else 0
                        target_field = c4.selectbox("Campo da Meta", target_field_opts, key='kpi_target_field', index=target_field_idx)
                        if target_field == 'Issues': target_op = 'Contagem'; c3.text_input("Operação da Meta", value="Contagem", disabled=True)
                        else:
                            target_op_opts = ["Soma", "Média", "Contagem"]; target_op_idx = target_op_opts.index(target_op) if editing_mode and target_op in target_op_opts else 0
                            target_op = c3.selectbox("Operação da Meta", target_op_opts, key='kpi_target_op', index=target_op_idx)
                    st.markdown("**Limites de Cor:**"); c1, c2 = st.columns(2)
                    gauge_poor_threshold = c1.number_input("Valor máximo para 'Ruim' (vermelho)", value=gauge_poor_threshold)
                    gauge_good_threshold = c2.number_input("Valor mínimo para 'Bom' (verde)", value=gauge_good_threshold)
                    cc1, cc2 = st.columns(2); bar_color = cc1.color_picker('Cor da Barra Principal', bar_color); target_color = cc2.color_picker('Cor da Linha de Meta', target_color)
                
                show_delta = st.toggle("Mostrar variação vs. média?", value=chart_data.get('show_delta', False)) if kpi_style == 'Número Grande' and num_field != 'Issues' else False
                
                chart_config = {
                    'id': str(uuid.uuid4()), 'type': 'indicator', 'title': kpi_title, 'icon': kpi_icon,
                    'num_op': num_op, 'num_field': num_field, 'use_den': use_den, 'den_op': den_op, 'den_field': den_field,
                    'style': kpi_style, 'gauge_min': chart_data.get('gauge_min',0), 'gauge_max_static': gauge_max_static,
                    'target_type': target_type, 'target_op': target_op, 'target_field': target_field, 'show_delta': show_delta,
                    'gauge_bar_color': bar_color, 'gauge_target_color': target_color, 'gauge_poor_threshold': gauge_poor_threshold,
                    'gauge_good_threshold': gauge_good_threshold, 'creator_type': chart_creator_type,
                    'source_type': 'visual',
                    'filters': st.session_state.get('creator_filters', [])
                }

        elif chart_creator_type == "Tabela Dinâmica":
            st.info("Crie uma tabela de referência cruzada para analisar a relação entre três campos.", icon="↔️")
            
            c1, c2, c3, c4 = st.columns(4)
            
            # Lógica de pré-seleção para o modo de edição
            rows_idx = categorical_cols.index(chart_data.get('rows')) if editing_mode and chart_data.get('rows') in categorical_cols else 0
            cols_idx = categorical_cols.index(chart_data.get('columns')) if editing_mode and chart_data.get('columns') in categorical_cols else 1
            vals_idx = numeric_cols.index(chart_data.get('values')) if editing_mode and chart_data.get('values') in numeric_cols else 0
            agg_opts = ["Soma", "Média", "Contagem"]; agg_idx = agg_opts.index(chart_data.get('aggfunc', 'Soma')) if editing_mode else 0

            # Seletores para a configuração
            rows = c1.selectbox("Agrupar Linhas por:", options=categorical_cols, key="pivot_rows", index=rows_idx)
            columns = c2.selectbox("Agrupar Colunas por:", options=categorical_cols, key="pivot_cols", index=cols_idx)
            values = c3.selectbox("Calcular Valores de:", options=numeric_cols, key="pivot_values", index=vals_idx)
            aggfunc = c4.selectbox("Usando o Cálculo:", options=agg_opts, key="pivot_agg", index=agg_idx)

            auto_title = f"{aggfunc} de '{values}' por '{rows}' e '{columns}'"
            custom_title_input = st.text_input("Título da Tabela:", value=chart_data.get('title', auto_title))

            
            chart_config = {
                'id': str(uuid.uuid4()), 'type': 'pivot_table', 
                'title': custom_title_input.strip(), # Limpa o título
                'rows': rows, 'columns': columns, 'values': values, 'aggfunc': aggfunc,
                'creator_type': chart_creator_type, 'source_type': 'visual',
                'filters': st.session_state.get('creator_filters', [])
            }
else: # MODO DE GERAÇÃO COM IA
    st.subheader("🤖 Assistente de Geração de Gráficos com IA")
    st.info("Descreva o gráfico que você quer ver, e o Gemini irá tentar criá-lo para si.")
    
    prompt = st.text_area("O seu pedido:", placeholder="Ex: Crie um gráfico de barras com a contagem de issues por responsável", height=100)
    
    if st.button("Gerar Gráfico com IA", use_container_width=True, type="primary"):
        if prompt:
            with st.spinner("O Gemini está a pensar..."):
                generated_config, error_message = generate_chart_config_from_text(prompt, numeric_cols, categorical_cols)
                if error_message:
                    st.error(error_message)
                else:
                    st.session_state.chart_config_ia = generated_config
        else:
            st.warning("Por favor, escreva o seu pedido.")

# --- Lógica de Pré-visualização Unificada ---
if creation_mode == "Gerar com IA ✨":
    chart_config = st.session_state.get('chart_config_ia', {})

# --- Lógica de Pré-visualização Unificada ---
st.divider()

st.subheader("Pré-visualização da Configuração Atual")
if chart_config:
    with st.container(border=True): render_chart(chart_config, df_for_preview)
else:
    st.info("Configure ou gere uma visualização acima para ver a pré-visualização.")

# --- BOTÕES DE AÇÃO ---
st.divider()
if editing_mode:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Salvar Alterações", type="primary", use_container_width=True, icon="💾", key="save_changes_btn"):
            if chart_config and chart_config.get('title'):
                chart_config['filters'] = convert_dates_in_filters(st.session_state.get('creator_filters', []))

                all_dashboards = find_user(st.session_state['email']).get('dashboard_layout', {})
                current_project_key = st.session_state.get('project_key')
                project_dashboard = all_dashboards.get(current_project_key, {})
                
                tabs_layout = project_dashboard.get("tabs", {"Geral": []})
                
                # Limpa quaisquer itens inválidos (que não sejam dicionários) de todas as abas
                for tab_name, charts in tabs_layout.items():
                    tabs_layout[tab_name] = [item for item in charts if isinstance(item, dict)]

                # Encontra o gráfico e a aba a serem atualizados
                chart_found = False
                for tab_name, charts in tabs_layout.items():
                    item_index = next((i for i, item in enumerate(charts) if item.get("id") == chart_data.get("id")), None)
                    if item_index is not None:
                        new_chart_config = chart_config; new_chart_config['id'] = chart_data['id']
                        tabs_layout[tab_name][item_index] = new_chart_config
                        chart_found = True
                        break
                
                if chart_found:
                    project_dashboard["tabs"] = tabs_layout
                    all_dashboards[current_project_key] = project_dashboard
                    save_user_dashboard(st.session_state['email'], all_dashboards)
                    st.success("Visualização atualizada! A redirecionar..."); del st.session_state['chart_to_edit'];
                    st.switch_page("pages/2_🏠_Meu_Dashboard.py")
                else: 
                    st.error("Erro ao encontrar a visualização para atualizar. Pode ter sido removida.")
            else: 
                st.warning("Configuração de visualização inválida ou sem título.")
    with col2:
        if st.button("Cancelar Edição", use_container_width=True, key="cancel_edit_btn"): 
            del st.session_state['chart_to_edit']; st.rerun()
else:
    user_data = find_user(st.session_state['email'])
    all_dashboards = user_data.get('dashboard_layout', {})
    current_project_key = st.session_state.get('project_key')
    dashboard_config = all_dashboards.get(current_project_key, {"tabs": {"Geral": []}})
    tabs_layout = dashboard_config.get("tabs", {"Geral": []})
    all_charts_count = sum(len(charts) for charts in tabs_layout.values())

    if all_charts_count >= DASHBOARD_CHART_LIMIT:
        st.warning(f"Limite de {DASHBOARD_CHART_LIMIT} visualizações no dashboard deste projeto atingido.")
    else:
        if st.button("Adicionar ao Meu Dashboard", type="primary", use_container_width=True, icon="➕"):
            if chart_config and chart_config.get('title'):
                # Lógica de Ler-Modificar-Guardar
                user_data = find_user(st.session_state['email'])
                all_dashboards = user_data.get('dashboard_layout', {})
                current_project_key = st.session_state.get('project_key')
                dashboard_config = all_dashboards.get(current_project_key, {"tabs": {"Geral": []}})
                tabs_layout = dashboard_config.get("tabs", {"Geral": []})
                all_charts = [chart for tab_charts in tabs_layout.values() for chart in tab_charts]

                if len(all_charts) >= 12:
                    st.warning("Limite de 12 visualizações no dashboard deste projeto atingido.")
                else:
                    if "Geral" not in tabs_layout: tabs_layout["Geral"] = []
                    tabs_layout["Geral"].append(chart_config)
                    dashboard_config["tabs"] = tabs_layout
                    all_dashboards[current_project_key] = dashboard_config
                    save_user_dashboard(st.session_state['email'], all_dashboards)
                    
                    # Limpa o estado e redireciona
                    if 'chart_config_ia' in st.session_state: del st.session_state['chart_config_ia']
                    st.success(f"Visualização adicionada! A redirecionar...")
                    st.switch_page("pages/2_🏠_Meu_Dashboard.py")
            else: 
                st.warning("Configuração de visualização inválida ou sem título.")
            st.session_state.creator_filters = []
            st.rerun()