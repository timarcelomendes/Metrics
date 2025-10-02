# pages/5_🏗️_Construir Gráficos.py

import streamlit as st
import pandas as pd
import uuid
from pathlib import Path
from datetime import datetime, timedelta
import importlib
import jira_connector
from jira_connector import get_jql_issue_count

# Supondo que as suas outras importações estejam aqui
from config import *
from utils import *
from security import *

st.set_page_config(page_title="Personalizar Gráficos", page_icon="🏗️", layout="wide")

def on_project_change():
    """Limpa o estado relevante ao trocar de projeto."""
    keys_to_clear = ['dynamic_df', 'chart_to_edit', 'creator_filters', 'chart_config_ia']
    for key in keys_to_clear:
        if key in st.session_state: st.session_state.pop(key, None)

editing_mode = 'chart_to_edit' in st.session_state and st.session_state.chart_to_edit is not None
chart_data = st.session_state.get('chart_to_edit', {})

if editing_mode: st.header(f"✏️ Editando: {chart_data.get('title', 'Visualização')}", divider='orange')
else: st.header("🏗️ Laboratório de Criação de Gráficos", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    # ... (o seu bloco de "nenhuma conexão ativa" permanece aqui)
    st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
    st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
    st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
    st.stop()

# --- CSS e Funções Auxiliares ---
st.markdown("""<style> 
    button[data-testid="stButton"][kind="primary"] span svg { fill: white; } 
    [data-testid="stHorizontalBlock"] { align-items: flex-end; }
</style>""", unsafe_allow_html=True)
        
# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    st.logo(str(logo_path), size="large")
    
    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), project_names[0] if project_names else None)) if last_project_key else 0

    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_creator", index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]; st.session_state.project_name = selected_project_name
        is_data_loaded = 'dynamic_df' in st.session_state and not st.session_state.dynamic_df.empty
        with st.expander("Carregar Dados", expanded=not is_data_loaded):
            
            # --- SOLUÇÃO FINAL E DEFINITIVA ---
            if st.button("Construir Gráficos", use_container_width=True, type="primary", icon="🔎"):
                # 1. Força o Python a reler o ficheiro jira_connector.py do disco
                importlib.reload(jira_connector)
                
                # 2. Chama a função a partir do módulo recarregado
                df = jira_connector.load_and_process_project_data(
                    st.session_state.jira_client,
                    st.session_state.project_key
                )
                st.session_state.dynamic_df = df
                st.rerun()

        if st.button("Logout", use_container_width=True, type='secondary'):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')

if df is None or not current_project_key:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Construir Gráficos' para começar.")
    st.stop()

st.caption(f"Utilizando dados do projeto: **{st.session_state.project_name}**")

# ======================= INÍCIO DO CÓDIGO DE DEBUG =======================
with st.expander("🐞 DEBUG: Verificar Colunas do DataFrame Carregado", expanded=True):
    st.warning("Esta é uma mensagem de depuração e pode ser removida mais tarde.")
    
    if df is not None:
        st.write("Abaixo estão as primeiras 5 linhas do DataFrame carregado:")
        st.dataframe(df.head())
        
        st.write("Lista de todas as colunas disponíveis:")
        # Filtra para mostrar especificamente as colunas que nos interessam
        tempo_em_status_cols = [col for col in df.columns if col.startswith('Tempo em:')]
        
        if tempo_em_status_cols:
            st.success(f"SUCESSO: {len(tempo_em_status_cols)} colunas de 'Tempo em Status' foram encontradas!")
            st.write(tempo_em_status_cols)
        else:
            st.error("FALHA: Nenhuma coluna 'Tempo em Status' (com o prefixo 'Tempo em:') foi encontrada no DataFrame.")
            st.info("Isso significa que o cálculo não está a ser executado ou não está a adicionar as colunas ao DataFrame final.")
            
    else:
        st.write("O DataFrame (df) ainda não foi carregado.")
# ======================== FIM DO CÓDIGO DE DEBUG =========================


st.caption(f"Utilizando dados do projeto: **{st.session_state.project_name}**")

