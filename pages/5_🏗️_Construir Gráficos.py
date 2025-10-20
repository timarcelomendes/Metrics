# pages/5_🏗️_Construir Gráficos.py (VERSÃO CORRIGIDA E FINAL)

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
from pathlib import Path
from datetime import datetime, timedelta, date
import importlib
from jira_connector import *
from utils import *
from security import *
from metrics_calculator import *

st.set_page_config(page_title="Personalizar Gráficos", page_icon="🏗️", layout="wide")

# --- BLOCO 1: INICIALIZAÇÃO E AUTENTICAÇÃO ---
# Validação robusta e função de callback para limpar o estado ao trocar de tipo de gráfico
if 'new_chart_config' not in st.session_state or not isinstance(st.session_state.new_chart_config, dict):
    st.session_state.new_chart_config = {}

def on_chart_type_change():
    """Limpa a configuração específica do gráfico ao trocar o tipo no construtor visual."""
    # Preserva o título e o ID se estiverem em modo de edição, mas limpa o resto
    current_config = st.session_state.new_chart_config
    st.session_state.new_chart_config = {
        'creator_type': st.session_state.visual_creator_type,
        'title': current_config.get('title', ''),
        'id': current_config.get('id')
    }

editing_mode = 'chart_to_edit' in st.session_state and st.session_state.chart_to_edit is not None
chart_data = st.session_state.get('chart_to_edit', {})

if editing_mode:
    if st.session_state.new_chart_config.get('id') != chart_data.get('id'):
        st.session_state.new_chart_config = chart_data.copy()
        st.session_state.creator_filters = parse_dates_in_filters(chart_data.get('filters', []))
else:
    if 'creator_filters' not in st.session_state:
        st.session_state.creator_filters = []


if editing_mode:
    st.header(f"✏️ Editando: {st.session_state.new_chart_config.get('title', 'Visualização')}", divider='orange')
else:
    st.header("🏗️ Laboratório de Criação de Gráficos", divider='rainbow')


if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
    st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
    st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
    st.stop()

# --- BLOCO 2: CSS E BARRA LATERAL ---
st.markdown("""<style> button[data-testid="stButton"][kind="primary"] span svg { fill: white; } [data-testid="stHorizontalBlock"] { align-items: flex-end; } </style>""", unsafe_allow_html=True)

with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(str(logo_path), size="large")
    except (FileNotFoundError, AttributeError):
        st.write("Gauge Metrics")
    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and last_project_key in projects.values() else 0
    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_creator", index=default_index, placeholder="Escolha um projeto...")
    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]; st.session_state.project_name = selected_project_name
        if st.button("Construir Gráficos", width='stretch', type="primary"):
            df_loaded, _ = load_and_process_project_data(st.session_state.jira_client, st.session_state.project_key)
            st.session_state.dynamic_df = df_loaded
            st.rerun()
        if st.button("Logout", width='stretch', type='secondary'):
            email_to_remember = st.session_state.get('remember_email', '')
            for key in list(st.session_state.keys()): del st.session_state[key]
            if email_to_remember: st.session_state['remember_email'] = email_to_remember
            st.switch_page("1_🔑_Autenticação.py")

# --- BLOCO 3: LÓGICA PRINCIPAL E PREPARAÇÃO DE DADOS ---
df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')

if df is None or df.empty or not current_project_key:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Carregar/Atualizar Dados' para começar.")
    st.stop()

# Mensagem de ajuda para o utilizador
st.info("ℹ️ Se você alterou suas preferências de campos na página 'Minha Conta', clique em 'Carregar/Atualizar Dados' na barra lateral para que os novos campos apareçam nas opções abaixo.", icon="🔄")
st.caption(f"Utilizando dados do projeto: **{st.session_state.project_name}**")

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

# Lógica de deteção automática para garantir que todos os campos sejam apanhados
auto_numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
auto_date_cols = [col for col in df.columns if pd.api.types.is_datetime64_any_dtype(df[col]) or 'Data' in col]
auto_categorical_cols = [col for col in df.columns if pd.api.types.is_object_dtype(df[col]) and col not in auto_date_cols]

# Combina a lógica manual com a automática para criar as listas finais
numeric_cols_from_master = [f['name'] for f in master_field_list if f['type'] in ['Numérico', 'Horas'] and f['name'] in df.columns]
numeric_cols = sorted(list(set(auto_numeric_cols + numeric_cols_from_master)))

date_cols_from_master = [f['name'] for f in master_field_list if f['type'] == 'Data' and f['name'] in df.columns]
date_cols = sorted(list(set(auto_date_cols + date_cols_from_master)))

categorical_cols_from_master = [f['name'] for f in master_field_list if f['type'] in ['Texto (Alfanumérico)', 'Texto'] and f['name'] in df.columns]
categorical_cols = sorted(list(set(auto_categorical_cols + categorical_cols_from_master)))

# Garante que os campos calculados estejam sempre presentes se existirem
for col in ['Lead Time (dias)', 'Cycle Time (dias)']:
    if col in df.columns and col not in numeric_cols:
        numeric_cols.append(col)

