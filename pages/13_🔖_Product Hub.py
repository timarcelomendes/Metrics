# pages/13_🔖_Product Hub.py - CÓDIGO COMPLETO E ATUALIZADO

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from security import *
from pathlib import Path
from config import SESSION_TIMEOUT_MINUTES
import uuid

# --- Configuração da Página ---
st.set_page_config(page_title="Gauge Product Hub", page_icon="🚀", layout="wide")

# ==============================================================================
# --- DEFINIÇÕES ESTRUTURANTIS (CONTEÚDO ESTÁTICO) ---
# ==============================================================================
SKILL_LEVELS = {
    0: {"name": "Não Avaliado", "desc": "Ainda não foi definido um nível para esta competência."},
    1: {"name": "Iniciante", "desc": "Possui conhecimento teórico, mas precisa de supervisão constante para aplicar na prática."},
    2: {"name": "Iniciante Avançado", "desc": "Consegue aplicar a competência em tarefas simples e com alguma supervisão. Segue processos definidos."},
    3: {"name": "Proficiente", "desc": "Atua de forma autônoma na maioria das situações. Contribui ativamente e pode orientar os menos experientes."},
    4: {"name": "Avançado", "desc": "Domina a competência em cenários complexos. É uma referência para o time e propõe melhorias nos processos."},
    5: {"name": "Especialista", "desc": "É uma referência na empresa. Inova, cria novas práticas e mentora outros, influenciando a estratégia."}
}

# ==============================================================================
# --- FUNÇÕES AUXILIARES ---
# ==============================================================================

def get_all_competencies_from_framework(framework):
    all_competencies = []
    all_competencies.extend(framework.get('hard_skills', []))
    all_competencies.extend(framework.get('soft_skills', []))
    return all_competencies

def sync_evaluations_with_framework():
    if 'competency_framework' not in st.session_state or 'membros' not in st.session_state or st.session_state.membros.empty:
        return
    framework = st.session_state.get('competency_framework', {})
    all_competencies = get_all_competencies_from_framework(framework)
    current_competency_names = {comp.get('Competência') for comp in all_competencies if comp.get('Competência')}
    
    for member_name in st.session_state.membros['Nome'].tolist():
        if member_name not in st.session_state.avaliacoes:
            st.session_state.avaliacoes[member_name] = {}
        
        evaluations = st.session_state.avaliacoes[member_name]
        
        for comp_name in current_competency_names:
            if comp_name not in evaluations:
                evaluations[comp_name] = {"leader": {"level": 0, "pdi": ""}, "member": {"level": 0, "pdi": ""}}
        
        for comp_name in list(evaluations.keys()):
            if comp_name not in current_competency_names:
                del evaluations[comp_name]

def save_and_rerun():
    # Salva apenas os dados relevantes para o hub do utilizador
    user_hub_data = {
        'membros': st.session_state.membros.to_dict('records'),
        'avaliacoes': st.session_state.avaliacoes,
        'one_on_ones': st.session_state.one_on_ones,
    }
    save_user_product_hub_data(st.session_state['email'], user_hub_data)
    st.success("Dados do Hub guardados com sucesso!")
    st.rerun()

def load_data():
    if 'hub_data_loaded' in st.session_state:
        return
    try:
        get_global_configs.clear()
    except Exception:
        pass
    
    global_configs = get_global_configs() or {}
    
    st.session_state.playbooks = global_configs.get('playbooks', {})
    st.session_state.competency_framework = global_configs.get('competency_framework', {})
    
    # Carrega os papéis da Administração
    user_roles_raw = global_configs.get('user_roles', [])
    migrated_roles = []
    for role in user_roles_raw:
        if isinstance(role, str): # Lógica de migração de dados antigos
            migrated_roles.append({"id": str(uuid.uuid4()), "name": role, "description": ""})
        elif isinstance(role, dict) and 'id' in role:
            migrated_roles.append(role)
    st.session_state.user_roles = migrated_roles

    # Carrega os dados específicos do utilizador
    user_hub_data = get_user_product_hub_data(st.session_state['email'])
    
    membros_data = user_hub_data.get('membros', [])
    st.session_state.membros = pd.DataFrame(membros_data, columns=["Nome", "Papel"])
    
    st.session_state.avaliacoes = user_hub_data.get('avaliacoes', {})
    st.session_state.one_on_ones = user_hub_data.get('one_on_ones', {})
          
    sync_evaluations_with_framework()
    st.session_state['hub_data_loaded'] = True

