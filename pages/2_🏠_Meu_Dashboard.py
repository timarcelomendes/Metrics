# pages/2_🏠_Meu_Dashboard.py

import streamlit as st
import pandas as pd
import os
from jira_connector import *
from metrics_calculator import *
from security import *
from utils import *
from config import *
from pathlib import Path

st.set_page_config(page_title="Meu Dashboard", page_icon="🏠", layout="wide")

# --- CSS PARA ESTILO DOS CARTÕES E ALINHAMENTO ---
st.markdown("""
<style>
/* Esta regra força os itens dentro de st.columns a alinharem-se no TOPO */
[data-testid="stHorizontalBlock"] {
    align-items: flex-start;
}
/* Estilo para o container nativo que serve como cartão */
div[data-testid="stVerticalBlock"] div.st-emotion-cache-1jicfl2 {
    background-color: #ffffff;
    border: 1px solid #e1e4e8;
    border-radius: 10px;
    box-shadow: 0 4px 8px 0 rgba(0,0,0,0.05);
    padding: 1rem;
    margin-bottom: 1rem;
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
            else: st.error("Falha na conexão com o Jira."); st.page_link("pages/7_👤_Minha_Conta.py", label="Verificar Credenciais", icon="👤"); st.stop()
    else: st.warning("Credenciais do Jira não configuradas."); st.page_link("pages/7_👤_Minha_Conta.py", label="Configurar Credenciais", icon="👤"); st.stop()

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

    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")
        
    st.header("Fonte de Dados")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    # --- LÓGICA DE PRÉ-SELEÇÃO MAIS ROBUSTA ---
    default_index = None # Inicia como None (sem seleção)
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    if last_project_key:
        # Tenta encontrar o nome do projeto correspondente à chave guardada
        project_name_map = {v: k for k, v in projects.items()}
        default_project_name = project_name_map.get(last_project_key)
        
        # Apenas define o índice se o projeto foi encontrado na lista atual
        if default_project_name in project_names:
            default_index = project_names.index(default_project_name)

    selected_project_name = st.selectbox(
        "Selecione um Projeto", options=project_names, 
        key="project_selector_dashboard", 
        index=default_index if default_index is not None else 0, # Usa o índice ou o padrão
        on_change=on_project_change,
        placeholder="Escolha um projeto..."
    )
    
    if selected_project_name:
        if st.button("Visualizar / Atualizar Dashboard", use_container_width=True, type="primary"):
            project_key = projects[selected_project_name]
            save_last_project(st.session_state['email'], project_key)
            st.session_state.project_key = project_key
            st.session_state.project_name = selected_project_name
            
            with st.spinner(f"A carregar dados do projeto '{selected_project_name}'..."):
                issues = get_all_project_issues(st.session_state.jira_client, st.session_state.project_key)
                data = []
                user_data = find_user(st.session_state['email'])
                global_configs = get_global_configs()
                project_config = get_project_config(project_key) or {}
                
                selected_standard_fields = user_data.get('standard_fields', [])
                custom_fields_to_fetch = global_configs.get('custom_fields', [])
                estimation_config = project_config.get('estimation_field', {})
                available_standard_fields_map = global_configs.get('available_standard_fields', {})
                for i in issues:
                    completion_date = find_completion_date(i)
                    issue_data = {'Issue': i.key, 'Data de Criação': pd.to_datetime(i.fields.created).tz_localize(None),'Data de Conclusão': completion_date, 'Mês de Conclusão': completion_date.strftime('%Y-%m') if completion_date else None, 'Lead Time (dias)': calculate_lead_time(i), 'Cycle Time (dias)': calculate_cycle_time(i), 'Tipo de Issue': i.fields.issuetype.name, 'Responsável': i.fields.assignee.displayName if i.fields.assignee else 'Não atribuído', 'Criado por': i.fields.reporter.displayName if i.fields.reporter else 'N/A', 'Status': i.fields.status.name, 'Prioridade': i.fields.priority.name if i.fields.priority else 'N/A', 'Labels': ', '.join(i.fields.labels) if i.fields.labels else 'Nenhum'}
                    for field_name in selected_standard_fields:
                        field_details = available_standard_fields_map.get(field_name, {})
                        field_id = field_details.get('id')
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
                        elif value is not None: issue_data[field_name] = value
                        else: issue_data[field_name] = None
                    data.append(issue_data)
                
                st.session_state.dynamic_df = pd.DataFrame(data)
                st.session_state.loaded_project_key = project_key
                st.rerun()
        if st.button("Logout", use_container_width=True, type='secondary'):
            for key in list(st.session_state.keys()): del st.session_state[key]
            st.switch_page("1_🔑_Autenticação.py")

# --- CONTEÚDO PRINCIPAL ---
df = st.session_state.get('dynamic_df')
if df is None or df.empty:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Visualizar / Atualizar Dashboard' para começar.")
    st.stop()

# --- CORREÇÃO: Define as variáveis principais aqui ---
user_data = find_user(st.session_state['email'])
all_dashboards = user_data.get('dashboard_layout', {})
current_project_key = st.session_state.get('project_key')
dashboard_items = all_dashboards.get(current_project_key, [])

# --- FILTROS GLOBAIS DO DASHBOARD ---
with st.expander("Filtros do Dashboard (afetam todas as visualizações)", expanded=True):
    filter_cols = st.columns(4)
    tipos = sorted(df['Tipo de Issue'].unique())
    resp = sorted(df['Responsável'].unique())
    stats = sorted(df['Status'].unique())
    prios = sorted(df['Prioridade'].unique())
    tipos_selecionados = filter_cols[0].multiselect("Filtrar por Tipo", options=tipos)
    responsaveis_selecionados = filter_cols[1].multiselect("Filtrar por Responsável", options=resp)
    status_selecionados = filter_cols[2].multiselect("Filtrar por Status", options=stats)
    prioridades_selecionadas = filter_cols[3].multiselect("Filtrar por Prioridade", options=prios)
    
    filtered_df = df.copy()
    if tipos_selecionados: filtered_df = filtered_df[filtered_df['Tipo de Issue'].isin(tipos_selecionados)]
    if responsaveis_selecionados: filtered_df = filtered_df[filtered_df['Responsável'].isin(responsaveis_selecionados)]
    if status_selecionados: filtered_df = filtered_df[filtered_df['Status'].isin(status_selecionados)]
    if prioridades_selecionadas: filtered_df = filtered_df[filtered_df['Prioridade'].isin(prioridades_selecionadas)]

st.caption(f"A exibir visualizações para o projeto: **{st.session_state.project_name}**.")

with st.container(border=True):
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.metric("Visualizações no Dashboard", f"{len(dashboard_items)} / 12")
    
    with col2:
        project_config = get_project_config(current_project_key) or {}
        default_cols = project_config.get('dashboard_columns', 2)

        use_two_columns = st.toggle(
            "Layout com 2 Colunas", 
            value=(default_cols == 2), 
            key="dashboard_layout_toggle",
            on_change=on_layout_change,
            help="Ative para duas colunas, desative para uma."
        )
        num_columns = 2 if use_two_columns else 1
    with col3:
        limit_reached = len(dashboard_items) >= 12
        if limit_reached: st.button("Limite Atingido", disabled=True, use_container_width=True)
        else: st.page_link("pages/5_🏗️_Construir Gráficos.py", label="➕ Adicionar Gráfico", use_container_width=True)

st.divider()

# --- EXIBIÇÃO DOS CARTÕES ---
if not dashboard_items:
    st.info(f"O dashboard para o projeto **{st.session_state.get('project_name')}** está vazio.")
    st.page_link("pages/5_🏗️_Construir Gráficos.py", label="Criar a sua primeira visualização", icon="➕")
else:
    cols = st.columns(num_columns, gap="large")
    for i, chart_to_render in enumerate(list(dashboard_items)):
        with cols[i % num_columns]:
            with st.container(border=True):
                
                # --- NOVO CABEÇALHO COM BOTÕES DE REORDENAÇÃO ---
                header_cols = st.columns([0.6, 0.1, 0.1, 0.1, 0.1])
                
                with header_cols[0]: # Título
                    card_title = chart_to_render.get('title', 'Visualização'); card_icon = chart_to_render.get('icon', '📊')
                    st.markdown(f"**{card_icon} {card_title}**")
                
                with header_cols[1]: # Seta para Cima
                    if st.button("⬆️", key=f"up_{chart_to_render['id']}", help="Mover para cima/esquerda", disabled=(i == 0), use_container_width=True):
                        new_order = move_item(list(dashboard_items), i, i - 1)
                        all_dashboards[current_project_key] = new_order
                        save_user_dashboard(st.session_state['email'], all_dashboards); st.rerun()
                
                with header_cols[2]: # Seta para Baixo
                    if st.button("⬇️", key=f"down_{chart_to_render['id']}", help="Mover para baixo/direita", disabled=(i == len(dashboard_items) - 1), use_container_width=True):
                        new_order = move_item(list(dashboard_items), i, i + 1)
                        all_dashboards[current_project_key] = new_order
                        save_user_dashboard(st.session_state['email'], all_dashboards); st.rerun()
                
                with header_cols[3]: # Editar
                    if st.button("✏️", key=f"edit_{chart_to_render['id']}", help="Editar Visualização", use_container_width=True):
                        st.session_state['chart_to_edit'] = chart_to_render
                        st.switch_page("pages/5_🏗️_Construir Gráficos.py")
                
                with header_cols[4]: # Remover
                    if st.button("❌", key=f"del_{chart_to_render['id']}", help="Remover Visualização", use_container_width=True):
                        all_dashboards[current_project_key] = [item for item in dashboard_items if item['id'] != chart_to_render['id']]
                        save_user_dashboard(st.session_state['email'], all_dashboards); st.rerun()
                
                render_chart(chart_to_render, filtered_df)