status_time_cols = sorted([col for col in df.columns if col.startswith('Tempo em: ')])
measure_options = ["Contagem de Issues"] + numeric_cols + categorical_cols
if project_config.get('calculate_time_in_status', False) and status_time_cols:
    measure_options.append("Tempo em Status")
all_cols_for_table = sorted(list(set(date_cols + categorical_cols + numeric_cols + status_time_cols)))

# --- BLOCO 4: INTERFACE DE FILTROS ---
st.subheader("Filtros da Pré-visualização")

def handle_filter_field_change(filter_index):
    st.session_state.creator_filters[filter_index] = {'field': st.session_state[f"filter_field_{filter_index}"]}

with st.container():
    for i, f in enumerate(list(st.session_state.creator_filters)):
        cols = st.columns([2, 2, 3, 1])
        all_filterable_fields = [""] + categorical_cols + numeric_cols + date_cols
        
        selected_field = cols[0].selectbox(
            "Campo",
            options=all_filterable_fields,
            key=f"filter_field_{i}",
            index=all_filterable_fields.index(f.get('field')) if f.get('field') in all_filterable_fields else 0,
            on_change=handle_filter_field_change,
            args=(i,)
        )
        
        if selected_field:
            st.session_state.creator_filters[i]['field'] = selected_field
            field_type = 'numeric' if selected_field in numeric_cols else 'date' if selected_field in date_cols else 'categorical'
            if field_type == 'categorical':
                op_options = ['está em', 'não está em', 'é igual a', 'não é igual a']
                operator = cols[1].selectbox("Operador", options=op_options, key=f"filter_op_cat_{i}", index=op_options.index(f.get('operator')) if f.get('operator') in op_options else 0)
                options = sorted(df[selected_field].dropna().unique())
                if operator in ['está em', 'não está em']:
                    saved_values = f.get('value', [])
                    # Garante que 'saved_values' é sempre uma lista para o multiselect
                    if not isinstance(saved_values, list):
                        saved_values = [saved_values]
                    
                    # Filtra os valores guardados para incluir apenas os que ainda existem nas opções
                    valid_default_values = [v for v in saved_values if v in options]
                    
                    value = cols[2].multiselect("Valores", options=options, key=f"filter_val_multi_{i}", default=valid_default_values)
                else:
                    saved_value = f.get('value')
                    # Verifica se o valor guardado existe nas opções antes de definir o índice
                    default_index = options.index(saved_value) if saved_value in options else 0
                    
                    value = cols[2].selectbox("Valor", options=options, key=f"filter_val_single_cat_{i}", index=default_index)
            elif field_type == 'numeric':
                op_options = ['maior que', 'menor que', 'entre', 'é igual a', 'não é igual a']
                operator = cols[1].selectbox("Operador", options=op_options, key=f"filter_op_num_{i}", index=op_options.index(f.get('operator')) if f.get('operator') in op_options else 0)
                if operator == 'entre':
                    min_val, max_val = df[selected_field].min(), df[selected_field].max()
                    value = cols[2].slider("Intervalo", float(min_val), float(max_val), f.get('value', (min_val, max_val)), key=f"filter_val_slider_{i}")
                else:
                    value = cols[2].number_input("Valor", key=f"filter_val_num_{i}", value=f.get('value', 0.0))
            elif field_type == 'date':
                op_options = ["Períodos Relativos", "Período Personalizado"]
                operator = cols[1].selectbox("Operador", op_options, key=f"filter_op_date_{i}", index=op_options.index(f.get('operator', "Períodos Relativos")))
                if operator == "Períodos Relativos":
                    period_options = ["Últimos 7 dias", "Últimos 14 dias", "Últimos 30 dias", "Últimos 60 dias", "Últimos 90 dias", "Últimos 120 dias", "Últimos 150 dias", "Últimos 180 dias"]
                    value = cols[2].selectbox("Período", period_options, key=f"filter_val_period_{i}", index=period_options.index(f.get('value')) if f.get('value') in period_options else 2)
                else:
                    current_value = f.get('value')
                    default_start = datetime.now().date() - timedelta(days=30)
                    default_end = datetime.now().date()
                    if isinstance(current_value, (list, tuple)) and len(current_value) == 2 and isinstance(current_value[0], date) and isinstance(current_value[1], date):
                        value_to_pass = (current_value[0], current_value[1])
                    else:
                        value_to_pass = (default_start, default_end)
                    value = cols[2].date_input("Intervalo", value=value_to_pass, key=f"filter_val_date_range_{i}")
            st.session_state.creator_filters[i]['operator'] = operator
            st.session_state.creator_filters[i]['value'] = value
        cols[3].button("❌", key=f"remove_filter_{i}", on_click=lambda i=i: st.session_state.creator_filters.pop(i), width='stretch')

def add_new_filter():
    st.session_state.creator_filters.append({})
st.button("➕ Adicionar Filtro", on_click=add_new_filter, width='stretch')
st.divider()

