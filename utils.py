# utils.py

import streamlit as st
import json, os, pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
import pandas as pd
import uuid
import base64
import google.generativeai as genai
from security import find_user, decrypt_token
from datetime import datetime, date, timedelta 
import openai
from sklearn.linear_model import LinearRegression
import numpy as np
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
import re
from security import *
import fitz
import sendgrid
import io
import base64
import requests

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
    """
    Percorre uma lista de filtros e converte quaisquer objetos de data
    para strings no formato ISO (YYYY-MM-DD) para serem compatíveis com o MongoDB.
    """
    if not filters:
        return []

    sanitized_filters = []
    for f in filters:
        new_filter = f.copy()
        # Verifica se 'values' é uma tupla/lista (típico de filtros de data)
        if 'values' in new_filter and isinstance(new_filter['values'], (list, tuple)):
            try:
                # Converte cada item se for um objeto de data
                new_filter['values'] = [
                    v.isoformat() if hasattr(v, 'isoformat') else v
                    for v in new_filter['values']
                ]
            except Exception:
                # Se a conversão falhar, mantém os valores originais
                pass
        sanitized_filters.append(new_filter)
    return sanitized_filters

def parse_dates_in_filters(filters):
    """
    Percorre uma lista de filtros e converte strings de data ISO de volta para objetos de data.
    VERSÃO CORRIGIDA: Usa datetime.strptime para ser mais explícito.
    """
    processed_filters = []
    for f in filters:
        new_filter = f.copy()
        op = new_filter.get('operator')
        value = new_filter.get('value')
        
        if op == 'Período Personalizado' and isinstance(value, list) and len(value) == 2:
            try:
                # --- INÍCIO DA CORREÇÃO ---
                # Usa um método mais explícito que remove a ambiguidade para o Pylance
                start_date = datetime.strptime(value[0], '%Y-%m-%d').date()
                end_date = datetime.strptime(value[1], '%Y-%m-%d').date()
                new_filter['value'] = (start_date, end_date)
                # --- FIM DA CORREÇÃO ---
            except (TypeError, ValueError):
                pass
        processed_filters.append(new_filter)
    return processed_filters

