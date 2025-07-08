# utils.py

import streamlit as st
import json, os, pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from jira_connector import get_all_project_issues
from config import STANDARD_FIELDS_FILE, CUSTOM_FIELDS_FILE, STORY_POINTS_FIELD_ID
from metrics_calculator import find_completion_date, calculate_cycle_time, calculate_lead_time

def on_project_change():
    """Limpa o dataframe de dados ao trocar de projeto."""
    if 'dynamic_df' in st.session_state:
        st.session_state['dynamic_df'] = None

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
        title = ""
        if chart_type in ['dispersão', 'linha']:
            fig = px.scatter(df, x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", title=title, hover_name="Issue", template=template) if chart_type == 'dispersão' else px.line(df.sort_values(by=chart_config['x']), x=chart_config['x'], y=chart_config['y'], color="Tipo de Issue", markers=True, title=title, hover_name="Issue", template=template)
        
        elif chart_type in ['barra', 'linha_agregada', 'pizza', 'treemap', 'funil', 'tabela']:
            measure, dimension, agg = chart_config['measure'], chart_config['dimension'], chart_config.get('agg')
            if measure == 'Contagem de Issues':
                grouped_df = df.groupby(dimension).size().reset_index(name='Contagem'); y_axis, values_col = 'Contagem', 'Contagem'
            else:
                agg_func = 'sum' if agg == 'Soma' else 'mean'; grouped_df = df.groupby(dimension)[measure].agg(agg_func).reset_index(); y_axis = values_col = measure
            
            if chart_type == 'barra': fig = px.bar(grouped_df, x=dimension, y=y_axis, color=dimension, title=title, template=template)
            elif chart_type == 'linha_agregada': fig = px.line(grouped_df.sort_values(by=dimension), x=dimension, y=y_axis, color=dimension, title=title, template=template, markers=True)
            elif chart_type == 'pizza': fig = px.pie(grouped_df, names=dimension, values=values_col, title=title, template=template)
            elif chart_type == 'treemap': fig = px.treemap(grouped_df, path=[px.Constant("Todos"), dimension], values=values_col, color=y_axis, title=title, color_continuous_scale='Blues', template=template)
            elif chart_type == 'funil': fig = px.funnel(grouped_df, x=y_axis, y=dimension, title=title, template=template)
            elif chart_type == 'tabela':
                st.dataframe(grouped_df.sort_values(by=y_axis, ascending=False), use_container_width=True); return
        
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

    except Exception as e:
        st.error(f"Erro ao gerar a visualização: {e}")

def common_sidebar():
    """Cria e gere a barra lateral comum a todas as páginas de análise."""
    with st.sidebar:
        try:
            st.image("images/gauge-logo.svg", width=150)
        except Exception:
            st.write("Gauge Metrics")
        st.divider()
        st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
        
        st.header("Fonte de Dados")
        projects = st.session_state.get('projects', {})
        
        project_name = st.selectbox(
            "Selecione um Projeto", 
            options=list(projects.keys()), 
            key="project_selector_dynamic", 
            on_change=on_project_change, 
            index=None, 
            placeholder="Escolha um projeto..."
        )
        
        if project_name:
            st.session_state.project_key = projects.get(project_name)
            st.session_state.project_name = project_name
            
            if st.button("Carregar Dados do Projeto", use_container_width=True, type="primary"):
                with st.spinner("Buscando e preparando dados..."):
                    issues = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key)
                    selected_standard_fields = load_config(STANDARD_FIELDS_FILE, [])
                    custom_fields_to_fetch = load_config(CUSTOM_FIELDS_FILE, [])
                    data = []
                    AVAILABLE_STANDARD_FIELDS_LOCAL = st.session_state.get('available_standard_fields', {})
                    for i in issues:
                        completion_date = find_completion_date(i)
                        issue_data = {
                            'Issue': i.key, 'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),'Data de Conclusão': completion_date, 'Mês de Conclusão': completion_date.strftime('%Y-%m') if completion_date else None, 
                            'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i), 
                            'Tipo de Issue': i.fields.issuetype.name, 'Responsável': i.fields.assignee.displayName if i.fields.assignee else 'Não atribuído', 
                            'Criado por': i.fields.reporter.displayName if i.fields.reporter else 'N/A', 'Status': i.fields.status.name, 
                            'Prioridade': i.fields.priority.name if i.fields.priority else 'N/A', 'Story Points': getattr(i.fields, STORY_POINTS_FIELD_ID, 0) or 0, 
                            'Labels': ', '.join(i.fields.labels) if i.fields.labels else 'Nenhum'
                        }
                        for field_name in selected_standard_fields:
                            field_id = AVAILABLE_STANDARD_FIELDS_LOCAL.get(field_name)
                            if field_id:
                                value = getattr(i.fields, field_id, None)
                                if isinstance(value, list): issue_data[field_name] = ', '.join([getattr(v, 'name', str(v)) for v in value]) if value else 'Nenhum'
                                elif hasattr(value, 'name'): issue_data[field_name] = value.name
                                elif value: issue_data[field_name] = str(value).split('T')[0]
                                else: issue_data[field_name] = 'N/A'
                        for field in custom_fields_to_fetch:
                            field_name, field_id = field['name'], field['id']
                            value = getattr(i.fields, field_id, None)
                            if hasattr(value, 'displayName'): issue_data[field_name] = value.displayName
                            elif hasattr(value, 'value'): issue_data[field_name] = value.value
                            elif value is not None: issue_data[field_name] = str(value)
                            else: issue_data[field_name] = 'N/A'
                        data.append(issue_data)
                    st.session_state.dynamic_df = pd.DataFrame(data)
                    st.rerun()