# --- BLOCO 5: INTERFACE DE CRIAÇÃO DE GRÁFICOS E PRÉ-VISUALIZAÇÃO (COMPLETO E CORRIGIDO) ---
st.subheader("Configuração da Visualização")
creation_mode = st.radio("Como deseja criar a sua visualização?", ["Construtor Visual", "Gerar com IA ✨"], horizontal=True, key="creation_mode_selector")
chart_config = {}
df_for_preview = df.copy()
new_measure_col = None

if creation_mode == "Construtor Visual":
    config = st.session_state.new_chart_config
    
    creator_type_options = ["Gráfico X-Y", "Gráfico Agregado", "Indicador (KPI)", "Tabela Dinâmica", "Gráfico de Tendência"]
    default_creator_index = creator_type_options.index(config.get('creator_type')) if config.get('creator_type') in creator_type_options else 0
    chart_creator_type = st.radio("Selecione o tipo de visualização:", creator_type_options, key="visual_creator_type", horizontal=True, index=default_creator_index)
    config['creator_type'] = chart_creator_type

    with st.container(border=True):
        if chart_creator_type == "Gráfico X-Y":
            st.markdown("###### **Configuração do Gráfico X-Y**")
            c1, c2, c3 = st.columns(3)
            x_options = date_cols + numeric_cols + categorical_cols
            y_options = numeric_cols + categorical_cols
            type_options = ["Dispersão", "Linha"]
            
            x_idx = x_options.index(config.get('x')) if config.get('x') in x_options else 0
            y_idx = y_options.index(config.get('y')) if config.get('y') in y_options else 0
            type_idx = type_options.index(config.get('type', 'dispersão').capitalize()) if config.get('type','').capitalize() in type_options else 0

            config['x'] = c1.selectbox("Eixo X", x_options, index=x_idx)
            config['y'] = c2.selectbox("Eixo Y", y_options, index=y_idx)
            config['type'] = c3.radio("Formato", type_options, index=type_idx, horizontal=True).lower()
            
            if config['x'] in date_cols:
                agg_c1, agg_c2 = st.columns(2)
                agg_options = ['Nenhum'] + ['Dia', 'Semana', 'Mês', 'Trimestre', 'Ano']
                default_agg_index = agg_options.index(config.get('date_aggregation')) if config.get('date_aggregation') in agg_options else 0
                config['date_aggregation'] = agg_c1.selectbox("Agrupar data do Eixo X por:", agg_options, index=default_agg_index)

                if config['date_aggregation'] != 'Nenhum':
                    y_agg_options = ['Média', 'Soma']
                    default_y_agg_index = y_agg_options.index(config.get('y_axis_aggregation')) if config.get('y_axis_aggregation') in y_agg_options else 0
                    config['y_axis_aggregation'] = agg_c2.selectbox("Calcular Eixo Y por:", y_agg_options, index=default_y_agg_index)
                else:
                    config['y_axis_aggregation'] = None
            else:
                config['date_aggregation'] = None
                config['y_axis_aggregation'] = None
            st.divider()
            
            adv_c1, adv_c2 = st.columns(2)
            with adv_c1:
                size_options = ["Nenhum"] + numeric_cols
                size_idx = size_options.index(config.get('size_by')) if config.get('size_by') in size_options else 0
                config['size_by'] = st.selectbox("Dimensionar por (Tamanho da Bolha)", options=size_options, index=size_idx, help="Transforme em um gráfico de bolhas selecionando um campo numérico.")
            with adv_c2:
                COMBINED_DIMENSION_OPTION, color_options = "— Criar Dimensão Combinada —", ["Nenhum", "— Criar Dimensão Combinada —"] + categorical_cols
                color_idx = color_options.index(config.get('color_by')) if config.get('color_by') in color_options else 0
                color_selection = st.selectbox("Colorir por (Dimensão Opcional)", color_options, index=color_idx)
                if color_selection == COMBINED_DIMENSION_OPTION:
                    with st.container(border=True): config['color_by'], df_for_preview = combined_dimension_ui(df, categorical_cols, date_cols, key_suffix="xy")
                else:
                    config['color_by'] = color_selection
            
            theme_options = list(COLOR_THEMES.keys())
            default_theme_name = config.get('color_theme', theme_options[0])
            config['color_theme'] = st.selectbox("Esquema de Cores", options=theme_options, index=theme_options.index(default_theme_name) if default_theme_name in theme_options else 0, key="xy_color_theme")
            st.divider()
            
            st.markdown("###### **Títulos e Rótulos**")
            title_c1, title_c2, title_c3 = st.columns(3)
            config['title'] = title_c1.text_input("Título do Gráfico:", value=config.get('title', f"{config.get('y')} vs {config.get('x')}"), key="chart_title_input_xy")
            config['x_axis_title'] = title_c2.text_input("Título do Eixo X:", value=config.get('x_axis_title', config.get('x')))
            config['y_axis_title'] = title_c3.text_input("Título do Eixo Y:", value=config.get('y_axis_title', config.get('y')))
            
            label_c1, label_c2 = st.columns(2)
            config['show_data_labels'] = label_c1.toggle("Exibir Rótulos de Dados", key="xy_labels", value=config.get('show_data_labels', False))
            config['trendline'] = label_c2.toggle("Exibir Reta de Tendência", key="xy_trendline", value=config.get('trendline', False), help="Disponível apenas para gráficos de dispersão.")

            y_field_details = next((item for item in master_field_list if item['name'] == config.get('y')), None)
            config['y_axis_format'] = 'hours' if y_field_details and y_field_details.get('type') == 'Horas' else None
            
            chart_config = config.copy()
            if chart_config.get('size_by') == "Nenhum": chart_config['size_by'] = None

        elif chart_creator_type == "Gráfico Agregado":
            st.markdown("###### **Configuração do Gráfico Agregado**")
            config = st.session_state.new_chart_config
            c1, c2 = st.columns(2)
            time_calc_method = "Soma"
            
            with c1:
                COMBINED_DIMENSION_OPTION = "— Criar Dimensão Combinada —"
                dim_options = [COMBINED_DIMENSION_OPTION] + categorical_cols
                dim_idx = dim_options.index(config.get('dimension')) if config.get('dimension') in dim_options else 0
                dim_selection = st.selectbox("Dimensão (Agrupar por)", options=dim_options, index=dim_idx)
                if dim_selection == COMBINED_DIMENSION_OPTION:
                    with st.container(border=True):
                        config['dimension'], df_for_preview = combined_dimension_ui(df, categorical_cols, date_cols, key_suffix="agg")
                else:
                    config['dimension'] = dim_selection
            with c2:
                measure_idx = measure_options.index(config.get('measure_selection')) if config.get('measure_selection') in measure_options else 0
                config['measure_selection'] = st.selectbox("Medida (Calcular)", options=measure_options, key="measure_selector", index=measure_idx)

            sec_dim_options = ["Nenhuma"] + [col for col in categorical_cols if col != config.get('dimension')]
            sec_dim_idx = sec_dim_options.index(config.get('secondary_dimension')) if config.get('secondary_dimension') in sec_dim_options else 0
            config['secondary_dimension'] = st.selectbox("Dimensão Secundária (Drill-down)", options=sec_dim_options, index=sec_dim_idx)
            if config.get('secondary_dimension') == "Nenhuma": config['secondary_dimension'] = None
            
            if config.get('measure_selection') == "Tempo em Status":
                status_cols_in_df = [col.replace('Tempo em: ', '') for col in df.columns if col.startswith('Tempo em: ')]
                if not status_cols_in_df:
                    st.warning("Não foram encontradas colunas de 'Tempo em Status' nos dados.")
                    config['measure'] = None
                else:
                    config['selected_statuses'] = st.multiselect("Selecione os Status para o cálculo", options=sorted(status_cols_in_df), default=config.get('selected_statuses', []), key="status_selector_multiselect")
                    if config.get('selected_statuses'):
                        time_calc_method = st.radio("Calcular a", ["Soma", "Média"], horizontal=True, key="time_calc_method")
                        cols_to_process = [f'Tempo em: {s}' for s in config.get('selected_statuses')]
                        new_measure_col_name = f"{time_calc_method} de tempo em: {', '.join(config.get('selected_statuses'))}"
                        if time_calc_method == "Soma": df_for_preview[new_measure_col_name] = df_for_preview[cols_to_process].sum(axis=1)
                        else: df_for_preview[new_measure_col_name] = df_for_preview[cols_to_process].mean(axis=1)
                        config['measure'] = new_measure_col_name
                    else:
                        config['measure'] = None
            else:
                config['measure'] = config.get('measure_selection')

            if config.get('dimension') and config.get('measure'):
                st.divider()
                c1, c2 = st.columns([1, 2])
                with c1:
                    if config.get('measure') in categorical_cols:
                        config['agg'] = 'Contagem Distinta'; st.info("Agregação: Contagem Distinta", icon="🔢")
                    elif config.get('measure') in numeric_cols or config.get('measure_selection') == "Tempo em Status":
                        agg_options = ["Soma", "Média"]
                        default_agg = config.get('agg', 'Soma')
                        if config.get('measure_selection') == "Tempo em Status": default_agg = time_calc_method
                        agg_idx = agg_options.index(default_agg) if default_agg in agg_options else 0
                        config['agg'] = st.radio("Cálculo Final do Grupo", agg_options, index=agg_idx, horizontal=True)
                    else:
                        config['agg'] = 'Contagem'; st.info("Agregação: Contagem", icon="🧮")
                with c2:
                    format_options = ["Barras", "Barras Horizontais", "Linhas", "Pizza", "Treemap", "Funil", "Tabela"]
                    type_map_inv = {'barra': 'Barras', 'barra_horizontal': 'Barras Horizontais', 'linha_agregada': 'Linhas', 'pizza': 'Pizza', 'treemap': 'Treemap', 'funil': 'Funil', 'tabela':'Tabela'}
                    type_from_data = type_map_inv.get(config.get('type', 'barra'))
                    type_idx = format_options.index(type_from_data) if type_from_data in format_options else 0
                    chart_type_str = st.radio("Formato", format_options, index=type_idx, horizontal=True)
                    type_map = {'barras': 'barra', 'barras horizontais': 'barra_horizontal', 'linhas': 'linha_agregada', 'pizza': 'pizza', 'treemap': 'treemap', 'funil': 'funil', 'tabela': 'tabela'}
                    config['type'] = type_map.get(chart_type_str.lower())
                
                with st.expander("Opções Avançadas"):
                    adv_c1, adv_c2, adv_c3 = st.columns(3)
                    sort_options = ["Padrão", "Dimensão (A-Z)", "Dimensão (Z-A)", "Medida (Crescente)", "Medida (Decrescente)"]
                    sort_index = sort_options.index(config.get('sort_by')) if config.get('sort_by') in sort_options else 0
                    config['sort_by'] = adv_c1.selectbox("Ordenação", sort_options, index=sort_index)
                    if config.get('sort_by') == "Padrão": config['sort_by'] = None
                    config['top_n'] = adv_c2.number_input("Filtrar Top N", min_value=0, value=config.get('top_n', 0), help="Deixe 0 para desativar.")
                    if config.get('top_n') == 0: config['top_n'] = None
                    config['show_as_percentage'] = adv_c3.toggle("Mostrar como Percentual", value=config.get('show_as_percentage', False))
                
                st.divider()
                theme_options = list(COLOR_THEMES.keys())
                default_theme_name = config.get('color_theme', theme_options[0])
                config['color_theme'] = st.selectbox("Esquema de Cores", options=theme_options, index=theme_options.index(default_theme_name) if default_theme_name in theme_options else 0, key="agg_color_theme")
                
                auto_title = f"{config.get('agg')} de '{config.get('measure')}' por '{config.get('dimension')}'" if config.get('type') != 'tabela' else f"Tabela de Dados por {config.get('dimension')}"
                config['title'] = st.text_input("Título do Gráfico:", value=config.get('title', auto_title))
                config['show_data_labels'] = st.toggle("Exibir Rótulos de Dados", key="agg_labels", value=config.get('show_data_labels', False))

                measure_field_details = next((item for item in master_field_list if item['name'] == config.get('measure_selection')), None)
                config['y_axis_format'] = 'hours' if (measure_field_details and measure_field_details.get('type') == 'Horas') or config.get('measure_selection') == "Tempo em Status" else None
                
                if config.get('type') == 'tabela':
                    config['columns'] = [config.get('dimension'), config.get('measure')]
            
            chart_config = config.copy()

        elif chart_creator_type == "Indicador (KPI)":
            config = st.session_state.new_chart_config
            st.markdown("###### **Configuração do Indicador (KPI)**")
            config['type'] = 'indicator'

            config['title'] = st.text_input("Título do Indicador", value=config.get('title', ''), key="kpi_title")

            theme_options = list(COLOR_THEMES.keys())
            default_theme_name = config.get('color_theme', theme_options[0])
            theme_idx = theme_options.index(default_theme_name) if default_theme_name in theme_options else 0
            config['color_theme'] = st.selectbox("Esquema de Cores", options=theme_options, index=theme_idx, key="kpi_color_theme")

            # --- NOVA SEÇÃO DE FORMATAÇÃO ---
            st.markdown("##### Formatação do Valor")
            f_col1, f_col2 = st.columns(2)
            
            decimal_places_value = config.get('kpi_decimal_places', 2)
            config['kpi_decimal_places'] = f_col1.number_input(
                "Casas Decimais", 
                min_value=0, 
                max_value=5, 
                value=int(decimal_places_value), 
                step=1, 
                key="kpi_decimal_places"
            )

            config['kpi_format_as_percentage'] = f_col2.toggle(
                "Formatar como Percentual (%)", 
                value=config.get('kpi_format_as_percentage', False),
                key="kpi_format_percentage"
            )
            st.divider()
            # --- FIM DA NOVA SEÇÃO ---

            source_options = ["Dados do Dashboard", "Consulta JQL"]
            source_idx = 1 if config.get('source_type') == 'jql' else 0
            source_type_selection = st.radio("Fonte de Dados para o KPI", source_options, horizontal=True, index=source_idx, key="kpi_source_type")
            config['source_type'] = 'jql' if source_type_selection == "Consulta JQL" else 'visual'

            if config['source_type'] == "jql":
                st.info("Crie um KPI usando até 3 consultas JQL. Use o botão 'Testar' para validar cada uma.")
                config['jql_a'] = st.text_area("Consulta JQL 1 (Valor A)*", config.get('jql_a', ''), height=100, key="kpi_jql_a")
                if st.button("Testar JQL 1", key="kpi_test_jql_a"):
                    if config['jql_a']:
                        with st.spinner("A testar..."):
                            count = get_jql_issue_count(st.session_state.jira_client, config['jql_a'])
                            if isinstance(count, int): st.success(f"✅ Sucesso! A consulta retornou {count} issues.")
                            else: st.error(f"❌ Falha. A consulta retornou um erro: {count}")

                config['jql_b'] = st.text_area("Consulta JQL 2 (Valor B)", config.get('jql_b', ''), height=100, key="kpi_jql_b")
                if st.button("Testar JQL 2", key="kpi_test_jql_b"):
                    if config['jql_b']:
                        with st.spinner("A testar..."):
                            count = get_jql_issue_count(st.session_state.jira_client, config['jql_b'])
                            if isinstance(count, int): st.success(f"✅ Sucesso! A consulta retornou {count} issues.")
                            else: st.error(f"❌ Falha. A consulta retornou um erro: {count}")

                op_options_jql = ["Nenhuma", "Dividir (A / B)", "Somar (A + B)", "Subtrair (A - B)", "Multiplicar (A * B)"]
                op_idx_jql = op_options_jql.index(config.get('jql_operation')) if config.get('jql_operation') in op_options_jql else 0
                config['jql_operation'] = st.selectbox("Operação entre A e B", op_options_jql, index=op_idx_jql, key="kpi_jql_op")

                config['jql_baseline'] = st.text_area("Consulta JQL da Linha de Base (Valor C)", config.get('jql_baseline', ''), height=100, key="kpi_jql_baseline")
                if st.button("Testar JQL da Linha de Base", key="kpi_test_jql_baseline"):
                    if config['jql_baseline']:
                        with st.spinner("A testar..."):
                            count = get_jql_issue_count(st.session_state.jira_client, config['jql_baseline'])
                            if isinstance(count, int): st.success(f"✅ Sucesso! A consulta retornou {count} issues.")
                            else: st.error(f"❌ Falha. A consulta retornou um erro: {count}")
            
            else:  # source_type == 'visual'
                op_options = ["Contagem", "Soma", "Média"]
                st.markdown("##### Numerador")
                col1, col2 = st.columns(2)
                
                num_op_idx = op_options.index(config.get('num_op', 'Contagem')) if config.get('num_op') in op_options else 0
                config['num_op'] = col1.selectbox("Operação do Numerador", op_options, index=num_op_idx, key="kpi_num_op")
                
                if config.get('num_op') == "Contagem":
                    col2.selectbox("Campo do Numerador", ["Contagem de Issues"], disabled=True, key="kpi_num_field_count")
                    config['num_field'] = "Contagem de Issues"
                else:
                    num_field_idx = numeric_cols.index(config.get('num_field')) if config.get('num_field') in numeric_cols else 0
                    config['num_field'] = col2.selectbox("Campo do Numerador", numeric_cols, index=num_field_idx, key="kpi_num_field_numeric")

                config['use_den'] = st.toggle("Usar Denominador (para calcular proporção)", value=config.get('use_den', False), key="kpi_use_den")
                
                if config.get('use_den'):
                    st.markdown("##### Denominador")
                    col3, col4 = st.columns(2)
                    
                    den_op_idx = op_options.index(config.get('den_op', 'Contagem')) if config.get('den_op') in op_options else 0
                    config['den_op'] = col3.selectbox("Operação do Denominador", op_options, index=den_op_idx, key="kpi_den_op")
                    
                    if config.get('den_op') == "Contagem":
                        col4.selectbox("Campo do Denominador", ["Contagem de Issues"], disabled=True, key="kpi_den_field_count")
                        config['den_field'] = "Contagem de Issues"
                    else:
                        den_field_idx = numeric_cols.index(config.get('den_field')) if config.get('den_field') in numeric_cols else 0
                        config['den_field'] = col4.selectbox("Campo do Denominador", numeric_cols, index=den_field_idx, key="kpi_den_field_numeric")

                st.divider()
                config['use_baseline'] = st.toggle("Exibir Variação (Delta)", value=config.get('use_baseline', False), key="kpi_use_baseline")

                if config.get('use_baseline'):
                    st.markdown("##### Linha de Base (Valor de Referência para o Delta)")
                    col5, col6 = st.columns(2)

                    base_op_idx = op_options.index(config.get('base_op', 'Contagem')) if config.get('base_op') in op_options else 0
                    config['base_op'] = col5.selectbox("Operação da Linha de Base", op_options, index=base_op_idx, key="kpi_base_op")

                    if config.get('base_op') == "Contagem":
                        col6.selectbox("Campo da Linha de Base", ["Contagem de Issues"], disabled=True, key="kpi_base_field_count")
                        config['base_field'] = "Contagem de Issues"
                    else:
                        base_field_idx = numeric_cols.index(config.get('base_field')) if config.get('base_field') in numeric_cols else 0
                        config['base_field'] = col6.selectbox("Campo da Linha de Base", numeric_cols, index=base_field_idx, key="kpi_base_field_numeric")

            # Lógica de validação e atribuição final
            is_jql_valid = config.get('source_type') == 'jql' and config.get('jql_a', '').strip()
            is_visual_valid = config.get('source_type') == 'visual' and config.get('num_op') and config.get('num_field')

            if is_jql_valid or is_visual_valid:
                chart_config = {k: v for k, v in config.items() if v is not None}
            else:
                chart_config = {}
                if config.get('source_type') == 'jql':
                    st.warning("Por favor, preencha a 'Consulta JQL 1 (Valor A)' para gerar a pré-visualização.")

        elif chart_creator_type == "Tabela Dinâmica":
            config = st.session_state.new_chart_config

            # --- Início da lógica de construção da UI ---
            st.markdown("###### **Configuração da Tabela Dinâmica**")

            title = st.text_input("Título da Tabela", config.get('title', 'Tabela Dinâmica'))

            theme_options = list(COLOR_THEMES.keys())
            default_theme_name = config.get('color_theme', theme_options[0])
            color_theme = st.selectbox("Esquema de Cores do Cabeçalho", options=theme_options, index=theme_options.index(default_theme_name) if default_theme_name in theme_options else 0, key="pivot_color_theme")
            
            all_row_col_options = [str(col) for col in (categorical_cols + date_cols)]
            rows_selection = st.multiselect("Linhas", options=all_row_col_options, default=config.get('rows', []))
            columns_selection = st.multiselect("Colunas", options=all_row_col_options, default=config.get('columns', []))
            
            all_numeric_measures = sorted(list(set(numeric_cols + status_time_cols)))
            values_options = [""] + all_numeric_measures
            
            default_values_idx = values_options.index(config.get('values')) if config.get('values') in values_options else 0
            values_selection = st.selectbox("Valores (campo numérico)", options=values_options, index=default_values_idx)
            
            agg_options = ['Soma', 'Média', 'Contagem']
            aggfunc_selection = st.selectbox("Função de Agregação", options=agg_options, index=agg_options.index(config.get('aggfunc')) if config.get('aggfunc') in agg_options else 0)
            # --- FIM da lógica de construção da UI ---

            # Lógica de validação e criação do chart_config
            if not rows_selection or not values_selection:
                chart_config = {}
                st.warning("Para gerar a pré-visualização, selecione pelo menos um campo para 'Linhas' e um para 'Valores'.")
            else:
                # Garante que 'rows' e 'columns' são listas simples de strings
                final_rows = [item for item in rows_selection if isinstance(item, str)]
                final_columns = [item for item in columns_selection if isinstance(item, str)]

                # Cria um dicionário de configuração limpo e validado
                pivot_config = {
                    'creator_type': 'Tabela Dinâmica',
                    'type': 'pivot_table',
                    'title': title,
                    'rows': final_rows,
                    'columns': final_columns if final_columns else None,
                    'values': values_selection,
                    'aggfunc': aggfunc_selection,
                    'id': config.get('id') # Preserva o ID original durante a edição
                }

                chart_config = pivot_config.copy()
                st.session_state.new_chart_config = chart_config.copy()
        
        elif chart_creator_type == "Gráfico de Tendência":
            config = st.session_state.new_chart_config
            st.markdown("###### **Configuração da Métrica com Gráfico de Tendência**")
            config['type'] = 'metric_with_chart'
            config['title'] = st.text_input("Título da Métrica", value=config.get('title', ''))

            st.markdown("##### **Configuração do Gráfico de Tendência**")
            mc_cols1, mc_cols2, mc_cols3 = st.columns(3)
            
            chart_type_options = ["Linha", "Área", "Barra"]
            chart_type_idx = chart_type_options.index(config.get('mc_chart_type')) if config.get('mc_chart_type') in chart_type_options else 0
            config['mc_chart_type'] = mc_cols1.selectbox("Tipo de Gráfico", chart_type_options, index=chart_type_idx, help="O tipo de gráfico a ser exibido sob a métrica.")
            
            dimension_options = date_cols + categorical_cols
            dimension_idx = dimension_options.index(config.get('mc_dimension')) if config.get('mc_dimension') in dimension_options else 0
            config['mc_dimension'] = mc_cols2.selectbox("Dimensão (Eixo X do gráfico)", options=dimension_options, index=dimension_idx, help="O campo que define a sequência de dados, como uma data ou categoria.")
            
            measure_options_mc = ["Contagem de Issues"] + numeric_cols
            measure_idx = measure_options_mc.index(config.get('mc_measure')) if config.get('mc_measure') in measure_options_mc else 0
            config['mc_measure'] = mc_cols3.selectbox("Medida (Eixo Y do gráfico)", options=measure_options_mc, index=measure_idx, help="O valor numérico ou a contagem de issues a ser plotada no gráfico.")

            st.markdown("##### **Configuração dos Valores Principais da Métrica**")
            mv_cols1, mv_cols2 = st.columns(2)

            main_value_options = ["Último valor da série", "Soma de todos os valores", "Média de todos os valores"]
            main_value_idx = main_value_options.index(config.get('mc_main_value_agg')) if config.get('mc_main_value_agg') in main_value_options else 0
            config['mc_main_value_agg'] = mv_cols1.selectbox("Valor Principal a Exibir", main_value_options, index=main_value_idx)
            
            delta_agg_options = ["Variação (último - primeiro)", "Variação (último - penúltimo)"]
            delta_agg_idx = delta_agg_options.index(config.get('mc_delta_agg')) if config.get('mc_delta_agg') in delta_agg_options else 0
            config['mc_delta_agg'] = mv_cols2.selectbox("Valor do Delta (Comparação)", delta_agg_options, index=delta_agg_idx)
            
            chart_config = config.copy()

