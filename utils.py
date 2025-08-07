# utils.py

import streamlit as st
import json, os, pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from jira_connector import get_jql_issue_count
from fpdf import FPDF
import pandas as pd
import uuid
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

def render_chart(chart_config, df):
    """
    Renderiza um único gráfico, aplicando os seus próprios filtros ao dataframe original.
    Esta é a versão final e completa, com a lógica de filtragem corrigida.
    """
    try:
        # --- ETAPA 1: LÓGICA DE FILTRAGEM (ÚNICA E CORRETA) ---
        df_to_render = df.copy() 
        
        chart_filters = chart_config.get('filters', [])
        if chart_filters:
            for f in chart_filters:
                field, op, val = f.get('field'), f.get('operator'), f.get('value')
                if field and op and val is not None and field in df_to_render.columns:
                    try:
                        if op == 'é igual a': df_to_render = df_to_render[df_to_render[field] == val]
                        elif op == 'não é igual a': df_to_render = df_to_render[df_to_render[field] != val]
                        elif op == 'está em': df_to_render = df_to_render[df_to_render[field].isin(val)]
                        elif op == 'não está em': df_to_render = df_to_render[~df_to_render[field].isin(val)]
                        elif op == 'maior que': df_to_render = df_to_render[pd.to_numeric(df_to_render[field], errors='coerce') > val]
                        elif op == 'menor que': df_to_render = df_to_render[pd.to_numeric(df_to_render[field], errors='coerce') < val]
                        elif op == 'entre' and isinstance(val, list) and len(val) == 2:
                             df_to_render = df_to_render[pd.to_numeric(df_to_render[field], errors='coerce').between(val[0], val[1])]
                    except Exception:
                        # Ignora silenciosamente um filtro malformado
                        pass
        
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
            st.warning(f"Não foi possível renderizar esta visualização.", icon="⚠️")
            st.error(f"Motivo: O(s) campo(s) **{', '.join(missing_cols)}** não foi/foram encontrado(s) nos dados atuais.")
            return

        # --- ETAPA 3: RENDERIZAÇÃO ---
        source_type = chart_config.get('source_type', 'visual')
        fig = None
        template = "plotly_white"

        if chart_type == 'indicator':
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
                    st.metric(label="", value=value_str, delta=delta_str)
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
                    st.metric(label="", value="N/A")
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
                    st.metric(label="", value=value_str, delta=delta_str, help=f"Variação vs. média ({mean_val:,.2f})" if delta_value is not None else None)
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
            elif chart_type == 'funil': fig = px.funnel(grouped_df, x=y_axis, y=dimension, title=None, template=template)
            
            # --- LÓGICA DE RÓTULOS ESPECÍFICA E CORRIGIDA ---
            if show_labels and fig:
                if chart_type in ['barra', 'funil']:
                    is_float = pd.api.types.is_float_dtype(grouped_df[y_axis])
                    text_template = '%{text:,.2f}' if is_float else '%{text:,.0f}'
                    fig.update_traces(texttemplate=text_template, textposition='outside')
                elif chart_type == 'linha_agregada':
                    is_float = pd.api.types.is_float_dtype(grouped_df[y_axis])
                    text_template = '%{text:,.2f}' if is_float else '%{text:,.0f}'
                    fig.update_traces(texttemplate=text_template, textposition='top center') # Usa 'top center'
                elif chart_type == 'pizza':
                    fig.update_traces(textinfo='percent+label', textposition='inside')
                elif chart_type == 'treemap':
                    fig.update_traces(textinfo='label+value+percent root')
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"Erro ao gerar a visualização '{chart_config.get('title', 'Desconhecido')}': {e}")

class PDF(FPDF):
    def header(self):
        try:
            self.set_font('Roboto', 'B', 12)
        except RuntimeError:
            self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'ORDEM DE SERVIÇO', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        try:
            self.set_font('Roboto', 'I', 8)
        except RuntimeError:
            self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def create_os_pdf(os_data):
    """Gera um PDF para uma Ordem de Serviço, com o formato de output corrigido."""
    pdf = PDF()
    
    # Adiciona as fontes
    try:
        font_path = Path(__file__).parent / "fonts"
        pdf.add_font('Roboto', '', str(font_path / 'Roboto-Regular.ttf'))
        pdf.add_font('Roboto', 'B', str(font_path / 'Roboto-Bold.ttf'))
        pdf.add_font('Roboto', 'I', str(font_path / 'Roboto-Italic.ttf'))
        DEFAULT_FONT = "Roboto"
    except Exception:
        DEFAULT_FONT = "Arial"

    pdf.add_page()
    pdf.set_font(DEFAULT_FONT, 'B', 11)

    # --- Tabela de Cabeçalho ---
    pdf.cell(95, 10, 'Fornecedor', 1, 0, 'L')
    pdf.cell(95, 10, 'Número do Contrato', 1, 1, 'L')
    pdf.set_font(DEFAULT_FONT, '', 10)
    pdf.cell(95, 10, os_data.get('fornecedor', ''), 1, 0, 'L')
    pdf.cell(95, 10, os_data.get('numero_contrato', ''), 1, 1, 'L')
    # ... (resto da tabela de cabeçalho)
    
    pdf.ln(10)

    # --- Corpo do Documento ---
    pdf.set_font(DEFAULT_FONT, 'B', 12)
    pdf.cell(0, 10, '1. Justificativa', 0, 1, 'L')
    pdf.set_font(DEFAULT_FONT, '', 10)
    pdf.multi_cell(0, 5, os_data.get('justificativa', ''))
    
    # ... (código para Entregáveis, Premissas e Cláusulas)

    # --- CORREÇÃO AQUI ---
    # Converte o output para o tipo 'bytes', que é o formato esperado pelo Streamlit
    return bytes(pdf.output())

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