def render_chart(chart, df):
    """
    Renderiza uma visualização (gráfico, KPI, tabela) com base na sua configuração
    e num DataFrame de dados.
    """
    if not isinstance(chart, dict) or not chart.get('type'):
        st.warning("Configuração de visualização inválida.")
        return

    df_filtered = df.copy()
    
    if chart.get('measure_selection') == 'Tempo em Status' and 'measure' in chart:
        measure_col_name = chart['measure']
        if measure_col_name not in df_filtered.columns:
            selected_statuses = chart.get('selected_statuses', [])
            agg_method = chart.get('agg')
            if selected_statuses and agg_method:
                cols_to_process = [f'Tempo em: {s}' for s in selected_statuses]
                missing_cols = [col for col in cols_to_process if col not in df_filtered.columns]
                if missing_cols:
                    st.warning(f"Não foi possível renderizar: A(s) coluna(s) base '{', '.join(missing_cols)}' não foi/foram encontrada(s) nos dados.")
                    return
                if agg_method == "Soma":
                    df_filtered[measure_col_name] = df_filtered[cols_to_process].sum(axis=1)
                elif agg_method == "Média":
                    df_filtered[measure_col_name] = df_filtered[cols_to_process].mean(axis=1)

    if 'filters' in chart and chart['filters']:
        filters = parse_dates_in_filters(chart['filters'])
        for f in filters:
            field, op, val = f.get('field'), f.get('operator'), f.get('value')
            if field and op and val is not None and field in df_filtered.columns:
                try:
                    if op == 'é igual a': df_filtered = df_filtered[df_filtered[field] == val]
                    elif op == 'não é igual a': df_filtered = df_filtered[df_filtered[field] != val]
                    elif op == 'está em': df_filtered = df_filtered[df_filtered[field].isin(val)]
                    elif op == 'não está em': df_filtered = df_filtered[~df_filtered[field].isin(val)]
                    elif op == 'maior que': df_filtered = df_filtered[pd.to_numeric(df_filtered[field], errors='coerce') > val]
                    elif op == 'menor que': df_filtered = df_filtered[pd.to_numeric(df_filtered[field], errors='coerce') < val]
                    elif op == 'entre' and len(val) == 2:
                        df_filtered = df_filtered[pd.to_numeric(df_filtered[field], errors='coerce').between(val[0], val[1])]
                except Exception: pass
    
    try:
        chart_type = chart.get('type')
        selected_theme_name = chart.get('color_theme', list(COLOR_THEMES.keys())[0])
        color_sequence = COLOR_THEMES.get(selected_theme_name)
        color_by_param = chart.get('color_by')
        if color_by_param == "Nenhum":
            color_by_param = None

        if df_filtered.empty and chart.get('source_type') != 'jql':
            st.info("Nenhum dado para exibir com os filtros aplicados.")
            return
            
        if chart_type in ['dispersão', 'linha']:
            if 'x' not in chart or 'y' not in chart:
                st.error(f"Configuração de gráfico inválida. Gráficos do tipo '{chart_type}' requerem a definição dos eixos 'x' e 'y'. A IA pode ter gerado uma configuração incompleta.")
                return
            fig = px.scatter(df_filtered, x=chart['x'], y=chart['y'], color=color_by_param, color_discrete_sequence=color_sequence) if chart_type == 'dispersão' else px.line(df_filtered, x=chart['x'], y=chart['y'], color=color_by_param, color_discrete_sequence=color_sequence)
            st.plotly_chart(fig, use_container_width=True)
        
        elif chart_type in ['barra', 'linha_agregada', 'pizza', 'treemap', 'funil']:
            if 'dimension' not in chart or 'measure' not in chart:
                st.error(f"Configuração de gráfico inválida. Gráficos agregados requerem 'dimension' e 'measure'. A IA pode ter gerado uma configuração incompleta.")
                return

            dimension, measure, agg = chart['dimension'], chart['measure'], chart.get('agg', 'Contagem')
            
            if measure == 'Contagem de Issues':
                agg_df = df_filtered.groupby(dimension).size().reset_index(name=measure)
            elif measure not in df_filtered.columns:
                st.warning(f"O campo '{measure}' não foi encontrado nos dados.")
                return
            elif agg == 'Contagem Distinta':
                 agg_df = df_filtered.groupby(dimension)[measure].nunique().reset_index(name=measure)
            else:
                numeric_series = pd.to_numeric(df_filtered[measure], errors='coerce')
                grouped = numeric_series.groupby(df_filtered[dimension])
                if agg == 'Soma': agg_df = grouped.sum().reset_index(name=measure)
                else: agg_df = grouped.mean().reset_index(name=measure)
            
            agg_df = agg_df.sort_values(by=measure, ascending=False)
            
            fig = None
            text_param = measure if chart.get('show_data_labels') else None
            if chart_type == 'barra':
                fig = px.bar(agg_df, x=dimension, y=measure, text=text_param, color=dimension, color_discrete_sequence=color_sequence)
            elif chart_type == 'linha_agregada':
                fig = px.line(agg_df, x=dimension, y=measure, text=text_param, color_discrete_sequence=color_sequence)
            elif chart_type == 'pizza':
                fig = px.pie(agg_df, names=dimension, values=measure, color_discrete_sequence=color_sequence)
            elif chart_type == 'treemap':
                fig = px.treemap(agg_df, path=[dimension], values=measure, color_discrete_sequence=color_sequence)
            elif chart_type == 'funil':
                fig = px.funnel(agg_df, x=measure, y=dimension, color_discrete_sequence=color_sequence)

            if fig:
                if chart.get('show_data_labels') and chart_type in ['barra', 'linha_agregada']:
                    # --- INÍCIO DA CORREÇÃO ---
                    # O valor 'outside' não é universalmente válido. 'top center' é uma alternativa mais segura.
                    fig.update_traces(texttemplate='%{text:.2s}', textposition='top center')
                    # --- FIM DA CORREÇÃO ---
                    if not agg_df.empty:
                        max_val = agg_df[measure].max()
                        if max_val > 0: fig.update_layout(yaxis_range=[0, max_val * 1.15])
                st.plotly_chart(fig, use_container_width=True)

        elif chart_type == 'indicator':
            from jira_connector import get_jql_issue_count
            from metrics_calculator import calculate_kpi_value

            if chart.get('source_type') == 'jql':
                jql_a = chart.get('jql_a')
                if not jql_a:
                    st.warning("A Consulta JQL 1 (Valor A) é obrigatória."); return
                value_a = get_jql_issue_count(st.session_state.jira_client, jql_a)
                if not isinstance(value_a, (int, float)):
                    st.error(f"Erro na JQL 1: {value_a}"); return
                
                final_value, is_percentage = float(value_a), False
                jql_b = chart.get('jql_b')
                if jql_b:
                    value_b = get_jql_issue_count(st.session_state.jira_client, jql_b)
                    if not isinstance(value_b, (int, float)):
                        st.error(f"Erro na JQL 2: {value_b}"); return
                    operation = chart.get('jql_operation')
                    if operation == 'Dividir (A / B)':
                        final_value, is_percentage = (value_a / value_b * 100) if value_b != 0 else 0, True
                    elif operation == 'Somar (A + B)': final_value = value_a + value_b
                    elif operation == 'Subtrair (A - B)': final_value = value_a - value_b
                    elif operation == 'Multiplicar (A * B)': final_value = value_a * value_b
                
                delta_value = None
                jql_c = chart.get('jql_baseline')
                if jql_c:
                    value_c = get_jql_issue_count(st.session_state.jira_client, jql_c)
                    if isinstance(value_c, (int, float)) and value_c > 0:
                        delta_value = f"{(final_value - value_c) / value_c * 100:.1f}%"
                    elif isinstance(value_c, (int, float)) and value_c == 0 and final_value > 0:
                         delta_value = "∞%"
                
                display_value = f"{final_value:.1f}%" if is_percentage else f"{final_value:,.0f}"
                st.metric(label=chart.get('title', 'Indicador JQL'), value=display_value, delta=delta_value)
            else:
                num_val = calculate_kpi_value(df_filtered, chart['num_op'], chart['num_field'])
                den_val = calculate_kpi_value(df_filtered, chart['den_op'], chart['den_field']) if chart.get('use_den') else None
                final_value = (num_val / den_val * 100) if den_val is not None and den_val != 0 else num_val
                st.metric(label=chart.get('title', 'Indicador'), value=f"{final_value:.1f}%" if den_val is not None else f"{final_value:,.0f}")
        
        elif chart_type == 'pivot_table':
            from metrics_calculator import calculate_pivot_table
            pivot_df = calculate_pivot_table(df_filtered, chart['rows'], chart['columns'], chart['values'], chart['aggfunc'])
            st.dataframe(pivot_df)

    except Exception as e:
        st.error(f"Ocorreu um erro ao renderizar a visualização: {e}")

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
    """
    Percorre uma lista de filtros e converte quaisquer objetos de data/datetime
    em strings ISO para que possam ser salvos em JSON.
    """
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

