# pages/6_⚙️_Configurações.py

import streamlit as st
from security import *
from config import *
from jira_connector import *
from pathlib import Path
import pandas as pd
import uuid

st.set_page_config(page_title="Configurações", page_icon="⚙️", layout="wide")

st.header("⚙️ Configurações da Aplicação", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

st.markdown("""<style> [data-testid="stHorizontalBlock"] { align-items-center; } </style>""", unsafe_allow_html=True)

configs = st.session_state.get('global_configs', get_global_configs())
projects = st.session_state.get('projects', {})
user_data = find_user(st.session_state['email'])

def update_global_configs_and_rerun(configs_dict):
    save_global_configs(configs_dict)
    get_global_configs.clear()
    st.session_state['global_configs'] = get_global_configs()
    st.success("Configurações salvas com sucesso!")
    st.rerun()

with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(str(logo_path), size="large")
    except (FileNotFoundError, AttributeError):
        st.write("Gauge Metrics") 

    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")

    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")
        
try:
    all_statuses_from_jira = [status.name for status in get_statuses(st.session_state.jira_client)]
    all_issue_types = [it.name for it in get_issue_types(st.session_state.jira_client)]
    all_priorities = [p.name for p in get_priorities(st.session_state.jira_client)]
except Exception as e:
    st.error(f"Não foi possível carregar os metadados do Jira (status, tipos, etc.): {e}")
    all_statuses_from_jira, all_issue_types, all_priorities = [], [], []

tab_projetos, tab_campos, tab_os, tab_email = st.tabs([
    "Configurações por Projeto", 
    "Campos Globais", 
    "Ordem de Serviço", 
    "E-mail"
])

with tab_projetos:
    st.subheader("Configurações Específicas por Projeto")
    project_names = list(projects.keys())
    if not project_names:
        st.warning("Nenhum projeto encontrado.")
    else:
        selected_project_name = st.selectbox("Selecione um projeto para configurar:", options=project_names)
        project_key = projects[selected_project_name]
        project_config = get_project_config(project_key) or {}

        with st.container(border=True):
            st.markdown("🔁 **Mapeamento de Status do Workflow**")
            st.caption("Defina os status que marcam o início, o fim e os que devem ser ignorados no fluxo deste projeto.")
            status_mapping = project_config.get('status_mapping', {}); 

            if not status_mapping and all_statuses_from_jira:
                initial_suggestion = [s for s in all_statuses_from_jira if any(keyword in s.lower() for keyword in ['to do', 'a fazer', 'backlog', 'aberto', 'novo'])]
                progress_suggestion = [s for s in all_statuses_from_jira if any(keyword in s.lower() for keyword in ['em andamento', 'in progress', 'desenvolvimento'])]
                done_suggestion = [s for s in all_statuses_from_jira if any(keyword in s.lower() for keyword in ['done', 'concluído', 'pronto', 'finalizado', 'resolvido'])]
                ignored_suggestion = [s for s in all_statuses_from_jira if any(keyword in s.lower() for keyword in ['cancelado', 'cancelled'])]
            else:
                initial_suggestion = status_mapping.get('initial', [])
                progress_suggestion = status_mapping.get('in_progress', [])
                done_suggestion = status_mapping.get('done', [])
                ignored_suggestion = status_mapping.get('ignored', [])

            initial_states_str = st.text_area("Status Iniciais (separados por vírgula)", value=", ".join(initial_suggestion), key=f"initial_{project_key}")
            in_progress_states_str = st.text_area("Status 'Em Andamento' (separados por vírgula)", value=", ".join(progress_suggestion), help="Status que iniciam o Cycle Time.", key=f"progress_{project_key}")
            done_states_str = st.text_area("Status Finais (separados por vírgula)", value=", ".join(done_suggestion), key=f"done_{project_key}")
            ignored_states_str = st.text_area("Status a Ignorar (separados por vírgula)", value=", ".join(ignored_suggestion), help="Issues nestes status são excluídas.", key=f"ignored_{project_key}")

            if st.button("Salvar Mapeamento de Status", use_container_width=True, key=f"save_status_{project_key}"):
                project_config['status_mapping'] = {
                    'initial': [s.strip() for s in initial_states_str.split(',') if s.strip()],
                    'in_progress': [s.strip() for s in in_progress_states_str.split(',') if s.strip()],
                    'done': [s.strip() for s in done_states_str.split(',') if s.strip()],
                    'ignored': [s.strip() for s in ignored_states_str.split(',') if s.strip()]
                }
                save_project_config(project_key, project_config)
                st.success(f"Mapeamento de status para '{selected_project_name}' salvo com sucesso!")

        with st.container(border=True):
            st.markdown("⏱️ **Configurações de SLA (Service Level Agreement)**")
            st.caption("Crie e gira as políticas de SLA para este projeto.")
            
            if 'editing_sla_policy_id' not in st.session_state:
                st.session_state.editing_sla_policy_id = None
            
            sla_policies = project_config.get('sla_policies', [])

            with st.expander("➕ Adicionar Nova Política de SLA"):
                with st.form(f"new_sla_policy_form_{project_key}", clear_on_submit=True):
                    st.markdown("**1. Definição da Política**")
                    policy_name = st.text_input("Nome da Política*", placeholder="Ex: Bugs Críticos")
                    
                    st.markdown("**2. Escopo da Política (Quais issues serão afetadas?)**")
                    col1, col2 = st.columns(2)
                    apply_to_types = col1.multiselect("Tipos de Tarefa", options=all_issue_types, placeholder="Todos os tipos")
                    apply_to_priorities = col2.multiselect("Prioridades", options=all_priorities, placeholder="Todas as prioridades")

                    st.markdown("**3. Metas (em horas úteis)**")
                    col1, col2 = st.columns(2)
                    ttr_goal = col1.number_input("Meta de Tempo de Resolução (horas)", min_value=0, step=1)
                    tfr_goal = col2.number_input("Meta de Tempo de Primeira Resposta (horas)", min_value=0, step=1)

                    st.markdown("**4. Workflow do SLA (Como o tempo é contado?)**")
                    col1, col2, col3 = st.columns(3)
                    start_statuses = col1.multiselect("Status de Início", options=all_statuses_from_jira, help="Quando a contagem do SLA começa.")
                    pause_statuses = col2.multiselect("Status de Pausa", options=all_statuses_from_jira, help="Quando a contagem é pausada (ex: aguardando cliente).")
                    stop_statuses = col3.multiselect("Status de Fim", options=all_statuses_from_jira, help="Quando a contagem do SLA para.")
                    
                    if st.form_submit_button("Adicionar Política de SLA", type="primary"):
                        if policy_name:
                            new_policy = {
                                "id": str(uuid.uuid4()), "name": policy_name,
                                "issue_types": apply_to_types, "priorities": apply_to_priorities,
                                "resolution_hours": ttr_goal, "first_response_hours": tfr_goal,
                                "start_statuses": start_statuses, "pause_statuses": pause_statuses,
                                "stop_statuses": stop_statuses
                            }
                            sla_policies.append(new_policy)
                            project_config['sla_policies'] = sla_policies
                            save_project_config(project_key, project_config)
                            st.rerun()
                        else:
                            st.error("O nome da política é obrigatório.")
            
            st.divider()
            st.markdown("**Políticas de SLA Atuais**")
            if not sla_policies:
                st.info("Nenhuma política de SLA foi criada para este projeto.")
            else:
                for i, policy in enumerate(sla_policies):
                    if st.session_state.editing_sla_policy_id == policy['id']:
                        with st.form(f"edit_sla_form_{policy['id']}"):
                            st.subheader(f"Editando: {policy['name']}")
                            
                            edited_name = st.text_input("Nome da Política*", value=policy['name'])
                            
                            st.markdown("**Escopo**")
                            c1, c2 = st.columns(2)
                            edited_types = c1.multiselect("Tipos de Tarefa", options=all_issue_types, default=policy['issue_types'])
                            edited_priorities = c2.multiselect("Prioridades", options=all_priorities, default=policy['priorities'])

                            st.markdown("**Metas (horas)**")
                            c1, c2 = st.columns(2)
                            edited_ttr = c1.number_input("Tempo de Resolução", value=policy['resolution_hours'], min_value=0, step=1)
                            edited_tfr = c2.number_input("Tempo de Primeira Resposta", value=policy['first_response_hours'], min_value=0, step=1)

                            st.markdown("**Workflow**")
                            c1, c2, c3 = st.columns(3)
                            edited_start = c1.multiselect("Status de Início", options=all_statuses_from_jira, default=policy['start_statuses'])
                            edited_pause = c2.multiselect("Status de Pausa", options=all_statuses_from_jira, default=policy['pause_statuses'])
                            edited_stop = c3.multiselect("Status de Fim", options=all_statuses_from_jira, default=policy['stop_statuses'])

                            c1, c2 = st.columns(2)
                            if c1.form_submit_button("Salvar Alterações", use_container_width=True, type="primary"):
                                sla_policies[i] = {
                                    "id": policy['id'], "name": edited_name,
                                    "issue_types": edited_types, "priorities": edited_priorities,
                                    "resolution_hours": edited_ttr, "first_response_hours": edited_tfr,
                                    "start_statuses": edited_start, "pause_statuses": edited_pause,
                                    "stop_statuses": edited_stop
                                }
                                project_config['sla_policies'] = sla_policies
                                save_project_config(project_key, project_config)
                                st.session_state.editing_sla_policy_id = None
                                st.rerun()

                            if c2.form_submit_button("Cancelar", use_container_width=True):
                                st.session_state.editing_sla_policy_id = None
                                st.rerun()

                    else:
                        with st.container(border=True):
                            c1, c2 = st.columns([0.8, 0.2])
                            with c1:
                                st.subheader(policy['name'])
                            with c2:
                                btn_cols = st.columns(2)
                                if btn_cols[0].button("✏️", key=f"edit_sla_{policy['id']}", help="Editar Política", use_container_width=True):
                                    st.session_state.editing_sla_policy_id = policy['id']
                                    st.rerun()
                                if btn_cols[1].button("❌", key=f"del_sla_{policy['id']}", help="Remover Política", use_container_width=True):
                                    sla_policies.pop(i)
                                    project_config['sla_policies'] = sla_policies
                                    save_project_config(project_key, project_config)
                                    st.rerun()
                            
                            c1, c2 = st.columns(2)
                            c1.metric("Meta de Resolução", f"{policy['resolution_hours']} horas")
                            c2.metric("Meta de Primeira Resposta", f"{policy['first_response_hours']} horas")
                            
                            st.markdown(f"**Aplica-se a:**")
                            st.write(f"- **Tipos:** {', '.join(policy['issue_types']) if policy['issue_types'] else 'Todos'}")
                            st.write(f"- **Prioridades:** {', '.join(policy['priorities']) if policy['priorities'] else 'Todas'}")
                            
                            st.markdown(f"**Workflow:**")
                            st.write(f"- **Inicia em:** {', '.join(policy['start_statuses'])}")
                            st.write(f"- **Pausa em:** {', '.join(policy['pause_statuses'])}")
                            st.write(f"- **Termina em:** {', '.join(policy['stop_statuses'])}")
    
with tab_campos:
    st.subheader("Gerir Campos Globais para Análise")
    
    with st.spinner("A buscar todos os campos disponíveis no Jira..."):
        all_jira_fields = get_all_jira_fields(st.session_state.jira_client) 

    if not all_jira_fields:
        st.warning("Nenhum campo foi encontrado na sua instância do Jira.", icon="⚠️")
        st.info(
            """
            **Possíveis Causas:**
            * **Permissões Insuficientes:** A conexão Jira que está a usar pode não ter as permissões de administrador necessárias para listar todos os campos.
            * **Erro de Rede:** Pode ter ocorrido uma falha temporária de comunicação com o seu Jira.
            **Ação Recomendada:** Verifique se o token de API associado à sua conexão ativa tem permissões de **"Administrar o Jira"** e tente recarregar a página.
            """
        )
    else:
        standard_fields = {f['name']: f for f in all_jira_fields if not f['custom']}
        custom_fields = [f for f in all_jira_fields if f['custom']]
        
        global_configs = get_global_configs()
        saved_standard_fields = global_configs.get('available_standard_fields', {})
        
        st.markdown("---")
        st.markdown("#### Campos Padrão (Standard Fields)")
        st.caption("Selecione os campos padrão do Jira que deseja disponibilizar para análise.")
        
        valid_defaults = [field for field in saved_standard_fields.keys() if field in standard_fields]
        selected_standard_names = st.multiselect(
            "Campos Padrão", options=sorted(standard_fields.keys()),
            default=valid_defaults, label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.markdown("#### Campos Personalizados (Custom Fields)")
        st.caption("Adicione e nomeie os campos personalizados que são importantes para o seu negócio.")

        df_custom = pd.DataFrame(custom_fields)
        df_custom_to_edit = df_custom[['id', 'name']].copy()
        df_custom_to_edit.rename(columns={'id': 'ID (Não editável)', 'name': 'Nome do Campo'}, inplace=True)

        edited_custom_fields_df = st.data_editor(
            df_custom_to_edit, use_container_width=True, hide_index=True,
            column_config={
                "ID (Não editável)": st.column_config.TextColumn("ID (Não editável)", disabled=True),
                "Nome do Campo": st.column_config.TextColumn("Nome do Campo (Pode renomear)", required=True)
            }
        )
        
        st.divider()

        if st.button("Salvar Configurações de Campos Globais", type="primary", use_container_width=True):
            new_standard_fields = {name: standard_fields[name] for name in selected_standard_names}
            configs['available_standard_fields'] = new_standard_fields
            
            final_custom_list = []
            original_custom_map = {f['id']: f for f in custom_fields}
            for index, row in edited_custom_fields_df.iterrows():
                field_id = row["ID (Não editável)"]
                original_field_data = original_custom_map.get(field_id, {})
                final_custom_list.append({
                    "id": field_id,
                    "name": row["Nome do Campo"],
                    "type": original_field_data.get('type', 'Desconhecido')
                })
            configs['custom_fields'] = final_custom_list
            
            update_global_configs_and_rerun(configs)

    with tab_os:
        st.subheader("📝 Padrões da Ordem de Serviço")
        with st.container(border=True):
            st.caption("Defina os valores padrão que serão pré-preenchidos na geração de minutas de OS.")
            
            os_defaults = configs.get('os_defaults', {})
            
            gestor = st.text_input("Nome do Gestor do Contrato", value=os_defaults.get('gestor_contrato', ''))
            fornecedor = st.text_input("Dados do Fornecedor", value=os_defaults.get('fornecedor', ''))
            lider = st.text_input("Nome do Líder do Projeto (Fornecedor)", value=os_defaults.get('lider_fornecedor', ''))

            if st.button("Salvar Padrões da OS", use_container_width=True, type="primary"):
                configs['os_defaults'] = {
                    'gestor_contrato': gestor,
                    'fornecedor': fornecedor,
                    'lider_fornecedor': lider
                }
                update_global_configs_and_rerun(configs)

    with tab_projetos:
        st.subheader("Configurações Específicas por Projeto")
        project_names = list(projects.keys())
        if not project_names:
            st.warning("Nenhum projeto encontrado.")
        else:
            selected_project_name = st.selectbox(
            "Selecione um projeto para configurar:", 
            options=project_names,
            key="config_project_selector")
            project_key = projects[selected_project_name]
            project_config = get_project_config(project_key) or {}

            with st.container(border=True):
                st.markdown(f"**Campo de Estimativa para o Projeto '{selected_project_name}'**")
                st.caption("Este campo será usado para cálculos de Velocidade e Burndown/Burnup neste projeto.")
                
                custom_fields = configs.get('custom_fields', [])
                standard_fields = configs.get('available_standard_fields', {})
                numeric_fields = {field['name']: {'id': field['id'], 'source': 'custom'} for field in custom_fields if field.get('type') == 'Numérico'}
                numeric_fields.update({name: {'id': details['id'], 'source': 'standard'} for name, details in standard_fields.items() if details.get('type') == 'Numérico'})
                standard_time_fields = {"Estimativa Original (Horas)": {'id': 'timeoriginalestimate', 'source': 'standard_time'}, "Tempo Gasto (Horas)": {'id': 'timespent', 'source': 'standard_time'}}
                all_estimation_options = {**numeric_fields, **standard_time_fields}
                
                if not all_estimation_options:
                    st.warning("Nenhum campo numérico ou de tempo configurado. Adicione-os na aba 'Gestão de Campos Globais'.")
                else:
                    options = ["Nenhum (usar contagem de issues)"] + list(all_estimation_options.keys())
                    saved_field_name = project_config.get('estimation_field', {}).get('name')
                    default_index = options.index(saved_field_name) if saved_field_name in options else 0
                    selected_field_name = st.selectbox("Campo para Pontos/Estimativa:", options=options, index=default_index, key=f"select_est_{project_key}")
                    if st.button(f"Salvar Campo de Estimativa para {selected_project_name}", use_container_width=True):
                        if selected_field_name == "Nenhum (usar contagem de issues)":
                            project_config['estimation_field'] = {}
                        else:
                            project_config['estimation_field'] = {'name': selected_field_name, **all_estimation_options[selected_field_name]}
                        save_project_config(project_key, project_config)
                        st.success("Configuração do projeto guardada!"); st.rerun()
            
            with st.container(border=True):
                st.markdown(f"**Mapeamento de Datas para o Projeto '{selected_project_name}'**")
                st.caption("Defina os campos de data para 'Prevista' e 'Conclusão' usados nas métricas deste projeto.")
                
                date_mappings = project_config.get('date_mappings', {})
                all_custom_fields = configs.get('custom_fields', [])
                date_fields = {f['name']: f['id'] for f in all_custom_fields if f.get('type') == 'Data'}
                date_field_options = [""] + list(date_fields.keys())
                
                with st.form(f"date_mapping_form_{project_key}"):
                    due_date_field_name = next((name for name, id_ in date_fields.items() if id_ == date_mappings.get('due_date_field_id')), "")
                    selected_due_date = st.selectbox("Campo para 'Data Prevista'", options=date_field_options, index=date_field_options.index(due_date_field_name) if due_date_field_name else 0)

                    completion_date_field_name = next((name for name, id_ in date_fields.items() if id_ == date_mappings.get('completion_date_field_id')), "")
                    selected_completion_date = st.selectbox("Campo para 'Data de Conclusão' (Opcional)", options=date_field_options, index=date_field_options.index(completion_date_field_name) if completion_date_field_name else 0, help="Se não for selecionado, a data será calculada pelo status.")

                    if st.form_submit_button("Salvar Mapeamento de Datas", use_container_width=True):
                        project_config['date_mappings'] = {
                            'due_date_field_id': date_fields.get(selected_due_date),
                            'completion_date_field_id': date_fields.get(selected_completion_date)
                        }
                        save_project_config(project_key, project_config)
                        st.success(f"Mapeamento de datas para '{selected_project_name}' guardado!"); st.rerun()

    with tab_email:
        st.subheader("Configuração de Envio de E-mail")
        st.caption("Configure as credenciais para que a aplicação possa enviar e-mails em seu nome.")
        
        current_smtp_configs = get_smtp_configs() or {}
        current_provider = current_smtp_configs.get('provider', 'SendGrid')

        st.markdown("##### 1. Provedor de E-mail")
        provider_options = ["SendGrid", "Gmail (SMTP)"]
        provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
        email_provider = st.radio("Selecione o seu provedor:", provider_options, horizontal=True, index=provider_index)
        
        with st.form("smtp_config_form"):
            st.markdown("##### 2. Credenciais")
            
            if email_provider == 'Gmail (SMTP)':
                st.info("Para usar o Gmail, você precisa de criar uma 'app password' na sua conta. Não use a sua senha normal.")
                from_email = st.text_input("E-mail de Origem", value=current_smtp_configs.get('from_email', '') if current_provider == 'Gmail (SMTP)' else '')
                app_password = st.text_input("Senha de Aplicação (App Password)", value=current_smtp_configs.get('app_password', '') if current_provider == 'Gmail (SMTP)' else '', type="password")
                
                smtp_configs_to_save = {
                    'provider': 'Gmail (SMTP)', 'from_email': from_email, 'app_password': app_password
                }
                
            elif email_provider == 'SendGrid':
                st.info("Obtenha a sua API Key na sua conta do SendGrid.")
                from_email = st.text_input("E-mail de Origem", value=current_smtp_configs.get('from_email', '') if current_provider == 'SendGrid' else '')
                sendgrid_api_key = st.text_input("SendGrid API Key", value=current_smtp_configs.get('api_key', '') if current_provider == 'SendGrid' else '', type="password")
                
                smtp_configs_to_save = {
                    'provider': 'SendGrid', 'from_email': from_email, 'api_key': sendgrid_api_key
                }
            
            if st.form_submit_button("Salvar Credenciais", use_container_width=True, type="primary"):
                if from_email:
                    save_smtp_configs(smtp_configs_to_save)
                    st.success("Configurações de e-mail salvas com sucesso!")
                    st.session_state['smtp_configs'] = get_smtp_configs()
                    st.rerun()
                else:
                    st.error("Por favor, preencha o e-mail de origem.")