# --- Lógica de construção de listas de colunas dinâmicas ---
global_configs = st.session_state.get('global_configs', {}); user_data = find_user(st.session_state['email']); project_config = get_project_config(current_project_key) or {}
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
base_categorical_cols = ['Issue'];
for col in ['Tipo de Issue', 'Responsável', 'Status', 'Prioridade', 'Categoria de Status']:
    if col in df.columns:
        base_categorical_cols.append(col)
numeric_cols = sorted(list(set(base_numeric_cols + [f['name'] for f in master_field_list if f['type'] in ['Numérico', 'Horas']])))
date_cols = sorted(list(set(base_date_cols + [f['name'] for f in master_field_list if f['type'] == 'Data'])))
categorical_cols = sorted(list(set(base_categorical_cols + [f['name'] for f in master_field_list if f['type'] in ['Texto (Alfanumérico)', 'Texto']])))
status_time_cols = sorted([col for col in df.columns if col.startswith('Tempo em: ')])

# --- CORREÇÃO DA MÉTRICA "Tempo em Status" ---
measure_options = ["Contagem de Issues"] + numeric_cols + categorical_cols
if project_config.get('calculate_time_in_status', False):
    measure_options.append("Tempo em Status")
all_cols_for_table = sorted(list(set(date_cols + categorical_cols + numeric_cols + status_time_cols)))

# ===== FILTROS DINÂMICOS COM PERÍODOS RELATIVOS =====
st.subheader("Filtros da Pré-visualização")

if 'creator_filters' not in st.session_state:
    st.session_state.creator_filters = chart_data.get('filters', []) if editing_mode else []

with st.container():
    for i, f in enumerate(st.session_state.creator_filters):
        cols = st.columns([2, 2, 3, 1])
        all_filterable_fields = [""] + categorical_cols + numeric_cols + date_cols
        
        previous_field = f.get('field')
        selected_field = cols[0].selectbox("Campo", options=all_filterable_fields, key=f"filter_field_{i}", index=all_filterable_fields.index(previous_field) if previous_field in all_filterable_fields else 0)
        
        if selected_field != previous_field:
            st.session_state.creator_filters[i] = {'field': selected_field}
            st.rerun()
        
        st.session_state.creator_filters[i]['field'] = selected_field
        
        operator, value = None, None
        if selected_field:
            field_type = 'numeric' if selected_field in numeric_cols else 'date' if selected_field in date_cols else 'categorical'
            
            if field_type == 'categorical':
                op_options = ['está em', 'não está em', 'é igual a', 'não é igual a']
                operator = cols[1].selectbox("Operador", options=op_options, key=f"filter_op_cat_{i}", index=op_options.index(f.get('operator')) if f.get('operator') in op_options else 0)
                options = sorted(df[selected_field].dropna().unique())
                if operator in ['está em', 'não está em']:
                    value = cols[2].multiselect("Valores", options=options, key=f"filter_val_multi_{i}", default=f.get('value', []))
                else:
                    value = cols[2].selectbox("Valor", options=options, key=f"filter_val_single_cat_{i}", index=options.index(f.get('value')) if f.get('value') in options else 0)

            elif field_type == 'numeric':
                op_options = ['maior que', 'menor que', 'entre', 'é igual a', 'não é igual a']
                operator = cols[1].selectbox("Operador", options=op_options, key=f"filter_op_num_{i}", index=op_options.index(f.get('operator')) if f.get('operator') in op_options else 0)
                if operator == 'entre':
                    min_val, max_val = df[selected_field].min(), df[selected_field].max()
                    value = cols[2].slider("Intervalo", float(min_val), float(max_val), f.get('value', [min_val, max_val]), key=f"filter_val_slider_{i}")
                else:
                    value = cols[2].number_input("Valor", key=f"filter_val_num_{i}", value=f.get('value', 0.0))

            elif field_type == 'date':
                op_options = ["Períodos Relativos", "Período Personalizado"]
                operator = cols[1].selectbox("Operador", op_options, key=f"filter_op_date_{i}")
                if operator == "Períodos Relativos":
                    period_options = ["Últimos 7 dias", "Últimos 14 dias", "Últimos 30 dias", "Últimos 60 dias", "Últimos 90 dias", "Últimos 120 dias", "Últimos 150 dias", "Últimos 180 dias"]
                    value = cols[2].selectbox("Período", period_options, key=f"filter_val_period_{i}")
                else:
                    value = cols[2].date_input("Intervalo", value=(datetime.now().date() - timedelta(days=30), datetime.now().date()), key=f"filter_val_date_range_{i}")

            st.session_state.creator_filters[i]['operator'] = operator
            st.session_state.creator_filters[i]['value'] = value

        cols[3].button("❌", key=f"remove_filter_{i}", on_click=lambda i=i: st.session_state.creator_filters.pop(i), use_container_width=True)