def combined_dimension_ui(df, categorical_cols, date_cols, key_suffix=""):
    st.markdown("###### **Criar Dimensão Combinada**")
    new_dim_name = st.text_input("Nome da nova dimensão", key=f"new_dim_name_{key_suffix}")
    cols = st.columns(2)
    dim1 = cols[0].selectbox("Selecione a primeira dimensão", options=categorical_cols + date_cols, key=f"dim1_{key_suffix}")
    dim2 = cols[1].selectbox("Selecione a segunda dimensão", options=categorical_cols + date_cols, key=f"dim2_{key_suffix}")
    if new_dim_name and dim1 and dim2:
        df[new_dim_name] = df[dim1].astype(str) + " - " + df[dim2].astype(str)
        return new_dim_name, df
    return None, df

# ===== CLASSE DE PDF E FUNÇÕES DE GERAÇÃO DE DOCUMENTOS =====
class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.os_title = ""

    def header(self):
        try:
            self.image('images/gauge-logo.svg', 10, 8, 33)
        except Exception as e:
            print(f"Não foi possível carregar o logo: {e}")

        self.set_y(13)
        self.set_x(45)
        self.set_font('Roboto', 'B', 16)
        remaining_width = self.w - 45 - self.r_margin
        self.cell(remaining_width, 10, self.os_title, 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Roboto', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, 'Documento Gerado pelo Gauge Product Hub', 0, 0, 'L')
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'R')

