# utils.py

import streamlit as st
import json, os, pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
import pandas as pd
import uuid
import base64
from jira import JIRA
import google.generativeai as genai
from security import find_user, decrypt_token, get_project_config, get_global_configs
from datetime import datetime, date, timedelta
import openai
from sklearn.linear_model import LinearRegression
import numpy as np
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
import re
from security import *
import fitz
import sendgrid
import mailersend
import sib_api_v3_sdk
import io
import base64
import requests
from config import COLOR_THEMES
from sklearn.linear_model import LinearRegression
from datetime import datetime, date, timedelta
import html
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
import unicodedata
from stqdm import stqdm
from security import find_user, get_project_config, get_global_configs
from metrics_calculator import find_completion_date, calculate_cycle_time, calculate_time_in_status, filter_ignored_issues
from jira_connector import get_project_issues, get_jira_statuses

# Em: Metrics/jira_connector.py

# ... (outras importações no topo do ficheiro) ...
# (Certifique-se que estas importações estão no topo do seu jira_connector.py)
from security import get_project_config, get_global_configs
from metrics_calculator import filter_ignored_issues, find_completion_date, calculate_cycle_time, calculate_time_in_status
from stqdm import stqdm
import pandas as pd
from jira import JIRA, Issue, JIRAError
import streamlit as st
from datetime import datetime
# ... (fim das importações) ...


@st.cache_data(ttl=900, show_spinner=False)
def load_and_process_project_data(_jira_client: JIRA, project_key: str, _user_data: dict):
    # Renomeia internamente para usar sem o underscore
    user_data = _user_data
    
    """
    Carrega, processa e enriquece os dados de um projeto Jira.
    (MODIFICADO para incluir o tradutor de categoria de status)
    """
    project_config = get_project_config(project_key) or {}
    estimation_config = project_config.get('estimation_field', {})
    timespent_config = project_config.get('timespent_field', {})
    estimation_field_id = estimation_config.get('id') if estimation_config else None
    timespent_field_id = timespent_config.get('id') if timespent_config else None

    user_enabled_standard_fields_ids = user_data.get('standard_fields', [])
    user_enabled_custom_fields_names = user_data.get('enabled_custom_fields', [])

    global_configs = get_global_configs()
    strategic_field_name = global_configs.get('strategic_grouping_field')

    if 'project_name' not in st.session_state or not st.session_state.project_name:
        try: project_details = _jira_client.project(project_key); st.session_state.project_name = project_details.name
        except Exception: st.session_state.project_name = project_key

    with st.spinner(f"A carregar issues do projeto '{st.session_state.project_name}'..."):
        # A sua função 'get_project_issues' (linha 351) é a correta
        raw_issues_list = get_project_issues(_jira_client, project_key)
        
    # --- INÍCIO DO TRADUTOR DE CONFIGURAÇÃO CENTRAL ---
    if 'status_category_mapping' in project_config and 'status_mapping' not in project_config:
        try:
            with st.spinner("A traduzir mapeamento de categorias de status..."):
                # A sua função 'get_jira_statuses' (linha 484) é a correta
                all_statuses = get_jira_statuses(_jira_client, project_key) 
                
                cat_mapping = project_config['status_category_mapping']
                initial_cats = [c.lower() for c in cat_mapping.get('initial', [])]
                inprogress_cats = [c.lower() for c in cat_mapping.get('in_progress', [])]
                done_cats = [c.lower() for c in cat_mapping.get('done', [])]
                
                new_status_mapping = {'initial': [], 'in_progress': [], 'done': []}
                for s in all_statuses:
                    if not hasattr(s, 'statusCategory') or not s.statusCategory:
                        continue
                        
                    s_cat_name = s.statusCategory.name.lower()
                    status_obj = {'id': s.id, 'name': s.name}
                    
                    if s_cat_name in initial_cats:
                        new_status_mapping['initial'].append(status_obj)
                    elif s_cat_name in inprogress_cats:
                        new_status_mapping['in_progress'].append(status_obj)
                    elif s_cat_name in done_cats:
                        new_status_mapping['done'].append(status_obj)
                
                # Injeta o mapeamento traduzido no project_config
                project_config['status_mapping'] = new_status_mapping
                
        except Exception as e:
            st.error(f"Erro ao traduzir categorias de status: {e}")
    # --- FIM DO TRADUTOR ---

    # Agora o filter_ignored_issues funciona com o 'project_config' traduzido
    issues = filter_ignored_issues(raw_issues_list, project_config)

    if not issues: return pd.DataFrame(), [], project_config # Retorna a config mesmo se vazio

    # Mapas para campos personalizados
    all_custom_field_id_to_name_map = { f['id']: f['name'] for f in global_configs.get('custom_fields', []) if isinstance(f, dict) and 'id' in f and 'name' in f }
    user_custom_field_name_to_id_map = { name: id for id, name in all_custom_field_id_to_name_map.items() if name in user_enabled_custom_fields_names }
    strategic_field_id = next((fid for fid, fname in all_custom_field_id_to_name_map.items() if fname == strategic_field_name), None)

    # --- MAPEAMENTO PADRÃO ID -> ATRIBUTO JIRA ---
    standard_field_id_to_attribute_map = {
        'Summary': 'summary', 'Issue Type': 'issuetype', 'Status': 'status', 'Priority': 'priority',
        'Resolution': 'resolution', 'Assignee': 'assignee', 'Reporter': 'reporter', 'Creator': 'creator',
        'Created': 'created', 'Updated': 'updated', 'DueDate': 'duedate', 'Components': 'components',
        'Affects Versions': 'versions', 'Fix Versions': 'fixVersions', 'Labels': 'labels',
        'Description': 'description', 'Environment': 'environment', 'Security Level': 'security',
        'Time Spent': 'timespent', 'Time Estimate': 'timeestimate', 'Original Estimate': 'timeoriginalestimate',
        'StatusCategory': 'statuscategory', 'Parent': 'parent',
    }

    # --- EXTRACT_VALUE ROBUSTO ---
    def extract_value(raw_value, field_identifier_for_debug=""):
        if raw_value is None: return None
        try:
            if isinstance(raw_value, (int, float, bool)): return raw_value
            if isinstance(raw_value, str) and raw_value.isdigit():
                try: return int(raw_value)
                except ValueError: pass
            if hasattr(raw_value, 'displayName'): return raw_value.displayName
            if hasattr(raw_value, 'name'): return raw_value.name 
            if hasattr(raw_value, 'value'): return raw_value.value 
            if isinstance(raw_value, str):
                try:
                    dt_obj = pd.to_datetime(raw_value).tz_localize(None).normalize()
                    if dt_obj.hour == 0 and dt_obj.minute == 0 and dt_obj.second == 0: return dt_obj.date()
                    return dt_obj
                except (ValueError, TypeError): pass
            if isinstance(raw_value, list):
                extracted_items = []
                for item in raw_value:
                    if hasattr(item, 'name'): extracted_items.append(item.name)
                    elif hasattr(item, 'value'): extracted_items.append(item.value)
                    elif hasattr(item, 'displayName'): extracted_items.append(item.displayName)
                    elif isinstance(item, str): extracted_items.append(item)
                return ', '.join(filter(None, extracted_items)) if extracted_items else None
            return str(raw_value) # Fallback
        except Exception as e:
            print(f"DEBUG extract_value ERROR para Campo '{field_identifier_for_debug}', Valor Bruto: '{raw_value}', Erro: {e}")
            return None 

    processed_issues_data = []
    try: _ = find_completion_date
    except NameError: st.error("Erro: 'find_completion_date' não importada."); st.stop()

    should_calc_time_in_status = project_config.get('calculate_time_in_status', False)
    all_project_statuses = []
    if should_calc_time_in_status:
        try: all_project_statuses = list(set([s.name for s in _jira_client.project_statuses(project_key)]))
        except Exception:
            try: all_project_statuses = list(set([s.name for s in _jira_client.statuses()]))
            except Exception as e: 
                print(f"Aviso: Falha ao buscar status: {e}")

    processed_by_default = {'ID', 'Issue', 'Tipo de Issue', 'Status', 'Data de Criação',
                             'Data de Conclusão', 'Lead Time (dias)', 'Cycle Time (dias)'}

    for issue_index, issue in enumerate(stqdm(issues, desc="A processar issues")):
        fields = issue.fields

        # Campos Base
        issue_data = {
            'ID': issue.key,
            'Issue': getattr(fields, 'summary', None),
            'Tipo de Issue': extract_value(getattr(fields, 'issuetype', None), f"{issue.key}-TipoIssue"),
            'Status': extract_value(getattr(fields, 'status', None), f"{issue.key}-Status"),
            'Data de Criação': extract_value(getattr(fields, 'created', None), f"{issue.key}-DataCriacao"),
        }
        
        # --- Cálculo de Datas e Métricas ---
        # (find_completion_date agora usa o project_config traduzido)
        completion_date_raw = find_completion_date(issue, project_config)
        completion_date_dt = pd.to_datetime(completion_date_raw, errors='coerce')
        issue_data['Data de Conclusão'] = completion_date_dt.tz_localize(None).normalize() if pd.notna(completion_date_dt) else pd.NaT
        
        try:
            dt_conclusao_ts = pd.to_datetime(issue_data.get('Data de Conclusão'), errors='coerce')
            dt_criacao_ts = pd.to_datetime(issue_data.get('Data de Criação'), errors='coerce')

            if pd.notna(dt_conclusao_ts) and pd.notna(dt_criacao_ts):
                issue_data['Lead Time (dias)'] = (dt_conclusao_ts - dt_criacao_ts).days
            else:
                issue_data['Lead Time (dias)'] = None
        except Exception as e:
            print(f"DEBUG Lead Time ERROR para {issue.key}: {e}")
            issue_data['Lead Time (dias)'] = None
            
        # (calculate_cycle_time agora usa o project_config traduzido)
        issue_data['Cycle Time (dias)'] = calculate_cycle_time(issue, completion_date_raw, project_config)

        # --- PROCESSAMENTO CAMPOS PADRÃO ---
        for field_id in user_enabled_standard_fields_ids:
            if field_id in processed_by_default or field_id in [estimation_field_id, timespent_field_id]:
                continue

            attribute_name = standard_field_id_to_attribute_map.get(field_id)
            raw_value = None 
            extracted_value = None 
            debug_source = "" 

            if attribute_name:
                try:
                    if field_id == 'StatusCategory':
                        raw_value = getattr(getattr(fields, 'status', None), 'statusCategory', 'NÃO ENCONTRADO')
                    else:
                        raw_value = getattr(fields, attribute_name, 'NÃO ENCONTRADO')
                    extracted_value = extract_value(raw_value, f"{issue.key}-{field_id}")
                    issue_data[field_id] = extracted_value 
                except Exception as e:
                    print(f"DEBUG Padrão Getattr ERROR para ID '{field_id}', Atributo '{attribute_name}', Erro: {e}")
                    issue_data[field_id] = None
            else:
                try:
                    raw_value = getattr(fields, field_id, 'NÃO ENCONTRADO')
                    extracted_value = extract_value(raw_value, f"{issue.key}-{field_id}")
                    issue_data[field_id] = extracted_value
                except Exception as e:
                    print(f"DEBUG Padrão Fallback Getattr ERROR para ID '{field_id}', Erro: {e}")
                    issue_data[field_id] = None

        # --- PROCESSAMENTO CAMPOS PERSONALIZADOS ---
        for field_name, field_id in user_custom_field_name_to_id_map.items():
            raw_value = None
            extracted_value = None
            try:
                raw_value = getattr(fields, field_id, 'NÃO ENCONTRADO')
                extracted_value = extract_value(raw_value, f"{issue.key}-{field_name}({field_id})")
                issue_data[field_name] = extracted_value
            except Exception as e:
                print(f"DEBUG Custom Getattr ERROR para Nome '{field_name}', ID '{field_id}', Erro: {e}")
                issue_data[field_name] = None

        # Campo Estratégico
        if strategic_field_name and strategic_field_id:
                if strategic_field_name not in issue_data:
                    raw_value = getattr(fields, strategic_field_id, 'NÃO ENCONTRADO')
                    extracted_value = extract_value(raw_value, f"{issue.key}-{strategic_field_name}({strategic_field_id})")
                    issue_data[strategic_field_name] = extracted_value

        # Tempo em Status
        if should_calc_time_in_status and all_project_statuses:
            time_in_status_data = calculate_time_in_status(issue, all_project_statuses, issue_data['Data de Conclusão'])
            for status_name, time_days in time_in_status_data.items():
                issue_data[f'Tempo em: {status_name}'] = time_days

        processed_issues_data.append(issue_data)
        
    # 1. Cria o DataFrame PRIMEIRO
    df = pd.DataFrame(processed_issues_data)

    # 2. AGORA executa a lógica de rename/verificação de Estimativa/Tempo Gasto
    estimation_name = estimation_config.get('name') if estimation_config else None
    timespent_name = timespent_config.get('name') if timespent_config else None
    rename_map_specific = {}
    ids_to_drop_specific = [] 

    if estimation_field_id and estimation_name and estimation_field_id in df.columns and estimation_name != estimation_field_id:
            if estimation_name not in df.columns:
                rename_map_specific[estimation_field_id] = estimation_name
            else:
                ids_to_drop_specific.append(estimation_field_id)

    if timespent_field_id and timespent_name and timespent_field_id in df.columns and timespent_name != timespent_field_id:
            if timespent_name not in df.columns:
                rename_map_specific[timespent_field_id] = timespent_name
            else:
                ids_to_drop_specific.append(timespent_field_id)

    if rename_map_specific:
        df.rename(columns=rename_map_specific, inplace=True)

    if ids_to_drop_specific:
        df.drop(columns=ids_to_drop_specific, errors='ignore', inplace=True)

    # --- GARANTIR COLUNAS E RENOMEAR ---
    all_expected_standard_ids = user_enabled_standard_fields_ids
    all_expected_custom_names = user_enabled_custom_fields_names
    expected_cols_before_rename = set(list(processed_by_default) + all_expected_standard_ids + all_expected_custom_names)
    if strategic_field_name: expected_cols_before_rename.add(strategic_field_name)
    if estimation_field_id: expected_cols_before_rename.add(estimation_field_id)
    if timespent_field_id: expected_cols_before_rename.add(timespent_field_id)

    for col in expected_cols_before_rename:
        if col not in df.columns:
            df[col] = None

    standard_fields_map = st.session_state.get('standard_fields_map', {})
    rename_map_standard = {}
    for field_id in user_enabled_standard_fields_ids:
            friendly_name = standard_fields_map.get(field_id)
            if friendly_name and field_id in df.columns and friendly_name != field_id:
                rename_map_standard[field_id] = friendly_name
            elif friendly_name and friendly_name != field_id and friendly_name not in df.columns:
                df[friendly_name] = None 

    df.rename(columns=rename_map_standard, inplace=True)

    final_expected_col_names = set(list(processed_by_default) +
                                     [standard_fields_map.get(fid, fid) for fid in all_expected_standard_ids] + 
                                     all_expected_custom_names)
    if strategic_field_name: final_expected_col_names.add(strategic_field_name)
    if estimation_name: final_expected_col_names.add(estimation_name)
    if timespent_name: final_expected_col_names.add(timespent_name)
    if should_calc_time_in_status:
        for status_name in all_project_statuses: final_expected_col_names.add(f'Tempo em: {status_name}')

    for col_name in final_expected_col_names:
            if col_name not in df.columns:
                df[col_name] = None

    final_columns_existing_and_expected = sorted([col for col in final_expected_col_names if col in df.columns])
    df = df[final_columns_existing_and_expected]

    # --- ALTERAÇÃO PRINCIPAL ---
    # Retorna o DF, as issues filtradas E a configuração traduzida
    return df, issues, project_config

