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
from datetime import datetime, timedelta
import openai
from sklearn.linear_model import LinearRegression
import numpy as np
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
import re
from jira_connector import *
from security import *
from metrics_calculator import *
import fitz
import sendgrid 
from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition
import io

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

def render_chart(chart_config, df, return_fig=False):
    """
    Renderiza um único gráfico, aplicando os seus próprios filtros ao dataframe original.
    Esta é a versão final e completa.
    """
    try:
        df_to_render = df.copy() 
        
        # --- LÓGICA DE FILTRAGEM COMPLETA E CORRIGIDA ---
        chart_filters = chart_config.get('filters', [])
        if chart_filters:
            for f in chart_filters:
                field, op, val = f.get('field'), f.get('operator'), f.get('value')
                if field and op and val is not None and field in df_to_render.columns:
                    try:
                        # Filtros Categóricos e Numéricos
                        if op == 'é igual a': df_to_render = df_to_render[df_to_render[field] == val]
                        elif op == 'não é igual a': df_to_render = df_to_render[df_to_render[field] != val]
                        elif op == 'está em': df_to_render = df_to_render[df_to_render[field].isin(val)]
                        elif op == 'não está em': df_to_render = df_to_render[~df_to_render[field].isin(val)]
                        elif op == 'maior que': df_to_render = df_to_render[pd.to_numeric(df_to_render[field], errors='coerce') > val]
                        elif op == 'menor que': df_to_render = df_to_render[pd.to_numeric(df_to_render[field], errors='coerce') < val]
                        elif op == 'entre' and isinstance(val, list) and len(val) == 2:
                             df_to_render = df_to_render[pd.to_numeric(df_to_render[field], errors='coerce').between(val[0], val[1])]
                        
                        # Filtros de Data
                        elif op == "Períodos Relativos":
                            days_map = {
                                "Últimos 7 dias": 7, "Últimos 14 dias": 14, "Últimos 30 dias": 30, 
                                "Últimos 60 dias": 60, "Últimos 90 dias": 90, "Últimos 120 dias": 120, 
                                "Últimos 150 dias": 150, "Últimos 180 dias": 180
                            }
                            end_date = pd.to_datetime(datetime.now().date())
                            start_date = end_date - timedelta(days=days_map.get(val, 0))
                            df_to_render = df_to_render[(pd.to_datetime(df_to_render[field]) >= start_date) & (pd.to_datetime(df_to_render[field]) <= end_date)]
                        elif op == "Período Personalizado" and len(val) == 2:
                            start_date, end_date = pd.to_datetime(val[0]), pd.to_datetime(val[1])
                            df_to_render = df_to_render[(pd.to_datetime(df_to_render[field]) >= start_date) & (pd.to_datetime(df_to_render[field]) <= end_date)]
                    except Exception:
                        pass # Ignora filtros malformados
        
        # --- ETAPA 2: VALIDAÇÃO DE CAMPOS ---
        required_cols = []
        chart_type = chart_config.get('type')
        if chart_type in ['dispersão', 'linha']:
            required_cols.extend([chart_config.get('x'), chart_config.get('y')])
            if chart_config.get('color_by') and chart_config.get('color_by') != 'Nenhum': required_cols.append(chart_config.get('color_by'))
        elif chart_type in ['barra', 'linha_agregada', 'pizza', 'treemap', 'funil']:
            required_cols.append(chart_config.get('dimension'))
            if chart_config.get('measure') != 'Contagem de Issues': required_cols.append(chart_config.get('measure'))
        elif chart_type == 'tabela':
            required_cols.extend(chart_config.get('columns', []))
        elif chart_type == 'pivot_table':
            required_cols.extend([chart_config.get('rows'), chart_config.get('columns'), chart_config.get('values')])
        
        missing_cols = [col for col in required_cols if col and col not in df_to_render.columns]
        if missing_cols:
            if not return_fig:
                st.warning(f"Não foi possível renderizar esta visualização.", icon="⚠️")
                st.error(f"Motivo: O(s) campo(s) **{', '.join(missing_cols)}** não foi/foram encontrado(s) nos dados atuais.")
                st.badge("Habilite o campo que deseja utilizar e **atualize os dados**", color='orange')
            return None

        # --- ETAPA 3: RENDERIZAÇÃO ---
        source_type = chart_config.get('source_type', 'visual')
        fig = None
        template = "plotly_white"

        if chart_type == 'indicator':
            # Gráficos do tipo 'indicator' (st.metric) não são exportáveis como imagem
            if return_fig:
                return None
                
            if source_type == 'jql':
                with st.spinner("A calcular KPI com JQL..."):
                    val_a = get_jql_issue_count(st.session_state.jira_client, chart_config.get('jql_a'))
                    final_value = float(val_a)
                    if chart_config.get('jql_b') and chart_config.get('jql_operation'):
                        val_b = get_jql_issue_count(st.session_state.jira_client, chart_config.get('jql_b'))
                        op = chart_config.get('jql_operation')
                        if op == 'Dividir (A / B)': final_value = (val_a / val_b) * 100 if val_b > 0 else 0
                        elif op == 'Somar (A + B)': final_value = val_a + val_b
                        elif op == 'Subtrair (A - B)': final_value = val_a - val_b
                        elif op == 'Multiplicar (A * B)': final_value = val_a * val_b
                    
                    value_str = f"{int(final_value):,}" if final_value == int(final_value) else f"{final_value:,.2f}"
                    if chart_config.get('jql_operation') == 'Dividir (A / B)': value_str += "%"
                    delta_value = None
                    if chart_config.get('jql_baseline'):
                        baseline_value = get_jql_issue_count(st.session_state.jira_client, chart_config.get('jql_baseline'))
                        delta_value = final_value - baseline_value
                    delta_str = None
                    if delta_value is not None:
                        delta_str = f"{int(delta_value):,}" if delta_value == int(delta_value) else f"{delta_value:,.2f}"
                    st.metric(label=chart_config.get('title', 'JQL KPI'), value=value_str, delta=delta_str, label_visibility="collapsed")
                return
            
            else: # Construtor Visual
                def calculate_value(op, field, data_frame):
                    if not op or not field: return None
                    if field == 'Contagem de Issues': return len(data_frame)
                    if field not in data_frame.columns: return None
                    if op == 'Contagem': return len(data_frame.dropna(subset=[field]))
                    numeric_series = pd.to_numeric(data_frame[field], errors='coerce')
                    if numeric_series.isnull().all(): return None
                    if op == 'Soma': return numeric_series.sum()
                    if op == 'Média': return numeric_series.mean()
                    return None
                
                num_value = calculate_value(chart_config['num_op'], chart_config['num_field'], df_to_render)
                final_value = num_value
                if chart_config.get('use_den'):
                    den_value = calculate_value(chart_config['den_op'], chart_config['den_field'], df_to_render)
                    if den_value is not None and den_value != 0 and num_value is not None:
                        final_value = (num_value / den_value)
                    else: final_value = None
                
                if final_value is None or pd.isna(final_value):
                    st.metric(label=chart_config.get('title', 'KPI'), value="N/A", label_visibility="collapsed")
                    return
                
                style = chart_config.get('style', 'Número Grande')
                if style == 'Número Grande':
                    delta_value, mean_val = None, 0
                    if chart_config.get('show_delta') and chart_config.get('num_field') != 'Contagem de Issues':
                        mean_val = calculate_value('Média', chart_config['num_field'], df_to_render)
                        if mean_val is not None and pd.notna(mean_val) and mean_val > 0: delta_value = final_value - mean_val
                    value_str = f"{int(final_value):,}" if pd.notna(final_value) and final_value == int(final_value) else f"{final_value:,.2f}"
                    delta_str = None
                    if delta_value is not None:
                        delta_str = f"{int(delta_value):,}" if delta_value == int(delta_value) else f"{delta_value:,.2f}"
                    st.metric(label=chart_config.get('title', 'KPI'), value=value_str, delta=delta_str, help=f"Variação vs. média ({mean_val:,.2f})" if delta_value is not None else None, label_visibility="collapsed")
                elif style in ['Medidor (Gauge)', 'Gráfico de Bala (Bullet)']:
                    target_value = 100
                    if chart_config.get('target_type') == 'Valor Fixo': target_value = chart_config.get('gauge_max_static', 100)
                    else:
                        if chart_config.get('target_op') and chart_config.get('target_field'): target_value = calculate_value(chart_config['target_op'], chart_config['target_field'], df_to_render)
                    poor_limit = chart_config.get('gauge_poor_threshold', target_value * 0.5); good_limit = chart_config.get('gauge_good_threshold', target_value * 0.8); fig = go.Figure()
                    if style == 'Medidor (Gauge)':
                        fig.add_trace(go.Indicator(mode = "gauge+number", value = final_value, gauge = {'axis': {'range': [chart_config.get('gauge_min', 0), target_value]}, 'bar': {'color': chart_config.get('gauge_bar_color', '#1f77b4')}, 'steps': [{'range': [0, poor_limit], 'color': 'rgba(255, 0, 0, 0.15)'}, {'range': [poor_limit, good_limit], 'color': 'rgba(255, 255, 0, 0.25)'}, {'range': [good_limit, target_value], 'color': 'rgba(0, 255, 0, 0.25)'}], 'threshold': {'line': {'color': chart_config.get('gauge_target_color', '#d62728'), 'width': 4}, 'thickness': 0.9, 'value': target_value}}))
                        fig.update_layout(height=150, margin=dict(l=20,r=20,t=1,b=1))
                    elif style == 'Gráfico de Bala (Bullet)':
                        fig.add_trace(go.Indicator(mode = "number+gauge", value = final_value, gauge = {'shape': "bullet", 'axis': {'range': [None, target_value]}, 'threshold': {'line': {'color': chart_config.get('gauge_target_color', '#d62728'), 'width': 3}, 'thickness': 0.9, 'value': target_value}, 'steps': [{'range': [0, poor_limit], 'color': "rgba(255, 0, 0, 0.25)"}, {'range': [poor_limit, good_limit], 'color': "rgba(255, 255, 0, 0.35)"}, {'range': [good_limit, target_value], 'color': "rgba(0, 255, 0, 0.35)"}], 'bar': {'color': chart_config.get('gauge_bar_color', '#1f77b4'), 'thickness': 0.5}}))
                        fig.update_layout(height=100, margin=dict(l=1,r=1,t=20,b=20))

        elif chart_type in ['dispersão', 'linha']:
            x_col, y_col, color_col = chart_config['x'], chart_config['y'], chart_config.get('color_by')
            plot_df = df_to_render.dropna(subset=[x_col, y_col]).copy()
            color_param = color_col if color_col and color_col != "Nenhum" and color_col in plot_df.columns else None
            text_param = y_col if chart_config.get('show_data_labels') else None

            if chart_type == 'dispersão':
                fig = px.scatter(plot_df, x=x_col, y=y_col, color=color_param, title=None, hover_name="Issue", template=template, text=text_param)
            else: # linha
                plot_df.sort_values(by=x_col, inplace=True)
                fig = px.line(plot_df, x=x_col, y=y_col, color=color_param, title=None, hover_name="Issue", template=template, markers=True, text=text_param)
            
            if chart_config.get('show_data_labels') and fig:
                fig.update_traces(textposition='top center', texttemplate='%{text:,.2f}')
 
        elif chart_type in ['barra', 'linha_agregada', 'pizza', 'treemap', 'funil']:
            measure, dimension, agg = chart_config['measure'], chart_config['dimension'], chart_config.get('agg')
            
            if measure == 'Contagem de Issues':
                grouped_df = df_to_render.groupby(dimension).size().reset_index(name='Contagem'); y_axis, values_col = 'Contagem', 'Contagem'
            elif agg == 'Contagem Distinta':
                new_column_name = f"Contagem de {measure}"; grouped_df = df_to_render.groupby(dimension)[measure].nunique().reset_index(name=new_column_name); y_axis, values_col = new_column_name, new_column_name
            else:
                agg_func = 'sum' if agg == 'Soma' else 'mean'; df_to_render[measure] = pd.to_numeric(df_to_render[measure], errors='coerce'); grouped_df = df_to_render.groupby(dimension)[measure].agg(agg_func).reset_index(); y_axis, values_col = measure, measure
            
            show_labels = chart_config.get('show_data_labels', False)
            text_param = y_axis if show_labels else None

            if chart_type == 'barra': fig = px.bar(grouped_df, x=dimension, y=y_axis, color=dimension, title=None, template=template, text=text_param)
            elif chart_type == 'linha_agregada': fig = px.line(grouped_df.sort_values(by=dimension), x=dimension, y=y_axis, title=None, template=template, markers=True, text=text_param)
            elif chart_type == 'pizza': fig = px.pie(grouped_df, names=dimension, values=values_col, title=None, template=template)
            elif chart_type == 'treemap': fig = px.treemap(grouped_df, path=[px.Constant("Todos"), dimension], values=values_col, color=y_axis, title=None, color_continuous_scale='Blues', template=template)
            elif chart_type == 'funil': fig = px.funnel(grouped_df, x=y_axis, y=dimension, title=None, template=template, text=text_param)
            
            if show_labels and fig:
                if chart_type in ['barra', 'linha_agregada', 'funil']:
                    is_float = pd.api.types.is_float_dtype(grouped_df[y_axis])
                    text_template = '%{text:,.2f}' if is_float else '%{text:,.0f}'
                    fig.update_traces(texttemplate=text_template, textposition='outside')
                elif chart_type == 'pizza':
                    fig.update_traces(textinfo='percent+label', textposition='inside')
                elif chart_type == 'treemap':
                    fig.update_traces(textinfo='label+value+percent root')
        
        if return_fig:
            return fig
        elif fig is not None:
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        if not return_fig:
            st.error(f"Erro ao gerar a visualização '{chart_config.get('title', 'Desconhecido')}': {e}")
        return None

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

    for field_data in os_data.get('custom_fields_layout', []):
        field_name = field_data.get('field_name')
        field_type = field_data.get('field_type')
        value = os_data.get('custom_fields', {}).get(field_name)

        if value is None or value == '' or (isinstance(value, list) and not value) or (isinstance(value, pd.DataFrame) and value.empty):
            continue

        pdf.set_font('Roboto', 'B', 11)
        pdf.multi_cell(0, 8, clean_text(f"{field_name}:"), border=0, align='L', ln=1)
        pdf.set_font('Roboto', '', 11)

        if field_type == "Tabela":
            if isinstance(value, list) and value:
                df_table = pd.DataFrame(value)
                if not df_table.empty:
                    pdf.ln(2)
                    pdf.set_font('Roboto', 'B', 10)
                    num_cols = len(df_table.columns)
                    col_width = 190 / num_cols if num_cols > 0 else 190
                    for col in df_table.columns:
                        pdf.cell(col_width, 7, clean_text(str(col)), 1, 0, 'C')
                    pdf.ln()
                    
                    pdf.set_font('Roboto', '', 10)
                    for index, row in df_table.iterrows():
                        y_before_row = pdf.get_y(); x_before_row = pdf.get_x(); max_y = y_before_row
                        for i, col in enumerate(df_table.columns):
                            pdf.set_xy(x_before_row + (i * col_width), y_before_row)
                            pdf.multi_cell(col_width, 7, clean_text(str(row[col])), 1, 'L')
                            if pdf.get_y() > max_y: max_y = pdf.get_y()
                        pdf.set_y(max_y)
            else:
                pdf.multi_cell(0, 5, "Nenhum dado na tabela.", 0, 'L')
        
        elif field_type == "Imagem":
            if isinstance(value, list) and value:
                for img_bytes in value:
                    try:
                        temp_img_path = f"temp_image_{uuid.uuid4().hex}.png"
                        with open(temp_img_path, "wb") as f: f.write(img_bytes)
                        pdf.image(temp_img_path, w=100); pdf.ln(2)
                        os.remove(temp_img_path)
                    except Exception as e:
                        pdf.multi_cell(0, 5, f"[Erro ao renderizar imagem: {e}]", 0, 'L')

        elif field_type == "Texto Longo":
            if isinstance(value, dict):
                if value.get("text"):
                    pdf.multi_cell(0, 5, clean_text(value["text"]), 0, 'L')
                if isinstance(value.get("images"), list) and value["images"]:
                    pdf.ln(2)
                    for img_bytes in value["images"]:
                        try:
                            temp_img_path = f"temp_image_{uuid.uuid4().hex}.png"
                            with open(temp_img_path, "wb") as f: f.write(img_bytes)
                            pdf.image(temp_img_path, w=100); pdf.ln(2)
                            os.remove(temp_img_path)
                        except Exception as e:
                            pdf.multi_cell(0, 5, f"[Erro ao renderizar imagem: {e}]", 0, 'L')
            else:
                pdf.multi_cell(0, 5, clean_text(value), 0, 'L')

        else:
            if isinstance(value, list): value_str = ", ".join(map(str, value))
            elif isinstance(value, bool): value_str = "Sim" if value else "Não"
            else: value_str = str(value)
            pdf.multi_cell(0, 5, clean_text(value_str), 0, 'L')
        
        pdf.ln(6)
        
    # --- INÍCIO DA ALTERAÇÃO ---
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
    # --- FIM DA ALTERAÇÃO ---
            
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
                    pdf.ln(10) # Adiciona espaço no topo da nova página

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
    api_key_encrypted = None
    if provider == "Google Gemini":
        api_key_encrypted = user_data.get('encrypted_gemini_key')
        if not api_key_encrypted:
            st.warning("Nenhuma chave de API do Gemini configurada.", icon="🔑")
            st.info("Para usar esta funcionalidade, por favor, adicione a sua chave na página 'Minha Conta'.")
            st.page_link("pages/9_👤_Minha_Conta.py", label="Configurar Chave de IA Agora", icon="🤖")
            return None
        try:
            api_key = decrypt_token(api_key_encrypted)
            genai.configure(api_key=api_key)
            model_name = user_data.get('ai_model_preference', 'gemini-1.5-flash-latest')
            return genai.GenerativeModel(model_name)
        except Exception as e:
            st.error(f"Erro com a API do Gemini: {e}"); return None

    elif provider == "OpenAI (ChatGPT)":
        api_key_encrypted = user_data.get('encrypted_openai_key')
        if not api_key_encrypted:
            st.warning("Nenhuma chave de API da OpenAI configurada.", icon="🔑")
            st.info("Para usar esta funcionalidade, por favor, adicione a sua chave na página 'Minha Conta'.")
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
    Versão final com prompt aprimorado e verificação de segurança.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return None, "A sua chave de API não está configurada ou é inválida."

    # --- PROMPT DE ENGENHARIA MELHORADO ---
    system_prompt = f"""
    Aja como um especialista em Business Intelligence. A sua tarefa é converter um pedido de utilizador em linguagem natural para um objeto JSON que define uma visualização.

    O utilizador tem acesso aos seguintes campos:
    - Campos Categóricos (para dimensões): {', '.join(categorical_cols)}
    - Campos Numéricos (para medidas): {', '.join(numeric_cols)}

    **Regras para a conversão:**
    1.  **Primeiro, identifique a intenção:**
        - Se o pedido for uma pergunta que resulta num **número único** (ex: "qual o total de issues?", "quantos bugs abertos?"), gere um **Indicador (KPI)**.
        - Se o pedido mencionar explicitamente "tabela", gere uma **Tabela**.
        - Para todos os outros casos (ex: "issues por status"), gere um **Gráfico Agregado**.

    2.  **Estruturas JSON:**
        - **KPI:** `{{"creator_type": "Indicador (KPI)", "type": "indicator", "style": "Número Grande", "title": "...", "num_op": "...", "num_field": "..."}}`
        - **Tabela:** `{{"creator_type": "Gráfico Agregado", "type": "tabela", "title": "...", "columns": ["campo1", "campo2"]}}`
        - **Gráfico Agregado:** `{{"creator_type": "Gráfico Agregado", "type": "barra", "dimension": "...", "measure": "...", "agg": "...", "title": "..."}}`

    3.  **Regras de Preenchimento:**
        - **IMPORTANTE:** Se o cálculo for uma contagem, a 'measure' ou 'num_field' DEVE ser a string exata "Contagem de Issues".
        - Se o pedido não especificar uma dimensão para um gráfico, você DEVE retornar uma mensagem de erro.

    Responda APENAS com o objeto JSON.
    """
    full_prompt = f"{system_prompt}\n\nPedido do Utilizador: \"{prompt}\""

    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(full_prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        else: # OpenAI
            response = model_client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": full_prompt}], response_format={"type": "json_object"})
            cleaned_response = response.choices[0].message.content

        if not cleaned_response:
            return None, "A IA não conseguiu gerar uma configuração válida. Tente reformular o seu pedido."

        chart_config = json.loads(cleaned_response)

        # --- VERIFICAÇÃO DE SEGURANÇA ---
        # Se a IA gerou um gráfico agregado sem dimensão, corrige para um KPI.
        if chart_config.get('type') in ['barra', 'pizza', 'linha_agregada'] and not chart_config.get('dimension'):
            st.warning("A IA interpretou o seu pedido como um gráfico, mas não encontrou uma dimensão. A exibir o total como um KPI.")
            chart_config = {
                'creator_type': 'Indicador (KPI)', 'type': 'indicator',
                'style': 'Número Grande', 'title': prompt,
                'num_op': 'Contagem', 'num_field': 'Contagem de Issues'
            }

        chart_config['filters'] = active_filters if active_filters else []
        chart_config['id'] = str(uuid.uuid4())
        chart_config['source_type'] = 'visual'

        return chart_config, None
    except Exception as e:
        return None, f"Ocorreu um erro ao comunicar com a IA: {e}"

def generate_risk_analysis_with_ai(project_name, metrics_summary):
    """
    Usa a API de IA preferida do utilizador para analisar um resumo de métricas
    e gerar uma lista de descrições de riscos potenciais.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

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
            api_key = decrypt_token(user_data['encrypted_gemini_key'])
            genai.configure(api_key=api_key)
            model_name = user_data.get('ai_model_preference', 'gemini-1.5-flash-latest')
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            # Limpa a resposta para garantir que é um JSON válido
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_response)

        elif provider == "OpenAI (ChatGPT)":
            api_key = decrypt_token(user_data['encrypted_openai_key'])
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Responda apenas com um JSON array de strings."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"} # Pede à OpenAI para forçar a saída em JSON
            )
            # A resposta da OpenAI pode vir num formato ligeiramente diferente, ajuste se necessário
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
            api_key = decrypt_token(user_data['encrypted_gemini_key'])
            genai.configure(api_key=api_key)
            model_name = user_data.get('ai_model_preference', 'gemini-1.5-flash-latest')
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            return json.loads(cleaned_response)

        elif provider == "OpenAI (ChatGPT)":
            api_key = decrypt_token(user_data['encrypted_openai_key'])
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
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
    if not model_client: return "Análise indisponível. Verifique a configuração da sua chave de IA."

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
            api_key = decrypt_token(user_data['encrypted_openai_key'])
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
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

def send_email_with_attachment(to_address, subject, body, attachment_bytes, attachment_filename):
    """
    Função central para enviar e-mails com anexo, com base no provedor
    configurado pelo utilizador na sua conta.
    """
    # Busca as configurações da memória da sessão, que foram carregadas no login
    smtp_configs = st.session_state.get('smtp_configs')
    if not smtp_configs or not smtp_configs.get('provider'):
        return False, "Nenhuma configuração de e-mail encontrada na sua conta."

    provider = smtp_configs['provider']

    if provider == 'SendGrid':
        try:
            # Usa a chave de API desencriptada
            api_key = decrypt_token(smtp_configs['api_key_encrypted'])
            sg = sendgrid.SendGridAPIClient(api_key)

            from_email = smtp_configs['from_email']
            message = Mail(from_email=from_email, to_emails=to_address, subject=subject, html_content=body)

            encoded_file = base64.b64encode(attachment_bytes).decode()
            attachedFile = Attachment(
                FileContent(encoded_file),
                FileName(attachment_filename),
                FileType('application/pdf'),
                Disposition('attachment')
            )
            message.attachment = attachedFile

            response = sg.send(message)
            if response.status_code in [200, 202]:
                return True, "E-mail enviado com sucesso via SendGrid!"
            else:
                return False, f"Falha ao enviar e-mail via SendGrid: Status {response.status_code}"
        except Exception as e:
            return False, f"Ocorreu um erro ao enviar e-mail via SendGrid: {e}"

    elif provider == 'Gmail (SMTP)':
        try:
            # Usa a senha de aplicação desencriptada
            app_password = decrypt_token(smtp_configs['app_password_encrypted'])
            from_email = smtp_configs['from_email']

            smtp_server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            smtp_server.login(from_email, app_password)

            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = to_address
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            attachment = MIMEApplication(attachment_bytes, _subtype="pdf")
            attachment.add_header('Content-Disposition', 'attachment', filename=attachment_filename)
            msg.attach(attachment)

            smtp_server.sendmail(from_email, to_address, msg.as_string())
            smtp_server.quit()
            return True, "E-mail enviado com sucesso via Gmail!"
        except Exception as e:
            return False, f"Ocorreu um erro ao enviar e-mail via SMTP: {e}"

    return False, "Provedor de e-mail não configurado ou inválido."

def send_notification_email(to_address, subject, body_html):
    """Envia um e-mail de notificação formatado em HTML."""
    try:
        sender_email = st.secrets["gmail_smtp"]["EMAIL_ADDRESS"]
        sender_password = st.secrets["gmail_smtp"]["EMAIL_PASSWORD"]

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()

        return True, "Notificação enviada com sucesso!"
    except Exception as e:
        # Em produção, você pode querer logar o erro em vez de o exibir
        print(f"Falha ao enviar a notificação: {e}")
        return False, f"Falha ao enviar a notificação: {e}"

def send_email_with_attachment(to_address, subject, body, attachment_bytes=None, attachment_filename=None):
    """Envia um e-mail com um anexo."""
    try:
        sender_email = st.secrets["gmail_smtp"]["EMAIL_ADDRESS"]
        sender_password = st.secrets["gmail_smtp"]["EMAIL_PASSWORD"]

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if attachment_bytes and attachment_filename:
            part = MIMEApplication(attachment_bytes, Name=attachment_filename)
            part['Content-Disposition'] = f'attachment; filename="{attachment_filename}"'
            msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()

        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, f"Falha ao enviar o e-mail: {e}"

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

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    tasks_summary_text = "\n".join([f"- {item['Tipo']}: {item['Título']}" for item in issues_data[:20]])
    context_text = "\n".join([f"- {summary}" for summary in contextual_projects_summary]) if contextual_projects_summary else "Nenhum"

    prompt = f"""
    Aja como um Diretor de Contas de uma consultoria de TI. A sua tarefa é analisar a saúde da conta do cliente "{client_name}", que está associada ao projeto "{project_name}", e gerar um diagnóstico estratégico em formato JSON.

    **Contexto da Conta (Dados inseridos manualmente para este cliente):**
    {project_profile_summary}

    **Performance Operacional (Métricas do projeto principal para este cliente):**
    {flow_metrics_summary}

    **Contexto de Gestão (Tarefas de gestão relacionadas a este cliente, de outros projetos):**
    {context_text}

    **Amostra de Tarefas de Desenvolvimento Recentes:**
    {tasks_summary_text}

    **A sua análise deve cruzar todas estas fontes de dados e seguir estritamente a seguinte estrutura JSON:**

    {{"diagnostico_estrategico": "(Resumo 2-3 frases a conectar os objetivos do negócio com a performance operacional)", "analise_natureza_trabalho": "(Análise da natureza do trabalho e alinhamento com a estratégia)", "plano_de_acao_recomendado": "(Sugestões de 2 ações estratégicas e práticas)"}}
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
        return {"error": f"Ocorreu um erro ao gerar o diagnóstico: {e}"}

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
    Usa a IA para analisar uma imagem e gerar uma Job Story completa com critérios
    de aceitação e cenários de teste BDD.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível."}

    prompt = f"""
    Aja como um Product Owner e um Analista de QA experientes. A sua tarefa é analisar a imagem de um elemento de interface chamado "{element_name}" e o contexto fornecido para criar uma História de Usuário completa em português, no formato JSON.

    **Contexto Adicional:**
    {user_context}

    **Regras para a Geração:**
    1.  **Título (title):** Crie um título curto e descritivo.
    2.  **Descrição (description):** Escreva a história no formato "Job Story": "Quando <situação>, Eu quero <motivação>, Então eu posso <resultado>."
    3.  **Critérios de Aceitação (acceptance_criteria):** Crie uma lista de 3 a 5 critérios de aceitação claros, separados por uma nova linha (\\n).
    4.  **Cenários de Teste BDD (bdd_scenarios):** Crie 2 a 3 cenários de teste detalhados no formato BDD: "Cenário: <nome do cenário>\\nDado <contexto>\\nE <outro contexto>\\nQuando <ação>\\nEntão <resultado esperado>", com cada cenário separado por duas novas linhas (\\n\\n).

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
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ],
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
    estruturada em JSON, no formato Job Story.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    prompt = f"""
    Aja como um Product Owner (PO) sênior, especialista em criar Job Stories claras e eficazes. A sua tarefa é analisar o contexto fornecido para criar uma História de Usuário completa, em português, no formato JSON.

    **Contexto Fornecido pelo Utilizador:**
    {user_context}

    **Regras para a Geração:**
    1.  **Título (title):** Crie um título curto e descritivo para a história, focado na ação principal do utilizador.
    2.  **Descrição (description):** Escreva a história estritamente no formato "Job Story": "Quando <situação específica>, Eu quero <motivação particular>, Então eu posso <resultado desejado>."
    3.  **Critérios de Aceitação (acceptance_criteria):** Crie uma lista de 3 a 5 critérios de aceitação claros e testáveis, no formato "Dado <contexto>, Quando <ação>, Então <resultado>.", separados por uma nova linha (\\n).

    **Estrutura de Saída (Responda APENAS com o JSON):**
    {{"title": "...", "description": "...", "acceptance_criteria": "..."}}
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

    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return {"error": "Análise indisponível. Verifique a configuração da sua chave de IA."}

    # Prepara a lista de campos da OS para o prompt
    field_names = [field['field_name'] for field in layout_fields]
    json_structure_example = {field_name: "" for field_name in field_names}

    # Converte o dicionário de dados da issue para uma string formatada
    issue_context = "\n".join([f"- {key}: {value}" for key, value in issue_data_dict.items() if value])

    prompt = f"""
    Aja como um Gerente de Projetos sênior. A sua tarefa é criar uma Ordem de Serviço (OS) com base nos dados completos de uma tarefa do Jira. Retorne o resultado num formato JSON.

    **Dados Completos da Tarefa do Jira:**
    {issue_context}

    **Regras para a Extração e Geração:**
    1.  Analise TODOS os dados da tarefa para preencher os campos do JSON da forma mais precisa possível. Use campos como 'Responsável', 'Relator', 'Labels' e campos personalizados para inferir informações.
    2.  Para campos como "Justificativa & Objetivo" ou "Escopo Técnico", resuma a informação relevante do campo 'Descrição' e do 'Resumo' da tarefa.
    3.  Se a informação para um campo específico não for encontrada em nenhum dos dados da tarefa, retorne uma string vazia "".

    **Estrutura de Saída (Responda APENAS com o JSON. Siga esta estrutura):**
    {json.dumps(json_structure_example, indent=2)}
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
        return {"error": f"Ocorreu um erro ao analisar a issue do Jira: {e}"}