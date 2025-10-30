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
        # 1. Busca os objetos de status (que contêm .name, .id, e .statusCategory)
        statuses = get_jira_statuses(st.session_state.jira_client, project_key)
        
        if not statuses:
            st.warning("Não foi possível carregar os status do Jira para este projeto.")
            statuses = []
            
        # 2. Cria mapas de ID <-> Nome
        status_id_map = {s.id: s.name for s in statuses}
        status_name_map = {s.name: s.id for s in statuses}
        status_names_sorted = sorted(list(status_name_map.keys()))

        # --- NOVO: Extrai Categorias ---
        all_categories = []
        category_to_status_names_map = {}
        status_to_category_map = {}

        for s in statuses:
            if hasattr(s, 'statusCategory') and hasattr(s.statusCategory, 'name'):
                cat_name = s.statusCategory.name
                if cat_name not in all_categories:
                    all_categories.append(cat_name)
                
                if cat_name not in category_to_status_names_map:
                    category_to_status_names_map[cat_name] = []
                
                category_to_status_names_map[cat_name].append(s.name)
                status_to_category_map[s.name] = cat_name
            else:
                # Trata status sem categoria (raro)
                if "Não Categorizado" not in all_categories:
                    all_categories.append("Não Categorizado")
                if "Não Categorizado" not in category_to_status_names_map:
                    category_to_status_names_map["Não Categorizado"] = []
                category_to_status_names_map["Não Categorizado"].append(s.name)
                status_to_category_map[s.name] = "Não Categorizado"
        
        all_categories_sorted = sorted(all_categories)
        # --- FIM NOVO ---


        # 3. Carrega a config salva
        project_config = get_project_config(project_key) or {}
        status_mapping = project_config.get('status_mapping', {})
        
        # --- LÓGICA DE MIGRAÇÃO (MODIFICADA para incluir 'in_progress') ---
        migration_needed = False
        
        for key in ['initial', 'done', 'in_progress']: # Itera sobre todas as chaves
            config_list = status_mapping.get(key, [])
            if config_list and isinstance(config_list[0], str): # Se for formato antigo (string/nome)
                migration_needed = True
                new_data_list = [{'id': status_name_map[name], 'name': name} for name in config_list if name in status_name_map]
                project_config['status_mapping'][key] = new_data_list

        if migration_needed:
            save_project_config(project_key, project_config)
            get_project_config.clear() # Limpa o cache
            st.success("Configuração de status antiga detectada e migrada automaticamente para o novo formato de IDs!")
            project_config = get_project_config(project_key) or {} # Recarrega
            status_mapping = project_config.get('status_mapping', {})
        # --- FIM DA MIGRAÇÃO ---

        # --- Lógica de Leitura (agora lê 'in_progress' também) ---
        initial_config = status_mapping.get('initial', [])
        default_initial_names = [d['name'] for d in initial_config if isinstance(d, dict) and d.get('name') in status_name_map]

        done_config = status_mapping.get('done', [])
        default_done_names = [d['name'] for d in done_config if isinstance(d, dict) and d.get('name') in status_name_map]

        in_progress_config = status_mapping.get('in_progress', [])
        default_in_progress_names = [d['name'] for d in in_progress_config if isinstance(d, dict) and d.get('name') in status_name_map]

        ignored_config = project_config.get('ignored_statuses', [])
        default_ignored_names = [d['name'] for d in ignored_config if isinstance(d, dict) and d.get('name') in status_name_map]
        
        # Lê o modo salvo (default é 'category' se não existir)
        saved_mode = project_config.get('status_mapping_mode', 'category')
        is_manual_mode_default = (saved_mode == 'manual')

        # --- NOVO: Toggle ---
        st.markdown("---")
        is_manual_mode = st.toggle(
            "Mapear por Status individual (Modo Avançado)", 
            value=is_manual_mode_default, # O valor default é o modo que estava salvo
            key=f"manual_mapping_toggle_{project_key}",
            help="Desativado (Padrão): Mapeie por Categoria (ex: 'To Do', 'In Progress'). Ativado: Mapeie status por status (ex: 'Backlog', 'Dev', 'Test')."
        )
        st.markdown("---")


        if not is_manual_mode:
            # --- MODO CATEGORIA (NOVO) ---
            st.subheader("Mapeamento por Categoria (Padrão)")
            st.caption("Mapeie por Categoria de Status do Jira. Esta é a forma mais simples e recomendada.")
            
            # Lógica para adivinhar o default das categorias
            default_initial_cats = list(set(status_to_category_map.get(name, 'Não Categorizado') for name in default_initial_names))
            default_progress_cats = list(set(status_to_category_map.get(name, 'Não Categorizado') for name in default_in_progress_names)) 
            default_done_cats = list(set(status_to_category_map.get(name, 'Não Categorizado') for name in default_done_names))

            st.markdown("##### 🛫 Categorias Iniciais")
            st.caption("Selecione as *categorias* que representam o início do trabalho.")
            selected_initial_categories = st.multiselect("Categorias Iniciais", options=all_categories_sorted, default=default_initial_cats, label_visibility="collapsed", key=f"cat_initial_{project_key}")

            st.markdown("##### ⚙️ Categorias 'Em Andamento'")
            st.caption("Selecione as *categorias* que representam o trabalho ativo (Cycle Time).")
            selected_in_progress_categories = st.multiselect("Categorias 'Em Andamento'", options=all_categories_sorted, default=default_progress_cats, label_visibility="collapsed", key=f"cat_progress_{project_key}")

            st.markdown("##### ✅ Categorias Finais")
            st.caption("Selecione as *categorias* que representam a conclusão do trabalho.")
            selected_done_categories = st.multiselect("Categorias Finais", options=all_categories_sorted, default=default_done_cats, label_visibility="collapsed", key=f"cat_done_{project_key}")
            
        else:
            # --- MODO MANUAL (CÓDIGO EXISTENTE + 'IN_PROGRESS') ---
            st.subheader("Mapeamento Manual por Status (Avançado)")
            st.caption("Mapeie status individuais. Use se o seu fluxo não se alinha perfeitamente com as categorias do Jira.")

            st.markdown("##### 🛫 Status Iniciais")
            st.caption("Selecione os status que representam o início do trabalho.")
            selected_initial_names = st.multiselect("Status Iniciais", options=status_names_sorted, default=default_initial_names, label_visibility="collapsed", key=f"manual_initial_{project_key}")
            
            st.markdown("##### ⚙️ Status 'Em Andamento' (In Progress)")
            st.caption("Selecione os status que representam o trabalho ativo. O **Cycle Time** é medido a partir daqui.")
            selected_in_progress_names = st.multiselect("Status 'Em Andamento'", options=status_names_sorted, default=default_in_progress_names, label_visibility="collapsed", key=f"manual_progress_{project_key}")

            st.markdown("##### ✅ Status Finais")
            st.caption("Selecione os status que representam a conclusão do trabalho.")
            selected_done_names = st.multiselect("Status Finais", options=status_names_sorted, default=default_done_names, label_visibility="collapsed", key=f"manual_done_{project_key}")
        
        # --- Fim do Bloco if/else ---
        
        st.markdown("##### ❌ Status a Ignorar (Aplicado em ambos os modos)")
        st.caption("Selecione quaisquer status que devam ser completamente ignorados (ex: 'Cancelado', 'Duplicado').")
        ignored_states = st.multiselect("Status a Ignorar", options=status_names_sorted, default=default_ignored_names, label_visibility="collapsed", key=f"manual_ignore_{project_key}")

        if st.button("Salvar Mapeamento de Status", type="primary", width='stretch'):
            
            initial_states_data = []
            in_progress_states_data = []
            done_states_data = []

            if not is_manual_mode:
                # --- Lógica de Salvar (Modo Categoria) ---
                for cat_name in selected_initial_categories:
                    for status_name in category_to_status_names_map.get(cat_name, []):
                        if status_name in status_name_map: # Confirma que o status é válido
                            initial_states_data.append({'id': status_name_map[status_name], 'name': status_name})
                
                for cat_name in selected_in_progress_categories:
                    for status_name in category_to_status_names_map.get(cat_name, []):
                         if status_name in status_name_map:
                            in_progress_states_data.append({'id': status_name_map[status_name], 'name': status_name})

                for cat_name in selected_done_categories:
                    for status_name in category_to_status_names_map.get(cat_name, []):
                         if status_name in status_name_map:
                            done_states_data.append({'id': status_name_map[status_name], 'name': status_name})
            
            else:
                # --- Lógica de Salvar (Modo Manual) ---
                initial_states_data = [{'id': status_name_map[name], 'name': name} for name in selected_initial_names]
                in_progress_states_data = [{'id': status_name_map[name], 'name': name} for name in selected_in_progress_names]
                done_states_data = [{'id': status_name_map[name], 'name': name} for name in selected_done_names]

            # Salva "Ignorados" (comum aos dois modos)
            ignored_states_data = [{'id': status_name_map[name], 'name': name} for name in ignored_states]

            # Salva a configuração
            project_config['status_mapping'] = {
                'initial': initial_states_data, 
                'done': done_states_data,
                'in_progress': in_progress_states_data
            }
            project_config['ignored_statuses'] = ignored_states_data 
            
            # Salva o modo que foi usado
            project_config['status_mapping_mode'] = 'category' if not is_manual_mode else 'manual'
            
            save_project_config(project_key, project_config)
            st.success("Mapeamento de status salvo com sucesso!")
            get_project_config.clear() 
            st.rerun()

    except Exception as e:
        st.error(f"Não foi possível buscar os status do projeto no Jira: {e}")
        st.expander("Detalhes do Erro").error(e)

