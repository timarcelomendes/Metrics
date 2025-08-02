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
    Renderiza um único gráfico, KPI ou tabela com base na sua configuração.
    Esta é a versão final e completa, com todas as funcionalidades.
    """
    try:
        # 1. Validação de Campos Necessários
        required_cols = []
        chart_type = chart_config.get('type')
        if chart_type in ['dispersão', 'linha']:
            required_cols.extend([chart_config.get('x'), chart_config.get('y')])
        elif chart_type in ['barra', 'linha_agregada', 'pizza', 'treemap', 'funil']:
            required_cols.append(chart_config.get('dimension'))
            if chart_config.get('measure') != 'Contagem de Issues': required_cols.append(chart_config.get('measure'))
        elif chart_type == 'tabela':
            required_cols.extend(chart_config.get('columns', []))
        elif chart_type == 'pivot_table':
            required_cols.extend([chart_config.get('rows'), chart_config.get('columns'), chart_config.get('values')])
        
        missing_cols = [col for col in required_cols if col and col not in df.columns]
        if missing_cols:
            st.warning(f"Não foi possível renderizar esta visualização.", icon="⚠️")
            st.error(f"Motivo: O(s) campo(s) **{', '.join(missing_cols)}** não foi/foram encontrado(s) nos dados atuais.")
            return

        # 2. Lógica de Filtragem e Renderização
        df_to_render = df.copy()
        chart_filters = chart_config.get('filters', [])
        if chart_filters:
            for f in chart_filters:
                field, values = f.get('field'), f.get('values')
                if field and values and field in df_to_render.columns:
                    if isinstance(values, list) and len(values) == 2 and isinstance(values[0], str) and '-' in values[0]:
                        try:
                            start_date, end_date = pd.to_datetime(values[0]), pd.to_datetime(values[1])
                            df_to_render[field] = pd.to_datetime(df_to_render[field], errors='coerce')
                            df_to_render = df_to_render.dropna(subset=[field])
                            df_to_render = df_to_render[(df_to_render[field] >= start_date) & (df_to_render[field] <= end_date)]
                        except (ValueError, TypeError): pass
                    elif isinstance(values, list):
                        df_to_render = df_to_render[df_to_render[field].isin(values)]

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
            required_cols = [x_col, y_col]
            if color_col and color_col != "Nenhum": required_cols.append(color_col)
            plot_df = df_to_render.dropna(subset=required_cols).copy()
            color_param = color_col if color_col and color_col != "Nenhum" and color_col in plot_df.columns else None
            text_param = y_col if chart_config.get('show_data_labels') else None
            if chart_type == 'dispersão':
                fig = px.scatter(plot_df, x=x_col, y=y_col, color=color_param, title=None, hover_name="Issue", template=template, text=text_param)
            else:
                plot_df.sort_values(by=x_col, inplace=True)
                fig = px.line(plot_df, x=x_col, y=y_col, color=color_param, title=None, hover_name="Issue", template=template, markers=True, text=text_param)
            if chart_config.get('show_data_labels'):
                fig.update_traces(textposition='top center', texttemplate='%{text:,.2f}')
        
        elif chart_type == 'tabela':
            columns_to_show = chart_config.get('columns', [])
            if columns_to_show: st.dataframe(df_to_render[[col for col in columns_to_show if col in df_to_render.columns]], use_container_width=True)
            else: st.info("Nenhuma coluna selecionada para esta tabela."); return

        elif chart_type == 'pivot_table':
            rows_col, cols_col, values_col, agg_func_name = chart_config.get('rows'), chart_config.get('columns'), chart_config.get('values'), chart_config.get('aggfunc')
            agg_map = {'Soma': 'sum', 'Média': 'mean', 'Contagem': 'count'}; agg_func = agg_map.get(agg_func_name, 'sum')
            df_to_render[values_col] = pd.to_numeric(df_to_render[values_col], errors='coerce')
            pivot_df = pd.pivot_table(df_to_render, values=values_col, index=rows_col, columns=cols_col, aggfunc=agg_func, fill_value=0)
            def auto_formatter(val):
                if pd.notna(val) and isinstance(val, (int, float)):
                    if float(val).is_integer(): return f"{int(val):,}"
                    else: return f"{val:,.2f}"
                return val
            st.dataframe(pivot_df.style.format(auto_formatter).background_gradient(cmap='Blues'), use_container_width=True); return

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
            
            if show_labels and fig and chart_type not in ['pizza']:
                is_float = pd.api.types.is_float_dtype(grouped_df[y_axis])
                text_template = '%{text:,.2f}' if is_float else '%{text:,.0f}'
                fig.update_traces(texttemplate=text_template, textposition='outside')
            elif show_labels and fig and chart_type == 'pizza':
                fig.update_traces(textinfo='percent+label', textposition='inside')
        
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"Erro ao gerar a visualização '{chart_config.get('title', 'Desconhecido')}': {e}")

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'ORDEM DE SERVIÇO', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def create_os_pdf(os_data):
    """Gera um PDF para uma Ordem de Serviço com base num dicionário de dados."""
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 11)

    # --- Tabela de Cabeçalho ---
    pdf.cell(95, 10, 'Área Demandante', 1, 0, 'L')
    pdf.cell(95, 10, 'Demandante', 1, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.cell(95, 10, os_data.get('area_demandante', ''), 1, 0, 'L')
    pdf.cell(95, 10, os_data.get('demandante', ''), 1, 1, 'L')
    
    pdf.set_font('Arial', 'B', 11)
    pdf.cell(95, 10, 'Área Executora', 1, 0, 'L')
    pdf.cell(95, 10, 'Gestor do Contrato', 1, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.cell(95, 10, 'Gerência de Transformação Digital', 1, 0, 'L')
    pdf.cell(95, 10, os_data.get('gestor_contrato', ''), 1, 1, 'L')
    # ... adicione outras linhas da tabela de cabeçalho aqui, seguindo o mesmo padrão ...
    
    pdf.ln(10)

    # --- Corpo do Documento ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '1. Justificativa', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, os_data.get('justificativa', ''))
    
    pdf.ln(5)
    
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '2. Objetivo da Ordem de Serviço', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 5, os_data.get('objetivo', ''))
    
    pdf.ln(5)

    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, '3. Entregáveis', 0, 1, 'L')
    pdf.set_font('Arial', '', 10)
    for i, ent in enumerate(os_data.get('entregaveis', [])):
        pdf.multi_cell(0, 5, f"{i+1}. {ent['Item']}")

    # Converte o PDF para bytes para o Streamlit poder usar
    return pdf.output(dest='S').encode('latin-1')

def summarize_chart_data(chart_config, df):
    """Gera um resumo em texto dos dados de um único gráfico."""
    title = chart_config.get('title', 'um gráfico')
    chart_type = chart_config.get('type')
    
    try:
        if chart_type == 'indicator':
            # A lógica para extrair o valor de um KPI precisa ser simplificada aqui
            # Esta é uma simulação, uma implementação real precisaria da função calculate_value
            return f"O indicador '{title}' está a mostrar um valor principal."

        elif chart_type in ['barra', 'linha_agregada', 'pizza']:
            dimension = chart_config.get('dimension')
            measure = chart_config.get('measure')
            if not dimension or not measure: return None

            if measure == 'Contagem de Issues':
                summary_df = df.groupby(dimension).size().nlargest(3)
                return f"O gráfico '{title}' mostra a contagem de issues por '{dimension}'. Os 3 maiores grupos são: {', '.join([f'{idx} ({val})' for idx, val in summary_df.items()])}."
            else:
                agg = chart_config.get('agg', 'Soma')
                summary_df = df.groupby(dimension)[measure].agg(agg.lower()).nlargest(3)
                return f"O gráfico '{title}' mostra a {agg} de '{measure}' por '{dimension}'. Os 3 maiores grupos são: {', '.join([f'{idx} ({val:.1f})' for idx, val in summary_df.items()])}."
        
        return f"Dados para o gráfico '{title}' do tipo {chart_type}."
    except Exception:
        return f"Não foi possível processar os dados para o gráfico '{title}'."


def get_ai_insights(project_name, chart_summaries):
    """
    Chama a API do Gemini para gerar insights, usando a chave de API guardada
    no perfil do utilizador.
    """
    # 1. Busca os dados do utilizador logado
    user_data = find_user(st.session_state['email'])
    if not user_data or 'encrypted_gemini_key' not in user_data:
        st.error("Nenhuma chave de API do Gemini configurada.")
        st.info("Por favor, adicione a sua chave na página 'Minha Conta' para usar esta funcionalidade.")
        st.page_link("pages/9_👤_Minha_Conta.py", label="Configurar Chave de IA", icon="🤖")
        return None

    try:
        # 2. Desencripta a chave e configura a API
        api_key = decrypt_token(user_data['encrypted_gemini_key'])
        genai.configure(api_key=api_key)
        # Usa o modelo guardado no perfil do utilizador, ou o 'flash' como padrão
        model_to_use = user_data.get('ai_model_preference', 'gemini-1.5-flash-latest')
        model = genai.GenerativeModel(model_to_use)

    except Exception as e:
        st.error(f"Erro ao configurar a API do Gemini. A sua chave pode ser inválida. Detalhes: {e}")
        return None

    # Constrói um prompt detalhado para a IA
    prompt = f"""
    Aja como um Analista de Negócios especialista em projetos de software e metodologias ágeis.
    O seu trabalho é analisar os dados de um dashboard do Jira para o projeto "{project_name}" e fornecer um resumo executivo em português.

    Aqui estão os dados resumidos de cada gráfico no dashboard:
    {chr(10).join(f"- {s}" for s in chart_summaries if s)}

    Com base nestes dados, por favor, gere uma análise concisa e acionável. A sua resposta deve ser formatada em Markdown e dividida nas seguintes secções:
    1.  **🎯 Pontos Fortes:** O que os dados indicam que está a correr bem? Seja específico.
    2.  **⚠️ Pontos de Atenção:** Onde podem estar os riscos, gargalos ou desvios? Aponte as métricas preocupantes.
    3.  **🚀 Recomendações:** Sugira 1 a 2 ações práticas que a equipa ou o gestor do projeto poderiam tomar com base nesta análise.
    """

    # 4. Chama a API e retorna a resposta
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Ocorreu um erro ao comunicar com a API do Gemini: {e}")
        return "Não foi possível gerar a análise. Tente novamente mais tarde."

def generate_chart_config_from_text(prompt, numeric_cols, categorical_cols):
    """
    Usa a API do Gemini para interpretar um pedido e gerar uma configuração de gráfico.
    Agora diferencia entre KPIs e gráficos agregados, e entende períodos de tempo.
    """
    prompt_lower = prompt.lower()
    config = {'id': str(uuid.uuid4()), 'source_type': 'visual', 'show_data_labels': True}

    # 1. Detetar Períodos de Tempo e Criar Filtros
    filters = []
    end_date = datetime.now().date()
    days_map = {"7 dias": 7, "30 dias": 30, "90 dias": 90, "180 dias": 180}
    for period_text, days in days_map.items():
        if f"últimos {period_text}" in prompt_lower or f"ultima semana" in prompt_lower:
            start_date = end_date - timedelta(days=days)
            filters.append({
                'field': 'Data de Criação',
                'values': [start_date.isoformat(), end_date.isoformat()]
            })
            break
    config['filters'] = filters

    # 2. Tentar Identificar uma Dimensão
    found_dimension = None
    connecting_words = ["por", "pelo", "pela", "de"]
    for word in connecting_words:
        for col in categorical_cols:
            if f"{word} {col.lower()}" in prompt_lower:
                found_dimension = col
                break
        if found_dimension: break
    
    if not found_dimension:
        found_dimension = next((col for col in categorical_cols if col.lower() in prompt_lower), None)

    # 3. Decidir se é um KPI ou um Gráfico Agregado
    if found_dimension:
        # Se encontrou uma dimensão, cria um Gráfico Agregado
        config['creator_type'] = "Gráfico Agregado"
        config['dimension'] = found_dimension
        if "barra" in prompt_lower: config['type'] = 'barra'
        elif "pizza" in prompt_lower: config['type'] = 'pizza'
        else: config['type'] = 'barra'

        if "contagem" in prompt_lower or "número de" in prompt_lower:
            config['measure'] = 'Contagem de Issues'; config['agg'] = 'Contagem'
        else:
            found_measure = next((col for col in numeric_cols if col.lower() in prompt_lower), 'Contagem de Issues')
            config['measure'] = found_measure
            config['agg'] = 'Média' if "média" in prompt_lower else 'Soma'
        
        config['title'] = prompt
    else:
        # Se NÃO encontrou uma dimensão, cria um Indicador (KPI)
        config['creator_type'] = "Indicador (KPI)"
        config['type'] = 'indicator'
        config['style'] = 'Número Grande'
        config['icon'] = '💡'
        config['title'] = prompt
        
        config['num_op'] = 'Contagem'
        config['num_field'] = 'Issues'

    return config, None