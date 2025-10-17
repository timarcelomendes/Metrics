# utils.py (VERSÃO FINAL CORRIGIDA E OTIMIZADA)

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


def apply_filters(df, filters):
    """Aplica a lista de filtros do construtor de gráficos a um DataFrame."""
    if not filters:
        return df
        
    df_filtered = df.copy()
    
    for f in filters:
        field = f.get('field')
        op = f.get('operator')
        value = f.get('value')

        if not field or not op or value is None or (isinstance(value, list) and not value):
            continue

        if field not in df_filtered.columns:
            st.warning(f"Não foi possível aplicar o filtro: o campo '{field}' não foi encontrado nos dados atuais.")
            continue

        try:
            if pd.api.types.is_datetime64_any_dtype(df_filtered[field]):
                 df_filtered[field] = pd.to_datetime(df_filtered[field], errors='coerce').dt.normalize()

            if op == 'é igual a':
                df_filtered = df_filtered[df_filtered[field] == value]
            elif op == 'não é igual a':
                df_filtered = df_filtered[df_filtered[field] != value]
            elif op == 'está em':
                df_filtered = df_filtered[df_filtered[field].isin(value)]
            elif op == 'não está em':
                df_filtered = df_filtered[~df_filtered[field].isin(value)]
            
            elif op == 'maior que':
                df_filtered = df_filtered[pd.to_numeric(df_filtered[field], errors='coerce') > value]
            elif op == 'menor que':
                df_filtered = df_filtered[pd.to_numeric(df_filtered[field], errors='coerce') < value]
            elif op == 'entre' and len(value) == 2:
                df_filtered = df_filtered[pd.to_numeric(df_filtered[field], errors='coerce').between(value[0], value[1])]
            
            elif op == 'Período Personalizado' and isinstance(value, (list, tuple)) and len(value) == 2:
                start_date = pd.to_datetime(value[0]).normalize()
                end_date = pd.to_datetime(value[1]).normalize()
                df_filtered = df_filtered[df_filtered[field].between(start_date, end_date)]
            
            elif op == 'Períodos Relativos':
                days_map = {
                    "Últimos 7 dias": 7, "Últimos 14 dias": 14, "Últimos 30 dias": 30,
                    "Últimos 60 dias": 60, "Últimos 90 dias": 90, "Últimos 120 dias": 120,
                    "Últimos 150 dias": 150, "Últimos 180 dias": 180
                }
                days = days_map.get(value)
                if days:
                    end_date = pd.to_datetime(datetime.now().date())
                    start_date = end_date - timedelta(days=days)
                    df_filtered = df_filtered[df_filtered[field].between(start_date, end_date)]
        
        except Exception as e:
            st.warning(f"Ocorreu um erro inesperado ao aplicar o filtro no campo '{field}': {e}")
            continue
            
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

        # --- INÍCIO DO BLOCO CORRIGIDO ---
        if chart_type in ['barra', 'barra_horizontal', 'linha_agregada', 'pizza', 'treemap', 'funil', 'tabela']:
            dimension = chart_config.get('dimension')
            measure = chart_config.get('measure')
            agg = chart_config.get('agg')
            if not dimension or not measure or not agg:
                st.warning("Configuração de gráfico agregado inválida.")
                return
            
            group_by_cols = [dimension]
            secondary_dimension = chart_config.get('secondary_dimension')
            if secondary_dimension: 
                group_by_cols.append(secondary_dimension)
            
            if measure == "Contagem de Issues":
                agg_df = df_chart_filtered.groupby(group_by_cols).size().reset_index(name='Contagem')
                agg_col = 'Contagem'
            else:
                agg_func_map = {'Soma': 'sum', 'Média': 'mean', 'Contagem': 'count', 'Contagem Distinta': 'nunique'}
                agg_name_map = {'Soma': 'Soma de', 'Média': 'Média de', 'Contagem': 'Contagem de', 'Contagem Distinta': 'Contagem Distinta de'}
                agg_df = df_chart_filtered.groupby(group_by_cols)[measure].agg(agg_func_map[agg]).reset_index()
                agg_col = f"{agg_name_map[agg]} {measure}"
                agg_df.rename(columns={measure: agg_col}, inplace=True)

            y_axis_title_text = agg_col
            if chart_config.get('y_axis_format') == 'hours' and agg_col in agg_df.columns:
                agg_df[agg_col] = agg_df[agg_col] / 3600.0
                y_axis_title_text = f"{agg_col} (horas)"
            
            sort_by = chart_config.get('sort_by')
            if sort_by:
                if "Dimensão" in sort_by:
                    ascending = "A-Z" in sort_by
                    agg_df = agg_df.sort_values(by=dimension, ascending=ascending)
                elif "Medida" in sort_by:
                    ascending = "Crescente" in sort_by
                    agg_df = agg_df.sort_values(by=agg_col, ascending=ascending)
            
            top_n = chart_config.get('top_n')
            if top_n and isinstance(top_n, int) and top_n > 0: 
                agg_df = agg_df.head(top_n)
            
            if chart_config.get('show_as_percentage'):
                total = agg_df[agg_col].sum()
                if total > 0: agg_df[agg_col] = (agg_df[agg_col] / total) * 100
            
            fig = None
            theme_colors = COLOR_THEMES.get(color_theme, COLOR_THEMES[default_theme])
            if not isinstance(theme_colors, dict):
                theme_colors = COLOR_THEMES[default_theme]

            if chart_type == 'barra': fig = px.bar(agg_df, x=dimension, y=agg_col, color=secondary_dimension)
            elif chart_type == 'barra_horizontal': fig = px.bar(agg_df, y=dimension, x=agg_col, orientation='h', color=secondary_dimension)
            elif chart_type == 'linha_agregada': fig = px.line(agg_df, x=dimension, y=agg_col, markers=True, color=secondary_dimension)
            elif chart_type == 'pizza': fig = px.pie(agg_df, names=dimension, values=agg_col)
            elif chart_type == 'treemap':
                path = [dimension]
                if secondary_dimension: path.append(secondary_dimension)
                fig = px.treemap(agg_df, path=path, values=agg_col)
            elif chart_type == 'funil': fig = px.funnel(agg_df, x=agg_col, y=dimension)
            elif chart_type == 'tabela':
                header_color = theme_colors.get('primary_color', '#1f77b4')
                fig = go.Figure(data=[go.Table(
                    header=dict(values=list(agg_df.columns), fill_color=header_color, align='left', font=dict(color='white')), 
                    cells=dict(values=[agg_df[col] for col in agg_df.columns], fill_color='#f0f2f6', align='left')
                )])
            
            if fig:
                fig = apply_chart_theme(fig, color_theme)
                fig.update_layout(title_text=None)
                if chart_config.get('y_axis_format') == 'hours':
                    fig.update_layout(yaxis_title=y_axis_title_text) if chart_type != 'barra_horizontal' else fig.update_layout(xaxis_title=y_axis_title_text)
                
                if chart_config.get('show_data_labels') and chart_type not in ['tabela', 'pizza', 'treemap']:
                    text_template = '%{value:.2f}h' if chart_config.get('y_axis_format') == 'hours' else '%{value:.2s}'
                    
                    if chart_type in ['barra', 'barra_horizontal']:
                        fig.update_traces(texttemplate=text_template, textposition='auto')
                    elif chart_type == 'linha_agregada':
                        fig.update_traces(texttemplate=text_template, textposition='top center')
                    elif chart_type == 'funil':
                        fig.update_traces(texttemplate=text_template, textposition='auto')

                if chart_config.get('show_as_percentage'):
                    if chart_type == 'pizza': fig.update_traces(texttemplate='%{value:.1f}%')
                    else: fig.update_layout(yaxis_ticksuffix="%")
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
                        agg_map = {'soma': 'sum', 'média': 'mean'}
                        
                        grouping_cols = [pd.Grouper(key=x, freq=freq)]
                        if color_by and color_by != "Nenhum": grouping_cols.append(color_by)

                        agg_dict = {y: agg_map.get(y_agg_func, 'mean')}
                        if size_by and size_by != "Nenhum": agg_dict[size_by] = 'mean'

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
            # --- LÓGICA DE RENDERIZAÇÃO ATUALIZADA ---
            theme_colors = COLOR_THEMES.get(color_theme, COLOR_THEMES[default_theme])
            if not isinstance(theme_colors, dict):
                theme_colors = COLOR_THEMES[default_theme]
            
            title_color = theme_colors.get('title_color', '#3D3D3D')
            number_color = theme_colors.get('primary_color', '#0068C9')
            delta_color = theme_colors.get('secondary_color', '#83C9FF')
            
            # Pega as configurações de formatação do gráfico
            decimal_places = int(chart_config.get('kpi_decimal_places', 2))
            format_as_pct = chart_config.get('kpi_format_as_percentage', False)
            valueformat = f".{decimal_places}f"
            suffix = "%" if format_as_pct else ""
            
            main_value = None
            baseline = None
            fig = None
            
            # Calcula os valores brutos (main_value e baseline)
            if chart_config.get('source_type') == 'jql':
                from jira_connector import get_jql_issue_count
                jql_a = chart_config.get('jql_a', '')
                if not jql_a.strip():
                    st.warning("A Consulta JQL 1 (Valor A) é obrigatória e está vazia.")
                    return
                val_a = get_jql_issue_count(st.session_state.jira_client, jql_a)
                if not isinstance(val_a, (int, float)):
                    st.error(f"Erro ao processar a Consulta JQL 1 (Valor A): {val_a}")
                    return
                val_b = None
                jql_b = chart_config.get('jql_b', '')
                if jql_b.strip():
                    val_b_raw = get_jql_issue_count(st.session_state.jira_client, jql_b)
                    if isinstance(val_b_raw, (int, float)): val_b = val_b_raw
                    else: st.warning(f"Aviso na Consulta JQL 2 (Valor B): {val_b_raw}")
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
                    else: st.warning(f"Aviso na Consulta da Linha de Base (Valor C): {baseline_raw}")
            
            else: # source_type == 'visual'
                main_value = calculate_kpi_value(chart_config.get('num_op'), chart_config.get('num_field'), df_chart_filtered)
                
                if chart_config.get('use_baseline', False):
                    baseline = calculate_kpi_value(
                        chart_config.get('base_op'), 
                        chart_config.get('base_field'), 
                        df_chart_filtered
                    )
                if chart_config.get('use_den'):
                    denominator = calculate_kpi_value(chart_config.get('den_op'), chart_config.get('den_field'), df_chart_filtered)
                    if denominator is not None and denominator != 0:
                        main_value = (main_value / denominator)
                        if baseline is not None:
                            baseline = (baseline / denominator)
                    else:
                        main_value = 0
                        baseline = 0 if baseline is not None else None

            # Aplica a formatação percentual (se ativada)
            if format_as_pct:
                if isinstance(main_value, (int, float)):
                    main_value *= 100
                if isinstance(baseline, (int, float)):
                    baseline *= 100
            
            # Constrói a figura final com a formatação
            fig = go.Figure(go.Indicator(
                mode="number" + ("+delta" if baseline is not None else ""),
                value=main_value,
                title={"text": chart_config.get('title'), "font": {"color": title_color}},
                number={"font": {"color": number_color}, "valueformat": valueformat, "suffix": suffix},
                delta={'reference': baseline, "font": {"color": delta_color}, "valueformat": valueformat} if baseline is not None else None
            ))
            
            if fig:
                fig.update_layout(margin=dict(l=0, r=0, t=40, b=10), height=150, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
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

        # --- LÓGICA DE ALINHAMENTO CORRIGIDA ---
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
        # --- FIM DA CORREÇÃO ---
            
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

def load_and_process_project_data(jira_client, project_key):
    """
    Carrega, processa, enriquece e armazena em cache os dados de um projeto Jira.
    Esta versão agora calcula e inclui o Cycle Time no DataFrame principal.
    """
    from jira_connector import get_project_issues, get_jira_fields
    from metrics_calculator import find_completion_date, filter_ignored_issues, calculate_cycle_time

    user_data = find_user(st.session_state['email'])
    project_config = get_project_config(project_key) or {}
    user_enabled_custom_fields = user_data.get('enabled_custom_fields', [])
    
    raw_issues_list = get_project_issues(jira_client, project_key, user_custom_fields=user_enabled_custom_fields)
    issues = filter_ignored_issues(raw_issues_list, project_config)
    
    if not issues:
        st.warning("Nenhuma issue foi encontrada para este projeto (ou todas foram ignoradas pela sua configuração de status).")
        return pd.DataFrame(), []

    all_jira_fields = get_jira_fields(jira_client)
    field_id_to_name_map = {field['id']: field['name'] for field in all_jira_fields}

    processed_issues_data = []
    for issue in issues:
        fields_data = issue.raw['fields'].copy()
        fields_data['key'] = issue.key
        
        completion_date = find_completion_date(issue, project_config)
        fields_data['calculated_completion_date'] = completion_date
        
        # Calcula o Cycle Time se houver data de conclusão
        if completion_date:
            completion_datetime = pd.to_datetime(completion_date)
            fields_data['calculated_cycle_time'] = calculate_cycle_time(issue, completion_datetime, project_config)
        else:
            fields_data['calculated_cycle_time'] = None
            
        processed_issues_data.append(fields_data)

    df = pd.DataFrame(processed_issues_data)

    global_configs = st.session_state.get('global_configs', {})
    available_custom_fields = global_configs.get('custom_fields', [])
    enabled_field_name_to_type_map = {
        field['name']: field.get('type', 'Texto') 
        for field in available_custom_fields 
        if field['name'] in user_enabled_custom_fields
    }

    for col in df.columns:
        if col.startswith('customfield_'):
            field_name = field_id_to_name_map.get(col)
            if field_name and field_name in enabled_field_name_to_type_map:
                field_type = enabled_field_name_to_type_map[field_name]
                df[field_name] = df[col].apply(lambda x: x.get('value') if isinstance(x, dict) else x)
                if field_type == 'Numérico':
                    df[field_name] = pd.to_numeric(df[field_name], errors='coerce')
                elif field_type == 'Data':
                    df[field_name] = pd.to_datetime(df[field_name], errors='coerce').dt.date

    df.rename(columns={'summary': 'Issue', 'key': 'ID'}, inplace=True)
    df['Tipo de Issue'] = df['issuetype'].apply(lambda x: x['name'] if x else None)
    df['Status'] = df['status'].apply(lambda x: x['name'] if x else None)
    df['Responsável'] = df['assignee'].apply(lambda x: x['displayName'] if x else 'Não atribuído')
    df['Prioridade'] = df['priority'].apply(lambda x: x['name'] if x else None)
    df['Categoria de Status'] = df['status'].apply(lambda x: x['statusCategory']['name'] if x and 'statusCategory' in x else None)
    
    data_criacao_dt = pd.to_datetime(df['created']).dt.tz_localize(None)
    data_conclusao_dt = pd.to_datetime(df['calculated_completion_date'], errors='coerce').dt.tz_localize(None)

    df['Lead Time (dias)'] = (data_conclusao_dt - data_criacao_dt).dt.days
    df['Cycle Time (dias)'] = df['calculated_cycle_time'] # Adiciona a nova coluna
    
    df['Data de Criação'] = data_criacao_dt.dt.normalize()
    df['Data de Conclusão'] = data_conclusao_dt.dt.normalize()

    final_columns = ['ID', 'Issue', 'Tipo de Issue', 'Status', 'Responsável', 'Prioridade', 'Categoria de Status', 'Data de Criação', 'Data de Conclusão', 'Lead Time (dias)', 'Cycle Time (dias)']
    
    final_columns.extend([name for name in enabled_field_name_to_type_map.keys() if name in df.columns])
    
    df_final = df[[col for col in final_columns if col in df.columns]].copy()

    return df_final, issues

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
    raw_response_text = "" # Inicializa para o bloco except

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
        else: # OpenAI
            response = model_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
    except Exception as e:
        st.error(f"Ocorreu um erro ao comunicar com a IA: {e}")
        return "Ocorreu uma falha ao tentar gerar a análise. Por favor, tente novamente."