# --- FUNÇÃO DE IA ATUALIZADA ---
def _get_ai_client_and_model(provider, user_data):
    """Função auxiliar para configurar e retornar o cliente de IA correto."""
    api_key_encrypted = None
    if provider == "Google Gemini":
        api_key_encrypted = user_data.get('encrypted_gemini_key')
        if not api_key_encrypted:
            st.warning("Nenhuma chave de API do Gemini configurada.", icon="🔑")
            st.info("Para usar esta funcionalidade, por favor, adicione a sua chave na página 'Minha Conta'.")
            st.page_link("pages/7_👤_Minha_Conta.py", label="Configurar Chave de IA Agora", icon="🤖")
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
            st.page_link("pages/7_👤_Minha_Conta.py", label="Configurar Chave de IA Agora", icon="🤖")
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
    except Exception as e:
        st.error(f"Erro ao gerar insights: {e}"); return None

def generate_chart_config_from_text(prompt, numeric_cols, categorical_cols):
    """
    Usa a API de IA preferida do utilizador para gerar uma configuração de gráfico.
    Agora, com tratamento robusto para respostas vazias da IA.
    """
    user_data = find_user(st.session_state['email'])
    provider = user_data.get('ai_provider_preference', 'Google Gemini')
    
    # 1. Obtém o cliente de IA de forma segura
    model_client = _get_ai_client_and_model(provider, user_data)
    if not model_client:
        return None, "A sua chave de API não está configurada ou é inválida. Por favor, verifique-a na página 'Minha Conta'."

    # 2. Constrói o prompt de engenharia (sem alterações)
    system_prompt = f"""
    Aja como um especialista em Business Intelligence. A sua tarefa é converter um pedido de utilizador em linguagem natural para um objeto JSON que define uma visualização.
    O utilizador tem acesso aos seguintes campos:
    - Campos Categóricos: {', '.join(categorical_cols)}
    - Campos Numéricos: {', '.join(numeric_cols)}
    O JSON de saída deve ter a estrutura: {{"type": "...", "dimension": "...", "measure": "...", "agg": "...", "title": "..."}}
    Responda APENAS com o objeto JSON.
    """
    full_prompt = f"{system_prompt}\n\nPedido do Utilizador: \"{prompt}\""

    # 3. Chama a API e processa a resposta de forma segura
    try:
        if provider == "Google Gemini":
            response = model_client.generate_content(full_prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Responda apenas com um objeto JSON válido."},
                    {"role": "user", "content": full_prompt}
                ],
                response_format={"type": "json_object"}
            )
            cleaned_response = response.choices[0].message.content
        
        # --- CORREÇÃO AQUI: Verifica se a resposta está vazia ANTES de tentar processar ---
        if not cleaned_response:
            return None, "A IA não conseguiu gerar uma configuração válida. Tente reformular o seu pedido com mais detalhes (ex: 'gráfico de barras da contagem de issues por status')."

        chart_config = json.loads(cleaned_response)
        chart_config['id'] = str(uuid.uuid4())
        chart_config['source_type'] = 'visual'
        if chart_config.get('dimension'):
            chart_config['creator_type'] = 'Gráfico Agregado'
        else:
            chart_config['creator_type'] = 'Indicador (KPI)'
            
        return chart_config, None
    except json.JSONDecodeError:
        return None, "A IA retornou uma resposta em formato inválido. Tente ser mais específico no seu pedido."
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
            api_key = decrypt_token(user_data['encrypted_gemini_key'])
            genai.configure(api_key=api_key)
            model_name = user_data.get('ai_model_preference', 'gemini-1.5-flash-latest')
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
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

def send_email_with_attachment(to_address, subject, body, attachment_bytes=None, attachment_filename=None):
    """
    Envia um e-mail usando as credenciais SMTP do Gmail guardadas nos segredos.
    Opcionalmente, anexa um ficheiro.
    """
    try:
        # Pega as credenciais dos segredos
        sender_email = st.secrets["gmail_smtp"]["EMAIL_ADDRESS"]
        sender_password = st.secrets["gmail_smtp"]["EMAIL_PASSWORD"]

        # Cria a mensagem
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Anexa o ficheiro, se existir
        if attachment_bytes and attachment_filename:
            part = MIMEApplication(attachment_bytes, Name=attachment_filename)
            part['Content-Disposition'] = f'attachment; filename="{attachment_filename}"'
            msg.attach(part)
        
        # Conecta-se ao servidor e envia o e-mail
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        
        return True, "E-mail enviado com sucesso!"
    except Exception as e:
        return False, f"Falha ao enviar o e-mail: {e}"
    
def send_notification_email(to_address, subject, body_html):
    """Envia um e-mail de notificação formatado em HTML."""
    try:
        sender_email = st.secrets["gmail_smtp"]["EMAIL_ADDRESS"]
        sender_password = st.secrets["gmail_smtp"]["EMAIL_PASSWORD"]

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.attach(MIMEText(body_html, 'html')) # Define o corpo do e-mail como HTML
        
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