def apply_filters(df, filters):
    """Aplica uma lista de filtros a um DataFrame de forma segura (VERSÃO CORRIGIDA)."""
    if not filters:
        return df
    
    df_filtered = df.copy()
    today = datetime.now().date()

    for f in filters:
        # Usar 'field' em vez de 'column'
        if not isinstance(f, dict) or 'field' not in f or 'operator' not in f:
            continue
        
        col = f['field']
        op = f['operator']
        val = f.get('value')

        if not col or col not in df_filtered.columns:
            # Ignora filtros vazios ou colunas que já não existem
            continue

        # Identifica o tipo de coluna
        if pd.api.types.is_numeric_dtype(df_filtered[col]):
            field_type = 'numeric'
        elif pd.api.types.is_datetime64_any_dtype(df_filtered[col]) or 'Data' in col or col in ['Data de Criação', 'Data de Conclusão']:
            field_type = 'date'
        else:
            field_type = 'categorical'

        try:
            if field_type == 'categorical':
                series = df_filtered[col].astype(str)
                if op == 'é igual a':
                    df_filtered = df_filtered[series == str(val)]
                elif op == 'não é igual a':
                    df_filtered = df_filtered[series != str(val)]
                elif op == 'está em' and isinstance(val, list):
                    val_list = [str(v).strip() for v in val]
                    df_filtered = df_filtered[series.isin(val_list)]
                elif op == 'não está em' and isinstance(val, list):
                    val_list = [str(v).strip() for v in val]
                    df_filtered = df_filtered[~series.isin(val_list)]
            
            # Adicionada lógica para filtros NUMÉRICOS
            elif field_type == 'numeric':
                series = pd.to_numeric(df_filtered[col], errors='coerce')
                df_filtered = df_filtered[pd.notna(series)] 
                series = series.dropna()
                
                if op == 'é igual a':
                    df_filtered = df_filtered[series == float(val)]
                elif op == 'não é igual a':
                    df_filtered = df_filtered[series != float(val)]
                elif op == 'maior que':
                    df_filtered = df_filtered[series > float(val)]
                elif op == 'menor que':
                    df_filtered = df_filtered[series < float(val)]
                elif op == 'entre' and isinstance(val, (list, tuple)):
                    df_filtered = df_filtered[series.between(float(val[0]), float(val[1]))]
            
            elif field_type == 'date':
                series = pd.to_datetime(df_filtered[col], errors='coerce').dt.date
                df_filtered = df_filtered[pd.notna(series)] 
                series = series.dropna()

                if op == "Períodos Relativos":
                    days_map = {
                        "Últimos 7 dias": 7, "Últimos 14 dias": 14, "Últimos 30 dias": 30,
                        "Últimos 60 dias": 60, "Últimos 90 dias": 90, "Últimos 120 dias": 120,
                        "Últimos 150 dias": 150, "Últimos 180 dias": 180
                    }
                    days_to_subtract = days_map.get(val, 0)
                    start_date = today - timedelta(days=days_to_subtract)
                    df_filtered = df_filtered[series.between(start_date, today)]
                
                elif op == "Período Personalizado" and isinstance(val, (list, tuple)):
                    start_date = val[0]
                    end_date = val[1]
                    
                    if isinstance(start_date, str):
                        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                    if isinstance(end_date, str):
                        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                    
                    df_filtered = df_filtered[series.between(start_date, end_date)]

        except Exception as e:
            st.warning(f"Não foi possível aplicar o filtro na coluna '{col}'. Erro: {e}")
            
    return df_filtered

def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError): return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def convert_dates_in_filters(filters):
    processed_filters = []
    for f in filters:
        new_filter = f.copy()
        value = new_filter.get('value')
        
        if isinstance(value, (date, datetime)):
            new_filter['value'] = value.isoformat()
        elif isinstance(value, (list, tuple)):
            new_filter['value'] = [
                v.isoformat() if isinstance(v, (date, datetime)) else v 
                for v in value
            ]
            
        processed_filters.append(new_filter)
    return processed_filters

def parse_dates_in_filters(filters):
    processed_filters = []
    for f in filters:
        new_filter = f.copy()
        op = new_filter.get('operator')
        value = new_filter.get('value')
        
        if op == 'Período Personalizado' and value and isinstance(value, (list, tuple)) and len(value) == 2:
            try:
                start_date_val, end_date_val = value
                
                def _to_date_obj(val):
                    if isinstance(val, str):
                        return datetime.strptime(val, '%Y-%m-%d').date()
                    if isinstance(val, datetime):
                        return val.date()
                    if isinstance(val, date):
                        return val
                    return None

                start_date = _to_date_obj(start_date_val)
                end_date = _to_date_obj(end_date_val)
                
                if start_date and end_date:
                    new_filter['value'] = (start_date, end_date)

            except (ValueError, TypeError):
                pass 
        
        processed_filters.append(new_filter)
    return processed_filters

@st.cache_data
def calculate_trendline(df, x_col, y_col):
    df_cleaned = df.dropna(subset=[x_col, y_col])
    if not pd.api.types.is_numeric_dtype(df_cleaned[x_col]) or \
       not pd.api.types.is_numeric_dtype(df_cleaned[y_col]) or \
       df_cleaned.empty:
        return None, None
    
    X = df_cleaned[[x_col]].values
    y = df_cleaned[y_col].values
    model = LinearRegression()
    model.fit(X, y)
    trend_y = model.predict(X)
    return df_cleaned[x_col], trend_y

def get_chart_colors(chart_config, df, color_col):
    """Obtém um esquema de cores para o gráfico."""
    project_key = st.session_state.get('project_key')
    if project_key:
        from security import get_project_config
        project_config = get_project_config(project_key)
        if project_config:
            if color_col == 'Status':
                return project_config.get('status_colors', {})
            elif color_col == 'Tipo de Issue':
                return project_config.get('type_colors', {})

    if color_col in df.columns:
        unique_values = df[color_col].unique()
        color_sequence = px.colors.qualitative.Plotly
        return {val: color_sequence[i % len(color_sequence)] for i, val in enumerate(unique_values)}
    return {}

