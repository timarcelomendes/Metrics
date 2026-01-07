# pages/10_👑_Administração.py
# (MODIFICADO para remover o input manual, corrigir StreamlitAPIException e NameError)
# (MODIFICADO NOVAMENTE para adicionar Mapeamento de Campos Estratégicos)

import streamlit as st
from security import *
from pathlib import Path
import pandas as pd
from config import SESSION_TIMEOUT_MINUTES
from streamlit_quill import st_quill
import uuid
from datetime import datetime 
from jira_connector import get_jira_fields # Mantido do seu ficheiro original

st.set_page_config(page_title="Administração", page_icon="👑", layout="wide")
st.header("👑 Painel de Administração", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente."); st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()
if not is_admin(st.session_state['email']):
    st.error("🚫 Acesso Negado. Esta página é reservada para administradores."); st.stop()

configs = get_global_configs() # <-- Variável 'configs' definida aqui

def force_hub_reload():
    if 'hub_data_loaded' in st.session_state:
        del st.session_state['hub_data_loaded']

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try: st.logo(str(logo_path), size="large")
    except: st.write("Gauge Metrics") 
    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else: st.info("⚠️ Usuário não conectado!")
    if st.button("Logout", width='stretch', type='secondary'):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("0_🔑_Autenticação.py")

# --- Interface Principal com 3 Abas ---
main_tab_kpis, main_tab_content, main_tab_system = st.tabs([
    "**💰 KPIs e Finanças**", 
    "**📄 Gestão de Conteúdo**", 
    "**⚙️ Configurações do Sistema**"
])

# --- NOVA ABA PRINCIPAL: KPIs e Finanças ---
with main_tab_kpis:
    st.markdown("##### 💰 Gestão de KPIs Financeiros e de Perfil")
    st.markdown("Defina os dados manuais (KPIs, Orçamento, Perfil) para os contextos estratégicos.")
    st.info("O contexto selecionado deve ser *exatamente* igual ao valor no Jira (ex: 'Cliente A', '— Visão Agregada do Projeto —').")

    # Carrega os dados financeiros do config global
    dados_financeiros_kpis = configs.get('dados_financeiros_kpis', {}) # Nomeado para maior clareza

    # --- LÓGICA DE SELEÇÃO DE CONTEXTO (CORRIGIDA) ---
    lista_de_contextos = []
    
    # Busca o nome do campo estratégico (ex: "Cliente")
    # --- CORREÇÃO DO NameError ---
    strategic_field_name = configs.get('strategic_grouping_field', 'Contexto') 
    if not strategic_field_name: strategic_field_name = 'Contexto' # Garante um fallback
    # --- FIM DA CORREÇÃO ---
    
    # Tenta carregar contextos do dynamic_df (se existir no cache de outra página)
    if 'dynamic_df' in st.session_state and not st.session_state.dynamic_df.empty:
        if strategic_field_name in st.session_state.dynamic_df.columns:
            lista_de_contextos = sorted(st.session_state.dynamic_df[strategic_field_name].dropna().unique())
            
    # Adiciona contextos já salvos que podem não estar no DF
    for ctx in dados_financeiros_kpis.keys():
        if ctx not in lista_de_contextos:
            lista_de_contextos.append(ctx)
            
    # Garante a Visão Agregada
    if '— Visão Agregada do Projeto —' not in lista_de_contextos:
        lista_de_contextos.insert(0, '— Visão Agregada do Projeto —')

    # --- CORREÇÃO: Remove o 'text_input' manual e o link entre eles ---
    st.markdown(f"###### 1. Selecione um Contexto ({strategic_field_name})")
    st.caption("A lista é populada com dados do último projeto carregado (no Radar ou Métricas) e contextos já salvos.")
    contexto_final = st.selectbox(
        f"Selecione o {strategic_field_name} para editar:",
        options=[""] + sorted(list(set(lista_de_contextos))), # Adiciona opção vazia
        key="kpi_context_select",
        index=0,
        help="Selecione um contexto da lista para carregar ou editar os seus dados."
    )
    # --- FIM DA CORREÇÃO ---
    
    st.markdown("---")
    
    # Só mostra o formulário se um contexto for selecionado
    if contexto_final:
        st.subheader(f"A editar dados para: '{contexto_final}'")
        
        with st.form(f"form_kpis_{contexto_final.replace(' ', '_').replace('—', '')}"):
            # Pega os dados atuais para este contexto
            dados_atuais = dados_financeiros_kpis.get(contexto_final, {})
            
            st.markdown("**1. Perfil (Módulo 3)**")
            col1, col2, col3 = st.columns(3)
            responsavel = col1.text_input("Responsável", value=dados_atuais.get('responsavel', ''))
            
            start_date_val = pd.to_datetime(dados_atuais.get('start_date')).date() if dados_atuais.get('start_date') else None
            end_date_val = pd.to_datetime(dados_atuais.get('end_date')).date() if dados_atuais.get('end_date') else None
            
            start_date = col2.date_input("Data de Início", value=start_date_val)
            end_date = col3.date_input("Data de Fim Prevista", value=end_date_val)

            st.markdown("---")
            st.markdown("**2. Forecast Preditivo (Módulo 2)**")
            col1, col2 = st.columns(2)
            orcamento = col1.number_input(
                "Orçamento Total (R$)", 
                value=dados_atuais.get('orcamento', 0.0), 
                min_value=0.0, step=1000.0,
                help="Qual o orçamento total aprovado para este contexto?"
            )
            custo_time_mes = col2.number_input(
                "Custo Mensal do Time (R$)", 
                value=dados_atuais.get('custo_time_mes', 0.0), 
                min_value=0.0, step=500.0,
                help="Qual o custo mensal (burn rate) médio do time neste contexto?"
            )
            
            st.markdown("---")
            st.markdown("**3. KPIs de Negócio Manuais (Módulo 3)**")
            col1, col2, col3 = st.columns(3)
            mrr = col1.number_input("Receita Recorrente (MRR)", min_value=0.0, value=dados_atuais.get('mrr', 0.0), format="%.2f")
            receita_nao_recorrente = col2.number_input("Receitas Não Recorrentes", min_value=0.0, value=dados_atuais.get('receita_nao_recorrente', 0.0), format="%.2f")
            total_despesas = col3.number_input("Total de Despesas", min_value=0.0, value=dados_atuais.get('total_despesas', 0.0), format="%.2f")
            
            nps_value = dados_atuais.get('nps', 0)
            try: nps_default = int(nps_value) if nps_value != 'N/A' else 0
            except: nps_default = 0
            nps = col1.number_input("NPS (Net Promoter Score)", min_value=-100, max_value=100, value=nps_default)

            if st.form_submit_button("Salvar Contexto", type="primary"):
                # Salva no config global usando o nome do contexto como chave
                configs.setdefault('dados_financeiros_kpis', {})[contexto_final] = {
                    'responsavel': responsavel,
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None,
                    'orcamento': orcamento,
                    'custo_time_mes': custo_time_mes,
                    'mrr': mrr,
                    'receita_nao_recorrente': receita_nao_recorrente,
                    'total_despesas': total_despesas,
                    'nps': nps
                }
                save_global_configs(configs) 
                get_global_configs.clear() 
                st.success(f"Dados financeiros e KPIs para '{contexto_final}' salvos!")
                st.rerun()
                
    else:
        st.info("Selecione um contexto existente na lista acima para inserir ou editar dados.")

    st.divider()
    st.markdown("###### Contextos Atuais (com dados salvos)")
    
    if not dados_financeiros_kpis:
        st.info("Nenhum contexto financeiro/KPI foi cadastrado.")
    else:
        rows = []
        for nome, dados in dados_financeiros_kpis.items():
            row = dados.copy() 
            row["Contexto"] = nome 
            rows.append(row)
        
        df_fin = pd.DataFrame(rows)
        
        cols_ordem = [
            "Contexto", "Responsável", "orcamento", "custo_time_mes", 
            "mrr", "receita_nao_recorrente", "total_despesas", "nps", 
            "start_date", "end_date"
        ]
        cols_finais = [col for col in cols_ordem if col in df_fin.columns]
        
        st.dataframe(df_fin[cols_finais], use_container_width=True, hide_index=True)
        
        contexto_para_remover = st.selectbox("Selecione um contexto para remover", options=[""] + list(dados_financeiros_kpis.keys()), key="remove_fin_context")
        if st.button("Remover Contexto Selecionado", type="secondary"):
            if contexto_para_remover and contexto_para_remover in configs.get('dados_financeiros_kpis', {}):
                del configs['dados_financeiros_kpis'][contexto_para_remover]
                save_global_configs(configs) 
                get_global_configs.clear()
                st.success(f"Contexto '{contexto_para_remover}' removido.")
                st.rerun()
            elif not contexto_para_remover:
                st.warning("Nenhum contexto selecionado para remoção.")


# --- ABA 2: Gestão de Conteúdo ---
with main_tab_content:
    st.subheader("Gestão de Conteúdo do Product Hub")
    
    content_tab_playbooks, content_tab_competencies, content_tab_roles = st.tabs([
        "📖 Playbooks", 
        "💎 Competências", 
        "👨‍🔬 Papéis"
    ])

    with content_tab_playbooks:
        # ... (O seu código para Playbooks - sem alterações) ...
        st.markdown("##### Gestão de Conteúdo dos Playbooks")
        playbooks = configs.get('playbooks', {})
        
        toolbar_options = [[{'header': [1, 2, 3, 4, 5, 6, False]}], ['bold', 'italic', 'underline', 'strike'], [{'list': 'ordered'}, {'list': 'bullet'}], [{'color': []}, {'background': []}], ['link', 'image'], ['clean']]

        with st.expander("➕ Adicionar Novo Tema de Playbook"):
            with st.form("new_playbook_form", clear_on_submit=True):
                new_theme_name_input = st.text_input("Nome do Novo Tema*")
                st.markdown("Conteúdo (suporta formatação de texto)*")
                new_theme_content = st_quill(placeholder="Escreva aqui o conteúdo do seu playbook...", html=True, toolbar=toolbar_options, key="new_playbook_editor")
                if st.form_submit_button("Adicionar Tema", type="primary"):
                    new_theme_name = new_theme_name_input.strip()
                    if new_theme_name and new_theme_content:
                        configs.setdefault('playbooks', {})[new_theme_name] = new_theme_content
                        save_global_configs(configs) 
                        force_hub_reload()
                        st.rerun()
        
        st.divider()
        st.markdown("###### Editar ou Remover Tema Existente")
        if playbooks:
            theme_to_edit = st.selectbox("Selecione um tema para gerir:", options=list(playbooks.keys()))
            if theme_to_edit:
                edited_content = st_quill(value=playbooks.get(theme_to_edit, ""), html=True, toolbar=toolbar_options, key="edit_playbook_editor")
                with st.container(border=True):
                    st.markdown("Pré-visualização do Conteúdo")
                    st.markdown(edited_content, unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("Salvar Alterações", width='stretch', key=f"save_{theme_to_edit}"):
                    configs['playbooks'][theme_to_edit] = edited_content
                    save_global_configs(configs) 
                    force_hub_reload()
                    st.rerun()
                if c2.button("❌ Remover Tema", width='stretch', type="secondary", key=f"del_{theme_to_edit}"):
                    del configs['playbooks'][theme_to_edit]
                    save_global_configs(configs) 
                    force_hub_reload()
                    st.rerun()

    with content_tab_competencies:
        # ... (O seu código para Competências - sem alterações) ...
        st.markdown("##### Framework de Competências")
        st.caption("Defina as competências e descrições que serão usadas na plataforma.")

        if 'competency_framework' not in configs:
            configs['competency_framework'] = {'hard_skills': [], 'soft_skills': []}

        framework_data = configs.get('competency_framework', {})
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("###### 🛠️ Hard Skills")
            edited_hard_skills = st.data_editor(
                pd.DataFrame(framework_data.get('hard_skills', [])), 
                num_rows="dynamic", 
                width='stretch', 
                column_config={"Competência": "Competência*", "Descrição": "Descrição"},
                key="hard_skills_editor"
            )
        with col2:
            st.markdown("###### 🧠 Soft Skills")
            edited_soft_skills = st.data_editor(
                pd.DataFrame(framework_data.get('soft_skills', [])), 
                num_rows="dynamic", 
                width='stretch', 
                column_config={"Competência": "Competência*", "Descrição": "Descrição"},
                key="soft_skills_editor"
            )
            
        if st.button("Salvar Framework de Competências", type="primary", width='stretch'):
            configs['competency_framework']['hard_skills'] = edited_hard_skills.to_dict('records')
            configs['competency_framework']['soft_skills'] = edited_soft_skills.to_dict('records')
            save_global_configs(configs) 
            force_hub_reload()
            st.success("Framework de competências salvo com sucesso!")
            st.rerun()

    with content_tab_roles:
        # ... (O seu código para Papéis - sem alterações) ...
        st.markdown("##### Papéis do Product Hub")
        st.caption("Adicione ou remova os papéis (funções) que podem ser atribuídos às equipas.")
        
        if 'editing_role_id' not in st.session_state: st.session_state.editing_role_id = None

        user_roles_raw = configs.get('user_roles', [])
        needs_migration = any(isinstance(role, str) for role in user_roles_raw)
        if needs_migration:
            migrated_roles = []
            for role in user_roles_raw:
                if isinstance(role, str): migrated_roles.append({"id": str(uuid.uuid4()), "name": role, "description": ""})
                elif isinstance(role, dict) and 'id' in role: migrated_roles.append(role)
            configs['user_roles'] = migrated_roles
            save_global_configs(configs) 
            user_roles = migrated_roles
            st.toast("Dados de papéis foram atualizados para o novo formato.", icon="✨")
        else:
            user_roles = user_roles_raw

        toolbar_options_roles = [[{'header': [1, 2, 3, False]}], ['bold', 'italic', 'underline'], [{'list': 'ordered'}, {'list': 'bullet'}]]

        with st.expander("➕ Adicionar Novo Papel"):
            with st.form("new_role_form", clear_on_submit=True):
                role_name_input = st.text_input("Nome do Papel* (Ex: PM, Tech Lead)")
                st.markdown("Descrição e Responsabilidades*")
                role_description = st_quill(placeholder="Descreva o papel...", html=True, toolbar=toolbar_options_roles, key="new_role_editor")
                if st.form_submit_button("Adicionar Papel", type="primary"):
                    role_name = role_name_input.strip()
                    if role_name and role_description:
                        new_role = {"id": str(uuid.uuid4()), "name": role_name, "description": role_description}
                        user_roles.append(new_role)
                        configs['user_roles'] = sorted(user_roles, key=lambda x: x['name'])
                        save_global_configs(configs) 
                        force_hub_reload()
                        st.rerun()
        
        st.divider()
        st.markdown("###### Papéis Atuais")
        if not user_roles:
            st.info("Nenhum papel foi cadastrado ainda.")
        else:
            for i, role in enumerate(user_roles):
                if st.session_state.editing_role_id == role['id']:
                    with st.form(f"edit_role_form_{role['id']}"):
                        st.subheader(f"Editando: {role['name']}")
                        edited_name_input = st.text_input("Nome do Papel*", value=role.get('name', ''))
                        st.markdown("Descrição e Responsabilidades*")
                        edited_description = st_quill(value=role.get('description', ''), html=True, toolbar=toolbar_options_roles, key=f"edit_role_editor_{role['id']}")
                        c1, c2 = st.columns(2)
                        if c1.form_submit_button("Salvar Alterações", width='stretch', type="primary"):
                            edited_name = edited_name_input.strip()
                            user_roles[i] = {"id": role['id'], "name": edited_name, "description": edited_description}
                            configs['user_roles'] = sorted(user_roles, key=lambda x: x['name'])
                            save_global_configs(configs) 
                            force_hub_reload()
                            st.session_state.editing_role_id = None
                            st.rerun()
                        if c2.form_submit_button("Cancelar", width='stretch'):
                            st.session_state.editing_role_id = None
                            st.rerun()
                else:
                    with st.container(border=True):
                        c1, c2 = st.columns([0.8, 0.2])
                        with c1: st.subheader(role['name'])
                        with c2:
                            btn_cols = st.columns(2)
                            if btn_cols[0].button("✏️", key=f"edit_role_{role['id']}", help="Editar Papel", width='stretch'):
                                st.session_state.editing_role_id = role['id']
                                st.rerun()
                            if btn_cols[1].button("❌", key=f"del_role_{role['id']}", help="Remover Papel", width='stretch'):
                                user_roles.pop(i)
                                configs['user_roles'] = user_roles
                                save_global_configs(configs) 
                                force_hub_reload()
                                st.rerun()
                        st.markdown(role.get('description', 'Nenhuma descrição.'), unsafe_allow_html=True)

with main_tab_system:
    st.subheader("Configurações Gerais do Sistema")
    
    system_tab_fields, system_tab_domains, system_tab_users, system_tab_kpis, system_tab_email, tab_link = st.tabs([
        "📝 Campos Jira", "🌐 Domínios", "👥 Utilizadores", "🎯 Metas", "📧 E-mail", "🔗 Link de Avaliação"
    ])

    with system_tab_fields:
        st.markdown("##### Gestão de Campos Globais para Análise")
        st.caption("Controle aqui os campos do Jira que estarão disponíveis para os utilizadores ativarem nos seus perfis.")
        
        current_configs_for_display = get_global_configs()

        # --- CAMPOS PADRÃO ---
        st.markdown("###### 🗂️ Campos Padrão (Standard Fields)")
        st.info("Estes são campos nativos do Jira. Ative aqueles que são relevantes para as suas análises.")

        STANDARD_FIELDS_MAP = st.session_state.get('standard_fields_map', {})
        available_options = list(STANDARD_FIELDS_MAP.keys())
        
        standard_fields_config = current_configs_for_display.get('available_standard_fields', {})
        if not isinstance(standard_fields_config, dict): standard_fields_config = {}
        
        # Filtra os defaults: só inclui o que está salvo E o que está disponível no JSON
        saved_defaults = list(standard_fields_config.keys())
        
        # Esta linha garante que 'default' só contém itens que existem em 'options'
        safe_defaults = [item for item in saved_defaults if item in available_options]

        if not available_options:
             st.warning("O mapa de campos padrão (jira_standard_fields.json) não foi carregado. Por favor, faça logout e login.")
        else:
            selected_standard_fields = st.multiselect(
                "Selecione os campos padrão a disponibilizar:",
                options=available_options, # <-- Usa a lista de opções
                format_func=lambda key: STANDARD_FIELDS_MAP.get(key, key),
                default=safe_defaults,     # <-- Usa a lista de defaults filtrada
                key="multiselect_standard_fields"
            )
        
        if st.button("Salvar Campos Padrão", key="save_standard_fields", width='stretch'):
            configs_to_save = get_global_configs()
            configs_to_save['available_standard_fields'] = {field: {} for field in selected_standard_fields}
            save_global_configs(configs_to_save)
            get_global_configs.clear()
            st.success("Campos padrão atualizados com sucesso!")
            st.rerun()

        st.divider()

        # --- CAMPOS PERSONALIZADOS ---
        st.markdown("###### ✨ Campos Personalizados (Custom Fields)")
        st.info("Selecione os campos personalizados do seu Jira que devem estar disponíveis para análise na aplicação.")

        try:
            # 1. Usar a função existente do jira_connector para buscar TUDO
            all_fields_raw = get_jira_fields(st.session_state['jira_client'])
            all_jira_custom_fields = None

            if all_fields_raw:
                # 2. Filtrar e formatar a lista APENAS para campos personalizados
                all_jira_custom_fields = [
                    {'id': field['id'], 'name': field['name']} 
                    for field in all_fields_raw 
                    if field['id'].startswith('customfield_')
                ]
                all_jira_custom_fields = sorted(all_jira_custom_fields, key=lambda x: x['name'])

            if all_jira_custom_fields is not None:
                saved_custom_fields = current_configs_for_display.get('custom_fields', [])
                if not isinstance(saved_custom_fields, list): saved_custom_fields = []
                
                saved_custom_field_ids = [field['id'] for field in saved_custom_fields if isinstance(field, dict)]
                field_display_map = {field['id']: f"{field['name']} ({field['id']})" for field in all_jira_custom_fields}
                
                selected_field_ids = st.multiselect(
                    "Selecione os campos personalizados a disponibilizar:",
                    options=list(field_display_map.keys()),
                    format_func=lambda field_id: field_display_map.get(field_id, field_id),
                    default=saved_custom_field_ids,
                    key="multiselect_custom_fields"
                )

                if st.button("Salvar Campos Personalizados", key="save_custom_fields", width='stretch', type="primary"):
                    configs_to_save = get_global_configs()
                    updated_custom_fields = [{'id': field_id, 'name': field_display_map[field_id].split(' (')[0]} for field_id in selected_field_ids]
                    configs_to_save['custom_fields'] = updated_custom_fields
                    save_global_configs(configs_to_save)
                    get_global_configs.clear()
                    st.success("Campos personalizados salvos com sucesso!")
                    st.rerun()

                # --- NOVO BLOCO INSERIDO ---
                # Esta seção depende de 'all_jira_custom_fields' e 'current_configs_for_display'
                
                st.divider()
                st.markdown("###### 🎯 Mapeamento de Campos Estratégicos (Radar Preditivo)")
                st.info(
                    "Selecione quais campos personalizados devem ser usados para agrupar os dados no Radar Preditivo. "
                    "O 'Seletor de Clientes' define o campo de agrupamento principal (strategic_grouping_field)."
                )

                # 1. Criar um mapa de NOME -> NOME (para consistência, já que vamos salvar o nome)
                #    e uma lista de nomes para as opções.
                custom_field_name_list = sorted([field['name'] for field in all_jira_custom_fields])
                options_list = [""] + custom_field_name_list # Adiciona opção vazia

                # 2. Obter valores atuais (os nomes dos campos)
                current_strategic_field = current_configs_for_display.get('strategic_grouping_field', None)
                current_project_field = current_configs_for_display.get('radar_project_field', None)
                current_board_field = current_configs_for_display.get('radar_board_field', None)
                
                # 3. Calcular índices para os selectbox
                try:
                    index_cliente = options_list.index(current_strategic_field) if current_strategic_field in options_list else 0
                except ValueError: index_cliente = 0
                
                try:
                    index_projeto = options_list.index(current_project_field) if current_project_field in options_list else 0
                except ValueError: index_projeto = 0
                
                try:
                    index_quadro = options_list.index(current_board_field) if current_board_field in options_list else 0
                except ValueError: index_quadro = 0

                # 4. Criar os seletores
                selected_customer_field = st.selectbox(
                    "Seletor de Clientes (strategic_grouping_field)",
                    options=options_list,
                    index=index_cliente,
                    help="Selecione o campo usado para agrupar por Cliente/Contexto no Radar Preditivo."
                )
                
                selected_project_field = st.selectbox(
                    "Seletor de Projetos (Opcional)",
                    options=options_list,
                    index=index_projeto,
                    help="Selecione o campo que identifica o 'Projeto' (se for diferente do projeto Jira)."
                )
                
                selected_board_field = st.selectbox(
                    "Seletor de Quadros (Opcional)",
                    options=options_list,
                    index=index_quadro,
                    help="Selecione o campo que identifica o 'Quadro' ou 'Time'."
                )

                # 5. Botão de Salvar
                if st.button("Salvar Mapeamento Estratégico", key="save_strategic_mapping", width='stretch', type="secondary"):
                    configs_to_save = get_global_configs()
                    
                    configs_to_save['strategic_grouping_field'] = selected_customer_field if selected_customer_field else None
                    configs_to_save['radar_project_field'] = selected_project_field if selected_project_field else None
                    configs_to_save['radar_board_field'] = selected_board_field if selected_board_field else None
                    
                    save_global_configs(configs_to_save)
                    get_global_configs.clear()
                    st.success("Mapeamento de campos estratégicos salvo com sucesso!")
                    st.rerun()
                
                # --- FIM DO NOVO BLOCO ---

            else:
                 st.error("Não foi possível carregar os campos personalizados do Jira. Verifique a conexão e as permissões.")
        except Exception as e:
            st.error(f"Ocorreu um erro inesperado na seção de campos personalizados."); st.caption(f"Detalhes: {e}");

    with system_tab_domains:
        st.markdown("##### Domínios com Permissão de Registro")
        with st.container(border=True):
            allowed_domains = configs.get('allowed_domains', [])
            for domain in list(allowed_domains):
                col1, col2 = st.columns([4, 1])
                col1.text(domain)
                if col2.button("Remover", key=f"del_sys_domain_{domain}", width='stretch'):
                    allowed_domains.remove(domain)
                    configs['allowed_domains'] = allowed_domains
                    save_global_configs(configs)
                    get_global_configs.clear()
                    st.rerun()
            with st.form("new_sys_domain_form", clear_on_submit=True):
                new_domain_input = st.text_input("Adicionar novo domínio permitido:")
                if st.form_submit_button("Adicionar Domínio", type="primary"):
                    new_domain = new_domain_input.strip()
                    if new_domain and new_domain not in allowed_domains:
                        allowed_domains.append(new_domain)
                        configs['allowed_domains'] = allowed_domains
                        save_global_configs(configs)
                        get_global_configs.clear()
                        st.rerun()

    with system_tab_users:
        # Verifica se o utilizador atual está na lista de MASTER_USERS (definido no config/security)
        if st.session_state['email'] in MASTER_USERS:
            with st.expander("🕵️‍♂️ Acesso Master: Logar como outro Utilizador", expanded=False):
                st.warning("⚠️ **Atenção:** Você assumirá a identidade e as conexões (API Keys) do utilizador selecionado.")
                
                all_users_for_login = get_all_users(exclude_email=st.session_state['email'])
                
                target_user_login = st.selectbox(
                    "Selecione o utilizador para aceder:", 
                    options=all_users_for_login,
                    key="master_impersonate_select"
                )
                
                if st.button("🚀 Entrar como este Utilizador", type="primary"):
                    if target_user_login:
                        # 1. Buscar dados COMPLETOS do utilizador alvo
                        target_user_data = find_user(target_user_login)
                        
                        if target_user_data:
                            # 2. Limpar a sessão do Administrador
                            for k in list(st.session_state.keys()):
                                # Mantém apenas configurações essenciais se necessário, mas limpa dados
                                if k not in ['standard_fields_map']: 
                                    del st.session_state[k]
                            
                            # 3. Definir a nova identidade
                            st.session_state['email'] = target_user_data['email']
                            st.session_state['user_data'] = target_user_data
                            st.session_state['last_activity_time'] = datetime.now()
                            
                            # 4. --- LÓGICA CRÍTICA: CARREGAR A CHAVE DE API (CONEXÃO) DO ALVO ---
                            # Precisamos conectar ao Jira usando as credenciais DELE, não as do Admin.
                            
                            from jira_connector import connect_to_jira, get_projects, validate_jira_connection
                            
                            last_conn_id = target_user_data.get('last_active_connection_id')
                            user_connections = target_user_data.get('jira_connections', [])
                            
                            # Tenta encontrar a última conexão ativa ou usa a primeira disponível
                            conn_details = None
                            if last_conn_id:
                                conn_details = next((c for c in user_connections if c.get('id') == last_conn_id), None)
                            
                            if not conn_details and user_connections:
                                conn_details = user_connections[0] # Fallback para a primeira
                                
                            connection_success = False
                            
                            if conn_details:
                                try:
                                    # Decripta o token do utilizador alvo
                                    token = decrypt_token(conn_details['encrypted_token'])
                                    
                                    # Conecta ao Jira
                                    client = connect_to_jira(conn_details['jira_url'], conn_details['jira_email'], token)
                                    
                                    is_valid, reason = validate_jira_connection(client)
                                    
                                    if client and is_valid:
                                        projects = get_projects(client)
                                        if projects:
                                            # Sucesso: Configura a sessão com a chave do utilizador
                                            st.session_state.active_connection = conn_details
                                            st.session_state.jira_client = client
                                            st.session_state.projects = projects
                                            connection_success = True
                                        else:
                                            st.error(f"Conexão estabelecida, mas sem permissão para ver projetos.")
                                    else:
                                        st.error(f"A conexão salva do utilizador falhou: {reason}")
                                except Exception as e:
                                    st.error(f"Erro ao processar a chave de API do utilizador: {e}")
                            
                            # 5. Redirecionamento Inteligente
                            if connection_success:
                                st.success(f"Identidade assumida com sucesso! Conectado ao Jira de {target_user_login}.")
                                # Vai direto para o Dashboard, pois já inicializamos tudo
                                st.switch_page("pages/2_🏠_Meu_Dashboard.py")
                            else:
                                st.warning(f"Logado como {target_user_login}, mas sem conexão Jira ativa.")
                                # Vai para a tela de conexões para verificar/corrigir
                                st.switch_page("pages/8_🔗_Conexões_Jira.py")
                                
                        else:
                            st.error("Erro ao recuperar dados do utilizador selecionado.")

        st.markdown("##### 👥 Utilizadores Registados no Sistema")
        st.caption("Gira as permissões e contas dos utilizadores da plataforma.")

        if 'confirming_delete_user' not in st.session_state:
            st.session_state.confirming_delete_user = None

        def handle_password_reset(user_account):
            """Gera, atualiza o DB e armazena a senha para exibição."""
            try:
                # 1. Gerar a senha UMA VEZ
                temp_pass = generate_temporary_password()
                
                # 2. Atualizar o banco de dados com o hash
                hashed_pass = get_password_hash(temp_pass)
                update_user_password(user_account['email'], hashed_pass)
                
                # 3. Salvar na session_state APENAS para exibição no próximo rerun
                st.session_state['temp_password_info'] = {
                    'email': user_account['email'], 
                    'password': temp_pass
                }
            except Exception as e:
                st.error(f"Erro ao redefinir a senha: {e}")

        def clear_temp_password():
            """Limpa a senha temporária da session_state."""
            if 'temp_password_info' in st.session_state:
                del st.session_state['temp_password_info']
        
        if 'temp_password_info' in st.session_state:
            user_email = st.session_state.temp_password_info['email']
            temp_pass = st.session_state.temp_password_info['password']
            
            # Usar um container para destacar a mensagem
            with st.container(border=True):
                st.success(f"Senha para **{user_email}** redefinida com sucesso!", icon="🔑")
                st.code(temp_pass, language=None)
                st.warning("Por favor, copie esta senha e envie-a ao utilizador por um canal seguro.")
                
                # Botão para dispensar a mensagem
                st.button(
                    "Entendido, dispensar mensagem", 
                    key="dismiss_temp_pass", 
                    on_click=clear_temp_password, 
                    type="primary",
                    use_container_width=True
                )
            
            st.divider()

        all_users = list(get_users_collection().find({}))
        users_to_display = [user for user in all_users if user['email'] != st.session_state['email']]
        
        if not users_to_display:
            st.info("Não há outros utilizadores no sistema para gerir.")
        else:
            for user in users_to_display:
                is_current_user_admin = user.get('is_admin', False)
                is_master_user_target = user['email'] in MASTER_USERS

                with st.container(border=True):
                    col1, col2 = st.columns([0.7, 0.3])
                    with col1:
                        st.subheader(user['email'])
                    with col2:
                        if is_master_user_target:
                            st.success("🏆 Master User", icon="🏆")
                        elif is_current_user_admin:
                            st.success("👑 Administrador", icon="👑")
                        else:
                            st.info("👤 Utilizador Padrão", icon="👤")

                    st.divider()

                    # --- INÍCIO DA LÓGICA DE CONFIRMAÇÃO ---
                    if st.session_state.confirming_delete_user == user['email']:
                        st.warning(f"**Tem a certeza que deseja remover {user['email']}?** Esta ação não pode ser desfeita.")
                        confirm_cols = st.columns(2)
                        if confirm_cols[0].button("🗑️ Sim, remover utilizador", key=f"confirm_del_{user['_id']}", use_container_width=True, type="primary"):
                            delete_user(user['email'])
                            st.session_state.confirming_delete_user = None # Limpa o estado
                            st.success(f"Utilizador {user['email']} removido com sucesso.")
                            st.rerun() # Recarrega para atualizar a lista
                        if confirm_cols[1].button("❌ Cancelar", key=f"cancel_del_{user['_id']}", use_container_width=True):
                            st.session_state.confirming_delete_user = None # Limpa o estado
                            st.rerun() # Recarrega para voltar ao normal
                    else:
                        # Mostra as ações normais se não estiver a confirmar a exclusão deste user
                        st.markdown("**Ações Disponíveis**")
                        action_cols = st.columns(3)

                        with action_cols[0]: # Promover / Despromover
                            if not is_master_user_target:
                                if is_current_user_admin:
                                    st.button(
                                        "Despromover",
                                        key=f"demote_admin_{user['_id']}",
                                        type="secondary",
                                        on_click=set_admin_status, # Mudança aqui para passar args
                                        args=(user['email'], False), # Mudança aqui
                                        use_container_width=True
                                    )
                                else:
                                    st.button(
                                        "Promover a Admin",
                                        key=f"promote_admin_{user['_id']}",
                                        type="primary",
                                        on_click=set_admin_status, # Mudança aqui
                                        args=(user['email'], True),  # Mudança aqui
                                        use_container_width=True
                                    )
                            else:
                                st.button("Promover", disabled=True, use_container_width=True)

                        with action_cols[1]: # Resetar Senha
                             st.button(
                                 "Resetar Senha",
                                 key=f"reset_pass_sys_{user['_id']}",
                                 on_click=handle_password_reset,
                                 args=(user,),
                                 use_container_width=True
                             )

                        with action_cols[2]: # Remover Utilizador (Agora define o estado de confirmação)
                            st.button(
                                "Remover Utilizador",
                                key=f"del_user_sys_{user['_id']}",
                                type="secondary",
                                disabled=is_master_user_target,
                                on_click=lambda u_email=user['email']: setattr(st.session_state, 'confirming_delete_user', u_email), # Mudança aqui
                                use_container_width=True
                            )

    with system_tab_kpis:
        st.markdown("##### Metas de KPIs Globais")
        with st.form("kpi_targets_form"):
            target_margin = st.number_input("Meta da Margem de Contribuição (%)", value=configs.get('target_contribution_margin', 25.0))
            if st.form_submit_button("Salvar Metas", width='stretch'):
                configs['target_contribution_margin'] = target_margin
                save_global_configs(configs)
                get_global_configs.clear()
                st.rerun()

    with system_tab_email:
        st.markdown("##### Configuração Global de Envio de E-mail")
        st.caption("Estas credenciais serão usadas por toda a aplicação para enviar e-mails.")
        
        configs = get_global_configs()
        current_smtp_configs = configs.get('smtp_settings', {})
        current_provider = current_smtp_configs.get('provider', 'SendGrid')
        
        provider_options = ["SendGrid", "Gmail (SMTP)", "Mailersend", "Brevo"]
        provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
        
        # --- CORREÇÃO 1: O rádio fica FORA do formulário ---
        # Isso permite que a página recarregue (rerun) instantaneamente ao trocar a opção,
        # atualizando os campos abaixo sem precisar clicar em "Salvar".
        email_provider = st.radio(
            "Selecione o provedor de e-mail do sistema:", 
            provider_options, 
            horizontal=True, 
            index=provider_index,
            key="provider_selector_trigger"
        )
        
        # --- FORMULÁRIO 1: CREDENCIAIS ---
        with st.form("global_smtp_config_form"):
            from_email = ""
            credential = ""
            
            # --- CORREÇÃO 2: Chaves únicas (key) para cada provedor ---
            # Isso impede que o Streamlit "reaproveite" o texto de um provedor no outro.
            if email_provider == 'SendGrid':
                if current_smtp_configs.get('api_key_encrypted'): st.success("Configuração SendGrid ativa.", icon="✅")
                from_email = st.text_input("E-mail de Origem (SendGrid)", value=current_smtp_configs.get('from_email', ''), key="sg_from")
                credential = st.text_input("SendGrid API Key", type="password", placeholder="Nova chave API", key="sg_key")
            
            elif email_provider == 'Gmail (SMTP)':
                if current_smtp_configs.get('app_password_encrypted'): st.success("Configuração Gmail ativa.", icon="✅")
                st.info("Requer 'Senha de Aplicação' do Google.")
                from_email = st.text_input("E-mail de Origem (Gmail)", value=current_smtp_configs.get('from_email', ''), key="gm_from")
                credential = st.text_input("Senha de Aplicação", type="password", placeholder="App Password", key="gm_key")

            elif email_provider == 'Mailersend':
                if current_smtp_configs.get('mailersend_api_key_encrypted'): st.success("Configuração Mailersend ativa.", icon="✅")
                from_email = st.text_input("E-mail de Origem (Mailersend)", value=current_smtp_configs.get('from_email', ''), key="ms_from")
                credential = st.text_input("Mailersend API Key", type="password", placeholder="Nova chave API", key="ms_key")

            elif email_provider == 'Brevo':
                if current_smtp_configs.get('brevo_api_key_encrypted'): st.success("Configuração Brevo ativa.", icon="✅")
                from_email = st.text_input("E-mail de Origem (Brevo)", value=current_smtp_configs.get('from_email', ''), key="bv_from")
                credential = st.text_input("Brevo API Key (v3)", type="password", placeholder="Nova chave API", key="bv_key")

            if st.form_submit_button("Validar e Salvar Credenciais Globais", width='stretch', type="primary"):
                if from_email and credential:
                    with st.spinner("Validando credenciais..."):
                        is_valid, message = validate_smtp_connection(email_provider, from_email, credential)
                    
                    if is_valid:
                        encrypted_credential = encrypt_token(credential)
                        smtp_data_to_save = {
                            'provider': email_provider, 
                            'from_email': from_email,
                            'templates': current_smtp_configs.get('templates', {}) 
                        }
                        
                        if email_provider == 'SendGrid': smtp_data_to_save['api_key_encrypted'] = encrypted_credential
                        elif email_provider == 'Gmail (SMTP)': smtp_data_to_save['app_password_encrypted'] = encrypted_credential
                        elif email_provider == 'Mailersend': smtp_data_to_save['mailersend_api_key_encrypted'] = encrypted_credential
                        elif email_provider == 'Brevo': smtp_data_to_save['brevo_api_key_encrypted'] = encrypted_credential
                        
                        configs['smtp_settings'] = smtp_data_to_save
                        save_global_configs(configs) 
                        get_global_configs.clear()
                        st.success("Credenciais salvas com sucesso!")
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Preencha todos os campos para validar.")

        st.divider()

        # --- FORMULÁRIO 2: IDs DE TEMPLATE (Salvo individualmente) ---
        st.markdown("##### IDs de Templates Transacionais (Opcional)")
        st.caption("Insira o ID do template do seu provedor (ex: Brevo, SendGrid) para substituir os e-mails HTML padrão.")
        
        current_templates = current_smtp_configs.get('templates', {})

        with st.form("templates_form"):
            password_recovery_id = st.text_input(
                "ID Template - Recuperação de Senha", 
                value=current_templates.get('password_recovery', ''),
                placeholder="Ex: 5"
            )
            welcome_id = st.text_input(
                "ID Template - Boas-Vindas", 
                value=current_templates.get('welcome', ''),
                placeholder="Ex: 2"
            )
            
            if st.form_submit_button("Salvar Configurações de Template", width='stretch', type="secondary"):
                # Este botão SÓ salva os IDs dos templates
                
                # Garante que as configs e as smtp_settings existem
                if 'smtp_settings' not in configs:
                    configs['smtp_settings'] = {}
                
                # Atualiza apenas o sub-dicionário de templates
                configs['smtp_settings']['templates'] = {
                    'password_recovery': password_recovery_id,
                    'welcome': welcome_id
                }
                
                # Salva as alterações
                save_global_configs(configs)
                get_global_configs.clear()
                st.success("IDs de template salvos com sucesso!")
                st.rerun()

    with tab_link:
        st.subheader("Configurações Gerais da Aplicação")
        with st.form("general_configs_form"):
            st.markdown("#### URL Base da Aplicação")
            st.info("Esta URL é usada para gerar links partilháveis, como os de autoavaliação.")
            base_url_input = st.text_input(
                "URL Base", 
                value=configs.get("app_base_url", ""),
                placeholder="https://seu-app.streamlit.app"
            )
            st.divider()
            st.markdown("#### Domínios Permitidos para Cadastro")
            st.info("Defina os domínios de e-mail que podem se cadastrar na aplicação. Separe múltiplos domínios por vírgula.")
            allowed_domains_input = st.text_area(
                "Domínios de E-mail Permitidos",
                value=", ".join(configs.get("allowed_domains", [])),
                placeholder="exemplo.com, outrodominio.com.br"
            )
            if st.form_submit_button("Salvar Configurações Gerais", type="primary", width='stretch'):
                configs['app_base_url'] = base_url_input
                configs['allowed_domains'] = [domain.strip() for domain in allowed_domains_input.split(',') if domain.strip()]
                save_global_configs(configs)
                get_global_configs.clear()
                st.success("Configurações gerais salvas com sucesso!")
                st.rerun()