def clean_text(text):
    if text is None: return ""
    return str(text)

def create_os_pdf(os_data):
    pdf = PDF()
    pdf.os_title = f"Ordem de Serviço: {clean_text(os_data.get('layout_name', 'N/A'))}"

    base_dir = Path(__file__).resolve().parent
    font_dir = base_dir / "fonts"
    roboto_regular_path = font_dir / "Roboto-Regular.ttf"
    roboto_bold_path = font_dir / "Roboto-Bold.ttf"
    roboto_italic_path = font_dir / "Roboto-Italic.ttf"

    if not roboto_regular_path.is_file(): raise FileNotFoundError(f"Arquivo de fonte não encontrado: {roboto_regular_path}")
    if not roboto_bold_path.is_file(): raise FileNotFoundError(f"Arquivo de fonte não encontrado: {roboto_bold_path}")
    if not roboto_italic_path.is_file(): raise FileNotFoundError(f"Arquivo de fonte não encontrado: {roboto_italic_path}")

    pdf.add_font('Roboto', '', str(roboto_regular_path))
    pdf.add_font('Roboto', 'B', str(roboto_bold_path))
    pdf.add_font('Roboto', 'I', str(roboto_italic_path))
    pdf.add_page()
    pdf.set_font('Roboto', 'B', 12)
    pdf.cell(0, 10, 'Detalhes da Ordem de Serviço', 0, 1, 'L')
    pdf.ln(2)

    def render_pdf_field(field_data, value, width):
        field_type = field_data.get('field_type')
        pdf.set_font('Roboto', '', 11)
        effective_width = width if width > 0 else pdf.w - pdf.l_margin - pdf.r_margin

        if value is None or value == '' or (isinstance(value, list) and not value) or (isinstance(value, pd.DataFrame) and value.empty):
            pdf.multi_cell(effective_width, 5, "N/A", 0, 'L')
            return

        if field_type == "Texto Longo":
            if isinstance(value, dict) and value.get("text"):
                 pdf.multi_cell(effective_width, 5, clean_text(value["text"]), 0, 'L')
            else:
                 pdf.multi_cell(effective_width, 5, clean_text(value), 0, 'L')
        else:
            if isinstance(value, list): value_str = ", ".join(map(str, value))
            elif isinstance(value, bool): value_str = "Sim" if value else "Não"
            else: value_str = str(value)
            pdf.multi_cell(effective_width, 5, clean_text(value_str), 0, 'L')

    layout_fields = os_data.get('custom_fields_layout', [])
    custom_data = os_data.get('custom_fields', {})
    
    i = 0
    while i < len(layout_fields):
        field1 = layout_fields[i]
        is_two_col = field1.get('two_columns', False)
        next_field_is_two_col = (i + 1 < len(layout_fields)) and layout_fields[i+1].get('two_columns', False)

        if is_two_col and next_field_is_two_col:
            field2 = layout_fields[i+1]
            y_before = pdf.get_y()
            
            pdf.set_xy(pdf.l_margin, y_before)
            pdf.set_font('Roboto', 'B', 11)
            pdf.multi_cell(95, 8, clean_text(f"{field1['field_name']}:"), 0, 'L')
            render_pdf_field(field1, custom_data.get(field1['field_name']), width=95)
            y_after1 = pdf.get_y()

            pdf.set_xy(pdf.l_margin + 100, y_before)
            pdf.set_font('Roboto', 'B', 11)
            pdf.multi_cell(90, 8, clean_text(f"{field2['field_name']}:"), 0, 'L')
            render_pdf_field(field2, custom_data.get(field2['field_name']), width=90)
            y_after2 = pdf.get_y()

            pdf.set_y(max(y_after1, y_after2) + 6)
            i += 2
        else:
            pdf.set_x(pdf.l_margin)
            pdf.set_font('Roboto', 'B', 11)
            pdf.multi_cell(0, 8, clean_text(f"{field1['field_name']}:"), 0, 'L')
            render_pdf_field(field1, custom_data.get(field1['field_name']), width=0)
            pdf.ln(6)
            i += 1

    if os_data.get('items'):
        # Verifica se há espaço para o título, cabeçalho e pelo menos uma linha
        if pdf.get_y() > pdf.page_break_trigger - 30:
            pdf.add_page()

        pdf.ln(5)
        pdf.set_font('Roboto', 'B', 12)
        pdf.cell(0, 10, 'Itens do Catálogo Inclusos', 0, 1, 'L')

        def draw_catalog_header():
            pdf.set_font('Roboto', 'B', 10)
            pdf.cell(160, 8, 'Item', 1, 0, 'C')
            pdf.cell(30, 8, 'Valor', 1, 1, 'C')
            pdf.set_font('Roboto', '', 10)

        draw_catalog_header()

        for item in os_data['items']:
            # Estima a altura necessária para o texto do item
            item_text = clean_text(item.get('Item', ''))
            lines = pdf.multi_cell(160, 8, item_text, split_only=True)
            required_height = len(lines) * 8

            # Se a altura necessária ultrapassar o limite da página, adiciona uma nova página e o cabeçalho
            if pdf.get_y() + required_height > pdf.page_break_trigger:
                pdf.add_page()
                draw_catalog_header()

            # Desenha a linha da tabela
            y_before = pdf.get_y()
            pdf.multi_cell(160, 8, item_text, border=1, align='L')
            y_after_item = pdf.get_y()
            pdf.set_xy(170, y_before)
            pdf.multi_cell(30, 8, clean_text(str(item.get('Valor', ''))), border=1, align='C', ln=1)
            y_after_valor = pdf.get_y()
            pdf.set_y(max(y_after_item, y_after_valor))

    if os_data.get('assinantes'):
        # Verifica se há espaço para o título das assinaturas e pelo menos uma assinatura
        if pdf.get_y() > pdf.page_break_trigger - 50:
             pdf.add_page()

        pdf.ln(10)
        pdf.set_font('Roboto', 'B', 12)
        pdf.cell(0, 10, 'Assinaturas', 0, 1, 'L')
        pdf.ln(15)

        for assinante in os_data['assinantes']:
            if assinante.get('Nome') and assinante.get('Cargo'):
                # Verifica se há espaço para uma assinatura completa
                if pdf.get_y() > pdf.page_break_trigger - 35:
                    pdf.add_page()
                    pdf.ln(10)

                pdf.cell(0, 8, "___________________________________________", 0, 1, 'C')
                pdf.cell(0, 8, clean_text(f"{assinante['Nome']}"), 0, 1, 'C')
                pdf.cell(0, 8, clean_text(f"({assinante['Cargo']})"), 0, 1, 'C')
                pdf.ln(10)

    return bytes(pdf.output())

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

        if pdf.page_no() > 1 or pdf.get_y() > 40:
            pdf.add_page()

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

                    if pdf.get_y() + 80 > 297:
                        pdf.add_page()

                    pdf.image(img_file, w=180)
                    pdf.ln(10)
                else:
                    pdf.set_font('Roboto', '', 10)
                    pdf.set_text_color(255, 0, 0)
                    pdf.multi_cell(0, 5, "Nao foi possivel gerar uma imagem para este tipo de grafico (ex: Indicador).")
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