if st.button("➕ Adicionar Filtro", on_click=lambda: st.session_state.creator_filters.append({}), use_container_width=True):
    pass

filtered_df = df.copy()
for f in st.session_state.creator_filters:
    field, op, val = f.get('field'), f.get('operator'), f.get('value')
    if field and op and val is not None:
        try:
            if op == 'é igual a': filtered_df = filtered_df[filtered_df[field] == val]
            elif op == 'não é igual a': filtered_df = filtered_df[filtered_df[field] != val]
            elif op == 'está em': filtered_df = filtered_df[filtered_df[field].isin(val)]
            elif op == 'não está em': filtered_df = filtered_df[~filtered_df[field].isin(val)]
            elif op == 'maior que': filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') > val]
            elif op == 'menor que': filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce') < val]
            elif op == 'entre' and len(val) == 2:
                filtered_df = filtered_df[pd.to_numeric(filtered_df[field], errors='coerce').between(val[0], val[1])]
        except Exception: pass

        if field in date_cols:
            if op == "Períodos Relativos":
                days_map = { "Últimos 7 dias": 7, "Últimos 14 dias": 14, "Últimos 30 dias": 30, "Últimos 60 dias": 60, "Últimos 90 dias": 90, "Últimos 120 dias": 120, "Últimos 150 dias": 150, "Últimos 180 dias": 180 }
                end_date = pd.to_datetime(datetime.now().date())
                start_date = end_date - timedelta(days=days_map.get(val, 0))
                filtered_df = filtered_df[(pd.to_datetime(filtered_df[field]) >= start_date) & (pd.to_datetime(filtered_df[field]) <= end_date)]
            elif op == "Período Personalizado" and len(val) == 2:
                start_date, end_date = pd.to_datetime(val[0]), pd.to_datetime(val[1])
                filtered_df = filtered_df[(pd.to_datetime(filtered_df[field]) >= start_date) & (pd.to_datetime(filtered_df[field]) <= end_date)]

st.divider()

st.subheader("Configuração da Visualização")
creation_mode = st.radio("Como deseja criar a sua visualização?", ["Construtor Visual", "Gerar com IA ✨"], horizontal=True, key="creation_mode_selector")
chart_config = {}
df_for_preview = filtered_df.copy()
new_measure_col = None

