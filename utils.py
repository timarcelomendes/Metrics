# utils.py

import streamlit as st
import json, os, pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from jira_connector import get_jql_issue_count

def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError): return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# Dentro do seu ficheiro utils.py

def render_chart(chart_config, df):
    """
    Renderiza um único gráfico ou indicador com base na sua configuração.
    Esta é a versão final e completa, com todas as funcionalidades.
    """
    chart_type = chart_config.get('type')
    source_type = chart_config.get('source_type', 'visual')
    fig = None
    template = "plotly_white"
    
    try:
        if chart_type == 'indicator':
            if source_type == 'jql':
                with st.spinner("A calcular KPI com JQL..."):
                    jql_a = chart_config.get('jql_a'); jql_b = chart_config.get('jql_b'); operation = chart_config.get('jql_operation')
                    val_a = get_jql_issue_count(st.session_state.jira_client, jql_a); final_value = float(val_a)
                    if jql_b and operation:
                        val_b = get_jql_issue_count(st.session_state.jira_client, jql_b)
                        if operation == 'Dividir (A / B)': final_value = (val_a / val_b) * 100 if val_b > 0 else 0
                        elif operation == 'Somar (A + B)': final_value = val_a + val_b
                        elif operation == 'Subtrair (A - B)': final_value = val_a - val_b
                        elif operation == 'Multiplicar (A * B)': final_value = val_a * val_b
                    
                    if final_value == int(final_value): value_str = f"{int(final_value):,}"
                    else: value_str = f"{final_value:,.2f}"
                    if operation == 'Dividir (A / B)': value_str += "%"
                    st.metric(label="", value=value_str)
                return
            else: # Construtor Visual
                def calculate_value(op, field, data_frame):
                    if not op or not field: return 0
                    if op == 'Contagem': return len(data_frame.dropna(subset=[field])) if field != 'Issues' else len(data_frame)
                    elif op == 'Soma': return pd.to_numeric(data_frame[field], errors='coerce').sum()
                    elif op == 'Média': return pd.to_numeric(data_frame[field], errors='coerce').mean()
                    return 0
                
                num_value = calculate_value(chart_config['num_op'], chart_config['num_field'], df); final_value = num_value
                if chart_config.get('use_den'):
                    den_value = calculate_value(chart_config['den_op'], chart_config['den_field'], df); final_value = (num_value / den_value) if den_value != 0 else 0
                
                style = chart_config.get('style', 'Número Grande')
                
                if style == 'Número Grande':
                    delta_value, mean_val = None, 0
                    if chart_config.get('show_delta') and chart_config.get('num_field') != 'Issues':
                        mean_val = calculate_value('Média', chart_config['num_field'], df)
                        if mean_val is not None and pd.notna(mean_val) and mean_val > 0: delta_value = final_value - mean_val
                    
                    if final_value == int(final_value): value_str = f"{int(final_value):,}"
                    else: value_str = f"{final_value:,.2f}"
                    delta_str = None
                    if delta_value is not None:
                        if delta_value == int(delta_value): delta_str = f"{int(delta_value):,}"
                        else: delta_str = f"{delta_value:,.2f}"
                    st.metric(label="", value=value_str, delta=delta_str, help=f"Variação vs. média ({mean_val:,.2f})" if delta_value is not None else None)
                
                elif style in ['Medidor (Gauge)', 'Gráfico de Bala (Bullet)']:
                    target_value = 100
                    if chart_config.get('target_type') == 'Valor Fixo': target_value = chart_config.get('gauge_max_static', 100)
                    else:
                        if chart_config.get('target_op') and chart_config.get('target_field'): target_value = calculate_value(chart_config['target_op'], chart_config['target_field'], df)
                    
                    poor_limit = chart_config.get('gauge_poor_threshold', target_value * 0.5); good_limit = chart_config.get('gauge_good_threshold', target_value * 0.8); fig = go.Figure()
                    if style == 'Medidor (Gauge)':
                        fig.add_trace(go.Indicator(mode = "gauge+number", value = final_value, gauge = {'axis': {'range': [chart_config.get('gauge_min', 0), target_value]}, 'bar': {'color': chart_config.get('gauge_bar_color', '#1f77b4')}, 'steps': [{'range': [0, poor_limit], 'color': 'rgba(255, 0, 0, 0.15)'}, {'range': [poor_limit, good_limit], 'color': 'rgba(255, 255, 0, 0.25)'}, {'range': [good_limit, target_value], 'color': 'rgba(0, 255, 0, 0.25)'}], 'threshold': {'line': {'color': chart_config.get('gauge_target_color', '#d62728'), 'width': 4}, 'thickness': 0.9, 'value': target_value}}))
                        fig.update_layout(height=150, margin=dict(l=20,r=20,t=1,b=1))
                    elif style == 'Gráfico de Bala (Bullet)':
                        fig.add_trace(go.Indicator(mode = "number+gauge", value = final_value, gauge = {'shape': "bullet", 'axis': {'range': [None, target_value]}, 'threshold': {'line': {'color': chart_config.get('gauge_target_color', '#d62728'), 'width': 3}, 'thickness': 0.9, 'value': target_value}, 'steps': [{'range': [0, poor_limit], 'color': "rgba(255, 0, 0, 0.25)"}, {'range': [poor_limit, good_limit], 'color': "rgba(255, 255, 0, 0.35)"}, {'range': [good_limit, target_value], 'color': "rgba(0, 255, 0, 0.35)"}], 'bar': {'color': chart_config.get('gauge_bar_color', '#1f77b4'), 'thickness': 0.5}}))
                        fig.update_layout(height=100, margin=dict(l=1,r=1,t=20,b=20))

        elif chart_type in ['dispersão', 'linha']:
            plot_df = df.dropna(subset=[chart_config['x'], chart_config['y']]).copy()
            if chart_type == 'linha': plot_df.sort_values(by=chart_config['x'], inplace=True)
            fig = px.scatter(plot_df, x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", title=None, hover_name="Issue", template=template) if chart_type == 'dispersão' else px.line(plot_df, x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", markers=True, title=None, hover_name="Issue", template=template)
        
        elif chart_type == 'tabela':
            columns_to_show = chart_config.get('columns', [])
            if columns_to_show: st.dataframe(df[[col for col in columns_to_show if col in df.columns]], use_container_width=True)
            else: st.info("Nenhuma coluna selecionada para esta tabela.")
            return

        elif chart_type in ['barra', 'linha_agregada', 'pizza', 'treemap', 'funil']:
            measure, dimension, agg = chart_config['measure'], chart_config['dimension'], chart_config.get('agg')
            if measure == 'Contagem de Issues':
                grouped_df = df.groupby(dimension).size().reset_index(name='Contagem'); y_axis, values_col = 'Contagem', 'Contagem'
            elif agg == 'Contagem Distinta':
                new_column_name = f"Contagem de {measure}"; grouped_df = df.groupby(dimension)[measure].nunique().reset_index(name=new_column_name); y_axis, values_col = new_column_name, new_column_name
            else:
                agg_func = 'sum' if agg == 'Soma' else 'mean'; df[measure] = pd.to_numeric(df[measure], errors='coerce'); grouped_df = df.groupby(dimension)[measure].agg(agg_func).reset_index(); y_axis, values_col = measure, measure
            
            if chart_type == 'barra': fig = px.bar(grouped_df, x=dimension, y=y_axis, color=dimension, title=None, template=template)
            elif chart_type == 'linha_agregada': fig = px.line(grouped_df.sort_values(by=dimension), x=dimension, y=y_axis, title=None, template=template, markers=True)
            elif chart_type == 'pizza': fig = px.pie(grouped_df, names=dimension, values=values_col, title=None, template=template)
            elif chart_type == 'treemap': fig = px.treemap(grouped_df, path=[px.Constant("Todos"), dimension], values=values_col, color=y_axis, title=None, color_continuous_scale='Blues', template=template)
            elif chart_type == 'funil': fig = px.funnel(grouped_df, x=y_axis, y=dimension, title=None, template=template)
        
        elif chart_type == 'pivot_table':
            rows_col = chart_config.get('rows')
            cols_col = chart_config.get('columns')
            values_col = chart_config.get('values')
            agg_func_name = chart_config.get('aggfunc')
            
            # Mapeia o nome amigável para a função do pandas
            agg_map = {'Soma': 'sum', 'Média': 'mean', 'Contagem': 'count'}
            agg_func = agg_map.get(agg_func_name, 'sum')

            # Garante que a coluna de valores é numérica para os cálculos
            df[values_col] = pd.to_numeric(df[values_col], errors='coerce')

            pivot_df = pd.pivot_table(
                df,
                values=values_col,
                index=rows_col,
                columns=cols_col,
                aggfunc=agg_func,
                fill_value=0 # Preenche células vazias com 0
            )
            
            # Exibe a tabela como um mapa de calor
            st.dataframe(pivot_df.style.background_gradient(cmap='Blues'), use_container_width=True)
            return

        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
            
    except Exception as e:
        st.error(f"Erro ao gerar a visualização '{chart_config.get('title', 'Desconhecido')}': {e}")