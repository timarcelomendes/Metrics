# pages/7_⚙️_Configurações.py
# (MODIFICADO para corrigir Imports, NameError, e usar funções existentes do jira_connector.py)

import streamlit as st
# --- CORREÇÃO DE IMPORT ---
# Importa apenas funções que existem no seu jira_connector.py
from jira_connector import get_jira_projects, get_jira_fields, get_jira_statuses
# --- FIM DA CORREÇÃO ---

from security import *
import pandas as pd
from config import SESSION_TIMEOUT_MINUTES
from pathlib import Path
from utils import * # Importa as funções de cache de projeto

st.set_page_config(page_title="Configurações", page_icon="⚙️", layout="wide")
st.header("⚙️ Configurações do Projeto", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente."); st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

jira_client = st.session_state['jira_client']
user_email = st.session_state['email']

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try: st.logo(str(logo_path))
    except: st.write("Gauge Metrics") 
    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.divider()

# --- Bloco de Seleção de Projeto ---
try:
    projects = st.session_state.get('projects', {})
    if not projects:
        projects = get_jira_projects(jira_client)
        st.session_state['projects'] = projects 
        
    project_names = list(projects.keys())
    
    # Tenta buscar a última seleção de projeto do usuário
    last_project_key = find_user(user_email).get('last_project_key')
    
    # Define o índice padrão baseado no último projeto, se existir
    default_index = 0
    if last_project_key and 'config_project_key' not in st.session_state:
        st.session_state['config_project_key'] = last_project_key
    
    if 'config_project_key' in st.session_state:
         default_index = project_names.index(next((name for name, key in projects.items() if key == st.session_state['config_project_key']), None))

    selected_project_name = st.selectbox(
        "Selecione o Projeto Jira para configurar:",
        options=project_names,
        index=default_index,
        key="config_project_selector",
        on_change=lambda: st.session_state.update(config_project_key=projects[st.session_state.config_project_selector])
    )
    selected_project_key = projects[selected_project_name]
    st.session_state['config_project_key'] = selected_project_key
    
except Exception as e:
    st.error(f"Não foi possível carregar os projetos do Jira. Erro: {e}")
    st.stop()


# --- Lógica Principal (só executa se um projeto foi selecionado) ---
if selected_project_key:
    # Carrega a configuração específica deste projeto
    project_config = get_project_config(selected_project_key)
    if not project_config:
        project_config = {} # Garante que é um dict

    tab_status, tab_estimativa, tab_tempo, tab_cores = st.tabs([
        "Status (Workflow)", "Estimativa", "Tempo no Status", "Cores"
    ])

    # --- ABA 1: MAPEAMENTO DE STATUS ---
    with tab_status:
        st.markdown("##### Mapeamento de Status do Workflow")
        st.info("Para calcular métricas como Lead Time e Cycle Time, precisamos que nos ajude a entender o seu fluxo de trabalho.")
        
        # Carrega os status e categorias DO JIRA (live)
        try:
            with st.spinner("Carregando status e categorias do Jira..."):
                
                # --- INÍCIO DA CORREÇÃO ---
                # 1. Carregar Status usando a função do seu jira_connector.py
                # (Isto retorna a lista de objetos de status)
                all_statuses_raw = get_jira_statuses(jira_client, selected_project_key)
                
                all_statuses_list = []
                category_names = set()
                
                # 2. Processar a lista de status para extrair nomes e categorias
                for s in all_statuses_raw:
                    try:
                        # O seu 'jira_connector.py' (linha 484) confirma que 'statusCategory' existe
                        category_name = s.statusCategory.name
                    except Exception:
                        category_name = "Sem Categoria"
                        
                    all_statuses_list.append({
                        'id': s.id, 
                        'name': s.name, 
                        'category_name': category_name
                    })
                    category_names.add(category_name)
                
                project_categories = sorted(list(category_names))
                # --- FIM DA CORREÇÃO ---

                if not all_statuses_list:
                    st.error(f"Não foi possível carregar os status do projeto '{selected_project_name}'. Verifique as permissões.")
                    st.stop()
                    
        except Exception as e:
            st.error(f"Erro ao carregar dados do workflow do Jira: {e}")
            st.stop()

        # --- Mapeamento por Categoria ---
        st.markdown("###### Mapeamento por Categoria (Padrão)")
        st.caption("Mapeie por Categoria de Status do Jira. Esta é a forma mais simples e recomendada.")
        
        with st.form("category_mapping_form"):
            
            # Carrega os mapeamentos *atuais* salvos no config
            current_mapping_cat = project_config.get('status_category_mapping', {})
            
            initial_defaults_cat = current_mapping_cat.get('initial', ['Itens Pendentes']) # Default para 'To Do'
            inprogress_defaults_cat = current_mapping_cat.get('in_progress', ['Em andamento']) # Default para 'In Progress'
            done_defaults_cat = current_mapping_cat.get('done', ['Itens concluídos']) # Default para 'Done'

            st.multiselect(
                "🛫 Categorias Iniciais",
                options=project_categories,
                default=initial_defaults_cat,
                key="map_cat_initial",
                help="Selecione as *categorias* que representam o início do trabalho (ex: 'Itens Pendentes')."
            )
            st.multiselect(
                "⚙️ Categorias 'Em Andamento'",
                options=project_categories,
                default=inprogress_defaults_cat,
                key="map_cat_inprogress",
                help="Selecione as *categorias* que representam o trabalho ativo (ex: 'Em andamento')."
            )
            st.multiselect(
                "✅ Categorias Finais",
                options=project_categories,
                default=done_defaults_cat,
                key="map_cat_done",
                help="Selecione as *categorias* que representam a conclusão do trabalho (ex: 'Itens concluídos')."
            )
            
            st.divider()
            
            # --- Status a Ignorar (Comum aos dois modos) ---
            st.markdown("###### ❌ Status a Ignorar (Aplicado em ambos os modos)")
            st.caption("Selecione quaisquer status que devam ser completamente ignorados (ex: 'Cancelado', 'Duplicado').")
            
            all_status_names = sorted(list(set(s['name'] for s in all_statuses_list)))
            ignored_defaults = project_config.get('ignored_statuses', [])

            st.multiselect(
                "Status a Ignorar",
                options=all_status_names,
                default=ignored_defaults,
                key="map_status_ignored",
                help="Issues com este status não aparecerão em *nenhum* cálculo."
            )

            if st.form_submit_button("Salvar Mapeamento por Categoria", use_container_width=True, type="primary"):
                # Carrega os valores dos widgets
                new_initial_cat = st.session_state.map_cat_initial
                new_inprogress_cat = st.session_state.map_cat_inprogress
                new_done_cat = st.session_state.map_cat_done # <-- O valor "Categorias Finais" é lido
                new_ignored_status = st.session_state.map_status_ignored 
                
                # --- CORREÇÃO DO BUG DE SALVAMENTO ---
                project_config['status_category_mapping'] = {
                    'initial': new_initial_cat,
                    'in_progress': new_inprogress_cat,
                    'done': new_done_cat # <-- CORRIGIDO (estava 'new_initial_cat')
                }
                # --- FIM DA CORREÇÃO ---
                
                project_config['ignored_statuses'] = new_ignored_status
                
                # Limpa o mapeamento antigo (por ID) para garantir que o de categoria seja usado
                if 'status_mapping' in project_config:
                    del project_config['status_mapping']
                    
                save_project_config(selected_project_key, project_config)
                # Limpa os caches relacionados
                get_project_config.clear()
                load_and_process_project_data.clear()
                
                st.success("Mapeamento por categoria salvo com sucesso!")
                st.rerun()

        st.divider()
        
        # --- Mapeamento por Status (Avançado) ---
        st.markdown("###### Mapeamento por Status (Avançado)")
        st.caption("Mapeie status individuais. Use se as categorias do Jira não forem suficientes.")
        
        with st.form("status_mapping_form"):
            
            # Carrega os mapeamentos *atuais* (baseados em ID)
            current_mapping = project_config.get('status_mapping', {})
            
            # --- INÍCIO DA CORREÇÃO (Bug 'item' is not defined) ---
            def get_names_from_ids(id_list, all_statuses):
                """Converte a lista de IDs/Nomes/Dicts salvos de volta para Nomes."""
                if not isinstance(id_list, list): 
                    return []
                
                saved_names = []
                for item in id_list:
                    if isinstance(item, str):
                        # Formato antigo (salvava o nome)
                        saved_names.append(item)
                    elif isinstance(item, dict) and 'name' in item:
                        # Formato novo (salvava dict)
                        saved_names.append(item['name'])
                
                # Filtra para garantir que os nomes ainda existem no Jira
                current_status_names = {s['name'] for s in all_statuses}
                return [name for name in saved_names if name in current_status_names]
            # --- FIM DA CORREÇÃO ---

            initial_defaults = get_names_from_ids(current_mapping.get('initial', []), all_statuses_list)
            inprogress_defaults = get_names_from_ids(current_mapping.get('in_progress', []), all_statuses_list)
            done_defaults = get_names_from_ids(current_mapping.get('done', []), all_statuses_list)

            st.multiselect(
                "🛫 Status Iniciais (ex: Backlog, To Do)",
                options=all_status_names,
                default=initial_defaults,
                key="map_status_initial"
            )
            st.multiselect(
                "⚙️ Status 'Em Andamento' (ex: Em Desenvolvimento, Em Teste)",
                options=all_status_names,
                default=inprogress_defaults,
                key="map_status_inprogress"
            )
            st.multiselect(
                "✅ Status Finais (ex: Concluído, Done)",
                options=all_status_names,
                default=done_defaults,
                key="map_status_done"
            )
            
            if st.form_submit_button("Salvar Mapeamento por Status (Avançado)", use_container_width=True, type="secondary"):
                
                def get_status_objects(name_list, all_statuses):
                    """Converte a lista de nomes selecionada em lista de dicts {'id':, 'name':}"""
                    return [
                        {'id': s['id'], 'name': s['name']} 
                        for s in all_statuses 
                        if s['name'] in name_list
                    ]

                new_initial = get_status_objects(st.session_state.map_status_initial, all_statuses_list)
                new_inprogress = get_status_objects(st.session_state.map_status_inprogress, all_statuses_list)
                new_done = get_status_objects(st.session_state.map_status_done, all_statuses_list)
                # O 'ignored' já é salvo no formulário de cima, mas podemos salvar aqui também por segurança
                new_ignored_status = st.session_state.map_status_ignored 

                project_config['status_mapping'] = {
                    'initial': new_initial,
                    'in_progress': new_inprogress,
                    'done': new_done
                }
                project_config['ignored_statuses'] = new_ignored_status
                
                # Limpa o mapeamento por categoria para garantir que o por status seja usado
                if 'status_category_mapping' in project_config:
                    del project_config['status_category_mapping']

                save_project_config(selected_project_key, project_config)
                # Limpa os caches relacionados
                get_project_config.clear()
                load_and_process_project_data.clear()
                
                st.success("Mapeamento por status (avançado) salvo com sucesso!")
                st.rerun()

    # --- ABA 2: ESTIMATIVA ---
    with tab_estimativa:
        st.markdown("##### Configuração de Estimativa")
        st.info("Selecione o campo que seu time usa para estimar o tamanho das issues (ex: Story Points ou Horas).")
        
        try:
            with st.spinner("Carregando campos de estimativa..."):
                all_fields = get_jira_fields(jira_client) # Usa a função que existe
                # Filtra apenas campos numéricos (float ou int)
                numeric_fields = [
                    f for f in all_fields 
                    if f.get('schema', {}).get('type') in ['number', 'float'] 
                    and f['id'].startswith('customfield_')
                ]
                
                # Adiciona os campos padrão de tempo
                standard_time_fields = [
                    {'id': 'timeoriginalestimate', 'name': 'Original Estimate (Horas)'},
                    {'id': 'timeestimate', 'name': 'Remaining Estimate (Horas)'},
                ]
                
                all_estimation_fields = standard_time_fields + numeric_fields
                field_map = {f['id']: f['name'] for f in all_estimation_fields}
                
        except Exception as e:
            st.error(f"Erro ao carregar campos do Jira: {e}")
            all_estimation_fields = []
            field_map = {}

        current_estimation_config = project_config.get('estimation_field', {})
        current_field_id = current_estimation_config.get('id', None)
        
        default_index = 0
        if current_field_id:
            try:
                default_index = list(field_map.keys()).index(current_field_id)
            except ValueError:
                default_index = 0 # O campo salvo não está mais disponível

        if not field_map:
             st.warning("Nenhum campo numérico (custom field) ou de tempo (standard) encontrado.")
        else:
            with st.form("estimation_form"):
                selected_field_id = st.selectbox(
                    "Campo de Estimativa Padrão",
                    options=list(field_map.keys()),
                    format_func=lambda x: field_map.get(x, "Desconhecido"),
                    index=default_index,
                    help="Selecione o campo usado para 'Story Points' ou 'Horas Estimadas'."
                )
                
                if st.form_submit_button("Salvar Configuração de Estimativa", type="primary"):
                    selected_name = field_map[selected_field_id]
                    source = 'standard_time' if selected_field_id in ['timeoriginalestimate', 'timeestimate'] else 'custom_field'
                    
                    project_config['estimation_field'] = {
                        'id': selected_field_id,
                        'name': selected_name,
                        'source': source
                    }
                    save_project_config(selected_project_key, project_config)
                    get_project_config.clear()
                    st.success(f"Campo de estimativa '{selected_name}' salvo com sucesso!")
                    st.rerun()

    # --- ABA 3: TEMPO NO STATUS ---
    with tab_tempo:
        st.markdown("##### Tempo no Status (Time in Status)")
        st.info("Ative esta opção para calcular o 'Tempo em cada Status' nas Métricas de Fluxo. (Pode deixar o carregamento mais lento)")

        with st.form("time_in_status_form"):
            calc_time_in_status = st.checkbox(
                "Calcular 'Tempo no Status'",
                value=project_config.get('calculate_time_in_status', False),
                help="Se ativado, o sistema irá calcular o tempo gasto em cada etapa do workflow para cada issue."
            )
            
            if st.form_submit_button("Salvar Configuração", type="primary"):
                project_config['calculate_time_in_status'] = calc_time_in_status
                save_project_config(selected_project_key, project_config)
                get_project_config.clear()
                st.success("Configuração de 'Tempo no Status' salva!")
                st.rerun()

    # --- ABA 4: CORES ---
    with tab_cores:
        st.markdown("##### Configuração de Cores (Em breve)")
        st.info("Personalize as cores dos gráficos para este projeto.")
        st.image("https://i.imgur.com/g2sKjEw.png", caption="Funcionalidade em desenvolvimento")

else:
    st.info("Selecione um projeto na barra lateral para começar a configurar.")