def apply_chart_theme(fig, theme_name="Padrão Gauge"):
    """Aplica um tema de cores a uma figura Plotly, extraindo a sequência de cores correta."""
    default_theme_key = list(COLOR_THEMES.keys())[0]
    theme_dict = COLOR_THEMES.get(theme_name, COLOR_THEMES[default_theme_key])
    
    if not isinstance(theme_dict, dict):
        theme_dict = COLOR_THEMES[default_theme_key]

    color_sequence = theme_dict.get('color_sequence', [])
    
    fig.update_layout(
        colorway=color_sequence,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(family="Roboto, sans-serif", color="#3D3D3D"),
        xaxis=dict(gridcolor='rgba(220, 220, 220, 0.5)'),
        yaxis=dict(gridcolor='rgba(220, 220, 220, 0.5)'),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

def render_chart(chart_config, df, chart_key):
    """Renderiza um gráfico com base na configuração, com validação robusta e aplicação de tema de cores."""
    try:
        if not isinstance(chart_config, dict):
            st.error(f"Erro: A configuração deste gráfico é inválida e não pode ser renderizada.")
            with st.expander("Ver dados corrompidos"):
                st.json(chart_config)
            return

        chart_key = f"chart_{chart_config.get('id', uuid.uuid4())}"
        chart_type = chart_config.get('type')
        default_theme = list(COLOR_THEMES.keys())[0]
        color_theme = chart_config.get('color_theme', default_theme)
        df_chart_filtered = apply_filters(df, chart_config.get('filters', []))

        # --- BLOCO DE GRÁFICO AGREGADO ---
        if chart_type in ['barra', 'barra_horizontal', 'linha_agregada', 'pizza', 'treemap', 'funil', 'tabela']:
            dimension = chart_config.get('dimension')
            measure = chart_config.get('measure') # Pode ser o nome da coluna calculada (ex: "Média de tempo em...")
            agg = chart_config.get('agg')

            # Verifica se a MEDIDA ORIGINAL selecionada foi "Tempo em Status"
            original_measure_selection = chart_config.get('measure_selection')
            is_time_in_status_measure = original_measure_selection == "Tempo em Status"

            if is_time_in_status_measure:
                # Tenta encontrar os status selecionados usando os prefixos conhecidos
                selected_statuses = None
                calc_method = None
                possible_prefixes = ['agg', 'kpi_num', 'kpi_den', 'kpi_base', 'mc_measure']
                for prefix in possible_prefixes:
                    if f'{prefix}_selected_statuses' in chart_config:
                        selected_statuses = chart_config.get(f'{prefix}_selected_statuses', [])
                        calc_method = chart_config.get(f'{prefix}_calc_method', 'Soma')
                        break # Encontrou a configuração correta

                if selected_statuses is None: 
                     selected_statuses = chart_config.get('selected_statuses', [])
                     calc_method = chart_config.get('calc_method', 'Soma')

                if selected_statuses:
                    cols_to_process = [f'Tempo em: {s}' for s in selected_statuses if f'Tempo em: {s}' in df_chart_filtered.columns]
                    if cols_to_process:
                        if calc_method == "Soma":
                            df_chart_filtered[measure] = df_chart_filtered[cols_to_process].sum(axis=1)
                        else:
                            df_chart_filtered[measure] = df_chart_filtered[cols_to_process].mean(axis=1)
                    else:
                        st.warning(f"Nenhuma coluna de status válida encontrada para '{measure}'. O gráfico pode ficar vazio.")
                        measure = None
                else:
                     st.warning(f"Medida '{measure}' requer status selecionados, mas nenhum foi encontrado na configuração.")
                     measure = None

            # Continua a lógica original, mas agora 'measure' existe ou é None
            if not dimension or not measure or not agg:
                if not st.session_state.get('_measure_none_warned', False):
                     st.warning(f"Configuração de gráfico agregado inválida ou medida '{chart_config.get('measure')}' não pôde ser calculada.")
                     st.session_state._measure_none_warned = True 
                if '_measure_none_warned' in st.session_state and measure: 
                    del st.session_state['_measure_none_warned']
                return

            group_by_cols = [dimension]
            secondary_dimension = chart_config.get('secondary_dimension')
            if secondary_dimension:
                group_by_cols.append(secondary_dimension)

            # Lógica de Agregação (agora usa 'measure' que PODE ser a coluna calculada)
            agg_col = None 
            if measure == "Contagem de Issues":
                agg_df = df_chart_filtered.groupby(group_by_cols).size().reset_index(name='Contagem')
                agg_col = 'Contagem'
            elif agg == 'Contagem Distinta' and measure in df_chart_filtered.columns:
                 agg_df = df_chart_filtered.groupby(group_by_cols)[measure].nunique().reset_index()
                 agg_col = f"Contagem Distinta de {measure}"
                 agg_df.rename(columns={measure: agg_col}, inplace=True)
            elif measure in df_chart_filtered.columns: # Para medidas numéricas OU a coluna calculada de Tempo Status
                agg_func_map = {'Soma': 'sum', 'Média': 'mean', 'Contagem': 'count'}
                agg_name_map = {'Soma': 'Soma de', 'Média': 'Média de', 'Contagem': 'Contagem de'}
                agg_function = agg_func_map.get(agg, 'sum')

                # Garante que a coluna é numérica antes de agregar
                df_chart_filtered[measure] = pd.to_numeric(df_chart_filtered[measure], errors='coerce')
                # Remove NaNs introduzidos pela conversão antes do groupby
                valid_data_df = df_chart_filtered.dropna(subset=[measure] + group_by_cols)

                if valid_data_df.empty:
                     st.warning(f"Não há dados válidos para agregar a medida '{measure}' pela dimensão '{dimension}'.")
                     return

                agg_df = valid_data_df.groupby(group_by_cols)[measure].agg(agg_function).reset_index()

                agg_col = f"{agg_name_map.get(agg, 'Valor de')} {measure}"
                agg_df.rename(columns={measure: agg_col}, inplace=True)
            else:
                 # Verifica se o warning já foi mostrado para evitar repetição
                 if not st.session_state.get(f'_measure_{measure}_warned', False):
                      st.error(f"Coluna de medida '{measure}' não encontrada ou inválida após o cálculo.")
                      st.session_state[f'_measure_{measure}_warned'] = True
                 return
            
            # Limpa warning se a medida voltou a ser válida
            if f'_measure_{measure}_warned' in st.session_state and agg_col is not None:
                 del st.session_state[f'_measure_{measure}_warned']

            # Define o título do eixo Y ANTES de qualquer conversão
            y_axis_title_text = agg_col

            # Se for Tempo em Status, o título deve indicar dias por padrão
            if is_time_in_status_measure:
                 y_axis_title_text = f"{agg_col} (dias)"

            # Lógica de Ordenação e Top N (sem alterações)
            sort_by = chart_config.get('sort_by')
            if sort_by and agg_col in agg_df.columns: # Garante que agg_col existe
                if "Dimensão" in sort_by:
                    ascending = "A-Z" in sort_by
                    agg_df = agg_df.sort_values(by=dimension, ascending=ascending)
                elif "Medida" in sort_by:
                    ascending = "Crescente" in sort_by
                    agg_df = agg_df.sort_values(by=agg_col, ascending=ascending)

            top_n = chart_config.get('top_n')
            if top_n and isinstance(top_n, int) and top_n > 0:
                agg_df = agg_df.head(top_n)

            # Lógica de Percentual (sem alterações)
            if chart_config.get('show_as_percentage') and agg_col in agg_df.columns: # Garante que agg_col existe
                total = agg_df[agg_col].sum()
                # Evita divisão por zero e NaNs
                if total != 0 and pd.notna(total):
                     agg_df[agg_col] = (agg_df[agg_col] / total) * 100
                else:
                     agg_df[agg_col] = 0 

            fig = None
            theme_colors = COLOR_THEMES.get(color_theme, COLOR_THEMES[default_theme])
            if not isinstance(theme_colors, dict):
                theme_colors = COLOR_THEMES[default_theme]

            # Criação da Figura (passando agg_col via 'text=')
            if chart_type == 'barra':
                fig = px.bar(agg_df, x=dimension, y=agg_col, color=secondary_dimension,
                             text=agg_col if chart_config.get('show_data_labels') else None)
            elif chart_type == 'barra_horizontal':
                fig = px.bar(agg_df, y=dimension, x=agg_col, orientation='h', color=secondary_dimension,
                             text=agg_col if chart_config.get('show_data_labels') else None)
            elif chart_type == 'linha_agregada':
                fig = px.line(agg_df, x=dimension, y=agg_col, markers=True, color=secondary_dimension,
                             text=agg_col if chart_config.get('show_data_labels') else None)
            elif chart_type == 'pizza':
                fig = px.pie(agg_df, names=dimension, values=agg_col)
            elif chart_type == 'treemap':
                path = [dimension]
                if secondary_dimension: path.append(secondary_dimension)
                fig = px.treemap(agg_df, path=path, values=agg_col)
            elif chart_type == 'funil':
                fig = px.funnel(agg_df, x=agg_col, y=dimension,
                                text=agg_col if chart_config.get('show_data_labels') else None)
            elif chart_type == 'tabela':
                 header_color = theme_colors.get('primary_color', '#1f77b4')
                 fig = go.Figure(data=[go.Table(
                    header=dict(values=list(agg_df.columns), fill_color=header_color, align='left', font=dict(color='white')),
                    cells=dict(values=[agg_df[col] for col in agg_df.columns], fill_color='#f0f2f6', align='left')
                 )])

            if fig:
                fig = apply_chart_theme(fig, color_theme)
                fig.update_layout(title_text=None) 

                # Obtém os títulos personalizados (se existirem)
                custom_dim_title = chart_config.get('dimension_axis_title')
                custom_measure_title = chart_config.get('measure_axis_title')

                # Define os títulos finais: usa o personalizado ou o automático (dimension/y_axis_title_text)
                final_dim_axis_title = custom_dim_title if custom_dim_title else dimension
                final_measure_axis_title = custom_measure_title if custom_measure_title else y_axis_title_text

                # Aplica aos eixos corretos dependendo da orientação
                if chart_type != 'barra_horizontal':
                     fig.update_layout(xaxis_title=final_dim_axis_title, yaxis_title=final_measure_axis_title)
                else: 
                     fig.update_layout(xaxis_title=final_measure_axis_title, yaxis_title=final_dim_axis_title)

                # --- Lógica Corrigida de Rótulos ---
                if chart_config.get('show_data_labels') and chart_type not in ['tabela', 'pizza']:

                    # Define o template base
                    if is_time_in_status_measure:
                        text_template = '%{text:.1f}d'
                    else:
                        text_template = '%{text:.2s}'

                    # Se for percentual, sobrescreve o template
                    if chart_config.get('show_as_percentage'):
                         text_template = '%{text:.1f}%'

                    # Aplica o template
                    if chart_type in ['barra', 'barra_horizontal']:
                        fig.update_traces(texttemplate=text_template, textposition='auto')
                    elif chart_type == 'linha_agregada':
                        fig.update_traces(texttemplate=text_template, textposition='top center')
                    elif chart_type == 'funil':
                        fig.update_traces(texttemplate=text_template, textposition='auto')

                    elif chart_type == 'treemap':
                        if chart_config.get('show_as_percentage'):
                             fig.update_traces(texttemplate='%{label}<br>%{percentRoot:.1%}', textinfo='text')
                        elif is_time_in_status_measure:
                             fig.update_traces(texttemplate='%{label}<br>%{value:.1f}d', textinfo='text')
                        else:
                             fig.update_traces(texttemplate='%{label}<br>%{value:,.0f}', textinfo='text')

                elif chart_config.get('show_data_labels') and chart_type == 'pizza':
                     if chart_config.get('show_as_percentage'):
                         fig.update_traces(textinfo='percent+label')
                     elif is_time_in_status_measure:
                          fig.update_traces(texttemplate='%{label}<br>%{value:.1f}d', textinfo='text+percent')
                     else:
                          fig.update_traces(texttemplate='%{label}<br>%{value:,.0f}', textinfo='text+percent')

                # Lógica sufixo percentual
                if chart_config.get('show_as_percentage'):
                     if chart_type == 'pizza':
                        pass
                     elif chart_type == 'treemap':
                        pass
                     else:
                        if chart_type != 'barra_horizontal' and fig.layout.yaxis:
                             fig.layout.yaxis.ticksuffix = "%"
                        elif chart_type == 'barra_horizontal' and fig.layout.xaxis:
                             fig.layout.xaxis.ticksuffix = "%"

                st.plotly_chart(fig, use_container_width=True, key=f"{chart_key}_agg")

        elif chart_type in ['linha', 'dispersão']:
            x, y = chart_config.get('x'), chart_config.get('y')
            size_by = chart_config.get('size_by')
            color_by = chart_config.get('color_by')

            if not x or not y:
                st.warning("Configuração de gráfico X-Y inválida: Eixos X e Y são obrigatórios.")
                return

            required_cols = [x, y]
            if size_by and size_by != "Nenhum": required_cols.append(size_by)
            if color_by and color_by != "Nenhum": required_cols.append(color_by)
            
            if not all(col in df.columns for col in required_cols):
                missing = [col for col in required_cols if col not in df.columns]
                st.warning(f"Não foi possível renderizar o gráfico. Coluna(s) não encontrada(s): {', '.join(missing)}")
                return

            plot_df = df_chart_filtered.copy().dropna(subset=required_cols)
            if plot_df.empty:
                st.warning("Não há dados para exibir com as colunas e filtros selecionados.")
                return

            x_axis_col_for_plotting = x 
            date_aggregation = chart_config.get('date_aggregation')
            if date_aggregation and date_aggregation != 'Nenhum' and x in plot_df.columns:
                plot_df[x] = pd.to_datetime(plot_df[x], errors='coerce')
                plot_df.dropna(subset=[x], inplace=True)

                if pd.api.types.is_datetime64_any_dtype(plot_df[x]):
                    freq_map = {'Dia': 'D', 'Semana': 'W-MON', 'Mês': 'MS', 'Trimestre': 'QS', 'Ano': 'AS'}
                    freq = freq_map.get(date_aggregation)

                    if freq:
                        y_agg_func = chart_config.get('y_axis_aggregation', 'Média').lower()
                        agg_map = {'soma': 'sum', 'média': 'mean', 'contagem': 'count', 'contagem distinta': 'nunique'}
                        
                        grouping_cols = [pd.Grouper(key=x, freq=freq)]
                        if color_by and color_by != "Nenhum": grouping_cols.append(color_by)

                        agg_function_name = agg_map.get(y_agg_func, 'count') 

                        agg_dict = {y: agg_function_name}

                        if size_by and size_by != "Nenhum": 
                            agg_dict[size_by] = 'mean' 

                        plot_df = plot_df.groupby(grouping_cols, as_index=False).agg(agg_dict)
                        plot_df = plot_df.sort_values(by=x)

                        x_axis_col_for_plotting = f"{x} ({date_aggregation})"
                        if date_aggregation == 'Dia':
                            plot_df[x_axis_col_for_plotting] = plot_df[x].dt.strftime('%Y-%m-%d')
                        elif date_aggregation == 'Semana':
                            plot_df[x_axis_col_for_plotting] = plot_df[x].dt.strftime('Semana %U (%Y)')
                        elif date_aggregation == 'Mês':
                            plot_df[x_axis_col_for_plotting] = plot_df[x].dt.strftime('%Y-%m')
                        elif date_aggregation == 'Trimestre':
                            plot_df[x_axis_col_for_plotting] = plot_df[x].dt.year.astype(str) + '-T' + plot_df[x].dt.quarter.astype(str)
                        elif date_aggregation == 'Ano':
                            plot_df[x_axis_col_for_plotting] = plot_df[x].dt.year.astype(str)

            y_axis_title = chart_config.get('y_axis_title', y)
            if chart_config.get('y_axis_format') == 'hours' and y in plot_df.columns:
                plot_df[y] = pd.to_numeric(plot_df[y], errors='coerce') / 3600.0
                y_axis_title = y_axis_title.replace(y, f"{y} (horas)") if y in y_axis_title else f"{y} (horas)"
            
            plot_args = {
                "data_frame": plot_df, "x": x_axis_col_for_plotting, "y": y,
                "color": color_by if color_by and color_by != "Nenhum" else None,
                "text": y if chart_config.get('show_data_labels') else None,
            }

            fig_func = px.line if chart_type == 'linha' else px.scatter

            if chart_type == 'dispersão':
                size_col = size_by if size_by and size_by != "Nenhum" else None
                if size_col and size_col in plot_df.columns:
                    plot_df[size_col] = pd.to_numeric(plot_df[size_col], errors='coerce').dropna()
                    
                    original_rows = len(plot_df)
                    plot_df = plot_df[plot_df[size_col] >= 0].copy()
                    if len(plot_df) < original_rows:
                        st.caption(f"ℹ️ {original_rows - len(plot_df)} pontos de dados foram removidos da visualização porque tinham valores negativos no campo de tamanho ('{size_col}').")
                    
                    plot_args['size'] = size_col
                    plot_args['data_frame'] = plot_df

            if plot_df.empty:
                st.warning("Não restaram dados para exibir após a remoção de valores inválidos.")
                return

            fig = fig_func(**plot_args)
            fig = apply_chart_theme(fig, color_theme)
            
            if chart_config.get('show_data_labels'):
                text_template = '%{text:.2f}h' if chart_config.get('y_axis_format') == 'hours' else '%{text:.2s}'
                fig.update_traces(textposition='top center', texttemplate=text_template)
            
            fig.update_layout(title_text=None, xaxis_title=chart_config.get('x_axis_title', x), yaxis_title=y_axis_title)
            st.plotly_chart(fig, use_container_width=True, key=f"{chart_key}_xy")

        elif chart_type == 'indicator':
            theme_colors = COLOR_THEMES.get(color_theme, COLOR_THEMES[default_theme])
            if not isinstance(theme_colors, dict):
                theme_colors = COLOR_THEMES[default_theme]
            
            title_color = theme_colors.get('title_color', '#3D3D3D')
            number_color = theme_colors.get('primary_color', '#0068C9')
            delta_color = theme_colors.get('secondary_color', '#83C9FF')
            
            decimal_places = int(chart_config.get('kpi_decimal_places', 2))
            format_as_pct = chart_config.get('kpi_format_as_percentage', False)
            valueformat = f".{decimal_places}f"
            suffix = "%" if format_as_pct else ""
            
            main_value = None
            baseline = None
            fig = None
            
            if chart_config.get('source_type') == 'jql':
                from jira_connector import get_jql_issue_count
                jql_a = chart_config.get('jql_a', '')
                if not jql_a.strip():
                    st.warning("A Consulta JQL 1 (Valor A) é obrigatória e está vazia."); return
                val_a = get_jql_issue_count(st.session_state.jira_client, jql_a)
                if not isinstance(val_a, (int, float)):
                    st.error(f"Erro ao processar a Consulta JQL 1 (Valor A): {val_a}"); return
                
                val_b = None
                jql_b = chart_config.get('jql_b', '')
                if jql_b.strip():
                    val_b_raw = get_jql_issue_count(st.session_state.jira_client, jql_b)
                    if isinstance(val_b_raw, (int, float)): val_b = val_b_raw
                
                main_value = val_a
                op = chart_config.get('jql_operation')
                if op != "Nenhuma" and val_b is not None:
                    if op == "Dividir (A / B)": main_value = val_a / val_b if val_b != 0 else 0
                    elif op == "Somar (A + B)": main_value = val_a + val_b
                    elif op == "Subtrair (A - B)": main_value = val_a - val_b
                    elif op == "Multiplicar (A * B)": main_value = val_a * val_b
                
                jql_baseline = chart_config.get('jql_baseline', '')
                if jql_baseline.strip():
                    baseline_raw = get_jql_issue_count(st.session_state.jira_client, jql_baseline)
                    if isinstance(baseline_raw, (int, float)): baseline = baseline_raw
            
            else: 
                main_value = calculate_kpi_value(chart_config.get('num_op'), chart_config.get('num_field'), df_chart_filtered)
                if chart_config.get('use_baseline', False):
                    baseline = calculate_kpi_value(chart_config.get('base_op'), chart_config.get('base_field'), df_chart_filtered)
                if chart_config.get('use_den'):
                    denominator = calculate_kpi_value(chart_config.get('den_op'), chart_config.get('den_field'), df_chart_filtered)
                    if denominator is not None and denominator != 0:
                        main_value = (main_value / denominator)
                        if baseline is not None:
                            baseline = (baseline / denominator)
                    else:
                        main_value = 0; baseline = 0 if baseline is not None else None

            if format_as_pct:
                if isinstance(main_value, (int, float)): main_value *= 100
                if isinstance(baseline, (int, float)): baseline *= 100
            
            fig = go.Figure(go.Indicator(
                mode="number" + ("+delta" if baseline is not None else ""),
                value=main_value,
                title={"text": chart_config.get('title'), "font": {"size": 16, "color": title_color}},
                number={"font": {"color": number_color}, "valueformat": valueformat, "suffix": suffix},
                delta={'reference': baseline, "font": {"color": delta_color}, "valueformat": valueformat} if baseline is not None else None
            ))
            
            if fig:
                fig.update_layout(
                    margin=dict(l=10, r=10, t=30, b=0), 
                    height=130, 
                    paper_bgcolor='rgba(0,0,0,0)', 
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True, key=f"{chart_key}_indicator")

        elif chart_type == 'pivot_table':
            rows = chart_config.get('rows'); cols = chart_config.get('columns'); values = chart_config.get('values'); aggfunc = chart_config.get('aggfunc', 'Soma').lower()
            agg_map = {'soma': 'sum', 'média': 'mean', 'contagem': 'count'}
            if rows and values:
                pivot_df = pd.pivot_table(df_chart_filtered, values=values, index=rows, columns=cols, aggfunc=agg_map.get(aggfunc, 'sum')).reset_index()

                theme_colors = COLOR_THEMES.get(color_theme, COLOR_THEMES[default_theme])
                if not isinstance(theme_colors, dict):
                    theme_colors = COLOR_THEMES[default_theme]
                header_color = theme_colors.get('primary_color', '#1f77b4')
                fig = go.Figure(data=[go.Table(
                    header=dict(values=list(pivot_df.columns), fill_color=header_color, align='left', font=dict(color='white')), 
                    cells=dict(values=[pivot_df[col] for col in pivot_df.columns], fill_color='#f0f2f6', align='left')
                )])
                st.plotly_chart(fig, use_container_width=True, key=f"{chart_key}_pivot")
            else: 
                st.warning("Para a Tabela Dinâmica, 'Linhas' e 'Valores' são obrigatórios.")

        elif chart_type == 'metric_with_chart':
            fig_func_map = {'linha': px.line, 'área': px.area, 'barra': px.bar}
            title = chart_config.get('title')
            dimension = chart_config.get('mc_dimension')
            measure = chart_config.get('mc_measure')
            chart_type_internal = chart_config.get('mc_chart_type', 'Linha').lower()
            main_value_agg = chart_config.get('mc_main_value_agg')
            delta_agg = chart_config.get('mc_delta_agg')

            if not dimension or not measure:
                st.warning("Configuração de Métrica inválida. Dimensão e Medida são obrigatórias.")
                return

            measure_col_for_plotting = measure
            if measure == "Contagem de Issues":
                df_chart = df_chart_filtered.groupby(dimension).size().reset_index(name="Contagem de Issues")
                df_chart = df_chart.sort_values(by=dimension)
                measure_col_for_plotting = "Contagem de Issues"
            else:
                df_chart = df_chart_filtered.sort_values(by=dimension).dropna(subset=[measure])
            
            if df_chart.empty:
                 st.warning("Não há dados para exibir na Métrica com Gráfico.")
                 st.metric(label=title, value="N/A")
                 return

            chart_data_values = df_chart[measure_col_for_plotting].tolist()
            
            main_value = 0
            if main_value_agg == "Último valor da série":
                main_value = chart_data_values[-1] if chart_data_values else 0
            elif main_value_agg == "Soma de todos os valores":
                main_value = sum(chart_data_values)
            elif main_value_agg == "Média de todos os valores":
                main_value = sum(chart_data_values) / len(chart_data_values) if chart_data_values else 0

            delta = None
            if len(chart_data_values) > 1:
                if delta_agg == "Variação (último - primeiro)":
                    delta = chart_data_values[-1] - chart_data_values[0]
                elif delta_agg == "Variação (último - penúltimo)":
                    delta = chart_data_values[-1] - chart_data_values[-2]

            st.metric(
                label=title,
                value=f"{main_value:,.2f}",
                delta=f"{delta:,.2f}" if delta is not None else None
            )

            spark_df = pd.DataFrame({
                dimension: df_chart[dimension],
                measure_col_for_plotting: chart_data_values
            })

            fig = fig_func_map[chart_type_internal](spark_df, x=dimension, y=measure_col_for_plotting)

            fig.update_layout(
                showlegend=False,
                xaxis=dict(visible=False, showgrid=False),
                yaxis=dict(visible=False, showgrid=False),
                margin=dict(l=0, r=0, t=0, b=0),
                height=60,
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
            )
            
            if chart_type_internal in ['linha', 'área']:
                fig.update_traces(line=dict(width=2.5))

            st.plotly_chart(fig, use_container_width=True, key=f"{chart_key}_sparkline")

    except Exception as e:
        import traceback
        title = chart_config.get('title', 'Desconhecido') if isinstance(chart_config, dict) else 'Desconhecido'
        st.error(f"Ocorreu um erro ao renderizar o gráfico '{title}'.")
        with st.expander("Ver detalhes técnicos do erro"):
            st.error(f"**Tipo de Erro:** {type(e).__name__}")
            st.error(f"**Mensagem:** {e}")
            st.code(traceback.format_exc())
        with st.expander("Ver dados do gráfico com erro"):
            try:
                st.json(chart_config)
            except:
                st.write(chart_config)

def combined_dimension_ui(df, categorical_cols, date_cols, key_suffix=""):
    st.markdown("###### **Criar Dimensão Combinada**")
    c1, c2 = st.columns(2)
    dim1 = c1.selectbox("Campo 1", options=categorical_cols + date_cols, key=f"dim1_{key_suffix}")
    dim2 = c2.selectbox("Campo 2", options=[c for c in categorical_cols + date_cols if c != dim1], key=f"dim2_{key_suffix}")
    new_dim_name = f"{dim1} & {dim2}"
    df_copy = df.copy()
    df_copy[new_dim_name] = df_copy[dim1].astype(str) + " - " + df_copy[dim2].astype(str)
    st.success(f"Dimensão '{new_dim_name}' criada para a pré-visualização.")
    return new_dim_name, df_copy

def get_start_end_states(project_key):
    project_config = get_project_config(project_key) or {}
    status_mapping = project_config.get('status_mapping', {})
    global_configs = get_global_configs()
    initial_states = status_mapping.get('initial', global_configs.get('initial_states', []))
    done_states = status_mapping.get('done', global_configs.get('done_states', []))
    return initial_states, done_states

def find_date_for_status(changelog, target_statuses, default=None):
    for history in changelog.histories:
        for item in history.items:
            if item.field == 'status' and item.toString in target_statuses:
                return pd.to_datetime(history.created).replace(tzinfo=None)
    return default

def convert_dates_in_filters(filters):
    processed_filters = []
    for f in filters:
        new_filter = f.copy()
        value = new_filter.get('value')
        if isinstance(value, (date, datetime)):
            new_filter['value'] = value.isoformat()
        elif isinstance(value, (list, tuple)) and any(isinstance(v, (date, datetime)) for v in value):
            new_filter['value'] = [v.isoformat() if isinstance(v, (date, datetime)) else v for v in value]
        processed_filters.append(new_filter)
    return processed_filters

def clean_html(raw_html):
    if not isinstance(raw_html, str):
        return str(raw_html)
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return html.unescape(cleantext)

def clean_text(text):
    """Remove caracteres que não são suportados pela fonte padrão do FPDF."""
    if text is None:
        return ''
    # Normaliza para decompor caracteres acentuados e remove caracteres de controle
    text = ''.join(c for c in unicodedata.normalize('NFKD', str(text)) if unicodedata.category(c) != 'Mn' and c.isprintable())
    return text

class PDF(FPDF):
    """Classe FPDF customizada para ter cabeçalho e rodapé com logo e título."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.os_title = "Ordem de Serviço"

    def header(self):
        try:
            # Caminho corrigido para a pasta 'images' no mesmo nível da pasta 'pages'
            logo_path = str(Path(__file__).resolve().parent.parent / "images" / "logo.png")
            self.image(logo_path, 10, 8, 25)
        except Exception as e:
            print(f"Erro ao carregar o logo: {e}")
            self.set_xy(10, 8)
            self.set_font('Roboto', 'I', 8)
            self.cell(25, 10, '[Logo]', 0, 0, 'L')

        self.set_font('Roboto', 'B', 15)
        self.cell(0, 10, clean_text(self.os_title), 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Roboto', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def render_pdf_field(pdf, field_info, value, width):
    """Renderiza o valor de um campo no PDF, tratando diferentes tipos."""
    pdf.set_font('Roboto', '', 10)
    field_type = field_info.get('field_type')

    if value is None or value == '' or (isinstance(value, list) and not value):
        pdf.multi_cell(width, 6, "-")
        return

    if field_type == "Tabela" and isinstance(value, list) and value:
        pdf.ln(2)
        if not value[0]: return
        headers = value[0].keys()
        pdf.set_font('Roboto', 'B', 9)
        col_width = (width / len(headers)) - 1 if len(headers) > 0 else width
        for h in headers:
            pdf.cell(col_width, 6, clean_text(h), 1, 0, 'C')
        pdf.ln()
        pdf.set_font('Roboto', '', 8)
        for row in value:
            for h in headers:
                pdf.cell(col_width, 6, clean_text(row.get(h)), 1, 0, 'L')
            pdf.ln()
    elif field_type == "Toggle (Sim/Não)":
        display_val = "Sim" if value else "Não"
        pdf.multi_cell(width, 6, display_val)
    elif isinstance(value, list):
        display_val = ", ".join(map(str, value))
        pdf.multi_cell(width, 6, clean_text(display_val))
    else:
        pdf.multi_cell(width, 6, clean_text(value))

def create_os_pdf(data, os_title=None):
    """
    Gera um PDF para a Ordem de Serviço, com o alinhamento de texto corrigido
    e a tabela de itens complexa.
    """
    pdf = PDF()
    
    if os_title:
        pdf.os_title = clean_text(os_title)
    else:
        pdf.os_title = f"Ordem de Serviço: {clean_text(data.get('layout_name', 'N/A'))}"

    base_dir = Path(__file__).resolve().parent
    font_dir = base_dir / "fonts"
    pdf.add_font('Roboto', '', str(font_dir / "Roboto-Regular.ttf"))
    pdf.add_font('Roboto', 'B', str(font_dir / "Roboto-Bold.ttf"))
    pdf.add_font('Roboto', 'I', str(font_dir / "Roboto-Italic.ttf"))
    
    pdf.add_page()
    pdf.set_font('Roboto', 'B', 12)
    pdf.cell(0, 10, 'Detalhes da Ordem de Serviço', 0, 1, 'L')
    pdf.ln(2)

    layout_fields = data.get('custom_fields_layout', [])
    custom_data = data.get('custom_fields', {})
    
    i = 0
    while i < len(layout_fields):
        field1 = layout_fields[i]
        
        field_value_dict = custom_data.get(field1['field_name'], {})
        field_actual_value = field_value_dict.get('value') if isinstance(field_value_dict, dict) else field_value_dict
        
        est_height = 15
        if isinstance(field_actual_value, str) and field1['field_type'] == 'Texto Longo':
            est_height = (len(field_actual_value) / 80) * 8 + 20
        elif isinstance(field_actual_value, list) and field1['field_type'] == 'Tabela':
            est_height = len(field_actual_value) * 10 + 25
        if pdf.get_y() + est_height > 270:
            pdf.add_page()
            
        is_two_col = field1.get('two_columns', False)
        next_field_is_two_col = (i + 1 < len(layout_fields)) and layout_fields[i+1].get('two_columns', False)

        line_height = 6

        if is_two_col and next_field_is_two_col:
            field2 = layout_fields[i+1]
            y_start = pdf.get_y()
            half_width = (pdf.w - pdf.l_margin - pdf.r_margin) / 2 - 2
            col2_start_x = pdf.l_margin + half_width + 4

            # --- Coluna 1 ---
            pdf.set_font('Roboto', 'B', 11)
            pdf.multi_cell(half_width, line_height, clean_text(field1['field_name']), 0, 'L')
            pdf.set_x(pdf.l_margin) # Garante que o valor comece no início da coluna
            render_pdf_field(pdf, field1, field_actual_value, width=half_width)
            y_after_col1 = pdf.get_y()

            # --- Coluna 2 ---
            pdf.set_xy(col2_start_x, y_start) # Move o cursor para o início da segunda coluna
            field2_value_dict = custom_data.get(field2['field_name'], {})
            field2_actual_value = field2_value_dict.get('value') if isinstance(field2_value_dict, dict) else field2_value_dict
            
            pdf.set_font('Roboto', 'B', 11)
            pdf.multi_cell(half_width, line_height, clean_text(field2['field_name']), 0, 'L')
            pdf.set_x(col2_start_x) # Garante que o valor comece no início da coluna 2
            render_pdf_field(pdf, field2, field2_actual_value, width=half_width)
            y_after_col2 = pdf.get_y()

            # --- Finaliza a linha ---
            pdf.set_y(max(y_after_col1, y_after_col2))
            pdf.ln(4)
            i += 2
        else:
            # Renderiza o campo de coluna única
            full_width = pdf.w - pdf.l_margin - pdf.r_margin
            pdf.set_font('Roboto', 'B', 11)
            pdf.multi_cell(full_width, line_height, clean_text(field1['field_name']), 0, 'L')
            pdf.set_x(pdf.l_margin) # Garante o alinhamento para o valor
            render_pdf_field(pdf, field1, field_actual_value, width=full_width)
            pdf.ln(4)
            i += 1
            
    items = data.get('items')
    totals = data.get('items_totals')
    currency_name = data.get('currency_name', 'Moeda')

    if items:
        if pdf.get_y() > 200: pdf.add_page()
        pdf.ln(10)
        pdf.set_font('Roboto', 'B', 12)
        pdf.cell(0, 10, 'Itens do Catálogo', 0, 1, 'L')
        pdf.ln(2)

        page_width = pdf.w - 2 * pdf.l_margin
        col_widths = {"id": page_width * 0.1, "desc": page_width * 0.35, "qtd": page_width * 0.1, "val": page_width * 0.15, "total": page_width * 0.15, "brl": page_width * 0.15}
        
        pdf.set_font('Roboto', 'B', 9)
        pdf.cell(col_widths["id"], 7, 'Item ID', 1, 0, 'C')
        pdf.cell(col_widths["desc"], 7, 'Descrição', 1, 0, 'C')
        pdf.cell(col_widths["qtd"], 7, 'Qtde. Itens', 1, 0, 'C')
        pdf.cell(col_widths["val"], 7, f'Valor ({currency_name})', 1, 0, 'C')
        pdf.cell(col_widths["total"], 7, f'Total ({currency_name})', 1, 0, 'C')
        pdf.cell(col_widths["brl"], 7, 'Valor (R$)', 1, 1, 'C')

        pdf.set_font('Roboto', '', 8)
        for item in items:
            desc_text = clean_text(item.get('Item', ''))
            
            lines_desc = pdf.multi_cell(col_widths["desc"], 5, desc_text, 0, 'L', split_only=True)
            cell_height = max(5 * len(lines_desc), 5) 

            if pdf.get_y() + cell_height > 277: 
                pdf.add_page()
                pdf.set_font('Roboto', 'B', 9)
                pdf.cell(col_widths["id"], 7, 'Item ID', 1, 0, 'C')
                pdf.cell(col_widths["desc"], 7, 'Descrição', 1, 0, 'C')
                pdf.cell(col_widths["qtd"], 7, 'Qtde. Itens', 1, 0, 'C')
                pdf.cell(col_widths["val"], 7, f'Valor ({currency_name})', 1, 0, 'C')
                pdf.cell(col_widths["total"], 7, f'Total ({currency_name})', 1, 0, 'C')
                pdf.cell(col_widths["brl"], 7, 'Valor (R$)', 1, 1, 'C')
                pdf.set_font('Roboto', '', 8)

            x_start, y_start = pdf.get_x(), pdf.get_y()

            pdf.multi_cell(col_widths["id"], cell_height, str(item.get('ID do Item', '')), 1, 'C')
            pdf.set_xy(x_start + col_widths["id"], y_start)
            pdf.multi_cell(col_widths["desc"], 5, desc_text, 1, 'L')
            
            pdf.set_xy(x_start + col_widths["id"] + col_widths["desc"], y_start)
            
            pdf.cell(col_widths["qtd"], cell_height, str(item.get('Qtde. Itens', '')), 1, 0, 'C')
            pdf.cell(col_widths["val"], cell_height, str(item.get('Valor', '')), 1, 0, 'C')
            pdf.cell(col_widths["total"], cell_height, str(item.get('Total Currency', '')), 1, 0, 'C')
            
            brl_value = item.get('Valor (R$)', 0)
            formatted_brl = f"R$ {brl_value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            pdf.cell(col_widths["brl"], cell_height, formatted_brl, 1, 1, 'R')

        if totals:
            pdf.set_font('Roboto', 'B', 9)
            total_currency = totals.get('TOTAL_CURRENCY', 0)
            total_brl = totals.get('TOTAL_BRL', 0)
            formatted_total_brl = f"R$ {total_brl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            
            total_label_width = sum(col_widths.values()) - col_widths["total"] - col_widths["brl"]
            pdf.cell(total_label_width, 7, 'TOTAL', 1, 0, 'R')
            pdf.cell(col_widths["total"], 7, str(round(total_currency, 2)), 1, 0, 'C')
            pdf.cell(col_widths["brl"], 7, formatted_total_brl, 1, 1, 'R')

    if data.get('assinantes'):
        if pdf.get_y() > 220: pdf.add_page()
        pdf.ln(10)
        pdf.set_font('Roboto', 'B', 12)
        pdf.cell(0, 10, 'Assinaturas', 0, 1, 'L')
        pdf.ln(15)
        for assinante in data['assinantes']:
            if assinante.get('Nome') and assinante.get('Papel'):
                if pdf.get_y() > 250: pdf.add_page(); pdf.ln(10)
                pdf.cell(0, 8, "___________________________________________", 0, 1, 'C')
                pdf.cell(0, 8, clean_text(f"{assinante['Nome']}"), 0, 1, 'C')
                pdf.cell(0, 8, clean_text(f"({assinante['Papel']})"), 0, 1, 'C')
                pdf.ln(10)
    
    return bytes(pdf.output(dest='S'))

def create_dashboard_pdf(dashboard_name, charts_by_tab, df):
    """Gera um PDF do dashboard, com gráficos como imagens."""
    pdf = PDF()
    pdf.os_title = f"Dashboard: {dashboard_name}"

    base_dir = Path(__file__).resolve().parent
    font_dir = base_dir / "fonts"
    pdf.add_font('Roboto', '', str(font_dir / "Roboto-Regular.ttf"))
    pdf.add_font('Roboto', 'B', str(font_dir / "Roboto-Bold.ttf"))

    pdf.add_page()

    for tab_name, charts in charts_by_tab.items():
        if not charts: continue
        if pdf.page_no() > 1 or pdf.get_y() > 40: pdf.add_page()

        pdf.set_font('Roboto', 'B', 18)
        pdf.cell(0, 10, f"Aba: {tab_name}", 0, 1, 'L')
        pdf.ln(5)

        for chart_config in charts:
            pdf.set_font('Roboto', 'B', 12)
            pdf.multi_cell(0, 8, f"📊 {chart_config.get('title', 'Gráfico sem título')}", 0, 'L')

            try:
                fig = render_chart(chart_config, df, return_fig=True)
                if fig:
                    img_bytes = fig.to_image(format="png", scale=2, width=800, height=450)
                    img_file = io.BytesIO(img_bytes)

                    if pdf.get_y() + 80 > 297: pdf.add_page()
                    pdf.image(img_file, w=180)
                    pdf.ln(10)
                else:
                    pdf.set_font('Roboto', '', 10)
                    pdf.set_text_color(255, 0, 0)
                    pdf.multi_cell(0, 5, "Nao foi possivel gerar uma imagem para este tipo de grafico.")
                    pdf.set_text_color(0, 0, 0)
                    pdf.ln(5)
            except Exception as e:
                pdf.set_font('Roboto', '', 10)
                pdf.set_text_color(255, 0, 0)
                error_type = type(e).__name__
                safe_error_message = f"Falha ao renderizar o grafico. Tipo de erro: {error_type}."
                pdf.multi_cell(0, 5, safe_error_message)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(5)

    return pdf.output(dest='S').encode('latin-1')

def summarize_chart_data(chart_config, df):
    """Gera um resumo em texto dos dados de um único gráfico."""
    title = chart_config.get('title', 'um gráfico')
    chart_type = chart_config.get('type')

    try:
        df_to_render = apply_filters(df, chart_config.get('filters', []))

        if chart_type == 'indicator':
            if chart_config.get('source_type') == 'jql':
                return f"O indicador '{title}' é calculado com uma consulta JQL personalizada."
            else:
                numerator = calculate_kpi_value(chart_config.get('num_op'), chart_config.get('num_field'), df_to_render)
                value = numerator
                if chart_config.get('use_den'):
                    denominator = calculate_kpi_value(chart_config.get('den_op'), chart_config.get('den_field'), df_to_render)
                    if denominator is not None and denominator != 0:
                        value = (numerator / denominator) * 100
                    else:
                        value = 0
                if value is not None and pd.notna(value):
                    return f"O indicador '{title}' mostra o valor de {value:.1f}."
                else:
                    return f"O indicador '{title}' não pôde ser calculado (N/A)."

        elif chart_type in ['barra', 'pizza']:
            dimension = chart_config.get('dimension'); measure = chart_config.get('measure'); agg = chart_config.get('agg', 'Soma')
            if not dimension or not measure: return None
            if measure == 'Contagem de Issues':
                summary_df = df_to_render.groupby(dimension).size().nlargest(5)
                return f"No gráfico '{title}', a contagem de issues por '{dimension}' revela que os 5 maiores grupos são: {', '.join([f'{idx} ({val})' for idx, val in summary_df.items()])}."
            else:
                summary_df = df_to_render.groupby(dimension)[measure].agg(agg.lower()).nlargest(5)
                return f"No gráfico '{title}', a {agg.lower()} de '{measure}' por '{dimension}' revela que os 5 maiores grupos são: {', '.join([f'{idx} ({val:.1f})' for idx, val in summary_df.items()])}."

        elif chart_type == 'linha':
            x_col, y_col = chart_config['x'], chart_config['y']
            plot_df = df_to_render.dropna(subset=[x_col, y_col])
            if len(plot_df) > 2:
                X = np.array(range(len(plot_df))).reshape(-1, 1); y = plot_df[y_col]
                model = LinearRegression().fit(X, y)
                trend = "de subida" if model.coef_[0] > 0 else "de descida"
                return f"O gráfico de linha '{title}' mostra '{y_col}' ao longo de '{x_col}', com uma tendência geral {trend}."

        return f"Dados para o gráfico '{title}' do tipo {chart_type}."
    except Exception:
        return f"Não foi possível processar os dados para o gráfico '{title}'."

# --- FUNÇÕES DE IA ---
def _get_ai_client_and_model(provider, user_data):
    """Função auxiliar para configurar e retornar o cliente de IA correto."""
    if user_data and user_data.get('role') == 'admin':
        with st.expander("🔍 Dados do Perfil (Depuração)", expanded=False):
            st.info("Verifique se a chave correta (Gemini ou OpenAI) está presente aqui.")
            st.json(user_data)

    api_key_encrypted = None
    if provider == "Google Gemini":
        api_key_encrypted = user_data.get('encrypted_gemini_key')
        if not api_key_encrypted:
            st.warning("Nenhuma chave de API do Gemini configurada.", icon="🔑")
            st.page_link("pages/9_👤_Minha_Conta.py", label="Configurar Chave de IA Agora", icon="🤖")
            return None
        try:
            api_key = decrypt_token(api_key_encrypted)
            genai.configure(api_key=api_key)
            model_name = user_data.get('ai_model_preference', 'gemini-flash-latest')
            return genai.GenerativeModel(model_name)
        except Exception as e:
            st.error(f"Erro com a API do Gemini: {e}"); return None

    elif provider == "OpenAI (ChatGPT)":
        api_key_encrypted = user_data.get('encrypted_openai_key')
        if not api_key_encrypted:
            st.warning("Nenhuma chave de API da OpenAI configurada.", icon="🔑")
            st.page_link("pages/9_👤_Minha_Conta.py", label="Configurar Chave de IA Agora", icon="🤖")
            return None
        try:
            api_key = decrypt_token(api_key_encrypted)
            return openai.OpenAI(api_key=api_key)
        except Exception as e:
            st.error(f"Erro com a API da OpenAI: {e}"); return None
    return None

def get_ai_insights(project_name, chart_summaries, provider):
    """Chama a API de IA preferida do utilizador para gerar insights do dashboard."""
    user_data = find_user(st.session_state['email'])
    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client: return None

    prompt = f"""
    Aja como um Analista de Negócios especialista em projetos de software e metodologias ágeis.
    O seu trabalho é analisar os dados de um dashboard do Jira para o projeto "{project_name}" e fornecer um resumo executivo em português.

    Aqui estão os dados resumidos de cada gráfico no dashboard:
    {chr(10).join(f"- {s}" for s in chart_summaries if s)}

    Com base nestes dados, gere uma análise concisa e acionável. A sua resposta deve ser formatada em Markdown e dividida nas seguintes secções:
    1.  **🎯 Pontos Fortes:** O que os dados indicam que está a correr bem? Seja específico.
    2.  **⚠️ Pontos de Atenção:** Onde podem estar os riscos, gargalos ou desvios? Aponte as métricas preocupantes.
    3.  **🚀 Recomendações:** Sugira 1 a 2 ações práticas que a equipa ou o gestor do projeto poderiam tomar com base nesta análise.
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            return response.text
        else: 
            response = model_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            return response.choices[0].message.content
    except openai.RateLimitError:
        st.error(
            """
            **Sua quota de utilização da API da OpenAI foi excedida.** 😟
            Isto geralmente acontece quando os créditos gratuitos expiram ou o seu limite de faturação é atingido.
            **O que fazer?**
            1. Aceda ao seu painel da [OpenAI Platform](https://platform.openai.com/account/billing/overview).
            2. Verifique a sua secção de **"Billing" (Faturação)** para adicionar um método de pagamento ou aumentar os seus limites.
            Enquanto isso, você pode ir à sua página **'Minha Conta'** e mudar o seu provedor de IA para o **Google Gemini**.
            """,
            icon="💳"
        )
        return None
    except openai.AuthenticationError:
        st.error("A sua chave de API da OpenAI é inválida ou foi revogada. Por favor, verifique-a na página 'Minha Conta'.", icon="🔑")
        return None
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado com a API da OpenAI: {e}"); return None

def generate_chart_config_from_text(prompt, numeric_cols, categorical_cols, active_filters=None):
    """
    Usa a API de IA para gerar uma configuração de gráfico e aplica os filtros ativos.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    cleaned_response = ""

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return None, "A sua chave de API não está configurada ou é inválida."

    system_prompt = f"""
    Aja como um especialista em Business Intelligence. Sua tarefa é converter um pedido em linguagem natural para um objeto JSON que define uma visualização.

    **GLOSSÁRIO DE CONCEITOS:**
    * **Dimensão ('dimension'):** O campo para agrupar os dados (ex: "issues POR STATUS").
    * **Medida ('measure'):** O valor a ser calculado (ex: "a SOMA DO LEAD TIME").
    * **Eixo X ('x') / Eixo Y ('y'):** Usados para gráficos não agregados que comparam duas colunas diretamente.
    * **Filtros ('filters'):** Condições para limitar os dados (ex: "APENAS PARA O CLIENTE 'APEX'").
    * **Rótulos de Dados ('show_data_labels'):** `true` se o utilizador pedir para "mostrar valores" ou "exibir totais".

    **CAMPOS DISPONÍVEIS:**
    - Categóricos: {', '.join(categorical_cols)}
    - Numéricos: {', '.join(numeric_cols)}

    **REGRAS DE GERAÇÃO:**
    1.  **Identificar a Intenção:**
        * Se o pedido compara duas colunas diretamente (ex: "cycle time vs data de conclusão"), gere um **Gráfico X-Y**.
        * Se o pedido agrega uma medida por uma dimensão (ex: "total de issues por status"), gere um **Gráfico Agregado**.
        * Se o pedido resulta num número único (ex: "qual o total de issues?"), gere um **Indicador (KPI)**.

    2.  **Estruturas JSON de Exemplo:**
        * **Gráfico X-Y:** `{{"creator_type": "Gráfico X-Y", "type": "[dispersão|linha]", "x": "...", "y": "...", "title": "..."}}`
        * **Gráfico Agregado:** `{{"creator_type": "Gráfico Agregado", "type": "[barra|linha_agregada|pizza]", "dimension": "...", "measure": "...", "agg": "...", "title": "..."}}`
        * **KPI:** `{{"creator_type": "Indicador (KPI)", "type": "indicator", "style": "Número Grande", "title": "...", "num_op": "...", "num_field": "..."}}`

    3.  **Regras de Preenchimento:**
        * Para contagem, a 'measure' DEVE ser "Contagem de Issues" e o 'agg' DEVE ser "Contagem".
        * Preste atenção a palavras-chave como "linha", "barras", "pizza" para definir o campo "type". Se nada for dito, use "barra".

    Responda APENAS com o objeto JSON.
    ---
    """
    
    full_prompt = f"{system_prompt}\n\n**TAREFA REAL:**\nPedido do Utilizador: \"{prompt}\""

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(full_prompt)
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            cleaned_response = match.group(0) if match else "{}"
        else: # OpenAI
            response = model_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": full_prompt}], response_format={"type": "json_object"})
            cleaned_response = response.choices[0].message.content

        if not cleaned_response: return None, "A IA não retornou uma resposta."

        chart_config = json.loads(cleaned_response)

        if not isinstance(chart_config, dict) or 'type' not in chart_config:
            return None, f"A IA retornou uma resposta inesperada. Resposta: {cleaned_response}"

        ia_filters = chart_config.get('filters', [])
        chart_config['filters'] = active_filters + ia_filters
        chart_config['id'] = str(uuid.uuid4())
        chart_config['source_type'] = 'visual'

        return chart_config, None
    except Exception as e:
        return None, f"Ocorreu um erro ao processar a resposta da IA: {e}"


def generate_risk_analysis_with_ai(project_name, metrics_summary):
    """
    Usa a API de IA preferida do utilizador para analisar um resumo de métricas
    e gerar uma lista de descrições de riscos potenciais.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    
    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        st.error("Análise de riscos indisponível. Verifique a configuração da sua chave de IA.")
        return [f"Erro: Chave de IA para o provedor '{provider}' não configurada."]

    prompt = f"""
    Aja como um Agile Coach especialista. Analise o seguinte resumo de métricas do projeto "{project_name}":
    {metrics_summary}

    Com base nestes dados, identifique 2 a 3 riscos ou pontos de atenção críticos.
    A sua resposta deve ser uma lista de descrições de riscos, formatada como um JSON array de strings.
    Exemplo de resposta: ["O Lead Time médio está a aumentar, o que pode indicar gargalos no início do fluxo.", "A baixa taxa de entregas no último mês sugere uma possível sobrecarga da equipa ou bloqueios externos."]
    Responda APENAS com o JSON array.
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_response)

        elif provider == "OpenAI (ChatGPT)":
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Responda apenas com um JSON array de strings."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)

    except Exception as e:
        st.error(f"Erro ao gerar análise de riscos: {e}")
        return [f"Erro na comunicação com a API: {e}"]

def generate_ai_risk_assessment(project_name, metrics_summary):
    """
    Usa a API de IA preferida do utilizador para analisar métricas e gerar
    um nível de risco e uma lista de descrições de riscos.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"risk_level": "Erro", "risks": [f"Chave de IA para o provedor '{provider}' não configurada."]}

    prompt = f"""
    Aja como um Gestor de Projetos Sênior. Analise o seguinte resumo de métricas do projeto "{project_name}":
    {metrics_summary}

    Com base nestes dados, faça o seguinte:
    1.  Classifique o Nível de Risco geral do projeto como "Baixo", "Moderado", "Alto" ou "Crítico".
    2.  Identifique de 2 a 3 riscos ou pontos de atenção críticos que justificam essa classificação.

    A sua resposta deve ser um objeto JSON com a seguinte estrutura:
    {{
      "risk_level": "Seu Nível de Risco aqui",
      "risks": [
        "Descrição detalhada do primeiro risco.",
        "Descrição detalhada do segundo risco."
      ]
    }}
    Responda APENAS com o objeto JSON.
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_response)

        elif provider == "OpenAI (ChatGPT)":
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Responda apenas com um objeto JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)

    except Exception as e:
        st.error(f"Erro ao gerar análise de riscos: {e}")
        return {"risk_level": "Erro", "risks": [f"Erro na comunicação com a API: {e}"]}

@st.cache_data(ttl=3600, show_spinner=False)
def get_ai_rag_status(project_name, metrics_summary):
    """
    Usa a API de IA preferida do utilizador para analisar métricas e determinar
    um status RAG para o projeto.
    """
    
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    
    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client: 
        st.error("Análise indisponível. Verifique a configuração da sua chave de IA.")
        return "⚪ Erro"

    prompt = f"""
    Aja como um Diretor de Projetos (PMO). Analise o seguinte resumo de métricas do projeto "{project_name}":
    {metrics_summary}

    Com base nestes dados, classifique o status do projeto em UMA das seguintes quatro categorias:
    "🟢 No prazo", "🟡 Atraso moderado", "🔴 Atrasado", "⚪ Não definido".

    Use o seguinte critério:
    - Se o percentual concluído for alto e o desvio de prazo for negativo ou próximo de zero, o status é "🟢 No prazo".
    - Se o percentual concluído for médio e o desvio de prazo for positivo, mas pequeno, o status é "🟡 Atraso moderado".
    - Se o percentual concluído for baixo e o desvio de prazo for significativamente positivo, o status é "🔴 Atrasado".
    - Se os dados forem insuficientes para uma conclusão, use "⚪ Não definido".

    Responda APENAS com a string da categoria escolhida, sem nenhuma outra palavra.
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            return response.text.strip()

        elif provider == "OpenAI (ChatGPT)":
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Responda apenas com a string da categoria escolhida."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()

    except Exception as e:
        st.error(f"Erro ao gerar status RAG: {e}")
        return "⚪ Erro"

