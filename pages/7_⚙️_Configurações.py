# pages/7_⚙️_Configuracoes.py

import streamlit as st
from pathlib import Path
from security import *
from config import *
import pandas as pd
from jira_connector import get_jira_statuses, get_project_issue_types, get_jira_fields

st.set_page_config(page_title="Configurações do Projeto", page_icon="⚙️", layout="wide")

# --- BLOCO DE AUTENTICAÇÃO E CONEXÃO ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(str(logo_path), size="large")
    except (FileNotFoundError, AttributeError):
        st.write("Gauge Metrics")
    
    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")

    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and last_project_key in projects.values() else 0

    selected_project_name = st.selectbox(
        "Selecione o Projeto para Configurar:",
        options=project_names,
        key="project_selector_config",
        index=default_index,
        placeholder="Escolha um projeto..."
    )

    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]
        st.session_state.project_name = selected_project_name

    if st.button("Logout", width='stretch', type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- Interface Principal ---
if 'project_key' not in st.session_state:
    st.info("⬅️ Por favor, selecione um projeto na barra lateral para começar.")
    st.stop()

project_key = st.session_state.project_key
st.header(f"⚙️ Configurações do Projeto: **{st.session_state.project_name}**", divider='rainbow')

# Carrega ambas as configurações: a específica do projeto e as globais
project_config = get_project_config(project_key) or {}
configs = get_global_configs() # <-- ADICIONADO PARA O CAMPO ESTRATÉGICO

tab_mapping, tab_estimation, tab_time_in_status, tab_colors = st.tabs([
    "Status (Workflow)", "Estimativa", "Tempo no Status", "Cores"
])

with tab_mapping:
    st.subheader("Mapeamento de Status do Workflow")
    st.info("Para calcular métricas como Lead Time e Cycle Time, precisamos que nos ajude a entender o seu fluxo de trabalho.")
    
    try:
        statuses = get_jira_statuses(st.session_state.jira_client, project_key)
        status_names = sorted(list(set([status.name for status in statuses])))
        status_mapping = project_config.get('status_mapping', {})

        st.markdown("##### 🛫 Status Iniciais")
        st.caption("Selecione os status que representam o início do trabalho (quando o 'relógio' do Cycle Time começa a contar).")
        initial_states = st.multiselect("Status Iniciais", options=status_names, default=status_mapping.get('initial', []), label_visibility="collapsed")

        st.markdown("##### ✅ Status Finais")
        st.caption("Selecione os status que representam a conclusão do trabalho (quando o 'relógio' do Lead Time e Cycle Time para).")
        done_states = st.multiselect("Status Finais", options=status_names, default=status_mapping.get('done', []), label_visibility="collapsed")

        st.markdown("##### ❌ Status a Ignorar")
        st.caption("Selecione quaisquer status que devam ser completamente ignorados nos cálculos (ex: Cancelado, Duplicado).")
        ignored_states = st.multiselect("Status a Ignorar", options=status_names, default=project_config.get('ignored_statuses', []), label_visibility="collapsed")

        if st.button("Salvar Mapeamento de Status", type="primary", width='stretch'):
            project_config['status_mapping'] = {'initial': initial_states, 'done': done_states}
            project_config['ignored_statuses'] = ignored_states
            save_project_config(project_key, project_config)
            st.success("Mapeamento de status salvo com sucesso!")

    except Exception as e:
        st.error(f"Não foi possível buscar os status do projeto no Jira. Verifique a conexão e as permissões.")
        st.expander("Detalhes do Erro").error(e)

with tab_estimation:
    st.subheader("Configuração de Estimativa")
    st.info("Selecione o campo que a sua equipa utiliza para estimar o tamanho ou esforço das tarefas (issues).")
    
    try:
        all_fields = get_jira_fields(st.session_state.jira_client)
        custom_fields = [{'name': f['name'], 'id': f['id']} for f in all_fields if f.get('custom', False)]
        
        field_options = {"Nenhum": None}
        sp_field = next((f for f in all_fields if f['id'] == 'customfield_10020'), None) # Assumindo ID de Story Points
        if sp_field:
            field_options[f"Padrão: {sp_field['name']} ({sp_field['id']})"] = {'name': sp_field['name'], 'id': sp_field['id'], 'source': 'standard_numeric'}
        
        for field in custom_fields:
             field_options[f"Personalizado: {field['name']} ({field['id']})"] = {'name': field['name'], 'id': field['id'], 'source': 'custom'}

        current_selection_name = project_config.get('estimation_field', {}).get('name')
        selection_key = next((k for k, v in field_options.items() if v and v['name'] == current_selection_name), "Nenhum")

        selected_field_key = st.selectbox(
            "Selecione o Campo de Estimativa",
            options=list(field_options.keys()),
            index=list(field_options.keys()).index(selection_key)
        )

        if st.button("Salvar Campo de Estimativa", type="primary", width='stretch'):
            project_config['estimation_field'] = field_options[selected_field_key]
            save_project_config(project_key, project_config)
            st.success("Campo de estimativa salvo com sucesso!")

        # --- INÍCIO DO CÓDIGO MOVIDO ---
        st.divider()
        
        st.markdown("###### 🎯 Campo de Agrupamento Estratégico")
        st.info("Selecione o campo que será usado para agrupar dados em visões executivas (Ex: Cliente, Produto, Squad).")
        st.caption("Nota: Este é um campo global. Os campos disponíveis aqui são ativados na página de 'Administração'.")

        # Pega a lista de campos personalizados que já foram salvos (da config global)
        saved_custom_fields = configs.get('custom_fields', [])
        if not isinstance(saved_custom_fields, list): saved_custom_fields = []
        
        field_options_strategic = []
        field_format_map = {}
        
        for field in saved_custom_fields:
            if isinstance(field, dict) and 'name' in field and 'id' in field:
                field_options_strategic.append(field['name'])
                field_format_map[field['name']] = f"{field['name']} ({field['id']})"
        
        if not field_options_strategic:
            st.warning("Nenhum campo personalizado foi ativado na 'Administração' global. Ative-os lá para poder selecionar um campo de agrupamento.")
        else:
            current_strategic_field = configs.get('strategic_grouping_field')
            
            try:
                default_index = field_options_strategic.index(current_strategic_field) if current_strategic_field in field_options_strategic else 0
            except ValueError:
                default_index = 0

            selected_field = st.selectbox(
                "Selecione o campo para agrupamento estratégico:",
                options=field_options_strategic,
                index=default_index,
                format_func=lambda name: field_format_map.get(name, name)
            )

            if st.button("Salvar Campo Estratégico", key="save_strategic_field", width='stretch'):
                configs_to_save = get_global_configs()
                configs_to_save['strategic_grouping_field'] = selected_field
                save_global_configs(configs_to_save)
                get_global_configs.clear()
                st.success(f"O campo '{selected_field}' foi definido como o campo de agrupamento estratégico!")
                st.rerun()
        # --- FIM DO CÓDIGO MOVIDO ---

    except Exception as e:
        st.error("Não foi possível carregar os campos de estimativa do Jira.")
        st.expander("Detalhes do Erro").error(e)


with tab_time_in_status:
    st.subheader("Cálculo de Tempo por Status")
    st.info("Ative esta opção para que a aplicação calcule o tempo que cada issue permaneceu em cada status do workflow.")
    calculate_time = st.toggle("Ativar cálculo de tempo por status", value=project_config.get('calculate_time_in_status', False))
    if st.button("Salvar Configuração de Tempo", type="primary", width='stretch'):
        project_config['calculate_time_in_status'] = calculate_time
        save_project_config(project_key, project_config)
        st.success("Configuração de cálculo de tempo salva com sucesso!")

with tab_colors:
    st.subheader("Personalização de Cores dos Gráficos")
    st.info("Personalize as cores associadas aos Status e Tipos de Issue para os seus gráficos.")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### 🎨 Cores por Status")
        status_colors = project_config.get('status_colors', DEFAULT_COLORS['status_colors']).copy()
        try:
            statuses = get_jira_statuses(st.session_state.jira_client, project_key)
            if statuses:
                status_names = sorted(list(set([status.name for status in statuses])))
                for status_name in status_names:
                    status_colors[status_name] = st.color_picker(
                        f"Cor para '{status_name}'", 
                        value=status_colors.get(status_name, "#000000"), 
                        key=f"status_color_{status_name}"
                    )
            else:
                st.warning("Nenhum status foi encontrado para este projeto no Jira.")
        except Exception as e:
            st.error(f"Ocorreu um erro ao processar os status.")
            st.expander("Detalhes do Erro").error(e)

    with col2:
        st.markdown("##### 🎨 Cores por Tipo de Issue")
        type_colors = project_config.get('type_colors', DEFAULT_COLORS['type_colors']).copy()
        try:
            issue_types = get_project_issue_types(st.session_state.jira_client, project_key)
            if issue_types:
                type_names = sorted(list(set([it.name for it in issue_types])))
                for type_name in type_names:
                    type_colors[type_name] = st.color_picker(
                        f"Cor para '{type_name}'", 
                        value=type_colors.get(type_name, "#000000"), 
                        key=f"type_color_{type_name}"
                    )
            else:
                st.warning("Nenhum tipo de issue foi encontrado para este projeto no Jira.")
        except Exception as e:
            st.error(f"Ocorreu um erro ao processar os tipos de issue.")
            st.expander("Detalhes do Erro").error(e)

    if st.button("Salvar Cores Personalizadas", type="primary", width='stretch'):
        project_config['status_colors'] = status_colors
        project_config['type_colors'] = type_colors
        save_project_config(project_key, project_config)
        st.success("Cores personalizadas salvas com sucesso!")