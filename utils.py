# utils.py

import streamlit as st
import json, os, pandas as pd
import plotly.express as px
import plotly.graph_objects as go

def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except (json.JSONDecodeError, UnicodeDecodeError): return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def render_chart(chart_config, df):
    chart_type = chart_config.get('type'); fig = None; template = "plotly_white"
    try:
        title = chart_config.get('title', 'Gráfico')

        # --- NOVA ETAPA DE VALIDAÇÃO ---
        # Verifica se todas as colunas necessárias para o gráfico existem no dataframe
        required_cols = []
        if 'x' in chart_config: required_cols.append(chart_config['x'])
        if 'y' in chart_config: required_cols.append(chart_config['y'])
        if 'dimension' in chart_config: required_cols.append(chart_config['dimension'])
        if 'measure' in chart_config and chart_config['measure'] != 'Contagem de Issues':
            required_cols.append(chart_config['measure'])
        if 'columns' in chart_config: required_cols.extend(chart_config['columns'])
        
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            st.warning(f"Não foi possível renderizar esta visualização.", icon="⚠️")
            st.error(f"Motivo: O(s) campo(s) **{', '.join(missing_cols)}** não foi/foram encontrado(s) nos dados atuais.")
            st.info("Isto pode acontecer se um Campo Personalizado foi removido ou renomeado nas configurações. Por favor, edite ou remova esta visualização.")
            return # Interrompe a renderização deste gráfico

        if chart_type in ['dispersão', 'linha']:
            fig = px.scatter(df, x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", title=title, hover_name="Issue", template=template) if chart_type == 'dispersão' else px.line(df.sort_values(by=chart_config['x']), x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", markers=True, title=title, hover_name="Issue", template=template)
        
        # ===== CORREÇÃO: Trata o caso da 'tabela' primeiro e separadamente =====
        elif chart_type == 'tabela':
            columns_to_show = chart_config.get('columns', [])
            if columns_to_show:
                st.dataframe(df[columns_to_show], use_container_width=True)
            else:
                st.info("Nenhuma coluna selecionada para esta tabela.")
            return # Sai da função, pois a tabela não usa o objeto 'fig'

        elif chart_type in ['barra', 'linha_agregada', 'pizza', 'treemap', 'funil']:
            measure, dimension, agg = chart_config['measure'], chart_config['dimension'], chart_config.get('agg')
            if measure == 'Contagem de Issues':
                grouped_df = df.groupby(dimension).size().reset_index(name='Contagem'); y_axis, values_col = 'Contagem', 'Contagem'
            elif agg == 'Contagem Distinta':
                grouped_df = df.groupby(dimension)[measure].nunique().reset_index(); y_axis = values_col = measure
            else: # Soma ou Média
                agg_func = 'sum' if agg == 'Soma' else 'mean'; grouped_df = df.groupby(dimension)[measure].agg(agg_func).reset_index(); y_axis = values_col = measure
            
            if chart_type == 'barra': fig = px.bar(grouped_df, x=dimension, y=y_axis, color=dimension, title=title, template=template)
            elif chart_type == 'linha_agregada': fig = px.line(grouped_df.sort_values(by=dimension), x=dimension, y=y_axis, color=dimension, title=title, template=template, markers=True)
            elif chart_type == 'pizza': fig = px.pie(grouped_df, names=dimension, values=values_col, title=title, template=template)
            elif chart_type == 'treemap': fig = px.treemap(grouped_df, path=[px.Constant("Todos"), dimension], values=values_col, color=y_axis, title=title, color_continuous_scale='Blues', template=template)
            elif chart_type == 'funil': fig = px.funnel(grouped_df, x=y_axis, y=dimension, title=title, template=template)
                
        elif chart_type == 'indicator':
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
                    else: mean_val = 0
                st.metric(label="", value=f"{final_value:,.2f}", delta=f"{delta_value:,.2f}" if delta_value is not None else None, help=f"Variação em relação à média do período ({mean_val:,.2f})" if delta_value is not None else None)
            
            elif style == 'Medidor (Gauge)':
                target_value = 100
                if chart_config.get('target_type') == 'Valor Fixo': target_value = chart_config.get('gauge_max_static', 100)
                else:
                    if chart_config.get('target_op') and chart_config.get('target_field'): target_value = calculate_value(chart_config['target_op'], chart_config['target_field'], df)
                bar_color = chart_config.get('gauge_bar_color', '#1f77b4'); threshold_color = chart_config.get('gauge_target_color', '#d62728')
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number", value = final_value,
                    gauge = {'axis': {'range': [chart_config.get('gauge_min', 0), target_value]}, 'bar': {'color': bar_color}, 'bgcolor': "white", 'borderwidth': 2, 'bordercolor': "gray",
                             'steps': [{'range': [0, target_value * 0.5], 'color': 'rgba(255, 0, 0, 0.15)'}, {'range': [target_value * 0.5, target_value * 0.8], 'color': 'rgba(255, 255, 0, 0.25)'}, {'range': [target_value * 0.8, target_value], 'color': 'rgba(0, 255, 0, 0.25)'}],
                             'threshold': {'line': {'color': threshold_color, 'width': 4}, 'thickness': 0.9, 'value': target_value}}))
                fig.update_layout(height=125, margin=dict(l=1,r=1,t=1,b=1), paper_bgcolor="rgba(0,0,0,0)", font={'size': 12})
        
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)

    except KeyError as e:
        st.error(f"Erro de configuração: o campo {e} não foi encontrado nos dados para o gráfico '{chart_config.get('title', 'Desconhecido')}'.")
    except Exception as e:
        st.error(f"Erro ao gerar a visualização '{chart_config.get('title', 'Desconhecido')}': {e}")