def get_ai_forecast_analysis(project_name, scope_total, completed_pct, avg_velocity, trend_velocity, forecast_date_str):
    """Gera um resumo de forecast usando a IA configurada."""
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client: return "Análise indisponível. Verifique a configuração da sua chave de IA."

    metrics_summary = f"- Escopo Total: {scope_total}\n- Percentual Concluído: {completed_pct}%\n- Velocidade Média: {avg_velocity:.1f}/semana\n- Velocidade de Tendência: {trend_velocity:.1f}/semana\n- Previsão de Conclusão: {forecast_date_str}"
    prompt = f"Aja como um Gestor de Projetos. Analise as métricas do projeto '{project_name}':\n{metrics_summary}\n\nEscreva um parágrafo de 'Resumo Executivo' a avaliar a saúde, aceleração e realismo da previsão de entrega."

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            return response.text
        else: # OpenAI
            response = model_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": prompt}])
            return response.choices[0].message.content
    except Exception as e:
        return f"Erro ao gerar a análise de forecast: {e}"

def get_ai_planning_analysis(project_name, remaining_work, remaining_weeks, required_throughput, trend_velocity, people_needed, current_team_size):
    """
    Usa a API de IA preferida do utilizador para analisar um cenário de planeamento
    e gerar uma análise de viabilidade, combinando a lógica de prompt detalhada
    com a gestão de chaves centralizada.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    # 1. Obtém o cliente de IA de forma segura através da função central
    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return "Análise indisponível. Verifique a configuração da sua chave de IA."

    # 2. Constrói o resumo das métricas e o prompt detalhado
    metrics_summary = f"""
    - Trabalho Restante: {remaining_work}
    - Semanas Restantes até a meta: {remaining_weeks:.1f}
    - Vazão (Throughput) Necessária: {required_throughput:.1f} por semana
    - Vazão de Tendência (performance recente): {trend_velocity:.1f} por semana
    - Pessoas Necessárias (estimativa): {people_needed}
    - Tamanho da Equipa Atual: {current_team_size}
    """

    prompt = f"""
    Aja como um Agile Coach Sênior. Analise o seguinte cenário de planeamento de entrega para o projeto "{project_name}":
    {metrics_summary}

    Com base nesta comparação entre o necessário e o histórico, escreva um parágrafo de "Análise de Viabilidade". O seu texto deve ser conciso e focado em responder às seguintes perguntas:
    1.  O plano é realista? Compare a "Vazão Necessária" com a "Vazão de Tendência".
    2.  Quais são os principais riscos se a vazão necessária for muito maior que a tendência? (Ex: risco de burnout, queda na qualidade).
    3.  Com base na estimativa de "Pessoas Necessárias" vs. o tamanho atual da equipa, qual é a sua recomendação? (Ex: "o plano é viável com a equipa atual", "o plano exige recursos adicionais", etc.).

    Seja direto e use uma linguagem clara e profissional.
    """

    # 3. Chama a API correta e retorna a resposta
    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            return response.text
        elif provider == "OpenAI (ChatGPT)":
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Aja como um Agile Coach Sênior."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
    except Exception as e:
        st.error(f"Erro ao gerar a análise de planeamento: {e}")
        return "Não foi possível gerar a análise de planeamento."

def get_field_value(issue, field_config):
    """
    Função inteligente que extrai o valor de qualquer campo do Jira,
    independentemente do seu tipo (texto, lista, objeto, etc.).
    """
    field_id = field_config.get('id')
    if not field_id:
        return None

    value = getattr(issue.fields, field_id, None)

    if value is None:
        return None

    # Lógica para os diferentes tipos de objeto do Jira
    if hasattr(value, 'displayName'): return value.displayName
    if hasattr(value, 'value'): return value.value
    if hasattr(value, 'name'): return value.name
    if isinstance(value, list):
        return ', '.join([getattr(v, 'name', str(v)) for v in value])

    return str(value).split('T')[0]

def send_email_with_attachment(to_address, subject, body, attachment_bytes=None, attachment_filename=None, template_purpose=None, template_params=None):
    """
    Função central para enviar e-mails.
    Busca automaticamente um ID de template das configs globais se um 'template_purpose' for fornecido.
    Reverte para o 'body' (HTML) se nenhum ID de template for encontrado.
    """
    # --- Carrega as configs GLOBAIS diretamente ---
    smtp_configs = get_global_smtp_configs()

    if not smtp_configs or not smtp_configs.get('provider') or not smtp_configs.get('from_email'):
        return False, "Falha: Configurações globais de SMTP incompletas ou não encontradas."

    provider = smtp_configs.get('provider')
    from_email = smtp_configs.get('from_email')
    sender_name = "Gauge Metrics" # Alias padrão

    # --- ALTERAÇÃO 1: LÓGICA DE LOOKUP DE TEMPLATE ---
    template_id = None # Padrão é None (enviar HTML bruto)
    if template_purpose and template_params is not None:
        # Tenta encontrar o ID do template nas configurações salvas
        template_id_str = smtp_configs.get("templates", {}).get(template_purpose)
        try:
            # Tenta converter o ID para um inteiro
            template_id = int(template_id_str)
        except (ValueError, TypeError):
            # Se falhar (vazio ou não numérico), template_id permanece None
            template_id = None 
    
    # Se template_id for None, a lógica de cada provedor reverterá para 'body'
    # --- FIM DA ALTERAÇÃO 1 ---

    # --- Lógica SendGrid ---
    if provider == 'SendGrid':
        try:
            # (Código de autenticação SendGrid...)
            api_key_encrypted = smtp_configs.get('api_key_encrypted')
            if not api_key_encrypted:
                return False, "Chave de API do SendGrid não encontrada nas configurações globais."
            api_key = decrypt_token(api_key_encrypted)
            if not api_key: 
                 return False, "Falha ao descriptografar a chave de API do SendGrid."

            import sendgrid
            from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition, From

            sg = sendgrid.SendGridAPIClient(api_key)

            message = Mail(
                from_email=From(email=from_email, name=sender_name), 
                to_emails=to_address, 
                subject=subject
                # html_content é adicionado abaixo
            )

            # --- ALTERAÇÃO 2: Adicionar lógica de template ao SendGrid ---
            if template_id is not None:
                message.template_id = template_id
                message.dynamic_template_data = template_params
            else:
                message.html_content = body
            # --- FIM DA ALTERAÇÃO 2 ---

            if attachment_bytes and attachment_filename:
                # (Código do anexo...)
                encoded_file = base64.b64encode(attachment_bytes).decode()
                attachedFile = Attachment(
                    FileContent(encoded_file),
                    FileName(attachment_filename),
                    FileType('application/pdf'), 
                    Disposition('attachment')
                )
                message.attachment = attachedFile

            response = sg.send(message)
            is_success = 200 <= response.status_code < 300
            return is_success, f"Status SendGrid: {response.status_code}"
        except Exception as e:
            return False, f"Ocorreu um erro ao enviar e-mail via SendGrid: {e}"

    # --- Lógica Gmail (SMTP) (Não suporta templates, sempre usa HTML) ---
    elif provider == 'Gmail (SMTP)':
        try:
            # (Código de autenticação Gmail...)
            app_password_encrypted = smtp_configs.get('app_password_encrypted')
            if not app_password_encrypted:
                return False, "Senha de aplicação do Gmail não encontrada nas configurações globais."
            app_password = decrypt_token(app_password_encrypted)
            if not app_password: 
                 return False, "Falha ao descriptografar a senha de aplicação do Gmail."

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{sender_name} <{from_email}>" 
            msg['To'] = to_address if isinstance(to_address, str) else ', '.join(to_address)

            # Gmail sempre usará o 'body' (HTML)
            part_html = MIMEText(body, 'html')
            msg.attach(part_html)

            if attachment_bytes and attachment_filename:
                # (Código do anexo...)
                part_attach = MIMEApplication(attachment_bytes, Name=attachment_filename)
                part_attach['Content-Disposition'] = f'attachment; filename="{attachment_filename}"'
                msg.attach(part_attach)

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls() 
                server.login(from_email, app_password) 
                server.sendmail(from_email, to_address, msg.as_string()) 

            return True, "E-mail enviado com sucesso via Gmail."
        except Exception as e:
             return False, f"Ocorreu um erro inesperado ao enviar e-mail via Gmail: {e}"

    # --- Lógica Mailersend ---
    elif provider == 'Mailersend':
        try:
            from mailersend import Mailersend, Email, Recipient, Attachment
            api_key_encrypted = smtp_configs.get('mailersend_api_key_encrypted')
            if not api_key_encrypted:
                return False, "Chave de API do Mailersend não encontrada nas configurações globais."
            api_key = decrypt_token(api_key_encrypted)
            if not api_key:
                return False, "Falha ao descriptografar a chave de API do Mailersend."

            ms = Mailersend(api_key)
            mail = Email()
            
            mail.set_from({"email": from_email, "name": sender_name})
            mail.set_to([to_address])
            mail.set_subject(subject)
            
            # --- ALTERAÇÃO 3: Adicionar lógica de template ao Mailersend ---
            if template_id is not None:
                # O Mailersend usa "variáveis" e não "params"
                mail.set_template_id(template_id)
                mail.set_variables([{"email": to_address, "substitutions": [{"var": k, "value": v} for k, v in template_params.items()]}])
            else:
                mail.set_html(body)
            # --- FIM DA ALTERAÇÃO 3 ---
            
            if attachment_bytes and attachment_filename:
                # (Código do anexo...)
                encoded_file = base64.b64encode(attachment_bytes).decode()
                att = Attachment(
                    content=encoded_file,
                    filename=attachment_filename
                )
                mail.set_attachments([att])

            response_dict, status_code = ms.email.send(mail.get_params())

            is_success = 200 <= status_code < 300 
            if is_success:
                return True, f"E-mail enviado com sucesso via Mailersend (Status: {status_code})."
            else:
                error_msg = response_dict.get('message', 'Erro desconhecido')
                return False, f"Falha no envio pelo Mailersend (Status: {status_code}): {error_msg}"
        except Exception as e:
            return False, f"Ocorreu um erro ao enviar e-mail via Mailersend: {e}"

    # --- Lógica Brevo (O if/else já estava correto) ---
    elif provider == 'Brevo':
        try:
            # (Código de autenticação Brevo...)
            import sib_api_v3_sdk
            from sib_api_v3_sdk.rest import ApiException
            api_key_encrypted = smtp_configs.get('brevo_api_key_encrypted')
            if not api_key_encrypted:
                return False, "Chave de API do Brevo não encontrada nas configurações globais."
            api_key = decrypt_token(api_key_encrypted)
            if not api_key:
                return False, "Falha ao descriptografar a chave de API do Brevo."

            config = sib_api_v3_sdk.Configuration()
            config.api_key['api-key'] = api_key
            api_client = sib_api_v3_sdk.ApiClient(config)
            api_instance = sib_api_v3_sdk.TransactionalEmailsApi(api_client)
            
            send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                sender=sib_api_v3_sdk.SendSmtpEmailSender(name=sender_name, email=from_email),
                to=[sib_api_v3_sdk.SendSmtpEmailTo(email=to_address)],
                subject=subject
            )

            # --- ALTERAÇÃO 4: Lógica de template do Brevo (já estava correta, apenas verificando) ---
            if template_id is not None and template_params is not None:
                send_smtp_email.template_id = template_id
                send_smtp_email.params = template_params
            else:
                send_smtp_email.html_content = body
            # --- FIM DA ALTERAÇÃO 4 ---

            if attachment_bytes and attachment_filename:
                # (Código do anexo...)
                encoded_file = base64.b64encode(attachment_bytes).decode()
                attachment = sib_api_v3_sdk.SendSmtpEmailAttachment(
                    content=encoded_file,
                    name=attachment_filename
                )
                send_smtp_email.attachment = [attachment]

            api_response = api_instance.send_transac_email(send_smtp_email)
            
            return True, "E-mail enviado com sucesso via Brevo."
        except Exception as e:
            return False, f"Ocorreu um erro inesperado ao enviar e-mail via Brevo: {e}"

    else:
        return False, f"Provedor de e-mail '{provider}' não configurado ou inválido nas configurações globais."
    
def is_valid_url(url):
    """Verifica se uma string corresponde ao formato de um URL."""
    # Expressão regular simples para validar URLs
    regex = re.compile(
        r'^(?:http|ftp)s?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def is_valid_email(email):
    """Verifica se uma string corresponde ao formato de um e-mail."""
    # Expressão regular para validar e-mails
    regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')
    return re.fullmatch(regex, email)

def get_ai_product_vision(project_name, issues_data):
    """
    Usa a IA para analisar uma lista de issues e gerar uma visão de produto,
    identificando gaps e sugerindo melhorias.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return "Análise indisponível. Verifique a configuração da sua chave de IA."

    # Prepara um resumo dos dados para enviar à IA
    tasks_summary = "\n".join([f"- {item['Tipo']}: {item['Título']} (Labels: {item['Labels']})" for item in issues_data])

    prompt = f"""
    Aja como um Diretor de Produto experiente. A sua tarefa é analisar uma lista de tarefas (issues) do projeto "{project_name}" e gerar uma análise estratégica de produto em português.

    **Dados das Tarefas Analisadas:**
    {tasks_summary}

    **A sua análise deve seguir estritamente a seguinte estrutura em Markdown:**

    ### 🔮 Visão Geral do Produto
    (Faça um resumo de 2-3 frases sobre o foco atual do produto, com base nos tipos de tarefas que estão a ser desenvolvidas.)

    ### 📊 Análise da Natureza do Trabalho
    (Classifique o esforço da equipa. Estime, em percentagem, quanto do trabalho parece ser dedicado a: **Valor para o Usuário** (novas features), **Manutenção do Negócio** (bugs, débitos técnicos) e **Inovação** (pesquisas, provas de conceito). Justifique a sua estimativa.)

    ### 🔍 Gaps e Oportunidades Identificados
    (Com base nas tarefas, identifique 2 a 3 "gaps" ou oportunidades que parecem estar a ser negligenciadas. Ex: "Parece haver pouco foco na experiência de novos utilizadores (onboarding)", ou "O grande número de bugs no módulo de pagamentos sugere uma oportunidade de refatoração para aumentar a estabilidade".)

    ### 🚀 Recomendações Estratégicas
    (Sugira 2 ações práticas e de alto impacto que a equipa de produto poderia tomar. As sugestões devem ser baseadas diretamente nos gaps que você identificou.)
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            return response.text
        else:
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Aja como um Diretor de Produto experiente."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
    except Exception as e:
        return f"Ocorreu um erro ao gerar a análise de produto: {e}"

def get_ai_strategic_diagnosis(project_name, client_name, issues_data, flow_metrics_summary, project_profile_summary, contextual_projects_summary=None):
    """
    Usa a IA para analisar o ecossistema de um projeto focado num cliente específico,
    retornando um objeto JSON estruturado.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    cleaned_response = "" 

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    tasks_summary_text = "\n".join([f"- {item['Tipo']}: {item['Título']}" for item in issues_data[:20]])
    context_text = "\n".join([f"- {summary}" for summary in contextual_projects_summary]) if contextual_projects_summary else "Nenhum"

    prompt = f"""
    Aja como um Diretor de Contas de uma consultoria de TI. Sua tarefa é analisar a saúde da conta do cliente "{client_name}", associada ao projeto "{project_name}", e gerar um diagnóstico estratégico em formato JSON.

    **DADOS PARA ANÁLISE:**
    1.  **Perfil da Conta (Dados do Cliente):**
        {project_profile_summary}
    2.  **Métricas Operacionais (Performance do Projeto):**
        {flow_metrics_summary}
    3.  **Contexto de Gestão (Tarefas relacionadas de outros projetos):**
        {context_text}
    4.  **Amostra de Tarefas Recentes:**
        {tasks_summary_text}

    **ESTRUTURA DA RESPOSTA (OBRIGATÓRIO):**
    Sua resposta DEVE ser um objeto JSON válido, sem nenhuma outra palavra ou explicação. Siga esta estrutura:
    {{
      "diagnostico_estrategico": "(Escreva aqui um resumo de 2-3 frases conectando os objetivos do cliente com a performance operacional do projeto.)",
      "analise_natureza_trabalho": "(Escreva aqui uma análise sobre o tipo de trabalho que está a ser feito e se está alinhado com a estratégia do cliente.)",
      "plano_de_acao_recomendado": [
        {{
          "acao": "(Escreva aqui a primeira ação recomendada, clara e direta.)",
          "justificativa": "(Justifique a primeira ação com base nos dados analisados.)"
        }},
        {{
          "acao": "(Escreva aqui a segunda ação recomendada.)",
          "justificativa": "(Justifique a segunda ação.)"
        }}
      ]
    }}
    """
    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            cleaned_response = response.choices[0].message.content
        
        if not cleaned_response:
            return {"error": "A IA retornou uma resposta vazia."}

        return json.loads(cleaned_response)
    except Exception as e:
        return {"error": f"Ocorreu um erro ao processar a resposta da IA: {e}. Resposta recebida: '{cleaned_response}'"}

