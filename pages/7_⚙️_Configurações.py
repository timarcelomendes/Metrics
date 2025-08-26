# pages/6_⚙️_Configurações.py

import streamlit as st
from security import *
from config import *
from jira_connector import *
from pathlib import Path
from security import *


st.set_page_config(page_title="Configurações", page_icon="⚙️", layout="wide")

st.markdown("""<style> [data-testid="stHorizontalBlock"] { align-items: center; } </style>""", unsafe_allow_html=True)
st.header("⚙️ Configurações da Aplicação", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    # Verifica se o utilizador tem alguma conexão guardada na base de dados
    user_connections = get_user_connections(st.session_state['email'])
    
    if not user_connections:
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

configs = st.session_state.get('global_configs', get_global_configs())
projects = st.session_state.get('projects', {})

def update_global_configs_and_rerun(configs_dict):
    """Função central para salvar, limpar cache, recarregar a sessão e a página."""
    save_global_configs(configs_dict)
    get_global_configs.clear()
    st.session_state['global_configs'] = get_global_configs()
    st.success("Configurações salvas com sucesso!")
    st.rerun()

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

    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

tab_campos, tab_metricas, tab_os, tab_projetos, tab_datas, tab_email = st.tabs([
    "Gestão de Campos Globais", 
    "Configurações de Métricas", 
    "Padrões de Ordem de Serviço", 
    "Configurações por Projeto",
    "Personalização de datas",
    "Configurações de E-mail"

])

with tab_campos:
    st.subheader("Campos Disponíveis para Toda a Aplicação")
    
    # --- Gestão de Campos Padrão em um container próprio ---
    with st.container(border=True):
        st.markdown("#### 🗂️ Campos Padrão do Jira")
        st.caption("Adicione ou remova os campos padrão que os utilizadores poderão ativar.")
        available_fields = configs.get('available_standard_fields', {})
        with st.form("new_std_field_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            new_name = f_col1.text_input("Nome Amigável", placeholder="Ex: Data de Vencimento")
            new_id = f_col2.text_input("ID do Atributo", placeholder="Ex: duedate")
            new_type = f_col3.selectbox("Tipo de Dado", ["Texto (Alfanumérico)", "Numérico", "Data"], key="new_std_type")
            if st.form_submit_button("➕ Adicionar Campo Padrão", use_container_width=True):
                if new_name and new_id:
                    if validate_jira_field(st.session_state.jira_client, new_id):
                        available_fields[new_name] = {'id': new_id, 'type': new_type}; configs['available_standard_fields'] = available_fields
                        update_global_configs_and_rerun(configs)
                    else: st.error(f"O ID '{new_id}' não é um campo válido no Jira.")
                else: st.error("Nome e ID são obrigatórios.")
        if available_fields:
            st.markdown("---"); st.markdown("**Campos Atuais:**")
            c1, c2, c3, c4 = st.columns([3, 3, 2, 1]); c1.caption("Nome"); c2.caption("ID"); c3.caption("Tipo"); c4.caption("Ação")
            for name, details in list(available_fields.items()):
                disp_col1, disp_col2, disp_col3, disp_col4 = st.columns([3, 3, 2, 1])
                disp_col1.text_input("Nome", value=name, key=f"name_std_{details.get('id')}", disabled=True, label_visibility="collapsed")
                disp_col2.text_input("ID", value=details.get('id', 'N/A'), key=f"id_std_{details.get('id')}", disabled=True, label_visibility="collapsed")
                disp_col3.text_input("Tipo", value=details.get('type', 'N/A'), key=f"type_std_{details.get('id')}", disabled=True, label_visibility="collapsed")
                if disp_col4.button("❌", key=f"del_std_{details.get('id')}", help=f"Remover '{name}'", use_container_width=True):
                    del available_fields[name]; configs['available_standard_fields'] = available_fields
                    update_global_configs_and_rerun(configs)
    
    st.divider()

    # --- Gestão de Campos Personalizados em um container próprio ---
    with st.container(border=True):
        st.markdown("#### ✨ Campos Personalizados (Custom Fields)")
        st.caption("Adicione campos específicos do seu Jira (ex: Story Points).")
        custom_fields = configs.get('custom_fields', [])
        with st.form("new_custom_field_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            new_name = f_col1.text_input("Nome do Campo", placeholder="Ex: Story Points")
            new_id = f_col2.text_input("ID do Campo", placeholder="Ex: customfield_10016")
            new_type = f_col3.selectbox("Tipo de Dado", ["Texto (Alfanumérico)", "Numérico", "Data"], key="new_custom_type")
            if st.form_submit_button("➕ Adicionar Campo Personalizado", use_container_width=True):
                if new_name and new_id:
                    if validate_jira_field(st.session_state.jira_client, new_id):
                        if any(f['id'] == new_id for f in custom_fields): st.error(f"O ID '{new_id}' já existe.")
                        else: custom_fields.append({'name': new_name, 'id': new_id, 'type': new_type}); configs['custom_fields'] = custom_fields; update_global_configs_and_rerun(configs)
                    else: st.error(f"O ID '{new_id}' não é válido no Jira.")
                else: st.error("Por favor, preencha o Nome e o ID.")
        if custom_fields:
            st.markdown("---"); st.markdown("**Campos Atuais:**")
            c1, c2, c3, c4 = st.columns([3, 3, 2, 1]); c1.caption("Nome"); c2.caption("ID"); c3.caption("Tipo"); c4.caption("Ação")
            for i, field in enumerate(custom_fields):
                disp_col1, disp_col2, disp_col3, disp_col4 = st.columns([3, 3, 2, 1])
                disp_col1.text_input("Nome", value=field['name'], key=f"name_custom_{i}", disabled=True, label_visibility="collapsed")
                disp_col2.text_input("ID", value=field['id'], key=f"id_custom_{i}", disabled=True, label_visibility="collapsed")
                disp_col3.text_input("Tipo", value=field.get('type', 'N/A'), key=f"type_custom_{i}", disabled=True, label_visibility="collapsed")
                if disp_col4.button("❌", key=f"del_custom_{field['id']}", help=f"Remover '{field['name']}'", use_container_width=True):
                    custom_fields.pop(i); configs['custom_fields'] = custom_fields; update_global_configs_and_rerun(configs)

with tab_metricas:
    with st.container(border=True):
        st.markdown("🔁 **Mapeamento de Status do Workflow**")
        st.caption("Defina os status que marcam o início, o fim e os que devem ser ignorados no fluxo.")
        status_mapping = configs.get('status_mapping', {}); 
        
        initial_states_str = st.text_area("Status Iniciais (separados por vírgula)", value=", ".join(status_mapping.get('initial', DEFAULT_INITIAL_STATES)))
        done_states_str = st.text_area("Status Finais (separados por vírgula)", value=", ".join(status_mapping.get('done', DEFAULT_DONE_STATES)))
        
        # --- NOVA CAIXA DE TEXTO ---
        ignored_states_str = st.text_area(
            "Status a Ignorar (separados por vírgula)", 
            value=", ".join(status_mapping.get('ignored', ['cancelado', 'cancelled'])),
            help="Issues que entrarem nestes status serão removidas das métricas de fluxo e escopo."
        )

        if st.button("Salvar Mapeamento de Status", use_container_width=True):
            configs['status_mapping'] = {
                'initial': [s.strip().lower() for s in initial_states_str.split(',') if s.strip()],
                'done': [s.strip().lower() for s in done_states_str.split(',') if s.strip()],
                'ignored': [s.strip().lower() for s in ignored_states_str.split(',') if s.strip()] # Salva a nova lista
            }
            update_global_configs_and_rerun(configs)
            
    # --- NOVA SECÇÃO PARA CONFIGURAÇÕES DE SLA ---
    with st.container(border=True):
        st.markdown("⏱️ **Configurações de SLA (Service Level Agreement)**")
        st.caption("Mapeie os campos que você usa no Jira para controlar o tempo de primeira resposta. Os valores de SLA devem estar em horas.")
        
        # Carrega os campos numéricos já configurados
        numeric_custom_fields = [field['name'] for field in configs.get('custom_fields', []) if field.get('type') == 'Numérico']
        date_custom_fields = [field['name'] for field in configs.get('custom_fields', []) if field.get('type') == 'Data']
        
        sla_configs = configs.get('sla_fields', {})

        if not numeric_custom_fields or not date_custom_fields:
            st.warning("Para configurar o SLA, por favor, cadastre pelo menos um campo do tipo 'Numérico' (para o SLA) e um do tipo 'Data' (para a resposta) na aba 'Gestão de Campos Globais'.")
        else:
            sla_field_options = [""] + numeric_custom_fields
            response_field_options = [""] + date_custom_fields

            sla_field_idx = sla_field_options.index(sla_configs.get('sla_hours_field')) if sla_configs.get('sla_hours_field') in sla_field_options else 0
            response_field_idx = response_field_options.index(sla_configs.get('first_response_field')) if sla_configs.get('first_response_field') in response_field_options else 0

            selected_sla_field = st.selectbox(
                "Campo que contém o SLA em horas (ex: 'SLA de Primeira Resposta')", 
                options=sla_field_options,
                index=sla_field_idx
            )
            selected_response_field = st.selectbox(
                "Campo que contém a data do primeiro atendimento (ex: 'Data da Primeira Resposta')",
                options=response_field_options,
                index=response_field_idx
            )

            if st.button("Salvar Configurações de SLA", use_container_width=True):
                configs['sla_fields'] = {
                    'sla_hours_field': selected_sla_field,
                    'first_response_field': selected_response_field
                }
                update_global_configs_and_rerun(configs)


# --- ABA DEDICADA PARA A ORDEM DE SERVIÇO ---
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
    if not project_names: st.warning("Nenhum projeto encontrado.")
    else:
        selected_project_name = st.selectbox("Selecione um projeto para configurar:", options=project_names)
        project_key = projects[selected_project_name]
        project_config = get_project_config(project_key) or {}
        with st.container(border=True):
            st.markdown(f"**Campo de Estimativa para o Projeto '{selected_project_name}'**")
            st.caption("Este campo será usado para cálculos de Velocidade e Burndown/Burnup neste projeto.")
            custom_fields = configs.get('custom_fields', []); standard_fields = configs.get('available_standard_fields', {})
            numeric_fields = {field['name']: {'id': field['id'], 'source': 'custom'} for field in custom_fields if field.get('type') == 'Numérico'}
            numeric_fields.update({name: {'id': details['id'], 'source': 'standard'} for name, details in standard_fields.items() if details.get('type') == 'Numérico'})
            standard_time_fields = {"Estimativa Original (Horas)": {'id': 'timeoriginalestimate', 'source': 'standard_time'}, "Tempo Gasto (Horas)": {'id': 'timespent', 'source': 'standard_time'}}
            all_estimation_options = {**numeric_fields, **standard_time_fields}
            if not all_estimation_options: st.warning("Nenhum campo numérico ou de tempo configurado. Adicione-os na aba 'Gestão de Campos Globais'.")
            else:
                options = ["Nenhum (usar contagem de issues)"] + list(all_estimation_options.keys())
                saved_field_name = project_config.get('estimation_field', {}).get('name')
                default_index = options.index(saved_field_name) if saved_field_name in options else 0
                selected_field_name = st.selectbox("Campo para Pontos/Estimativa:", options=options, index=default_index, key=f"select_est_{project_key}")
                if st.button(f"Salvar Campo de Estimativa para {selected_project_name}", use_container_width=True):
                    if selected_field_name == "Nenhum (usar contagem de issues)": project_config['estimation_field'] = {}
                    else: project_config['estimation_field'] = {'name': selected_field_name, **all_estimation_options[selected_field_name]}
                    save_project_config(project_key, project_config); st.success("Configuração do projeto guardada!"); st.rerun()
        st.divider()
        st.subheader("Resumo das Configurações de Estimativa")
        all_project_configs_cursor = get_project_configs_collection().find({}); all_project_configs = {p['_id']: p for p in all_project_configs_cursor}
        summary_data = []
        for name, key in projects.items():
            config = all_project_configs.get(key, {})
            est_field = config.get('estimation_field', {}).get('name', 'Nenhum / Contagem')
            summary_data.append({"Projeto": name, "Campo de Estimativa Configurado": est_field})
        st.dataframe(summary_data, use_container_width=True, hide_index=True)

with tab_datas:
    st.subheader("Mapeamento de Datas para Métricas")
    st.caption("Para cada projeto, 'diga' à aplicação quais campos do Jira correspondem às datas de 'Prevista' e 'Conclusão'.")

    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    selected_project_name = st.selectbox("Selecione um Projeto para Configurar:", options=project_names)

    if selected_project_name:
        project_key = projects[selected_project_name]
        project_config = get_project_config(project_key) or {}
        date_mappings = project_config.get('date_mappings', {})

        # Busca os campos do tipo "Data" que o utilizador ativou
        user_data = find_user(st.session_state['email'])
        all_custom_fields = configs.get('custom_fields', [])
        date_fields = {f['name']: f['id'] for f in all_custom_fields if f.get('type') == 'Data'}
        date_field_options = [""] + list(date_fields.keys())

        with st.form(f"date_mapping_form_{project_key}"):
            st.info(f"A configurar as datas para o projeto: **{selected_project_name}**")
            
            due_date_field_name = next((name for name, id_ in date_fields.items() if id_ == date_mappings.get('due_date_field_id')), "")
            selected_due_date = st.selectbox(
                "Campo para 'Data Prevista' (Due Date)",
                options=date_field_options,
                index=date_field_options.index(due_date_field_name) if due_date_field_name else 0
            )

            completion_date_field_name = next((name for name, id_ in date_fields.items() if id_ == date_mappings.get('completion_date_field_id')), "")
            selected_completion_date = st.selectbox(
                "Campo para 'Data de Conclusão' (Opcional)",
                options=date_field_options,
                index=date_field_options.index(completion_date_field_name) if completion_date_field_name else 0,
                help="Se não for selecionado, a data de conclusão será calculada automaticamente com base no histórico de status."
            )

            if st.form_submit_button("Salvar Mapeamento de Datas", use_container_width=True):
                project_config['date_mappings'] = {
                    'due_date_field_id': date_fields.get(selected_due_date),
                    'completion_date_field_id': date_fields.get(selected_completion_date)
                }
                save_project_config(project_key, project_config)
                st.success(f"Mapeamento de datas para o projeto '{selected_project_name}' guardado com sucesso!")
                st.rerun()

        # --- NOVO BLOCO DE VISUALIZAÇÃO ---
        st.divider()
        st.markdown("##### Configuração Atual")
        
        # Carrega a configuração mais recente para garantir que a exibição está atualizada
        current_config = get_project_config(project_key) or {}
        current_mappings = current_config.get('date_mappings', {})
        
        due_date_id = current_mappings.get('due_date_field_id')
        completion_date_id = current_mappings.get('completion_date_field_id')

        due_date_name = next((name for name, id_ in date_fields.items() if id_ == due_date_id), "Padrão (Due Date)")
        completion_date_name = next((name for name, id_ in date_fields.items() if id_ == completion_date_id), "Automático (via Status)")

        col1, col2 = st.columns(2)
        col1.metric("Campo de Data Prevista", due_date_name)
        col2.metric("Campo de Data de Conclusão", completion_date_name)

# ===== ABA DE CONFIGURAÇÃO DE E-MAIL =====
with tab_email:
    st.subheader("Configuração de Envio de E-mail")
    st.caption("Configure as credenciais para que a aplicação possa enviar e-mails em seu nome.")
    
    # Carrega as configurações existentes no início
    current_smtp_configs = get_smtp_configs() or {}
    current_provider = current_smtp_configs.get('provider', 'SendGrid')

    # --- SELEÇÃO DO PROVEDOR (FORA DO FORMULÁRIO) ---
    st.markdown("##### 1. Provedor de E-mail")
    provider_options = ["SendGrid", "Gmail (SMTP)"]
    provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
    email_provider = st.radio(
        "Selecione o seu provedor:",
        provider_options,
        horizontal=True,
        index=provider_index
    )
    
    # --- FORMULÁRIO DE CREDENCIAIS (ADAPTADO AO PROVEDOR) ---
    with st.form("smtp_config_form"):
        st.markdown("##### 2. Credenciais")
        
        if email_provider == 'Gmail (SMTP)':
            st.info("Para usar o Gmail, você precisa de criar uma 'app password' na sua conta. Não use a sua senha normal.")
            from_email = st.text_input("E-mail de Origem", value=current_smtp_configs.get('from_email', '') if current_provider == 'Gmail (SMTP)' else '')
            app_password = st.text_input("Senha de Aplicação (App Password)", value=current_smtp_configs.get('app_password', '') if current_provider == 'Gmail (SMTP)' else '', type="password")
            
            smtp_configs_to_save = {
                'provider': 'Gmail (SMTP)',
                'from_email': from_email,
                'app_password': app_password
            }
            
        elif email_provider == 'SendGrid':
            st.info("Obtenha a sua API Key na sua conta do SendGrid.")
            from_email = st.text_input("E-mail de Origem", value=current_smtp_configs.get('from_email', '') if current_provider == 'SendGrid' else '')
            sendgrid_api_key = st.text_input("SendGrid API Key", value=current_smtp_configs.get('api_key', '') if current_provider == 'SendGrid' else '', type="password")
            
            smtp_configs_to_save = {
                'provider': 'SendGrid',
                'from_email': from_email,
                'api_key': sendgrid_api_key
            }
        
        if st.form_submit_button("Salvar Credenciais", use_container_width=True, type="primary"):
            if from_email:
                save_smtp_configs(smtp_configs_to_save)
                st.success("Configurações de e-mail salvas com sucesso!")
                # Atualiza os dados na sessão para uso imediato
                st.session_state['smtp_configs'] = get_smtp_configs()
                st.rerun()
            else:
                st.error("Por favor, preencha o e-mail de origem.")