if creation_mode == "Construtor Visual":
    creator_type_options = ["Gráfico X-Y", "Gráfico Agregado", "Indicador (KPI)", "Tabela Dinâmica"]
    default_creator_index = creator_type_options.index(chart_data.get('creator_type')) if editing_mode and chart_data.get('creator_type') in creator_type_options else 0
    chart_creator_type = st.radio("Selecione o tipo de visualização:", creator_type_options, key="visual_creator_type", horizontal=True, index=default_creator_index)

    with st.container(border=True):
        if chart_creator_type == "Gráfico X-Y":
            st.markdown("###### **Configuração do Gráfico X-Y**")
            c1, c2, c3 = st.columns(3)
            x_options, y_options, type_options = date_cols + numeric_cols, numeric_cols, ["Dispersão", "Linha"]
            x_idx, y_idx, type_idx = (x_options.index(chart_data.get('x')) if editing_mode and chart_data.get('x') in x_options else 0,
                                      y_options.index(chart_data.get('y')) if editing_mode and chart_data.get('y') in y_options else 0,
                                      type_options.index(chart_data.get('type', 'dispersão').capitalize()) if editing_mode and chart_data.get('type','').capitalize() in type_options else 0)
            x, y, chart_type = c1.selectbox("Eixo X", x_options, index=x_idx), c2.selectbox("Eixo Y", y_options, index=y_idx), c3.radio("Formato", type_options, index=type_idx, horizontal=True).lower()
            st.divider()
            COMBINED_DIMENSION_OPTION, color_options = "— Criar Dimensão Combinada —", ["Nenhum", "— Criar Dimensão Combinada —"] + categorical_cols
            color_idx = color_options.index(chart_data.get('color_by')) if editing_mode and chart_data.get('color_by') in color_options else 0
            color_selection = st.selectbox("Colorir por (Dimensão Opcional)", color_options, index=color_idx)
            final_color_by = color_selection
            if color_selection == COMBINED_DIMENSION_OPTION:
                with st.container(border=True): final_color_by, df_for_preview = combined_dimension_ui(filtered_df, categorical_cols, date_cols, key_suffix="xy")
            custom_title_input = st.text_input("Título do Gráfico:", value=chart_data.get('title', f"{y} vs {x}"), key="chart_title_input_xy")
            show_labels = st.toggle("Exibir Rótulos de Dados", key="xy_labels", value=chart_data.get('show_data_labels', False))
            chart_config = {'id': str(uuid.uuid4()),'type': chart_type,'x': x,'y': y,'title': custom_title_input.strip(),'creator_type': chart_creator_type,'source_type': 'visual','color_by': final_color_by,'filters': st.session_state.get('creator_filters', []),'show_data_labels': show_labels}

        elif chart_creator_type == "Gráfico Agregado":
            st.markdown("###### **Configuração do Gráfico Agregado**")
            c1, c2 = st.columns(2)
            time_calc_method = "Soma"
            new_measure_col = None

            with c1:
                COMBINED_DIMENSION_OPTION = "— Criar Dimensão Combinada —"
                dim_options = [COMBINED_DIMENSION_OPTION] + categorical_cols
                dim_selection_index = dim_options.index(chart_data.get('dimension')) if editing_mode and chart_data.get('dimension') in dim_options else 0
                dim_selection = st.selectbox("Dimensão (Agrupar por)", options=dim_options, index=dim_selection_index)
                final_dimension = dim_selection
                if dim_selection == COMBINED_DIMENSION_OPTION:
                    with st.container(border=True):
                        final_dimension, df_for_preview = combined_dimension_ui(filtered_df, categorical_cols, date_cols, key_suffix="agg")
            
            with c2:
                measure_selection_index = measure_options.index(chart_data.get('measure_selection')) if editing_mode and chart_data.get('measure_selection') in measure_options else 0
                measure = st.selectbox("Medida (Calcular)", options=measure_options, key="measure_selector", index=measure_selection_index)

            if measure == "Tempo em Status":
                status_cols_in_df = [col.replace('Tempo em: ', '') for col in df.columns if col.startswith('Tempo em: ')]
                if not status_cols_in_df:
                    st.warning("Não foram encontradas colunas de 'Tempo em Status' nos dados. Verifique a configuração do seu projeto.")
                    measure_for_chart = None
                else:
                    default_statuses = chart_data.get('selected_statuses', [])
                    selected_statuses = st.multiselect("Selecione os Status para o cálculo", options=sorted(status_cols_in_df), default=default_statuses, help="Escolha um ou mais status.", key="status_selector_multiselect")
                    
                    if selected_statuses:
                        time_calc_method = st.radio("Calcular a", ["Soma", "Média"], horizontal=True, key="time_calc_method")
                        cols_to_process = [f'Tempo em: {s}' for s in selected_statuses]
                        
                        if time_calc_method == "Soma":
                            new_measure_col = f"Soma de tempo em: {', '.join(selected_statuses)}"
                            df_for_preview[new_measure_col] = df_for_preview[cols_to_process].sum(axis=1)
                        else:
                            new_measure_col = f"Média de tempo em: {', '.join(selected_statuses)}"
                            df_for_preview[new_measure_col] = df_for_preview[cols_to_process].mean(axis=1)
                        
                        measure_for_chart = new_measure_col
                    else:
                        measure_for_chart = None
            else:
                measure_for_chart = measure

            if final_dimension and measure_for_chart:
                st.divider()
                c1, c2 = st.columns([1, 2])
                with c1:
                    if measure_for_chart in categorical_cols:
                        agg = 'Contagem Distinta'; st.info("Agregação: Contagem Distinta", icon="🔢")
                    elif measure_for_chart in numeric_cols or new_measure_col:
                        agg_options = ["Soma", "Média"]; default_agg = 'Soma'
                        if measure == "Tempo em Status": default_agg = time_calc_method
                        elif editing_mode and chart_data.get('agg') in agg_options: default_agg = chart_data.get('agg')
                        agg_idx = agg_options.index(default_agg); agg = st.radio("Cálculo Final do Grupo", agg_options, index=agg_idx, horizontal=True)
                    else:
                        agg = 'Contagem'; st.info("Agregação: Contagem", icon="🧮")
                
                with c2:
                    format_options = ["Barras", "Linhas", "Pizza", "Treemap", "Funil", "Tabela"]
                    type_map_inv = {'barra': 'Barras', 'linha_agregada': 'Linhas', 'pizza': 'Pizza', 'treemap': 'Treemap', 'funil': 'Funil', 'tabela':'Tabela'}
                    type_from_data = type_map_inv.get(chart_data.get('type', 'barra'))
                    type_idx = format_options.index(type_from_data) if editing_mode and type_from_data in format_options else 0
                    chart_type_str = st.radio("Formato", format_options, index=type_idx, horizontal=True)
                    chart_type = chart_type_str.lower().replace("s", "").replace("á", "a")
                
                auto_title = f"{agg} de '{measure_for_chart}' por '{final_dimension}'" if chart_type != 'tabela' else f"Tabela de Dados por {final_dimension}"

                if not editing_mode:
                    custom_title = st.text_input("Título do Gráfico:", value=auto_title, key=f"chart_title_input_agg_{auto_title}")
                else:
                    custom_title = st.text_input("Título do Gráfico:", value=chart_data.get('title', auto_title), key="chart_title_input_agg_edit")

                show_labels = st.toggle("Exibir Rótulos de Dados", key="agg_labels", value=chart_data.get('show_data_labels', False))

                chart_config = {'id': str(uuid.uuid4()), 'type': 'linha_agregada' if chart_type == 'linha' else chart_type, 'dimension': final_dimension, 'measure': measure_for_chart, 'measure_selection': measure, 'agg': agg, 'title': custom_title, 'creator_type': chart_creator_type, 'source_type': 'visual', 'filters': st.session_state.get('creator_filters', []), 'show_data_labels': show_labels}
                if measure == "Tempo em Status":
                    chart_config['selected_statuses'] = selected_statuses
                if chart_type == 'tabela': 
                    chart_config['columns'] = [final_dimension, measure_for_chart]
        
        elif chart_creator_type == "Indicador (KPI)":
            kpi_source_type = st.radio("Como deseja criar o seu KPI?", ["Construtor Visual", "Avançado (com JQL)"], horizontal=True, key="kpi_source_selector")
            st.divider()
            if kpi_source_type == "Avançado (com JQL)":
                st.info("Crie um KPI com até três consultas JQL para cálculos personalizados.", icon="💡")
                kpi_title = st.text_input("Título do Indicador", key="jql_kpi_title", value=chart_data.get('title', ''))
                st.markdown("**Consulta JQL 1 (Valor A)**")
                col1, col2 = st.columns([4, 1])
                jql_a = col1.text_area("JQL 1", placeholder='project = "PROJ" AND issuetype = Bug', value=chart_data.get('jql_a', ''), label_visibility="collapsed")
                with col2:
                    st.write("")
                    if st.button("Testar", key="test_jql_a", use_container_width=True):
                        with st.spinner("Testando..."): st.session_state.jql_test_result_a = get_jql_issue_count(st.session_state.jira_client, jql_a)
                if st.session_state.get('jql_test_result_a') is not None:
                    st.success(f"Resultado do Teste: **{st.session_state.jql_test_result_a}** issues encontradas.", icon="✅"); st.session_state.pop('jql_test_result_a', None)
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
                        st.success(f"Resultado do Teste: **{st.session_state.jql_test_result_b}** issues encontradas.", icon="✅"); st.session_state.pop('jql_test_result_b', None)
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
                        st.success(f"Resultado do Teste: **{st.session_state.jql_test_result_c}** issues encontradas.", icon="✅"); st.session_state.pop('jql_test_result_c', None)
                chart_config = {'id': str(uuid.uuid4()),'type': 'indicator','style': 'Número Grande','title': kpi_title,'icon': "🧮",'source_type': 'jql','jql_a': jql_a,'jql_b': jql_b if use_b else None,'jql_operation': operation if use_b else None,'jql_baseline': jql_c if use_baseline else None,'creator_type': chart_creator_type,'filters': st.session_state.get('creator_filters', [])}
            else:
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
                chart_config = {'id': str(uuid.uuid4()),'type': 'indicator','title': kpi_title,'icon': kpi_icon,'num_op': num_op,'num_field': num_field,'use_den': use_den,'den_op': den_op,'den_field': den_field,'style': kpi_style,'gauge_min': chart_data.get('gauge_min',0),'gauge_max_static': gauge_max_static,'target_type': target_type,'target_op': target_op,'target_field': target_field,'show_delta': show_delta,'gauge_bar_color': bar_color,'gauge_target_color': target_color,'gauge_poor_threshold': gauge_poor_threshold,'gauge_good_threshold': gauge_good_threshold,'creator_type': chart_creator_type,'source_type': 'visual','filters': st.session_state.get('creator_filters', [])}
        
        elif chart_creator_type == "Tabela Dinâmica":
            st.info("Crie uma tabela de referência cruzada para analisar a relação entre três campos.", icon="↔️")
            c1, c2, c3, c4 = st.columns(4)
            rows_idx = categorical_cols.index(chart_data.get('rows')) if editing_mode and chart_data.get('rows') in categorical_cols else 0
            cols_idx = categorical_cols.index(chart_data.get('columns')) if editing_mode and chart_data.get('columns') in categorical_cols else 1
            vals_idx = numeric_cols.index(chart_data.get('values')) if editing_mode and chart_data.get('values') in numeric_cols else 0
            agg_opts = ["Soma", "Média", "Contagem"]; agg_idx = agg_opts.index(chart_data.get('aggfunc', 'Soma')) if editing_mode else 0
            rows, columns, values, aggfunc = c1.selectbox("Agrupar Linhas por:", options=categorical_cols, key="pivot_rows", index=rows_idx), c2.selectbox("Agrupar Colunas por:", options=categorical_cols, key="pivot_cols", index=cols_idx), c3.selectbox("Calcular Valores de:", options=numeric_cols, key="pivot_values", index=vals_idx), c4.selectbox("Usando o Cálculo:", options=agg_opts, key="pivot_agg", index=agg_idx)
            auto_title = f"{aggfunc} de '{values}' por '{rows}' e '{columns}'"
            custom_title_input = st.text_input("Título da Tabela:", value=chart_data.get('title', auto_title))
            chart_config = {'id': str(uuid.uuid4()),'type': 'pivot_table','title': custom_title_input.strip(),'rows': rows,'columns': columns,'values': values,'aggfunc': aggfunc,'creator_type': chart_creator_type,'source_type': 'visual','filters': st.session_state.get('creator_filters', [])}

