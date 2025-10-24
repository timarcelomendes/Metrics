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
configs = get_global_configs()

tab_mapping, tab_estimation, tab_time_in_status, tab_colors = st.tabs([
    "Status (Workflow)", "Estimativa", "Tempo no Status", "Cores"
])

with tab_mapping:
    st.subheader("Mapeamento de Status do Workflow")
    st.info("Para calcular métricas como Lead Time e Cycle Time, precisamos que nos ajude a entender o seu fluxo de trabalho.")
    
    try:
        # 1. Busca os objetos de status (que contêm .name e .id)
        statuses = get_jira_statuses(st.session_state.jira_client, project_key)
        
        if not statuses:
            st.warning("Não foi possível carregar os status do Jira para este projeto.")
            statuses = []
            
        # 2. Cria mapas de ID <-> Nome (para a migração e UI)
        status_id_map = {s.id: s.name for s in statuses}
        status_name_map = {s.name: s.id for s in statuses}
        status_names_sorted = sorted(list(status_name_map.keys()))

        # 3. Carrega a config salva
        project_config = get_project_config(project_key) or {}
        status_mapping = project_config.get('status_mapping', {})
        
        # --- INÍCIO DA MIGRAÇÃO AUTOMÁTICA ---
        migration_needed = False
        
        # Checa 'initial'
        initial_config = status_mapping.get('initial', [])
        if initial_config and isinstance(initial_config[0], str): # Se for formato antigo (string/nome)
            migration_needed = True
            # Converte Nomes para Dicionários (ID + Nome)
            initial_states_data = [{'id': status_name_map[name], 'name': name} for name in initial_config if name in status_name_map]
            project_config['status_mapping']['initial'] = initial_states_data

        # Checa 'done'
        done_config = status_mapping.get('done', [])
        if done_config and isinstance(done_config[0], str): # Se for formato antigo (string/nome)
            migration_needed = True
            # Converte Nomes para Dicionários (ID + Nome)
            done_states_data = [{'id': status_name_map[name], 'name': name} for name in done_config if name in status_name_map]
            project_config['status_mapping']['done'] = done_states_data

        if migration_needed:
            save_project_config(project_key, project_config)
            get_project_config.clear() # Limpa o cache
            st.success("Configuração de status antiga detectada e migrada automaticamente para o novo formato de IDs!")
            # Recarrega a config migrada
            project_config = get_project_config(project_key) or {}
            status_mapping = project_config.get('status_mapping', {})
        # --- FIM DA MIGRAÇÃO AUTOMÁTICA ---

        # --- Lógica de Leitura (agora só precisa ler o formato novo) ---
        initial_config = status_mapping.get('initial', [])
        default_initial_names = [d['name'] for d in initial_config if isinstance(d, dict) and d.get('name') in status_name_map]

        done_config = status_mapping.get('done', [])
        default_done_names = [d['name'] for d in done_config if isinstance(d, dict) and d.get('name') in status_name_map]
        
        # (O resto do código da 'tab_mapping' continua o mesmo)
        st.markdown("##### 🛫 Status Iniciais")
        st.caption("Selecione os status que representam o início do trabalho.")
        selected_initial_names = st.multiselect("Status Iniciais", options=status_names_sorted, default=default_initial_names, label_visibility="collapsed")

        st.markdown("##### ✅ Status Finais")
        st.caption("Selecione os status que representam a conclusão do trabalho.")
        selected_done_names = st.multiselect("Status Finais", options=status_names_sorted, default=default_done_names, label_visibility="collapsed")

        st.markdown("##### ❌ Status a Ignorar")
        st.caption("Selecione quaisquer status que devam ser completamente ignorados.")
        ignored_states = st.multiselect("Status a Ignorar", options=status_names_sorted, default=project_config.get('ignored_statuses', []), label_visibility="collapsed")

        if st.button("Salvar Mapeamento de Status", type="primary", width='stretch'):
            # 7. CONVERTE os nomes selecionados de volta para objetos (com ID e Nome)
            initial_states_data = [{'id': status_name_map[name], 'name': name} for name in selected_initial_names]
            done_states_data = [{'id': status_name_map[name], 'name': name} for name in selected_done_names]

            # 8. SALVA a nova estrutura (IDs e Nomes)
            project_config['status_mapping'] = {'initial': initial_states_data, 'done': done_states_data}
            project_config['ignored_statuses'] = ignored_states
            save_project_config(project_key, project_config)
            st.success("Mapeamento de status salvo com sucesso!")
            get_project_config.clear() # Limpa o cache

    except Exception as e:
        st.error(f"Não foi possível buscar os status do projeto no Jira: {e}")
        st.expander("Detalhes do Erro").error(e)