def get_ai_chat_response(initial_diagnosis, chat_history, user_question, issues_context):
    """
    Usa a IA para responder a uma pergunta de seguimento, com acesso à lista de issues
    que originaram a análise.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return "Não consigo responder agora. Verifique a configuração da sua chave de IA."

    # Prepara um resumo das issues para o contexto
    issues_summary = "\n".join([
        f"- Chave: {item['Key']}, Título: {item['Título']}, Status: {item['Status']}, Responsável: {item['Responsável']}"
        for item in issues_context
    ])

    history_for_prompt = "\n".join([f"- {msg['role']}: {msg['content']}" for msg in chat_history])

    prompt = f"""
    Aja como o mesmo Consultor de Produto que escreveu a análise abaixo. A sua tarefa é responder a uma pergunta de seguimento do utilizador.
    Você tem acesso à lista completa de issues que foram usadas para gerar a análise. Use esta lista para encontrar exemplos específicos e dados concretos para justificar as suas respostas.

    **Diagnóstico Inicial (Contexto Principal):**
    {initial_diagnosis}

    **Dados das Issues (Use para pesquisar e encontrar exemplos):**
    {issues_summary}

    **Histórico da Conversa:**
    {history_for_prompt}

    **Nova Pergunta do Utilizador:**
    {user_question}

    Responda à nova pergunta de forma concisa e direta, usando sempre o contexto e os dados das issues fornecidos. Se o utilizador pedir exemplos, cite as chaves das issues (ex: AMS-123).
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            return response.text
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
    except Exception as e:
        return f"Ocorreu um erro ao processar a sua pergunta: {e}"