else: # Modo IA
    st.subheader("🤖 Assistente de Geração de Gráficos com IA")
    st.info("Descreva o gráfico que você quer ver. A IA irá respeitar os filtros da pré-visualização que você definiu acima.")
    prompt = st.text_area("O seu pedido:", placeholder="Ex: Crie um gráfico de barras com a contagem de issues por responsável", height=100)
    if st.button("Gerar Gráfico com IA", use_container_width=True, type="primary"):
        if prompt:
            with st.spinner("A IA está a pensar..."):
                generated_config, error_message = generate_chart_config_from_text(prompt, numeric_cols, categorical_cols, st.session_state.get('creator_filters', []))
                if error_message:
                    st.error(error_message)
                    if 'chart_config_ia' in st.session_state: del st.session_state['chart_config_ia']
                else:
                    st.session_state.chart_config_ia = generated_config; st.rerun()
        else:
            st.warning("Por favor, escreva o seu pedido.")

if creation_mode == "Gerar com IA ✨":
    chart_config = st.session_state.get('chart_config_ia', {})

st.divider()
st.subheader("Pré-visualização da Configuração Atual")
if chart_config:
    with st.container(border=True):
        render_chart(chart_config, df_for_preview)
else:
    st.info("Configure ou gere uma visualização acima para ver a pré-visualização.")

