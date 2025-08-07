# pages/2_🏠_Meu_Dashboard.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import uuid
import json
import os
from jira_connector import *
from metrics_calculator import *
from config import *
from utils import *
from security import *
from pathlib import Path
from datetime import datetime, timedelta

st.set_page_config(page_title="Meu Dashboard", page_icon="🏠", layout="wide")

# --- CSS FINAL PARA ESTILO E ALINHAMENTO ---
st.markdown("""
<style>
/* 1. Regra geral: Alinha os cartões do dashboard no TOPO */
[data-testid="stVerticalBlock"] div.st-emotion-cache-1jicfl2 {
    align-items: flex-start;
}
/* 2. Regra específica: Alinha os itens DENTRO do painel de controlo ao CENTRO */
#control-panel [data-testid="stHorizontalBlock"] {
    align-items: center;
}
</style>
""", unsafe_allow_html=True)

def on_project_change():
    """Limpa o estado relevante ao trocar de projeto."""
    if 'dynamic_df' in st.session_state: st.session_state.pop('dynamic_df', None)
    if 'loaded_project_key' in st.session_state: st.session_state.pop('loaded_project_key', None)

def on_layout_change():
    """Callback que lê o estado do toggle e chama a função para guardar a preferência."""
    use_two_cols = st.session_state.dashboard_layout_toggle
    num_cols = 2 if use_two_cols else 1
    save_dashboard_column_preference(st.session_state.project_key, num_cols)

def move_item(items_list, from_index, to_index):
    """Move um item dentro de uma lista de uma posição para outra."""
    if 0 <= from_index < len(items_list) and 0 <= to_index < len(items_list):
        item = items_list.pop(from_index)
        items_list.insert(to_index, item)
    return items_list