def get_ai_user_story_from_figma(image_url, user_context, element_name):
    """
    Usa a IA para analisar uma imagem e gerar uma Job Story completa.
    Esta função agora usa a configuração de IA centralizada.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)

    if not model_client:
        return {"error": "Análise indisponível. Verifique a sua chave de API."}

    prompt = f"""
    Aja como um Product Owner e um Analista de QA experientes. A sua tarefa é analisar a imagem de um elemento de interface chamado "{element_name}" e o contexto fornecido para criar uma História de Usuário completa em português, no formato JSON.
    **Contexto Adicional:** {user_context}
    **Regras para a Geração:**
    1.  **Título (title):** Crie um título curto e descritivo.
    2.  **Descrição (description):** Escreva a história no formato "Job Story", usando asteriscos para negrito nos marcadores e quebras de linha, exatamente assim: "*Quando* <situação>\\n*Quero* <motivação>\\n*Então* <resultado>."
    3.  **Critérios de Aceitação (acceptance_criteria):** Crie uma lista de 3 a 5 critérios de aceitação claros, separados por uma nova linha (\\n).
    4.  **Cenários de Teste BDD (bdd_scenarios):** Crie 2 a 3 cenários de teste detalhados no formato BDD, usando asteriscos para negrito e quebras de linha, exatamente assim: "*Cenário:* <nome do cenário>\\n*Dado* <contexto>\\n*Quando* <ação>\\n*Então* <resultado esperado>", com cada cenário separado por duas novas linhas (\\n\\n).
    **Estrutura de Saída (Responda APENAS com o JSON):**
    {{"title": "...", "description": "...", "acceptance_criteria": "...", "bdd_scenarios": "..."}}
    """
    try:
        if provider == "Google Gemini":
            image_response = requests.get(image_url)
            image_parts = [{"mime_type": "image/png", "data": image_response.content}]
            prompt_parts = [prompt, image_parts[0]]
            response = model_client.generate_content(prompt_parts)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_url}}] }],
                response_format={"type": "json_object"}
            )
            cleaned_response = response.choices[0].message.content
        return json.loads(cleaned_response)
    except Exception as e:
        return {"error": f"Ocorreu um erro ao gerar a história de usuário: {e}"}

def get_ai_contract_analysis(pdf_bytes):
    """
    Usa a IA para analisar o texto de um contrato em PDF e extrair os campos-chave
    para uma Ordem de Serviço, retornando um objeto JSON.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    # Extrai o texto do PDF
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        contract_text = ""
        for page in doc:
            contract_text += page.get_text()
        doc.close()
    except Exception as e:
        return {"error": f"Não foi possível ler o ficheiro PDF: {e}"}

    prompt = f"""
    Aja como um Analista de Contratos sênior. A sua tarefa é analisar o texto de uma Ordem de Serviço (OS) ou contrato e extrair as seguintes informações, retornando o resultado num formato JSON.

    **Texto do Contrato para Análise:**
    {contract_text[:8000]} # Limita o tamanho do prompt

    **Regras para a Extração:**
    1.  **setor_demandante:** Identifique a área ou setor que solicitou o serviço.
    2.  **responsavel_demandante:** Identifique o nome do responsável pela solicitação.
    3.  **email_demandante:** Extraia o e-mail do responsável.
    4.  **lider_projeto_gauge:** Identifique o nome do líder de projeto do lado do fornecedor.
    5.  **data_emissao:** Encontre a data de emissão do documento (formato DD/MM/AAAA).
    6.  **previsao_inicio:** Encontre a data de previsão de início (formato DD/MM/AAAA).
    7.  **previsao_conclusao:** Encontre a data de previsão de término (formato DD/MM/AAAA).
    8.  **justificativa_objetivo:** Faça um resumo conciso da justificativa e dos objetivos.
    9.  **escopo_tecnico:** Faça um resumo dos principais pontos do escopo técnico ou dos entregáveis.
    10. **premissas:** Liste as premissas importantes.
    11. **orcamento:** Extraia o valor total do orçamento como um número.
    12. **pagamento:** Resuma o cronograma ou as condições de pagamento.

    **Estrutura de Saída (Responda APENAS com o JSON. Se um campo não for encontrado, retorne uma string vazia ""):**
    {{
        "setor_demandante": "", "responsavel_demandante": "", "email_demandante": "",
        "lider_projeto_gauge": "", "data_emissao": "", "previsao_inicio": "",
        "previsao_conclusao": "", "justificativa_objetivo": "", "escopo_tecnico": "",
        "premissas": "", "orcamento": 0.0, "pagamento": ""
    }}
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            cleaned_response = response.choices[0].message.content

        return json.loads(cleaned_response)
    except Exception as e:
        return {"error": f"Ocorreu um erro ao analisar o contrato: {e}"}

def get_ai_os_from_context_and_contract(user_context, contract_text=None):
    """
    Usa a IA para analisar o contexto do utilizador e, opcionalmente, o texto de um contrato
    para preencher os campos de uma Ordem de Serviço em formato JSON.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    # --- PROMPT DINÂMICO ---
    prompt_base = f"""
    Aja como um Gerente de Projetos sênior. A sua tarefa é criar uma Ordem de Serviço (OS) com base no contexto fornecido pelo utilizador e, se disponível, complementá-la com os detalhes encontrados no documento do contrato em anexo. Retorne o resultado num formato JSON.

    **Contexto da OS (Fonte Principal de Informação):**
    {user_context}
    """

    prompt_contrato = f"""
    **Texto do Contrato (Use para encontrar detalhes objetivos como nomes, datas, valores):**
    {contract_text[:8000]} # Limita o tamanho do prompt
    """ if contract_text else ""

    prompt_final = f"""
    {prompt_base}
    {prompt_contrato}

    **Regras para a Extração e Geração:**
    1.  Use o "Contexto da OS" como a principal fonte de verdade, especialmente para campos subjetivos como 'Justificativa & Objetivo' e 'Escopo Técnico'.
    2.  Use o "Texto do Contrato", se fornecido, para encontrar e extrair os valores para os outros campos.
    3.  Se um campo não for encontrado em nenhuma das fontes, retorne uma string vazia "".

    **Estrutura de Saída (Responda APENAS com o JSON):**
    {{
        "setor_demandante": "", "responsavel_demandante": "", "email_demandante": "",
        "lider_projeto_gauge": "", "data_emissao": "DD/MM/AAAA", "previsao_inicio": "DD/MM/AAAA",
        "previsao_conclusao": "DD/MM/AAAA", "justificativa_objetivo": "", "escopo_tecnico": "",
        "premissas": "", "orcamento": "", "pagamento": ""
    }}
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt_final)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt_final}],
                response_format={"type": "json_object"}
            )
            cleaned_response = response.choices[0].message.content

        return json.loads(cleaned_response)
    except Exception as e:
        return {"error": f"Ocorreu um erro ao analisar o contrato: {e}"}

def get_ai_user_story_from_text(user_context):
    """
    Usa a IA para analisar o contexto do utilizador e gerar uma história de usuário
    estruturada em JSON, no formato Job Story, incluindo cenários BDD.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    prompt = f"""
    Aja como um Product Owner e um Analista de QA experientes. A sua tarefa é analisar o contexto fornecido para criar uma História de Usuário completa em português, no formato JSON.
    **Contexto Fornecido pelo Utilizador:** {user_context}
    **Regras para a Geração:**
    1.  **Título (title):** Crie um título curto e descritivo.
    2.  **Descrição (description):** Escreva a história no formato "Job Story", usando asteriscos para negrito nos marcadores e quebras de linha, exatamente assim: "*Quando* <situação>\\n*Quero* <motivação>\\n*Então* <resultado>."
    3.  **Critérios de Aceitação (acceptance_criteria):** Crie uma lista de 3 a 5 critérios de aceitação claros, separados por uma nova linha (\\n).
    4.  **Cenários de Teste BDD (bdd_scenarios):** Crie 2 a 3 cenários de teste detalhados no formato BDD, usando asteriscos para negrito e quebras de linha, exatamente assim: "*Cenário:* <nome do cenário>\\n*Dado* <contexto>\\n*Quando* <ação>\\n*Então* <resultado esperado>", com cada cenário separado por duas novas linhas (\\n\\n).
    **Estrutura de Saída (Responda APENAS com o JSON):**
    {{"title": "...", "description": "...", "acceptance_criteria": "...", "bdd_scenarios": "..."}}
    """
    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        else:
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            cleaned_response = response.choices[0].message.content
        return json.loads(cleaned_response)
    except Exception as e:
        return {"error": f"Ocorreu um erro ao gerar a história de usuário: {e}"}