st.divider()
if editing_mode:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Salvar Alterações", type="primary", use_container_width=True, icon="💾"):
            if chart_config and chart_config.get('title'):
                if new_measure_col: chart_config['measure'] = new_measure_col
                chart_config['filters'] = convert_dates_in_filters(st.session_state.get('creator_filters', []))
                all_layouts = find_user(st.session_state['email']).get('dashboard_layout', {})
                project_layouts = all_layouts.get(current_project_key, {})
                active_dashboard_id = project_layouts.get('active_dashboard_id')
                if active_dashboard_id and active_dashboard_id in project_layouts.get('dashboards', {}):
                    tabs_layout = project_layouts['dashboards'][active_dashboard_id]['tabs']
                    chart_found = False
                    for tab_name, charts in tabs_layout.items():
                        item_index = next((i for i, item in enumerate(charts) if isinstance(item, dict) and item.get("id") == chart_data.get("id")), None)
                        if item_index is not None:
                            new_chart_config = chart_config; new_chart_config['id'] = chart_data['id']
                            tabs_layout[tab_name][item_index] = new_chart_config
                            chart_found = True
                            break
                    if chart_found:
                        save_user_dashboard(st.session_state['email'], all_layouts)
                        del st.session_state['chart_to_edit']; st.success("Visualização atualizada!"); st.switch_page("pages/2_🏠_Meu_Dashboard.py")
    with col2:
        if st.button("Cancelar Edição", use_container_width=True): 
            del st.session_state['chart_to_edit']; st.rerun()