# --- Bloco de Autenticação e Conexão (sem alterações) ---
st.header(f"🏠 Meu Dashboard: {st.session_state.get('project_name', 'Nenhum Projeto Carregado')}", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça autenticação para acessar esta página."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if 'jira_client' not in st.session_state:
    user_data = find_user(st.session_state['email'])
    if user_data and user_data.get('encrypted_token'):
        with st.spinner("A conectar ao Jira..."):
            token = decrypt_token(user_data['encrypted_token'])
            client = connect_to_jira(user_data['jira_url'], user_data['jira_email'], token)
            if client:
                st.session_state.jira_client = client; st.session_state.projects = get_projects(client); st.rerun()
            else: st.error("Falha na conexão com o Jira."); st.page_link("pages/9_👤_Minha_Conta.py", label="Verificar Credenciais", icon="👤"); st.stop()

    if not user_data:
        # Cenário 1: O utilizador nunca configurou uma conexão
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌")
        st.info("Para começar, você precisa de adicionar as suas credenciais do Jira.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗")
        st.stop()
    else:
        # Cenário 2: O utilizador tem conexões, mas nenhuma está ativa
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
        st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
        st.stop()

# --- BARRA LATERAL SIMPLIFICADA ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(
            logo_path, 
            size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 

    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else None
    
    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, key="project_selector_dashboard", index=default_index, on_change=on_project_change, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        if st.button("Visualizar / Atualizar Dashboard", use_container_width=True, type="primary"):
            project_key = projects[selected_project_name]
            save_last_project(st.session_state['email'], project_key)
            st.session_state.project_key = project_key
            st.session_state.project_name = selected_project_name
            
            with st.spinner(f"A carregar e processar dados de '{selected_project_name}'..."):
                all_issues_raw = get_all_project_issues(st.session_state.jira_client, project_key)
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

                for i in valid_issues:
                    completion_date = find_completion_date(i)
                    issue_data = {
                        'Issue': i.key,
                        'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),
                        'Data de Conclusão': completion_date,
                        'Lead Time (dias)': calculate_lead_time(i),
                        'Cycle Time (dias)': calculate_cycle_time(i),
                    }
                    
                    # --- LÓGICA DE PROCESSAMENTO UNIVERSAL CORRIGIDA ---
                    fields_to_process = []
                    for field_name in user_enabled_standard:
                        if field_name in all_available_standard:
                            fields_to_process.append({**all_available_standard[field_name], 'name': field_name})
                    for field_config in all_available_custom:
                        if field_config.get('name') in user_enabled_custom:
                            fields_to_process.append(field_config)
                    
                    for field in fields_to_process:
                        field_id, field_name = field['id'], field['name']
                        value = getattr(i.fields, field_id, None)
                        
                        # Lógica inteligente para extrair o valor correto de qualquer tipo de campo
                        if value is None:
                            issue_data[field_name] = None
                        elif hasattr(value, 'displayName'): # Para campos de Utilizador (Assignee, Reporter)
                            issue_data[field_name] = value.displayName
                        elif isinstance(value, list) and value: # Para campos de lista (Seleção Múltipla, Componentes, etc.)
                            processed_list = []
                            for item in value:
                                if hasattr(item, 'value'): processed_list.append(item.value)
                                elif hasattr(item, 'name'): processed_list.append(item.name)
                                else: processed_list.append(str(item))
                            issue_data[field_name] = ', '.join(processed_list)
                        elif hasattr(value, 'value'): # Para campos de Seleção Única
                            issue_data[field_name] = value.value
                        elif hasattr(value, 'name'): # Para campos de Objeto Simples (Status, Priority)
                            issue_data[field_name] = value.name
                        else: # Para campos de texto simples, número ou data
                            issue_data[field_name] = str(value).split('T')[0]

                    # Adiciona o campo de estimativa
                    if estimation_config.get('id'):
                        issue_data[estimation_config['name']] = get_issue_estimation(i, estimation_config)
                        
                    data.append(issue_data)
                
                st.session_state.dynamic_df = pd.DataFrame(data)
                st.rerun()

        if st.button("Logout", use_container_width=True, type='secondary'):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.switch_page("1_🔑_Autenticação.py")

# --- CONTEÚDO PRINCIPAL ---
df = st.session_state.get('dynamic_df')
if df is None:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Visualizar / Atualizar Dashboard' para começar."); st.stop()

user_data = find_user(st.session_state['email']); all_dashboards = user_data.get('dashboard_layout', {})
current_project_key = st.session_state.get('project_key'); dashboard_config = all_dashboards.get(current_project_key, {})
if isinstance(dashboard_config, list):
    dashboard_config = {"tabs": {"Geral": dashboard_config}}; all_dashboards[current_project_key] = dashboard_config
    save_user_dashboard(st.session_state['email'], all_dashboards)
tabs_layout = dashboard_config.get("tabs", {"Geral": []}); all_charts = [chart for tab_charts in tabs_layout.values() for chart in tab_charts]
project_config = get_project_config(current_project_key) or {}
default_cols = project_config.get('dashboard_columns', 2) 

# --- FILTROS GLOBAIS DO DASHBOARD ---
with st.expander("Filtros do Dashboard (afetam todas as visualizações)", expanded=True):
    filter_cols = st.columns(4)
    
    # Define os campos de filtro padrão que queremos exibir
    default_filter_fields = ["Tipo de Issue", "Responsável", "Status", "Prioridade"]
    
    # Dicionário para guardar as seleções
    selections = {}

    for i, field_name in enumerate(default_filter_fields):
        has_field = field_name in df.columns
        options = sorted(df[field_name].dropna().unique()) if has_field else []
        
        selections[field_name] = filter_cols[i].multiselect(
            f"Filtrar por {field_name}", 
            options=options, 
            placeholder="Todos", 
            disabled=not has_field,
            help=f"O campo '{field_name}' não foi carregado. Ative-o em 'Minha Conta' e recarregue os dados." if not has_field else ""
        )
    
    # Cria o dataframe filtrado
    filtered_df = df.copy()
    for field_name, selected_values in selections.items():
        if selected_values:
            filtered_df = filtered_df[filtered_df[field_name].isin(selected_values)]

st.caption(f"A exibir visualizações para o projeto: **{st.session_state.project_name}**.")

# --- PAINEL DE CONTROLE ---
# Adiciona um container com um ID para o CSS
st.markdown('<div id="control-panel">', unsafe_allow_html=True)
with st.container(border=True):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Visualizações", f"{len(all_charts)} / {DASHBOARD_CHART_LIMIT}")
    with col2:
        use_two_columns = st.toggle("2 Colunas", value=(default_cols == 2), key="dashboard_layout_toggle", on_change=on_layout_change)
        num_columns = 2 if use_two_columns else 1
    with col3:
        organize_mode = st.toggle("Organizar", help="Ative para adicionar/renomear abas e mover gráficos.")
    with col4:
        limit_reached = len(all_charts) >= 12
        if limit_reached:
            st.button("Limite Atingido", disabled=True, use_container_width=True)
        else:
            # --- BOTÃO MELHORADO AQUI ---
            # Usamos um st.button com type="primary" e st.switch_page para navegação
            if st.button("➕ Adicionar Gráfico", use_container_width=True, type="primary"):
                st.switch_page("pages/5_🏗️_Construir Gráficos.py")

st.markdown('</div>', unsafe_allow_html=True)


# --- INTERFACE DE ORGANIZAÇÃO OU VISUALIZAÇÃO ---
if organize_mode:
    st.subheader("🛠️ Modo de Organização do Dashboard")
    st.markdown("**1. Gerir Abas**")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            with st.form("add_tab_form"):
                new_tab_name = st.text_input("Nome da Nova Aba")
                if st.form_submit_button("Adicionar Aba", use_container_width=True):
                    if new_tab_name and new_tab_name not in tabs_layout:
                        tabs_layout[new_tab_name] = []; dashboard_config["tabs"] = tabs_layout
                        all_dashboards[current_project_key] = dashboard_config; save_user_dashboard(st.session_state['email'], all_dashboards); st.rerun()
                    else: st.error("Nome de aba inválido ou já existente.")
        with c2:
            with st.form("remove_tab_form"):
                tabs_to_remove = [name for name, charts in tabs_layout.items() if not charts and name != "Geral"]
                selected_tab_to_remove = st.selectbox("Remover Aba Vazia", options=[""] + tabs_to_remove, format_func=lambda x: "Selecione..." if x == "" else x)
                if st.form_submit_button("Remover Aba Selecionada", use_container_width=True, type="secondary"):
                    if selected_tab_to_remove:
                        del tabs_layout[selected_tab_to_remove]; dashboard_config["tabs"] = tabs_layout
                        all_dashboards[current_project_key] = dashboard_config; save_user_dashboard(st.session_state['email'], all_dashboards); st.rerun()
    st.divider()
    st.markdown("**2. Atribuir Gráficos às Abas**")
    new_assignments = {}
    for chart in all_charts:
        current_tab = next((tab_name for tab_name, charts in tabs_layout.items() if chart['id'] in [c['id'] for c in charts]), "Geral")
        tab_options = list(tabs_layout.keys()); default_index = tab_options.index(current_tab) if current_tab in tab_options else 0
        new_assignments[chart['id']] = st.selectbox(f"**{chart.get('title', 'Gráfico')}**:", options=tab_options, index=default_index, key=f"select_tab_{chart['id']}")
    if st.button("Salvar Organização dos Gráficos", use_container_width=True, type="primary"):
        new_tabs_layout = {tab_name: [] for tab_name in tabs_layout.keys()}
        for chart in all_charts: new_tabs_layout[new_assignments[chart['id']]].append(chart)
        dashboard_config["tabs"] = new_tabs_layout; all_dashboards[current_project_key] = dashboard_config
        save_user_dashboard(st.session_state['email'], all_dashboards); st.success("Organização do dashboard guardada!"); st.rerun()
else:
    tabs_with_charts = {name: charts for name, charts in tabs_layout.items() if charts}

# ===== PAINEL DE INSIGHTS COM IA (INTELIGENTE E CONTEXTUAL) =====
st.divider()
with st.expander("🤖 Análise com IA: Obter Insights do Dashboard"):
    
    # Verifica se o utilizador tem pelo menos uma chave de IA configurada
    has_gemini_key = 'encrypted_gemini_key' in user_data and user_data['encrypted_gemini_key']
    has_openai_key = 'encrypted_openai_key' in user_data and user_data['encrypted_openai_key']

    if not has_gemini_key and not has_openai_key:
        st.warning("Nenhuma chave de API de IA configurada.", icon="⚠️")
        st.info("Para usar esta funcionalidade, por favor, adicione a sua chave de API do Gemini ou da OpenAI na sua página de 'Minha Conta'.")
        st.page_link("pages/7_👤_Minha_Conta.py", label="Configurar Chave de IA Agora", icon="🤖")
    else:
        # Determina qual provedor de IA está ativo e se a chave correspondente existe
        ai_provider = user_data.get('ai_provider_preference', 'Google Gemini')
        provider_key_exists = (ai_provider == 'Google Gemini' and has_gemini_key) or \
                              (ai_provider == 'OpenAI (ChatGPT)' and has_openai_key)

        col1, col2 = st.columns([2, 1])
        with col1:
            st.info(f"A sua análise será gerada usando o seu provedor preferido: **{ai_provider}**.")
        
        with col2:
            if st.button(f"Gerar Insights com {ai_provider.split(' ')[0]}", use_container_width=True, type="primary", disabled=not provider_key_exists):
                st.session_state.run_ai_analysis = True
                st.session_state.provider_for_analysis = ai_provider # Guarda o provedor a ser usado

        if not provider_key_exists:
            st.error(f"Você selecionou **{ai_provider}** como seu provedor, mas nenhuma chave de API foi encontrada para ele. Por favor, adicione-a em 'Minha Conta'.", icon="🔑")

    # Lógica para executar e exibir a análise apenas quando o botão é clicado
    if st.session_state.get('run_ai_analysis', False):
        provider_to_use = st.session_state.provider_for_analysis
        with st.spinner(f"A IA ({provider_to_use}) está a analisar os seus gráficos..."):
            chart_summaries = [
                summarize_chart_data(chart, filtered_df) 
                for tab_charts in tabs_layout.values() for chart in tab_charts
            ]
            
            # --- CHAMADA CORRIGIDA ---
            # Passa o provedor escolhido como argumento para a função
            ai_analysis = get_ai_insights(st.session_state.get('project_name'), chart_summaries, provider_to_use)
            
            if ai_analysis:
                # Guarda o resultado na sessão para que não se perca
                st.session_state.ai_analysis_result = ai_analysis

        # Limpa o gatilho da análise para não re-executar
        st.session_state.run_ai_analysis = False

    # Exibe o último resultado da análise que está na memória
    if 'ai_analysis_result' in st.session_state and st.session_state.ai_analysis_result:
        st.divider()
        st.markdown("### Resumo da Análise:")
        st.markdown(st.session_state.ai_analysis_result)

    st.divider()

tabs_with_charts = {name: charts for name, charts in tabs_layout.items() if charts}
if not tabs_with_charts:
    st.info(f"O dashboard para o projeto **{st.session_state.get('project_name')}** está vazio.")
else:
    tab_names = list(tabs_with_charts.keys())
    st_tabs = st.tabs(tab_names)
    for i, tab_name in enumerate(tab_names):
        with st_tabs[i]:
            dashboard_items_in_tab = tabs_with_charts[tab_name]
            cols = st.columns(num_columns, gap="large")
            for j, chart_to_render in enumerate(dashboard_items_in_tab):
                with cols[j % num_columns]:
                    with st.container(border=True):
                        header_cols = st.columns([0.6, 0.1, 0.1, 0.1, 0.1])
                        with header_cols[0]:
                            card_title = chart_to_render.get('title', 'Visualização'); card_icon = chart_to_render.get('icon', '📊')
                            st.markdown(f"**{card_icon} {card_title}**")
                        with header_cols[1]:
                            if st.button("⬆️", key=f"up_{chart_to_render['id']}", help="Mover", disabled=(j == 0), use_container_width=True):
                                tabs_layout[tab_name] = move_item(list(dashboard_items_in_tab), j, j - 1); all_dashboards[current_project_key]["tabs"] = tabs_layout; save_user_dashboard(st.session_state['email'], all_dashboards); st.rerun()
                        with header_cols[2]:
                            if st.button("⬇️", key=f"down_{chart_to_render['id']}", help="Mover", disabled=(j == len(dashboard_items_in_tab) - 1), use_container_width=True):
                                tabs_layout[tab_name] = move_item(list(dashboard_items_in_tab), j, j + 1); all_dashboards[current_project_key]["tabs"] = tabs_layout; save_user_dashboard(st.session_state['email'], all_dashboards); st.rerun()
                        with header_cols[3]:
                            if st.button("✏️", key=f"edit_{chart_to_render['id']}", help="Editar", use_container_width=True):
                                st.session_state['chart_to_edit'] = chart_to_render; st.switch_page("pages/5_🏗️_Construir Gráficos.py")
                        with header_cols[4]:
                            if st.button("❌", key=f"del_{chart_to_render['id']}", help="Remover", use_container_width=True):
                                tabs_layout[tab_name] = [item for item in dashboard_items_in_tab if item['id'] != chart_to_render['id']]; all_dashboards[current_project_key]["tabs"] = tabs_layout; save_user_dashboard(st.session_state['email'], all_dashboards); st.rerun()
                        render_chart(chart_to_render, filtered_df)