def get_ai_os_from_jira_issue(issue_data_dict, layout_fields):
    """
    Usa a IA para analisar um dicionário com todos os dados de uma issue do Jira
    e preencher os campos de uma Ordem de Serviço em formato JSON.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    raw_response_text = ""

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    field_names = [field['field_name'] for field in layout_fields]
    json_structure_example = {field_name: "" for field_name in field_names}
    
    # Sanitiza os dados da issue para remover caracteres problemáticos
    sanitized_issue_dict = {}
    for key, value in issue_data_dict.items():
        if isinstance(value, str):
            sanitized_issue_dict[key] = value.encode('utf-8', 'ignore').decode('utf-8')
        else:
            sanitized_issue_dict[key] = value
    issue_context = "\n".join([f"- {key}: {value}" for key, value in sanitized_issue_dict.items() if value])

    prompt = f"""
    Sua única tarefa é extrair dados de uma tarefa do Jira e preencher um formulário JSON.

    **INFORMAÇÕES DA TAREFA:**
    ```
    {issue_context}
    ```

    **FORMULÁRIO JSON PARA PREENCHER:**
    {json.dumps(json_structure_example, indent=2, ensure_ascii=False)}

    **REGRAS:**
    1. As chaves no seu JSON de resposta devem ser EXATAMENTE IGUAIS às do formulário.
    2. Preencha os valores com o máximo de detalhes possível com base nas informações da tarefa.
    3. Se uma informação não for encontrada, retorne uma string vazia "" para o campo correspondente.
    4. Sua resposta final deve ser APENAS o código JSON, sem nenhum outro texto, explicação ou marcadores de código.
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            raw_response_text = response.text
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            raw_response_text = response.choices[0].message.content
        
        # 1. Remove marcadores de código e espaços em branco
        cleaned_text = raw_response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        
        cleaned_text = cleaned_text.strip()

        # 2. Tenta carregar o JSON
        if not cleaned_text:
             return {"error": "A IA retornou uma resposta vazia."}

        return json.loads(cleaned_text)
        
    except json.JSONDecodeError:
        # Erro se o texto não for um JSON válido
        return {"error": "A IA retornou um formato de dados inválido (não é um JSON válido).", "raw_response": raw_response_text}
    except Exception as e:
        # Captura outras exceções (ex: falha na API)
        return {"error": f"Ocorreu um erro ao processar a resposta da IA: {e}", "raw_response": raw_response_text}