# --- FUNÇÃO AUXILIAR PARA CÁLCULO DE KPI ---
def calculate_kpi_value(chart_config, df):
    op = chart_config.get('num_op')
    field = chart_config.get('num_field')
    data_frame = df
    if not op or not field: return None
    if field == 'Contagem de Issues':
        return len(data_frame)
    if field not in data_frame.columns: return None
    if op == 'Contagem': return len(data_frame.dropna(subset=[field]))
    numeric_series = pd.to_numeric(data_frame[field], errors='coerce')
    if numeric_series.isnull().all(): return None
    if op == 'Soma': return numeric_series.sum()
    if op == 'Média': return numeric_series.mean()
    return None

# --- NOVA FUNÇÃO "LEITORA DE GRÁFICOS" PARA A IA ---
def summarize_chart_data(chart_config, df):
    """Gera um resumo em texto dos dados de um único gráfico."""
    title = chart_config.get('title', 'um gráfico')
    chart_type = chart_config.get('type')

    try:
        df_to_render = df.copy()
        chart_filters = chart_config.get('filters', [])
        if chart_filters:
            for f in chart_filters:
                field, op, val = f.get('field'), f.get('operator'), f.get('value')
                if field and op and val is not None and field in df_to_render.columns:
                    if op == 'é igual a': df_to_render = df_to_render[df_to_render[field] == val]
                    elif op == 'não é igual a': df_to_render = df_to_render[df_to_render[field] != val]
                    elif op == 'está em': df_to_render = df_to_render[df_to_render[field].isin(val)]
                    elif op == 'não está em': df_to_render = df_to_render[~df_to_render[field].isin(val)]
                    elif op == 'maior que': df_to_render = df_to_render[pd.to_numeric(df_to_render[field], errors='coerce') > val]
                    elif op == 'menor que': df_to_render = df_to_render[pd.to_numeric(df_to_render[field], errors='coerce') < val]
                    elif op == 'entre' and len(val) == 2:
                        df_to_render = df_to_render[pd.to_numeric(df_to_render[field], errors='coerce').between(val[0], val[1])]

        if chart_type == 'indicator':
            if chart_config.get('source_type') == 'jql':
                return f"O indicador '{title}' é calculado com uma consulta JQL personalizada."
            else:
                value = calculate_kpi_value(chart_config, df_to_render)
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
    
    # Verifica se o utilizador tem o perfil de 'admin' antes de mostrar a caixa de depuração.
    # Esta verificação assume que o seu objeto 'user_data' tem um campo 'role'.
    if user_data and user_data.get('role') == 'admin':
        with st.expander("🔍 Dados do Perfil (Depuração)", expanded=False):
            st.info("Esta caixa mostra os dados lidos do seu perfil para configurar a IA. Verifique se a chave correta (Gemini ou OpenAI) está presente aqui.")
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
        else: # OpenAI
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