else: # Modo IA
    st.subheader("🤖 Assistente de Geração de Gráficos com IA")
    with st.container(border=True):
        ia_prompt = st.text_input("Descreva a visualização que você deseja criar:", placeholder="Ex: 'gráfico de barras com a contagem de issues por status' ou 'qual o lead time médio?'")
        if st.button("Gerar com IA", key="ia_generate_button", type="primary", width='stretch'):
            if 'chart_config_ia' in st.session_state:
                del st.session_state['chart_config_ia']
            if ia_prompt:
                with st.spinner("A IA está a pensar... 🤖"):
                    active_filters = st.session_state.get('creator_filters', [])
                    generated_config, error_message = generate_chart_config_from_text(ia_prompt, numeric_cols, categorical_cols, active_filters=active_filters)
                    if error_message:
                        st.error(error_message)
                    else:
                        st.success("Configuração gerada com sucesso! Verifique a pré-visualização abaixo.")
                        st.session_state.chart_config_ia = generated_config
            else:
                st.warning("Por favor, descreva a visualização que você deseja.")
    if 'chart_config_ia' in st.session_state:
        chart_config = st.session_state.chart_config_ia

st.divider()
st.subheader("Pré-visualização da Configuração Atual")

df_filtered_for_preview = apply_filters(df_for_preview.copy(), st.session_state.get('creator_filters', []))