with tab_estimation:
    st.subheader("Configuração de Estimativa e Tempo Gasto")
    st.info("Selecione os campos que a sua equipa utiliza para estimar o esforço (Previsto) e para registrar o tempo de trabalho (Realizado).")
    
    try: 
        # 1. Carrega TODOS os campos do Jira
        all_fields = get_jira_fields(st.session_state.jira_client)
        
        # 2. Carrega as configs globais (lista de campos aprovados)
        configs = get_global_configs() 
        approved_custom_fields = configs.get('custom_fields', [])
        approved_field_ids = {f['id'] for f in approved_custom_fields}

        # --- INÍCIO DA MUDANÇA ---
        
        # 3. Cria UM dicionário mestre de opções numéricas/tempo
        master_field_options = {"Nenhum": None}

        # 4. Adiciona campos Padrão (standard)
        # (Idealmente, estes IDs viriam da config global)
        standard_ids_to_check = {
            'customfield_10020': 'standard_numeric', # Story Points (Exemplo de ID)
            'timespent': 'standard_time',           # Tempo gasto
            'timeoriginalestimate': 'standard_time' # Estimativa Original
        }

        for field in all_fields:
            field_id = field['id']
            field_name = field['name']
            
            if field_id in standard_ids_to_check:
                source_type = standard_ids_to_check[field_id]
                option_label = f"Padrão: {field_name} ({field_id})"
                if option_label not in master_field_options:
                    master_field_options[option_label] = {'name': field_name, 'id': field_id, 'source': source_type}

        # 5. Adiciona APENAS os campos personalizados APROVADOS
        for field in approved_custom_fields:
            field_name = field['name']
            field_id = field['id']
            # Garante que não estamos a adicionar duplicatas (caso um campo aprovado seja um padrão)
            option_label = f"Personalizado: {field_name} ({field_id})"
            if option_label not in master_field_options:
                # O 'source' 'custom' indica que é um campo da lista aprovada
                master_field_options[option_label] = {'name': field_name, 'id': field_id, 'source': 'custom'} 
        
        # --- FIM DA MUDANÇA ---

        # --- CAMPO DE ESTIMATIVA (PREVISTO) ---
        st.markdown("##### 🎯 Campo de Estimativa (Previsto)")
        
        # 6. Lógica do Selectbox (Usa o master_field_options)
        current_estimation_name = project_config.get('estimation_field', {}).get('name')
        estimation_selection_key = next((k for k, v in master_field_options.items() if v and v['name'] == current_estimation_name), "Nenhum")

        selected_estimation_key = st.selectbox(
            "Selecione o Campo de Estimativa",
            options=list(master_field_options.keys()),
            index=list(master_field_options.keys()).index(estimation_selection_key),
            key="estimation_selector"
        )

        if st.button("Salvar Campo de Estimativa", type="primary", width='stretch'):
            project_config['estimation_field'] = master_field_options[selected_estimation_key]
            save_project_config(project_key, project_config)
            st.success("Campo de estimativa salvo com sucesso!")
            get_project_config.clear() # Limpa cache para garantir recarregamento

        st.divider()

        # --- CAMPO DE TEMPO GASTO (REALIZADO) ---
        st.markdown("##### ⏱️ Campo de Tempo Gasto (Realizado)")
        st.caption("Selecione o campo que a sua equipa utiliza para registrar o tempo gasto (worklogs).")

        # 7. Lógica do Selectbox (Usa o MESMO master_field_options)
        current_time_selection_name = project_config.get('timespent_field', {}).get('name')
        time_selection_key = next(
            (k for k, v in master_field_options.items() if v and v['name'] == current_time_selection_name), 
            "Nenhum"
        )
        
        selected_time_field_key = st.selectbox(
            "Selecione o Campo de Tempo Gasto",
            options=list(master_field_options.keys()),
            index=list(master_field_options.keys()).index(time_selection_key),
            key="time_spent_selector"
        )
        
        if st.button("Salvar Campo de Tempo Gasto", type="primary", width='stretch', key="save_time_spent"):
            project_config['timespent_field'] = master_field_options[selected_time_field_key]
            save_project_config(project_key, project_config)
            st.success("Campo de tempo gasto salvo com sucesso!")
            get_project_config.clear() # Limpa cache

        st.divider()
        
        # --- CAMPO DE AGRUPAMENTO ESTRATÉGICO ---        
        st.markdown("###### 🎯 Campo de Agrupamento Estratégico")
        st.info("Selecione o campo que será usado para agrupar dados em visões executivas (Ex: Cliente, Produto, Squad).")
        st.caption("Nota: Este é um campo global. Os campos disponíveis aqui são ativados na página de 'Administração'.")

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
        st.error(f"Não foi possível carregar os campos de estimativa do Jira: {e}")
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