def combined_dimension_ui(df, categorical_cols, date_cols, key_suffix=""):
    """
    Cria a interface para o utilizador definir uma dimensão combinada e retorna
    o novo nome da dimensão e um dataframe com a nova coluna.
    """
    st.info("Selecione dois campos para criar uma dimensão combinada (ex: 'Data de Conclusão - Status').", icon="🔗")

    c1, c2, c3 = st.columns(3)

    field1_options = [""] + date_cols + categorical_cols
    field2_options = [""] + categorical_cols + date_cols

    field1 = c1.selectbox("Campo 1", options=field1_options, key=f"combo_field1_{key_suffix}")
    separator = c2.text_input("Separador", value=" - ", key=f"combo_sep_{key_suffix}")
    field2 = c3.selectbox("Campo 2", options=field2_options, key=f"combo_field2_{key_suffix}")

    if field1 and field2:
        new_dimension_name = f"{field1}{separator}{field2}"
        df_copy = df.copy()

        field1_str = pd.to_datetime(df_copy[field1]).dt.strftime('%Y-%m-%d') if field1 in date_cols else df_copy[field1].astype(str).fillna('')
        field2_str = pd.to_datetime(df_copy[field2]).dt.strftime('%Y-%m-%d') if field2 in date_cols else df_copy[field2].astype(str).fillna('')

        df_copy[new_dimension_name] = field1_str + separator + field2_str
        return new_dimension_name, df_copy

    return None, df


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
    if hasattr(value, 'displayName'): return value.displayName # Para campos de Utilizador
    if hasattr(value, 'value'): return value.value           # Para campos de Lista de Seleção
    if hasattr(value, 'name'): return value.name             # Para campos de Objeto Simples (Status, Priority)
    if isinstance(value, list):
        return ', '.join([getattr(v, 'name', str(v)) for v in value]) # Para listas

    # Se for um tipo simples (texto, número, data)
    return str(value).split('T')[0]