with tab_estimation:
    st.subheader("Configuração de Estimativa e Tempo Gasto")
    st.info("Selecione os campos que a sua equipa utiliza para estimar o esforço (Previsto) e para registrar o tempo de trabalho (Realizado).")
    
    try:        
        # 1. Carrega TODOS os campos do Jira (para encontrar os campos Padrão)
        all_fields = get_jira_fields(st.session_state.jira_client)
        
        # 2. Carrega as configs globais (que contêm a lista de campos aprovados)
        # (Esta linha já deve existir no topo da sua página)
        # configs = get_global_configs() 
        
        # 3. Obtém a lista de campos personalizados APROVADOS na Adm
        approved_custom_fields = configs.get('custom_fields', [])
        approved_field_ids = {f['id'] for f in approved_custom_fields}
        
        # --- CAMPO DE ESTIMATIVA (PREVISTO) ---
        st.markdown("##### 🎯 Campo de Estimativa (Previsto)")
        
        # 1. Começa o dicionário de opções
        estimation_options = {"Nenhum": None}

        # 2. Adiciona o campo Padrão de Story Points (se existir)
        sp_field = next((f for f in all_fields if f['id'] == 'customfield_10020'), None) # Assumindo ID de Story Points
        if sp_field:
            estimation_options[f"Padrão: {sp_field['name']} ({sp_field['id']})"] = {'name': sp_field['name'], 'id': sp_field['id'], 'source': 'standard_numeric'}

        # 3. Adiciona APENAS os campos personalizados APROVADOS
        for field in approved_custom_fields:
            field_name = field['name']
            field_id = field['id']
            # Garante que não estamos a adicionar duplicatas
            option_label = f"Personalizado: {field_name} ({field_id})"
            if option_label not in estimation_options:
                estimation_options[option_label] = {'name': field_name, 'id': field_id, 'source': 'custom'}
        
        # 4. Lógica do Selectbox (como antes)
        current_selection_name = project_config.get('estimation_field', {}).get('name')
        selection_key = next((k for k, v in estimation_options.items() if v and v['name'] == current_selection_name), "Nenhum")

        selected_field_key = st.selectbox(
            "Selecione o Campo de Estimativa",
            options=list(estimation_options.keys()),
            index=list(estimation_options.keys()).index(selection_key),
            key="estimation_selector"
        )

        if st.button("Salvar Campo de Estimativa", type="primary", width='stretch'):
            project_config['estimation_field'] = estimation_options[selected_field_key]
            save_project_config(project_key, project_config)
            st.success("Campo de estimativa salvo com sucesso!")

        st.divider()

        # --- CAMPO DE TEMPO GASTO (REALIZADO) ---
        st.markdown("##### ⏱️ Campo de Tempo Gasto (Realizado)")
        st.caption("Selecione o campo que a sua equipa utiliza para registrar o tempo gasto (worklogs).")

        # 1. Começa o dicionário de opções
        time_field_options = {"Nenhum": None}
        
        # 2. Adiciona campos Padrão de tempo (buscando em 'all_fields')
        for field in all_fields:
            field_id = field['id']
            field_name = field['name']
            if field_id in ['timespent', 'timeoriginalestimate', 'aggregatetimespent']:
                option_label = f"Padrão: {field_name} ({field_id})"
                time_field_options[option_label] = {'name': field_name, 'id': field_id, 'source': 'standard_time'}
        
        # 3. Adiciona APENAS os campos personalizados APROVADOS
        for field in approved_custom_fields:
            field_name = field['name']
            field_id = field['id']
            option_label = f"Personalizado: {field_name} ({field_id})"
            if option_label not in time_field_options:
                time_field_options[option_label] = {'name': field_name, 'id': field_id, 'source': 'custom'}

        # 4. Lógica do Selectbox (como antes)
        current_time_selection_name = project_config.get('timespent_field', {}).get('name')
        time_selection_key = next(
            (k for k, v in time_field_options.items() if v and v['name'] == current_time_selection_name), 
            "Nenhum"
        )
        
        selected_time_field_key = st.selectbox(
            "Selecione o Campo de Tempo Gasto",
            options=list(time_field_options.keys()),
            index=list(time_field_options.keys()).index(time_selection_key),
            key="time_spent_selector"
        )
        
        if st.button("Salvar Campo de Tempo Gasto", type="primary", width='stretch', key="save_time_spent"):
            project_config['timespent_field'] = time_field_options[selected_time_field_key]
            save_project_config(project_key, project_config)
            st.success("Campo de tempo gasto salvo com sucesso!")
        
        st.divider()
        
        # --- CAMPO DE AGRUPAMENTO ESTRATÉGICO (JÁ ESTAVA CORRETO) ---
        st.markdown("###### 🎯 Campo de Agrupamento Estratégico")
        st.info("Selecione o campo que será usado para agrupar dados em visões executivas (Ex: Cliente, Produto, Squad).")
        st.caption("Nota: Este é um campo global. Os campos disponíveis aqui são ativados na página de 'Administração'.")

        # Pega a lista de campos personalizados que já foram salvos (da config global)
        # Esta lógica já estava correta e não foi alterada
        saved_custom_fields = configs.get('custom_fields', [])
        if not isinstance(saved_custom_fields, list): saved_custom_fields = []
        
        unique_field_options = []
        field_format_map = {}
        seen_names = set() 

        for field in saved_custom_fields:
            if isinstance(field, dict) and 'name' in field and 'id' in field:
                field_name = field['name']
                field_id = field['id']
                if field_name not in seen_names:
                    unique_field_options.append(field_name)
                    field_format_map[field_name] = f"{field_name} ({field_id})"
                    seen_names.add(field_name)

        if not unique_field_options:
            st.warning("Nenhum campo personalizado foi ativado na 'Administração' global. Ative-os lá para poder selecionar um campo de agrupamento.")
        else:
            current_strategic_field = configs.get('strategic_grouping_field')
            
            try:
                default_index = unique_field_options.index(current_strategic_field) if current_strategic_field in unique_field_options else 0
            except ValueError:
                default_index = 0

            selected_field = st.selectbox(
                "Selecione o campo para agrupamento estratégico:",
                options=unique_field_options, 
                index=default_index,
                format_func=lambda name: field_format_map.get(name, name) 
            )

            if st.button("Salvar Campo Estratégico", key="save_strategic_field", width='stretch'):
                configs_to_save = get_global_configs()
                configs_to_save['strategic_grouping_field'] = selected_field
                save_global_configs(configs_to_save)
                get_global_configs.clear() 
                st.success(f"O campo '{selected_field}' foi definido como o campo de agrupamento estratégico!")
                st.session_state['global_configs'] = configs_to_save 
                st.rerun()

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