else:
    if st.button("Adicionar ao Dashboard Ativo", type="primary", use_container_width=True, icon="➕"):
        if chart_config and chart_config.get('title'):
            if new_measure_col: chart_config['measure'] = new_measure_col
            chart_config['filters'] = convert_dates_in_filters(st.session_state.get('creator_filters', []))
            user_data = find_user(st.session_state['email'])
            all_layouts = user_data.get('dashboard_layout', {})
            if current_project_key not in all_layouts: all_layouts[current_project_key] = {}
            project_layouts = all_layouts[current_project_key]
            if 'dashboards' not in project_layouts: project_layouts['dashboards'] = {}
            active_dashboard_id = project_layouts.get('active_dashboard_id')
            if not active_dashboard_id or active_dashboard_id not in project_layouts['dashboards']:
                active_dashboard_id = str(uuid.uuid4())
                project_layouts['active_dashboard_id'] = active_dashboard_id
                project_layouts['dashboards'][active_dashboard_id] = {"id": active_dashboard_id, "name": "Dashboard Principal", "tabs": {"Geral": []}}
            active_dashboard = project_layouts['dashboards'][active_dashboard_id]
            all_charts_count = sum(len(charts) for charts in active_dashboard.get('tabs', {}).values())
            if all_charts_count >= DASHBOARD_CHART_LIMIT:
                st.warning(f"Limite de {DASHBOARD_CHART_LIMIT} visualizações atingido.")
            else:
                if "Geral" not in active_dashboard.get('tabs', {}): active_dashboard['tabs']['Geral'] = []
                active_dashboard['tabs']['Geral'].append(chart_config)
                save_user_dashboard(st.session_state['email'], all_layouts)
                if 'chart_config_ia' in st.session_state: del st.session_state['chart_config_ia']
                st.success(f"Visualização adicionada ao '{active_dashboard.get('name', 'Dashboard')}'!")
                st.switch_page("pages/2_🏠_Meu_Dashboard.py")
        else: 
            st.warning("Configuração de visualização inválida ou sem título.")