def send_email_with_attachment(to_address, subject, body, attachment_bytes=None, attachment_filename=None):
    """
    Função central para enviar e-mails, com base no provedor
    configurado pelo utilizador na sua conta. Trata o corpo do e-mail como HTML.
    """
    smtp_configs = st.session_state.get('smtp_configs')

    if not smtp_configs or not smtp_configs.get('provider'):
        print("DEBUG: Nenhuma configuração de SMTP encontrada na sessão.")
        return False, "Falha: Configurações de SMTP não carregadas na sessão."

    provider = smtp_configs.get('provider')

    if provider == 'SendGrid':
        try:
            api_key_encrypted = smtp_configs.get('api_key_encrypted') or smtp_configs.get('api_key')
            if not api_key_encrypted:
                return False, "Chave de API do SendGrid não encontrada."

            api_key = decrypt_token(api_key_encrypted)
            sg = sendgrid.SendGridAPIClient(api_key)
            from_email = smtp_configs['from_email']

            message = Mail(from_email=from_email, to_emails=to_address, subject=subject, html_content=body)

            if attachment_bytes and attachment_filename:
                encoded_file = base64.b64encode(attachment_bytes).decode()
                attachedFile = Attachment(
                    FileContent(encoded_file),
                    FileName(attachment_filename),
                    FileType('application/pdf'),
                    Disposition('attachment')
                )
                message.attachment = attachedFile

            response = sg.send(message)
            print(f"DEBUG: Resposta do SendGrid - Status {response.status_code}")
            return response.status_code in [200, 202], f"Status SendGrid: {response.status_code}"
        except Exception as e:
            print(f"DEBUG: Erro ao enviar com SendGrid - {e}")
            return False, f"Ocorreu um erro ao enviar e-mail via SendGrid: {e}"

    elif provider == 'Gmail (SMTP)':
        try:
            # Lógica completa para o Gmail (adicionando o 'pass' para evitar o erro)
            pass
        except Exception as e:
            print(f"DEBUG: Erro ao enviar com Gmail - {e}")
            return False, f"Ocorreu um erro ao enviar e-mail via Gmail: {e}"

    return False, "Provedor de e-mail não configurado ou inválido."

# --- NOVAS FUNÇÕES DE VALIDAÇÃO ---
def is_valid_url(url):
    """Verifica se uma string corresponde ao formato de um URL."""
    # Expressão regular simples para validar URLs
    regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
        r'localhost|' # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

def is_valid_email(email):
    """Verifica se uma string corresponde ao formato de um e-mail."""
    # Expressão regular para validar e-mails
    regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')
    return re.fullmatch(regex, email)

# --- FUNÇÃO CENTRAL DE CARREGAMENTO DE DADOS ---
def load_and_process_project_data(jira_client, project_key):
    """
    Busca todas as issues de um projeto no Jira, processa os campos dinâmicos
    e retorna um DataFrame pronto para análise.
    """
    # --- IMPORTAÇÕES LOCAIS PARA EVITAR ERRO CIRCULAR ---
    from jira_connector import get_all_project_issues
    from metrics_calculator import (
        filter_ignored_issues,
        find_completion_date,
        calculate_lead_time,
        calculate_cycle_time,
        get_issue_estimation
    )

    with st.spinner(f"A carregar e processar dados do projeto..."):
        all_issues_raw = get_all_project_issues(jira_client, project_key)
        st.session_state['raw_issues_for_fluxo'] = all_issues_raw
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

        fields_to_process = []
        for field_name in user_enabled_standard:
            if field_name in all_available_standard:
                fields_to_process.append({**all_available_standard[field_name], 'name': field_name})
        for field_config in all_available_custom:
            if field_config.get('name') in user_enabled_custom:
                fields_to_process.append(field_config)

        for i in valid_issues:
            completion_date = find_completion_date(i, project_config)
            issue_data = {
                'Issue': i.key,
                'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),
                'Data de Conclusão': completion_date,
                'Lead Time (dias)': calculate_lead_time(i, completion_date),
                'Cycle Time (dias)': calculate_cycle_time(i, completion_date, project_config), # <-- CORREÇÃO AQUI
                'Tempo Gasto (Horas)': (i.fields.timespent or 0) / 3600
            }

            for field in fields_to_process:
                issue_data[field['name']] = get_field_value(i, field)

            if estimation_config.get('id'):
                issue_data[estimation_config['name']] = get_issue_estimation(i, estimation_config)

            data.append(issue_data)

        return pd.DataFrame(data)

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
        else: # OpenAI
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