with st.expander("🔍 Depuração: Ver Dados Após Filtragem"):
    st.info(f"A tabela abaixo mostra os {len(df_filtered_for_preview)} registos que restaram após a aplicação dos filtros da pré-visualização.")
    st.dataframe(df_filtered_for_preview)

if chart_config:
    with st.container(border=True):
        render_chart(chart_config, df_filtered_for_preview, "preview_chart")
else:
    st.info("Configure ou gere uma visualização acima para ver a pré-visualização.")
st.divider()

# --- BLOCO 6: AÇÕES FINAIS (SALVAR/CANCELAR) ---
def cleanup_editor_state_and_switch_page():
    """Limpa o estado do editor e volta para o dashboard."""
    keys_to_clear = ['chart_to_edit', 'creator_filters', 'chart_config_ia', 'new_chart_config']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.switch_page("pages/2_🏠_Meu_Dashboard.py")

if editing_mode:
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Salvar Alterações", type="primary", width='stretch', icon="💾"):
            # A fonte de verdade é o estado 'new_chart_config', que mantém o ID original.
            final_config = st.session_state.new_chart_config
            original_chart_id = final_config.get('id')

            if final_config and final_config.get('title') and original_chart_id:
                if new_measure_col: final_config['measure'] = new_measure_col # Atualiza a medida se necessário
                final_config['filters'] = convert_dates_in_filters(st.session_state.get('creator_filters', []))
                
                user_data = find_user(st.session_state['email'])
                all_layouts = user_data.get('dashboard_layout', {})
                project_layouts = all_layouts.get(current_project_key, {})
                active_dashboard_id = project_layouts.get('active_dashboard_id')
                
                if active_dashboard_id and active_dashboard_id in project_layouts.get('dashboards', {}):
                    tabs_layout = project_layouts['dashboards'][active_dashboard_id]['tabs']
                    chart_found_and_updated = False
                    for tab_name, charts in tabs_layout.items():
                        # Procura o gráfico usando o ID que foi guardado no estado da sessão
                        for i, item in enumerate(charts):
                            if isinstance(item, dict) and item.get("id") == original_chart_id:
                                tabs_layout[tab_name][i] = final_config
                                chart_found_and_updated = True
                                break
                        if chart_found_and_updated:
                            break
                    
                    if chart_found_and_updated:
                        save_user_dashboard(st.session_state['email'], all_layouts)
                        st.success("Visualização atualizada com sucesso!")
                        cleanup_editor_state_and_switch_page()
                    else:
                        st.error("Não foi possível encontrar o gráfico original no dashboard para atualizar.")
                else:
                    st.error("Dashboard ativo não encontrado para salvar as alterações.")
            else:
                st.warning("Configuração de visualização inválida, sem título ou sem um ID rastreável.")
    with col2:
        if st.button("Cancelar Edição", width='stretch'):
            cleanup_editor_state_and_switch_page()

else: # Lógica para adicionar novo gráfico (sem alterações)
    if st.button("Adicionar ao Dashboard Ativo", type="primary", width='stretch', icon="➕"):
        if chart_config and chart_config.get('title'):
            if new_measure_col: chart_config['measure'] = new_measure_col
            chart_config['filters'] = convert_dates_in_filters(st.session_state.get('creator_filters', []))
            chart_config['id'] = str(uuid.uuid4())
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
                st.success(f"Visualização adicionada ao '{active_dashboard.get('name', 'Dashboard')}'!")
                cleanup_editor_state_and_switch_page()
        else:
            st.warning("Configuração de visualização inválida ou sem título.")