def get_ai_os_from_text(user_text, layout_fields):
    """
    Usa a IA para analisar um texto livre do usuário e preencher os campos
    de uma Ordem de Serviço em formato JSON, atuando como um analista técnico.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    raw_response_text = ""

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    field_names = [
        field['field_name'] for field in layout_fields 
        if field.get('field_type') not in ["Subtítulo", "Valor Calculado", "Imagem"]
    ]
    json_structure_example = {field_name: "" for field_name in field_names}

    # --- PROMPT APRIMORADO COM PERSONA E EXEMPLO TÉCNICO ---
    prompt = f"""
    **PERSONA:** Você é a Gauge AI, uma assistente especialista em engenharia de software e gestão de projetos. Sua tarefa é atuar como um analista de negócios sênior, transformando uma descrição simples de uma necessidade em um texto técnico, detalhado и bem estruturado, adequado para uma Ordem de Serviço (OS). Você deve inferir detalhes técnicos, detalhar o escopo e enriquecer a descrição inicial.

    **EXEMPLO DE TAREFA:**
    * **Texto do Usuário:** "Preciso criar uma nova tela de login para o app mobile. O design já foi aprovado e o prazo de entrega é para a próxima sexta-feira."
    * **Formulário para Preencher:**
        {{
            "Título da Demanda": "",
            "Objetivo": "",
            "Escopo Detalhado": "",
            "Prazo Estimado": ""
        }}
    * **Sua Resposta JSON (Exemplo de alta qualidade):**
        {{
            "Título da Demanda": "Desenvolvimento da Nova Interface de Autenticação para Aplicativo Móvel",
            "Objetivo": "Implementar uma nova interface de usuário (UI) para o processo de login e autenticação no aplicativo móvel, visando melhorar a experiência do usuário (UX), reforçar a segurança com validação de campos em tempo real e garantir a compatibilidade com os sistemas de backend existentes.",
            "Escopo Detalhado": "O escopo compreende o desenvolvimento front-end dos seguintes componentes: campo de e-mail com validação de formato, campo de senha com opção de visualização, botão de 'Entrar' com feedback de estado (loading, erro), link para recuperação de senha e integração com a API de autenticação. Deverá ser assegurada a responsividade para diferentes tamanhos de tela e a implementação de tratamento de erros para cenários como credenciais inválidas ou falhas de conexão.",
            "Prazo Estimado": "Próxima sexta-feira"
        }}
    ---
    **TAREFA REAL:**

    **Texto Fornecido Pelo Usuário:**
    ```
    {user_text}
    ```

    **Formulário JSON para Preencher (Sua Resposta):**
    {json.dumps(json_structure_example, indent=2, ensure_ascii=False)}

    **REGRAS FINAIS:**
    1.  Analise o texto do usuário e preencha o formulário JSON, enriquecendo-o com detalhes técnicos e linguagem profissional.
    2.  As chaves no seu JSON devem ser **EXATAMENTE IGUAIS** às do formulário.
    3.  Seja o mais **DETALHADO** possível. Infira requisitos técnicos comuns quando apropriado.
    4.  Responda **APENAS** com o código JSON final, sem nenhum outro texto ou explicação.
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            raw_response_text = response.text
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            raw_response_text = response.choices[0].message.content
        
        cleaned_text = raw_response_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        
        cleaned_text = cleaned_text.strip()

        if not cleaned_text:
             return {"error": "A IA retornou uma resposta vazia."}

        return json.loads(cleaned_text)
        
    except json.JSONDecodeError:
        return {"error": "A IA retornou um formato de dados inválido (não é um JSON válido).", "raw_response": raw_response_text}
    except Exception as e:
        return {"error": f"Ocorreu um erro ao processar a resposta da IA: {e}", "raw_response": raw_response_text}
    
def load_local_css(file_path):
    """Lê um arquivo CSS e o injeta na aplicação Streamlit."""
    try:
        with open(file_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"Arquivo CSS não encontrado: {file_path}")

def get_ai_team_performance_analysis(team_performance_df):
    """
    Usa a IA para analisar um DataFrame de competências da equipa (incluindo comentários)
    e gerar uma análise de performance detalhada.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return "### 🔮 Análise Indisponível\nPara usar esta funcionalidade, por favor, configure a sua chave de API."

    # Remove colunas com comentários vazios para um prompt mais limpo
    df_clean = team_performance_df.dropna(axis=1, how='all')
    dados_csv = df_clean.to_csv(index=False)
    
    prompt = f"""
    Aja como um Diretor de RH (People & Culture Director) especialista em análise de performance. A sua tarefa é analisar os dados de uma matriz de competências que inclui tanto a avaliação quantitativa (níveis) quanto a qualitativa (comentários), e fornecer uma análise estratégica profunda em Português.

    **Dados da Matriz de Competências (formato CSV):**
    (Níveis de 0 a 5; Comentários do Plano de Desenvolvimento Individual - PDI)
    ```csv
    {dados_csv}
    ```

    **Estrutura da Análise (Obrigatório):**
    A sua resposta DEVE ser formatada em Markdown, ser perspicaz e usar tanto os níveis quanto os comentários para justificar as suas conclusões. Siga estritamente esta estrutura:

    ### 📈 Resumo Executivo
    * Forneça um parágrafo com uma visão geral do perfil da equipa. Conecte os níveis de competência com os temas recorrentes nos comentários. (Ex: "A equipa demonstra alta proficiência técnica em [Competência X], mas os comentários, tanto dos líderes quanto dos próprios membros, apontam para uma necessidade de desenvolver a comunicação com stakeholders.")

    ### ✅ Pontos Fortes e Sinergias
    * Identifique os pontos fortes com base nos níveis altos. **Use os comentários para dar profundidade.** (Ex: "A proficiência em 'Metodologias Ágeis' é evidente, e o comentário do líder para [Membro Y] sobre 'propor melhorias no processo de sprint' confirma esta senioridade.")
    * Aponte sinergias ou discrepâncias positivas entre a autoavaliação e a avaliação do líder.

    ### 🎯 Oportunidades Estratégicas de Desenvolvimento
    * Aponte as competências com níveis mais baixos. **Use os comentários para identificar a causa-raiz.** (Ex: "A baixa avaliação em 'Gestão de Stakeholders' é corroborada por vários PDIs que mencionam 'melhorar a clareza nas apresentações' e 'antecipar as necessidades do cliente'.")
    * Identifique temas comuns nos PDIs que representem uma oportunidade de treino em grupo.

    ### 🤝 Plano de Ação e Mentoria
    * Com base em toda a análise (níveis e comentários), sugira um plano de ação prático.
    * Sugira mentorias internas, justificando a escolha com base nos dados. (Ex: "O(A) **[Nome do Mentor(a)]** é um(a) especialista em **[Competência Z]** e o seu PDI demonstra interesse em liderança. Ele(a) poderia mentorar o(a) **[Nome do Mentorado(a)]**, cujo PDI expressa a necessidade de 'ganhar autonomia' nesta área.")
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            return response.text
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
    except Exception as e:
        st.error(f"Ocorreu um erro ao comunicar com a IA: {e}")
        return "Ocorreu uma falha ao tentar gerar a análise. Por favor, tente novamente."
    
def calculate_kpi_value(op, field, df):
    """
    Calcula um valor de KPI (Soma, Média, Contagem) a partir de um DataFrame.
    Esta função reside em utils.py para evitar importações circulares.
    """
    if op == 'Contagem':
        return len(df)
    
    if not field or field == "Contagem de Issues":
        return len(df)

    if field not in df.columns:
        st.warning(f"O campo '{field}' usado no KPI não foi encontrado nos dados atuais.")
        return 0 

    numeric_series = pd.to_numeric(df[field], errors='coerce').dropna()
    
    if numeric_series.empty:
        return 0

    if op == 'Soma':
        return numeric_series.sum()
    if op == 'Média':
        return numeric_series.mean()
    
    return 0

def save_help_topic(topic_key, content):
    """Guarda o conteúdo de um tópico de ajuda num ficheiro JSON."""
    file_path = Path(__file__).parent / "help_documentation.json"
    docs = {}
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                docs = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass # Se o ficheiro estiver corrompido, será sobrescrito
    
    docs[topic_key] = {
        "content": content,
        "last_updated": datetime.now().isoformat()
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(docs, f, indent=4, ensure_ascii=False)

def load_help_topics():
    """Carrega todos os tópicos de ajuda do ficheiro JSON."""
    file_path = Path(__file__).parent / "help_documentation.json"
    if file_path.exists():
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return {}

def get_ai_page_summary_and_faq(page_name, page_content):
    """
    Usa a IA para analisar o código de uma PÁGINA ESPECÍFICA e gerar
    uma página de "Sobre" e um FAQ técnico para ela.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return "### Análise Indisponível\nPara usar esta funcionalidade, configure a sua chave de API."

    prompt = f"""
    Aja como um Redator Técnico (Technical Writer). A sua tarefa é analisar o código-fonte de uma página específica de uma aplicação Streamlit chamada "{page_name}" e gerar uma documentação clara em Português.

    **Código da Página "{page_name}":**
    ```python
    {page_content}
    ```

    **Estrutura da Resposta (Obrigatório):**
    A sua resposta DEVE ser formatada em Markdown e seguir estritamente esta estrutura:

    ### Sobre a Página: {page_name}
    (Escreva um parágrafo conciso sobre o propósito principal e a funcionalidade desta página específica, com base no código fornecido.)

    ### Como Usar
    (Crie um passo a passo ou uma lista de tópicos explicando como um utilizador deve interagir com as principais funcionalidades da página.)

    ### Perguntas Frequentes (FAQ) da Página
    **(Crie de 3 a 5 perguntas e respostas focadas exclusivamente nesta página. As perguntas devem ser do tipo 'Como eu faço para...' ou 'O que significa...').**

    **P: [Pergunta relevante para a página]**
    *R: [Resposta clara e direta baseada no código da página.]*

    **P: [Outra pergunta relevante]**
    *R: [Outra resposta clara.]*
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            return response.text
        else:
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
    except Exception as e:
        st.error(f"Ocorreu um erro ao comunicar com a IA: {e}")
        return "Ocorreu uma falha ao tentar gerar a análise. Por favor, tente novamente."

def get_ai_sentiment_analysis(project_name, issues_list, max_items=50, max_comments_per_issue=3):
    """
    Usa a IA para analisar o sentimento geral de uma lista de issues (títulos, descrições, e os N últimos comentários).
    Retorna um dicionário com sentimento, emoji, confiança e justificativa.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    model_client = _get_ai_client_and_model(provider, user_data)
    
    if not model_client:
        return {"sentiment": "Erro", "emoji": "⚪", "confidence": "N/A", "justification": "Cliente de IA não configurado."}

    # 1. Extrair contexto dos issues (mais recentes primeiro)
    context_snippets = []
    total_context_len = 0
    # Limite de segurança para o tamanho total do prompt
    MAX_CONTEXT_LEN = 15000 

    for issue in reversed(issues_list):
        if total_context_len >= MAX_CONTEXT_LEN or len(context_snippets) >= max_items:
            break
        
        try:
            snippet = f"--- Issue {issue.key} ({issue.fields.issuetype.name}) ---\n"
            snippet += f"Título: {issue.fields.summary}\n"
            
            # Adiciona descrição (se houver) e limita o tamanho
            if issue.fields.description:
                desc_clean = re.sub(r'\s+', ' ', str(issue.fields.description)).strip()
                snippet += f"Descrição: {desc_clean[:200]}...\n"
            
            # Adiciona os N comentários MAIS RECENTES
            if hasattr(issue.fields, 'comment') and issue.fields.comment.comments:
                
                # Pega os últimos 'max_comments_per_issue' comentários
                comments_to_add = issue.fields.comment.comments[-max_comments_per_issue:]
                
                if comments_to_add:
                    snippet += f"Últimos {len(comments_to_add)} Comentários:\n"
                    for comment in comments_to_add:
                        author = getattr(comment.author, 'displayName', 'Usuário')
                        comment_clean = re.sub(r'\s+', ' ', str(comment.body)).strip()
                        # Limita cada comentário
                        snippet += f"  - [{author}]: {comment_clean[:150]}...\n"
            
            # Verifica se o novo snippet excede o limite total
            if (total_context_len + len(snippet)) <= MAX_CONTEXT_LEN:
                context_snippets.append(snippet)
                total_context_len += len(snippet)
            else:
                # Se adicionar este snippet estoura o limite, paramos
                break
                
        except Exception:
            pass # Pula issues que falham na leitura
    
    if not context_snippets:
        return {"sentiment": "Neutro", "emoji": "😐", "confidence": "Alta", "justification": "Não há itens ou comentários suficientes para análise."}

    # 2. Criar o Prompt Melhorado
    full_context = "\n".join(context_snippets)
    prompt = f"""
    Aja como um Analista de QA e Product Owner Sênior. Analise os seguintes trechos de issues (títulos, descrições e comentários recentes) do projeto "{project_name}".

    **Dados das Issues:**
    {full_context}

    **Sua Tarefa:**
    1.  Determine o sentimento GERAL predominante (Positivo, Negativo ou Neutro).
    2.  Preste atenção especial ao tom dos comentários. Procure por sinais de frustração (ex: 'ainda não funciona', 'lento', 'demorando') ou satisfação (ex: 'obrigado', 'perfeito', 'resolvido').
    3.  Baseie sua análise também no *tipo* de trabalho (ex: muitos 'Bugs' podem indicar um sentimento negativo, mesmo que os comentários sejam neutros).
    4.  Atribua um nível de confiança (Alta, Média, Baixa) à sua análise.
    5.  Forneça uma breve justificativa (uma frase) para sua classificação.
    6.  Forneça um emoji que represente o sentimento (😃, 😠, 😐).

    **Formato de Saída (Obrigatório - Responda APENAS com este objeto JSON):**
    {{
      "sentiment": "Positivo|Negativo|Neutro",
      "emoji": "😃|😠|😐",
      "confidence": "Alta|Média|Baixa",
      "justification": "Sua justificativa de uma frase aqui."
    }}
    """

    # 3. Chamar a IA
    try:
        cleaned_response = ""
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            # Tenta extrair o JSON mesmo que a IA adicione marcadores
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                cleaned_response = match.group(0)
            else:
                # Se não encontrar JSON, é uma resposta de fallback/erro
                cleaned_response = f'{{"sentiment": "Erro", "emoji": "⚪", "confidence": "N/A", "justification": "Resposta inesperada da IA: {response.text}"}}'
        
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            cleaned_response = response.choices[0].message.content
        
        return json.loads(cleaned_response)
    
    except json.JSONDecodeError:
        return {"sentiment": "Erro", "emoji": "⚪", "confidence": "N/A", "justification": f"A IA retornou uma resposta em formato inválido (não-JSON). Resposta: {cleaned_response}"}
    except Exception as e:
        return {"sentiment": "Erro", "emoji": "⚪", "confidence": "N/A", "justification": f"Falha na API de IA: {e}"}