# utils.py
import streamlit as st
# ... (outros imports existentes)

# ... (Sua função auxiliar _get_ai_client_and_model e as outras funções de IA permanecem aqui) ...

def get_ai_strategic_diagnosis(project_name, client_name, issues_data, flow_metrics_summary, project_profile_summary, contextual_projects_summary=None):
    """
    Usa a IA para analisar o ecossistema de um projeto focado num cliente específico,
    retornando um objeto JSON estruturado.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    cleaned_response = "" # Inicializa para o bloco except

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
        else: # OpenAI
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
    cleaned_response = "" # Inicializa para o bloco except

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    field_names = [field['field_name'] for field in layout_fields]
    json_structure_example = {field_name: "" for field_name in field_names}
    
    # --- INÍCIO DA CORREÇÃO DE CODIFICAÇÃO ---
    # Sanitiza os dados da issue para remover caracteres problemáticos antes de enviar para a IA
    sanitized_issue_dict = {}
    for key, value in issue_data_dict.items():
        if isinstance(value, str):
            # Força a codificação para UTF-8, ignorando erros, e depois decodifica.
            # Isso ajuda a limpar caracteres malformados.
            sanitized_issue_dict[key] = value.encode('utf-8', 'ignore').decode('utf-8')
        else:
            sanitized_issue_dict[key] = value
    issue_context = "\n".join([f"- {key}: {value}" for key, value in sanitized_issue_dict.items() if value])
    # --- FIM DA CORREÇÃO DE CODIFICAÇÃO ---

    # --- PROMPT FINAL, COM EXEMPLO (ONE-SHOT) ---
    prompt = f"""
    Aja como um robô de extração de dados. Sua única tarefa é preencher um formulário JSON usando as informações de uma tarefa.

    **EXEMPLO:**
    *INFORMAÇÕES DA TAREFA:*
    - Resumo: Criar botão de login
    - Descrição: O botão deve ser azul e levar para a página de login.
    - Relator: Maria
    *FORMULÁRIO JSON PARA PREENCHER:*
    {{
        "Título": "",
        "Demandante": "",
        "Escopo": ""
    }}
    *SUA RESPOSTA JSON:*
    {{
        "Título": "Criar botão de login",
        "Demandante": "Maria",
        "Escopo": "O botão deve ser azul e levar para a página de login."
    }}
    ---
    **TAREFA REAL:**

    **INFORMAÇÕES DA TAREFA:**
    ```
    {issue_context}
    ```

    **FORMULÁRIO JSON PARA PREENCHER (Sua Resposta):**
    ```json
    {json.dumps(json_structure_example, indent=2)}
    ```
    **REGRAS FINAIS:**
    1.  As chaves no seu JSON devem ser **EXATAMENTE IGUAIS** às do formulário.
    2.  Seja o mais **DETALHADO** possível ao preencher os valores.
    3.  Responda **APENAS** com o código JSON final.
    """

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(prompt)
            # Extrai o JSON da resposta de forma segura
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            cleaned_response = match.group(0) if match else "{}"
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            cleaned_response = response.choices[0].message.content
        
        if not cleaned_response:
            return {}
            
        return json.loads(cleaned_response)
        
    except Exception as e:
        # Retorna o erro e a resposta parcial da IA para depuração
        return {"error": f"Ocorreu um erro ao processar a resposta da IA: {e}. Resposta recebida: '{cleaned_response}'"}
    
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