# ==============================================================================
# --- ESTRUTURA PRINCIPAL DA PÁGINA ---
# ==============================================================================

st.markdown("<h1 style='text-align: center; color: #262730;'>🚀 Gauge Product Hub</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size: 1.1rem; color: #525f7f;'>Bem-vindo ao centro de conhecimento e padrões do seu produto.</p>", unsafe_allow_html=True)
st.markdown("---")

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()

if 'jira_client' not in st.session_state:
    user_connections = get_user_connections(st.session_state['email'])
    if not user_connections:
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌"); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗"); st.stop()
    else:
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡"); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

load_data()

with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(logo_path, size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 
    
    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")
        
    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- ABAS PRINCIPAIS ---
tab_playbook, tab_papeis, tab_competencias, tab_gestao = st.tabs([
    "**📖 Playbook**", "**🎭 Papéis**", "**⚙️ Competências**",
    "**👥 Gestão de Pessoas**"
])

with tab_playbook:
    st.markdown('<p class="section-header">O Playbook de Produto</p>', unsafe_allow_html=True)
    playbooks_to_show = st.session_state.get('playbooks', {})
    
    if not playbooks_to_show:
        st.info("Nenhum playbook foi configurado ainda. Peça a um administrador para adicionar conteúdo.")
    else:
        playbook_titles = list(playbooks_to_show.keys())
        sub_tabs = st.tabs([f"**{title}**" for title in playbook_titles])
        
        for i, tab in enumerate(sub_tabs):
            with tab:
                playbook_title = playbook_titles[i]
                playbook_content = playbooks_to_show[playbook_title]
                st.markdown(playbook_content, unsafe_allow_html=True)

with tab_papeis:
    st.markdown('<p class="section-header">Papéis e Responsabilidades</p>', unsafe_allow_html=True)
    roles_from_admin = st.session_state.get('user_roles', [])
    if not roles_from_admin:
        st.warning("Nenhum papel cadastrado na área de Administração.", icon="👑")
    else:
        for role_data in roles_from_admin:
            with st.expander(f"**{role_data['name']}**", expanded=False):
                st.markdown(role_data.get('description', 'Nenhuma descrição.'), unsafe_allow_html=True)

with tab_competencias:
    st.markdown('<p class="section-header">Framework de Competências</p>', unsafe_allow_html=True)
    framework = st.session_state.get('competency_framework', {})
    
    if not framework or (not framework.get('hard_skills') and not framework.get('soft_skills')):
        st.info("O Framework de Competências ainda não foi definido. Peça a um administrador para o configurar.")
    else:
        tab_hard, tab_soft = st.tabs(["**🛠️ Hard Skills**", "**🧠 Soft Skills**"])

        def display_skills(skills_list):
            if not skills_list:
                st.info("Nenhuma competência deste tipo foi definida.")
                return
            
            for skill in skills_list:
                with st.expander(f"**{skill.get('Competência', 'N/A')}**"):
                    st.caption(skill.get('Descrição', 'Nenhuma descrição fornecida.'))

        with tab_hard:
            display_skills(framework.get('hard_skills', []))

        with tab_soft:
            display_skills(framework.get('soft_skills', []))

with tab_gestao:
    st.markdown('<p class="section-header">Gestão de Pessoas (Chapter)</p>', unsafe_allow_html=True)
    # --- INÍCIO DA ALTERAÇÃO ---
    sub_tab_membros, sub_tab_matriz, sub_tab_1on1s, sub_tab_assessment = st.tabs([
        "**👥 Time**", "**📊 Matriz de Competências**", "**💬 Registro de 1-on-1s**", "**🚀 Enviar Avaliação**"
    ])
    # --- FIM DA ALTERAÇÃO ---
    
    with sub_tab_membros:
        role_names = [role['name'] for role in st.session_state.get('user_roles', [])]
        
        with st.expander("➕ Adicionar Novo Membro"):
            with st.form("novo_membro_form", clear_on_submit=True):
                nome = st.text_input("Nome do Membro")
                papel = st.selectbox("Papel", role_names if role_names else ["Nenhum papel cadastrado"])
                if st.form_submit_button("Adicionar Membro", type="primary"):
                    if nome and nome not in st.session_state.membros['Nome'].tolist():
                        novo_membro = pd.DataFrame([{"Nome": nome, "Papel": papel}])
                        st.session_state.membros = pd.concat([st.session_state.membros, novo_membro], ignore_index=True)
                        sync_evaluations_with_framework(); save_and_rerun()
        st.dataframe(st.session_state.membros, use_container_width=True)

    with sub_tab_matriz:
        st.subheader("Avaliação e Desenvolvimento")
        if st.session_state.membros.empty:
            st.warning("Adicione membros ao time na aba 'Time' para começar.")
        else:
            sub_tab_aval, sub_tab_dash = st.tabs(["Avaliação Individual", "Visão Geral do Time"])
            with sub_tab_aval:
                membro_selecionado = st.selectbox("Selecione um membro para avaliar:", st.session_state.membros['Nome'].tolist(), key="aval_member_select")
                
                if membro_selecionado:
                    sync_evaluations_with_framework()
                    aval_lider, aval_membro, aval_comp = st.tabs(["Avaliação do Líder", "Autoavaliação", "Comparativo & PDI"])
                    
                    framework = st.session_state.competency_framework
                    hard_skills = framework.get('hard_skills', [])
                    soft_skills = framework.get('soft_skills', [])

                    def render_evaluation_ui(eval_type, skills_list, member_name):
                        if not skills_list: return
                        with st.container(border=True):
                            for skill in skills_list:
                                comp = skill['Competência']
                                st.markdown(f"**{comp}**")
                                level = st.slider("Nível", 0, 5, value=st.session_state.avaliacoes[member_name][comp][eval_type]['level'], key=f"level_{eval_type}_{member_name}_{comp}")
                                st.info(f"**{SKILL_LEVELS[level]['name']}:** {SKILL_LEVELS[level]['desc']}")
                                pdi_text = "Plano de Desenvolvimento (Líder)" if eval_type == 'leader' else "Comentários / Autoavaliação (Membro)"
                                pdi = st.text_area(pdi_text, value=st.session_state.avaliacoes[member_name][comp][eval_type]['pdi'], key=f"pdi_{eval_type}_{member_name}_{comp}", height=100)
                                st.session_state.avaliacoes[member_name][comp][eval_type]['level'] = level
                                st.session_state.avaliacoes[member_name][comp][eval_type]['pdi'] = pdi
                                st.markdown("---")
                    
                    with aval_lider:
                        lider_hard, lider_soft = st.tabs(["🛠️ Hard Skills", "🧠 Soft Skills"])
                        with lider_hard: render_evaluation_ui('leader', hard_skills, membro_selecionado)
                        with lider_soft: render_evaluation_ui('leader', soft_skills, membro_selecionado)

                    with aval_membro:
                        membro_hard, membro_soft = st.tabs(["🛠️ Hard Skills", "🧠 Soft Skills"])
                        with membro_hard: render_evaluation_ui('member', hard_skills, membro_selecionado)
                        with membro_soft: render_evaluation_ui('member', soft_skills, membro_selecionado)
                    
                    with aval_comp:
                        st.subheader(f"Comparativo de Avaliações: {membro_selecionado}")
                        dados_avaliacoes = st.session_state.avaliacoes[membro_selecionado]
                        all_competencies = get_all_competencies_from_framework(framework)
                        competencies_list = [c['Competência'] for c in all_competencies]
                        levels_leader = [dados_avaliacoes.get(comp, {}).get('leader', {}).get('level', 0) for comp in competencies_list]
                        levels_member = [dados_avaliacoes.get(comp, {}).get('member', {}).get('level', 0) for comp in competencies_list]
                        
                        fig = go.Figure()
                        fig.add_trace(go.Scatterpolar(r=levels_leader, theta=competencies_list, fill='toself', name='Avaliação do Líder'))
                        fig.add_trace(go.Scatterpolar(r=levels_member, theta=competencies_list, fill='toself', name='Autoavaliação'))
                        st.plotly_chart(fig, use_container_width=True)

                    if st.button("Salvar Avaliações", use_container_width=True, type="primary", key="save_eval_button"):
                        save_and_rerun()
            
            with sub_tab_dash:
                st.subheader("Dashboard de Competências do Time")
                dados_completos = []
                for membro, avaliacoes in st.session_state.avaliacoes.items():
                    for comp, data in avaliacoes.items():
                        if 'leader' in data:
                            dados_completos.append({"Membro": membro, "Competência": comp, "Nível": data['leader']['level']})
                
                if not dados_completos:
                    st.info("Nenhuma avaliação registrada ainda.")
                else:
                    df_completo = pd.DataFrame(dados_completos)
                    st.markdown("#### Distribuição de Níveis por Competência")
                    all_competencies_df = pd.DataFrame(get_all_competencies_from_framework(st.session_state.competency_framework))
                    competencias_list = all_competencies_df['Competência'].unique().tolist() if not all_competencies_df.empty else []
                    comp_selecionada = st.selectbox("Selecione a Competência", competencias_list)
                    
                    if comp_selecionada:
                        dados_filtrados = df_completo[df_completo['Competência'] == comp_selecionada]
                        niveis_contagem = dados_filtrados['Nível'].value_counts().sort_index()
                        niveis_contagem.index = niveis_contagem.index.map(lambda x: SKILL_LEVELS.get(x, {}).get('name', 'N/A'))
                        fig_bar = px.bar(niveis_contagem, x=niveis_contagem.index, y=niveis_contagem.values, labels={"x": "Nível", "y": "Nº de Pessoas"}, text_auto=True)
                        st.plotly_chart(fig_bar, use_container_width=True)
                    
                    st.markdown("#### Mapa de Calor de Competências")
                    if not df_completo.empty:
                        df_pivot = df_completo.pivot_table(index="Membro", columns="Competência", values="Nível")
                        fig_heatmap = go.Figure(data=go.Heatmap(z=df_pivot.values, x=df_pivot.columns, y=df_pivot.index, colorscale='Viridis'))
                        st.plotly_chart(fig_heatmap, use_container_width=True)

    with sub_tab_1on1s:
        st.subheader("Acompanhamento Individual")
        if not st.session_state.membros.empty:
            membro_1on1 = st.selectbox("Selecione o membro:", st.session_state.membros['Nome'], key="1on1_membro")
            with st.form("form_1on1", clear_on_submit=True):
                data_1on1 = st.date_input("Data da Conversa")
                anotacoes = st.text_area("Pontos discutidos, ações e próximos passos:", height=200)
                if st.form_submit_button("Salvar Registro", type="primary"):
                    if anotacoes and membro_1on1:
                        if membro_1on1 not in st.session_state.one_on_ones:
                            st.session_state.one_on_ones[membro_1on1] = []
                        registro = {"data": str(data_1on1), "anotacoes": anotacoes}
                        st.session_state.one_on_ones[membro_1on1].append(registro)
                        save_and_rerun()
            
            if membro_1on1:
                st.subheader(f"Histórico de {membro_1on1}")
                if membro_1on1 in st.session_state.one_on_ones and st.session_state.one_on_ones[membro_1on1]:
                    for registro in sorted(st.session_state.one_on_ones[membro_1on1], key=lambda x: x['data'], reverse=True):
                        with st.expander(f"**Data:** {registro['data']}"):
                            st.write(registro['anotacoes'])
                else:
                    st.info(f"Nenhum registro de 1-on-1 para {membro_1on1} ainda.")
        else:
            st.warning("Adicione membros ao time primeiro.")
            
    with sub_tab_assessment:
        st.subheader("Gerar e Enviar Links para Autoavaliação")
        st.info("Selecione os membros da equipa para quem deseja gerar um link de avaliação. Os links são de uso único e expiram em 72 horas.")

        if st.session_state.membros.empty:
            st.warning("Nenhum membro encontrado. Adicione membros na aba 'Time' primeiro.")
        else:
            member_names = st.session_state.membros['Nome'].tolist()

            selected_members = st.multiselect(
                "Selecione um ou mais membros:",
                options=member_names
            )

            if st.button("Gerar Links de Avaliação", type="primary", use_container_width=True, disabled=not selected_members):
                base_url = ""
                try:
                    # Tenta obter a URL base da aplicação
                    base_url = st.get_option("server.baseUrlPath")
                except Exception:
                    pass # Ignora o erro se a opção não estiver disponível (ex: localmente)

                if not base_url or base_url == "/":
                     st.warning("A URL base da aplicação não foi detectada automaticamente.")
                     base_url = st.text_input("Por favor, insira a URL completa da sua aplicação (ex: https://meu-app.streamlit.app)")

                if base_url:
                    with st.spinner("A gerar links..."):
                        for name in selected_members:
                            token = generate_assessment_token(name)
                            # Constrói a URL completa para a página de avaliação
                            assessment_url = f"{base_url.rstrip('/')}/15_📝_Auto_Avaliação?token={token}"
                            
                            st.markdown(f"**Link para {name}:**")
                            st.code(assessment_url, language=None)
                    
                    st.success("Links gerados com sucesso! Copie e envie os links para os respetivos utilizadores.")
