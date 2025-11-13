# pages/7_⚙️_Configurações.py
# (MODIFICADO para corrigir a lógica de 'Controle de tempo')

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
user_email = st.session_state['email'] # <-- Email do usuário já está aqui

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
        "Status (Workflow)", "Estimativa e Esforço", "Tempo no Status", "Cores" 
    ])

    # --- ABA 1: MAPEAMENTO DE STATUS ---
    with tab_status:
        st.markdown("##### Mapeamento de Status do Workflow")
        st.info("Para calcular métricas como Lead Time e Cycle Time, precisamos que nos ajude a entender o seu fluxo de trabalho.")
        
        # Carrega os status e categorias DO JIRA (live)
        try:
            with st.spinner("Carregando status e categorias do Jira..."):
                
                all_statuses_raw = get_jira_statuses(jira_client, selected_project_key)
                
                all_statuses_list = []
                category_names = set()
                
                for s in all_statuses_raw:
                    try:
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
            
            current_mapping_cat = project_config.get('status_category_mapping', {})
            
            initial_defaults_cat = current_mapping_cat.get('initial', ['Itens Pendentes'])
            inprogress_defaults_cat = current_mapping_cat.get('in_progress', ['Em andamento'])
            done_defaults_cat = current_mapping_cat.get('done', ['Itens concluídos'])

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
                new_initial_cat = st.session_state.map_cat_initial
                new_inprogress_cat = st.session_state.map_cat_inprogress
                new_done_cat = st.session_state.map_cat_done
                new_ignored_status = st.session_state.map_status_ignored 
                
                project_config['status_category_mapping'] = {
                    'initial': new_initial_cat,
                    'in_progress': new_inprogress_cat,
                    'done': new_done_cat
                }
                
                project_config['ignored_statuses'] = new_ignored_status
                
                if 'status_mapping' in project_config:
                    del project_config['status_mapping']
                    
                save_project_config(selected_project_key, project_config)
                get_project_config.clear()
                load_and_process_project_data.clear()
                
                st.success("Mapeamento por categoria salvo com sucesso!")
                st.rerun()

        st.divider()
        
        # --- Mapeamento por Status (Avançado) ---
        st.markdown("###### Mapeamento por Status (Avançado)")
        st.caption("Mapeie status individuais. Use se as categorias do Jira não forem suficientes.")
        
        with st.form("status_mapping_form"):
            
            current_mapping = project_config.get('status_mapping', {})
            
            def get_names_from_ids(id_list, all_statuses):
                """Converte a lista de IDs/Nomes/Dicts salvos de volta para Nomes."""
                if not isinstance(id_list, list): 
                    return []
                
                saved_names = []
                for item in id_list:
                    if isinstance(item, str):
                        saved_names.append(item)
                    elif isinstance(item, dict) and 'name' in item:
                        saved_names.append(item['name'])
                
                current_status_names = {s['name'] for s in all_statuses}
                return [name for name in saved_names if name in current_status_names]

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
                new_ignored_status = st.session_state.map_status_ignored 

                project_config['status_mapping'] = {
                    'initial': new_initial,
                    'in_progress': new_inprogress,
                    'done': new_done
                }
                project_config['ignored_statuses'] = new_ignored_status
                
                if 'status_category_mapping' in project_config:
                    del project_config['status_category_mapping']

                save_project_config(selected_project_key, project_config)
                get_project_config.clear()
                load_and_process_project_data.clear()
                
                st.success("Mapeamento por status (avançado) salvo com sucesso!")
                st.rerun()

    # --- ABA 2: ESTIMATIVA E ESFORÇO ---
    with tab_estimativa:
        st.markdown("##### Configuração de Estimativa (Previsto) e Esforço (Realizado)")
        st.info("Selecione os campos que seu time usa para 'Estimativa' (ex: Story Points ou Horas) e 'Tempo Gasto' (ex: Time Spent).")
        st.caption("ℹ️ Apenas os campos que você **habilitou** na página 'Minha Conta' aparecerão aqui.")
        
        try:
            # --- INÍCIO DA MODIFICAÇÃO (FILTRO POR CONTA) ---
            with st.spinner("Carregando e filtrando campos habilitados..."):
                # 1. Obter TODOS os campos do Jira (para mapear Nomes <-> IDs)
                all_jira_fields = get_jira_fields(jira_client)
                
                # 2. Obter a configuração do USUÁRIO ATUAL
                user_data = find_user(user_email) 
                enabled_standard_ids = user_data.get('standard_fields', [])
                enabled_custom_names = user_data.get('enabled_custom_fields', [])
                
                # 3. Criar um mapa de Nomes de campos custom para IDs
                custom_name_to_id_map = {
                    f['name']: f['id'] 
                    for f in all_jira_fields 
                    if f['id'].startswith('customfield_') and 'name' in f
                }
                
                # 4. Converter os Nomes custom habilitados em IDs
                enabled_custom_ids = [
                    custom_name_to_id_map.get(name) 
                    for name in enabled_custom_names 
                    if custom_name_to_id_map.get(name)
                ]
                
                # 5. Criar um CONJUNTO (set) final com TODOS os IDs habilitados
                all_enabled_ids = set(enabled_standard_ids + enabled_custom_ids)
                
                # --- INÍCIO DA NOVA CORREÇÃO ---
                # Se o usuário ativou "Controle de tempo" (cujo ID é 'timetracking'),
                # devemos adicionar explicitamente os campos de tempo individuais
                # para que eles apareçam nos seletores.
                if 'timetracking' in all_enabled_ids:
                    all_enabled_ids.add('timespent')
                    all_enabled_ids.add('timeoriginalestimate')
                    all_enabled_ids.add('timeestimate')
                # --- FIM DA NOVA CORREÇÃO ---

                # 6. Filtrar a lista de 'numeric_fields'
                # Apenas campos numéricos que TAMBÉM estão na lista de habilitados
                numeric_fields = [
                    f for f in all_jira_fields 
                    if f.get('schema', {}).get('type') in ['number', 'float'] 
                    and f['id'].startswith('customfield_')
                    and f['id'] in all_enabled_ids # <-- O FILTRO PRINCIPAL
                ]
                
                # 7. Definir e Filtrar os campos padrão (standard)
                
                # Campos Padrão para "Previsto"
                standard_previsto_fields_all = [
                    {'id': 'timeoriginalestimate', 'name': 'Original Estimate (Horas)'},
                    {'id': 'timeestimate', 'name': 'Remaining Estimate (Horas)'},
                ]
                filtered_standard_previsto = [
                    f for f in standard_previsto_fields_all if f['id'] in all_enabled_ids
                ]

                # Campos Padrão para "Realizado"
                standard_realizado_fields_all = [
                    {'id': 'timespent', 'name': 'Time Spent (Horas)'},
                ]
                filtered_standard_realizado = [
                    f for f in standard_realizado_fields_all if f['id'] in all_enabled_ids
                ]

                # 8. Construir as listas finais e os mapas
                # 'numeric_fields' já está filtrada
                all_previsto_fields = filtered_standard_previsto + numeric_fields
                previsto_field_map = {f['id']: f['name'] for f in all_previsto_fields}

                all_realizado_fields = filtered_standard_realizado + numeric_fields
                realizado_field_map = {f['id']: f['name'] for f in all_realizado_fields}
            # --- FIM DA MODIFICAÇÃO (FILTRO POR CONTA) ---
                
        except Exception as e:
            st.error(f"Erro ao carregar campos do Jira: {e}")
            previsto_field_map = {}
            realizado_field_map = {}

        # Carrega a config ATUAL para "Previsto"
        current_estimation_config = project_config.get('estimation_field', {})
        current_estim_field_id = current_estimation_config.get('id', None)
        default_estim_index = 0
        if current_estim_field_id and current_estim_field_id in previsto_field_map:
            try:
                default_estim_index = list(previsto_field_map.keys()).index(current_estim_field_id)
            except ValueError:
                default_estim_index = 0 

        # Carrega a config ATUAL para "Realizado"
        current_timespent_config = project_config.get('timespent_field', {})
        current_spent_field_id = current_timespent_config.get('id', None)
        default_spent_index = 0
        if current_spent_field_id and current_spent_field_id in realizado_field_map:
            try:
                default_spent_index = list(realizado_field_map.keys()).index(current_spent_field_id)
            except ValueError:
                default_spent_index = 0

        # Modificado para verificar se AMBOS os mapas estão vazios
        if not previsto_field_map and not realizado_field_map:
             st.warning("Nenhum campo de estimativa ou tempo foi habilitado na sua página 'Minha Conta'.")
             st.info("Por favor, vá até 'Minha Conta' -> 'Jira: Campos Dinâmicos' e ative os campos que deseja usar (ex: 'Controle de tempo', 'Story point estimate').")
        else:
            with st.form("effort_form"): 
                st.markdown("###### 1. Campo de Esforço Previsto (Estimativa)")
                selected_estim_field_id = st.selectbox(
                    "Campo de Estimativa (Previsto)",
                    options=list(previsto_field_map.keys()),
                    format_func=lambda x: previsto_field_map.get(x, "Desconhecido"),
                    index=default_estim_index,
                    help="Selecione o campo usado para 'Story Points' ou 'Horas Estimadas'."
                )
                
                st.markdown("###### 2. Campo de Esforço Realizado (Tempo Gasto)")
                selected_spent_field_id = st.selectbox(
                    "Campo de Tempo Gasto (Realizado)",
                    options=list(realizado_field_map.keys()),
                    format_func=lambda x: realizado_field_map.get(x, "Desconhecido"),
                    index=default_spent_index,
                    help="Selecione o campo usado para 'Time Spent' (Horas) ou um campo numérico equivalente."
                )
                
                st.divider()
                
                if st.form_submit_button("Salvar Configurações de Esforço", type="primary"):
                    
                    # Lógica para o campo "Previsto"
                    if selected_estim_field_id:
                        selected_estim_name = previsto_field_map[selected_estim_field_id]
                        estim_source = 'standard_time' if selected_estim_field_id in ['timeoriginalestimate', 'timeestimate'] else 'custom_field'
                        
                        project_config['estimation_field'] = {
                            'id': selected_estim_field_id,
                            'name': selected_estim_name,
                            'source': estim_source
                        }
                    else:
                        project_config['estimation_field'] = {} # Salva como vazio se nada for selecionado
                    
                    # Lógica para o campo "Realizado"
                    if selected_spent_field_id:
                        selected_spent_name = realizado_field_map[selected_spent_field_id]
                        spent_source = 'standard_time' if selected_spent_field_id == 'timespent' else 'custom_field'
                        
                        project_config['timespent_field'] = {
                            'id': selected_spent_field_id,
                            'name': selected_spent_name,
                            'source': spent_source
                        }
                    else:
                         project_config['timespent_field'] = {} # Salva como vazio

                    save_project_config(selected_project_key, project_config)
                    get_project_config.clear()
                    load_and_process_project_data.clear()
                    st.success(f"Configurações de esforço (Previsto e Realizado) salvas com sucesso!")
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