# pages/13_🚀_Product_Hub.py

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from security import get_global_configs, get_user_product_hub_data, save_user_product_hub_data
from pathlib import Path

# --- Configuração da Página ---
st.set_page_config(
    page_title="Gauge Product Hub",
    page_icon="🚀",
    layout="wide"
)

# --- Bloco de Autenticação ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

# ==============================================================================
# --- DEFINIÇÕES ESTRUTURANTES (CONTEÚDO ESTÁTICO) ---
# ==============================================================================

SKILL_LEVELS = {
    0: {"name": "Não Avaliado", "desc": "Ainda não foi definido um nível para esta competência."},
    1: {"name": "Iniciante", "desc": "Possui conhecimento teórico, mas precisa de supervisão constante para aplicar na prática."},
    2: {"name": "Iniciante Avançado", "desc": "Consegue aplicar a competência em tarefas simples e com alguma supervisão. Segue processos definidos."},
    3: {"name": "Proficiente", "desc": "Atua de forma autônoma na maioria das situações. Contribui ativamente e pode orientar os menos experientes."},
    4: {"name": "Avançado", "desc": "Domina a competência em cenários complexos. É uma referência para o time e propõe melhorias nos processos."},
    5: {"name": "Especialista", "desc": "É uma referência na empresa. Inova, cria novas práticas e mentora outros, influenciando a estratégia."}
}

DEFAULT_PLAYBOOKS = {
    "Geral (Manifesto)": """
### Nosso Manifesto de Produto
Este playbook é o guia oficial para a criação e gestão de produtos na Gauge...
- **Resultados acima de Entregas (Outcomes over Outputs):** ...
""",
    "Discovery": """
### O Processo de Discovery (Descoberta de Produto)
Fazer um bom Product Discovery é a etapa mais crucial para evitar a construção de produtos que ninguém quer...
"""
}

ROLES = {
    "PM": {
        "missao": "Ser a voz estratégica do cliente e do mercado dentro da Gauge, garantindo que a solução desenvolvida não apenas atenda aos requisitos, mas principalmente gere resultados de negócio mensuráveis e maximize o valor do contrato. O PM é o 'CEO' do produto/solução do cliente.",
        "principais_responsabilidades": [
            "Definir e comunicar a visão e a estratégia de longo prazo do produto, em alinhamento com os objetivos de negócio do cliente.",
            "Gerenciar o roadmap do produto, priorizando iniciativas e épicos que tragam maior impacto (outcome over output).",
            "Realizar pesquisas de mercado, análise competitiva e de usuários para identificar oportunidades e validar hipóteses.",
            "Definir e acompanhar as métricas de sucesso do produto (KPIs e OKRs), reportando o progresso para stakeholders C-level do cliente e da Gauge.",
            "Atuar como o principal ponto de contato para stakeholders estratégicos do cliente, garantindo alinhamento e gerenciando expectativas.",
            "Colaborar com o time comercial em oportunidades de upsell e renovação de contrato, baseado no valor gerado pelo produto."
        ]
    },
    "PO": {
        "missao": "Maximizar o valor do trabalho entregue pelo time de desenvolvimento a cada sprint. O PO traduz a estratégia do PM em um backlog de produto tático, claro, priorizado e pronto para ser executado pela squad.",
        "principais_responsabilidades": [
            "Criar, gerenciar e priorizar o Product Backlog, garantindo que ele esteja visível, transparente e compreendido por todos.",
            "Escrever histórias de usuário (User Stories) detalhadas e com critérios de aceite claros.",
            "Planejar as Sprints em colaboração com a squad e o Scrum Master.",
            "Ser o ponto de contato diário para o time de desenvolvimento, esclarecendo dúvidas sobre os itens do backlog.",
            "Validar e aceitar as histórias entregues ao final da Sprint, garantindo que atendem aos critérios de aceite e à 'Definição de Pronto' (DoD).",
            "Participar ativamente das cerimônias ágeis (Planning, Review, Retrospective)."
        ]
    },
    "ANALISTA_PRODUTO": {
        "missao": "Suportar o Product Manager e o Product Owner com dados e análises quantitativas e qualitativas, fornecendo os insumos necessários para uma tomada de decisão informada sobre a estratégia e o backlog do produto.",
        "principais_responsabilidades": [
            "Coletar e analisar dados de uso do produto, funis de conversão e comportamento do usuário (usando ferramentas como Google Analytics, Hotjar, etc.).",
            "Construir e manter dashboards para acompanhar as métricas de produto e de negócio.",
            "Conduzir pesquisas com usuários (entrevistas, questionários) para coletar feedback e validar hipóteses.",
            "Apoiar na documentação de requisitos, regras de negócio e fluxos do usuário.",
            "Ajudar a preparar relatórios de performance do produto para o PM e para o cliente."
        ]
    },
    "SM": {
        "missao": "Atuar como um líder-servidor para a squad, garantindo que o time siga os valores e práticas do framework ágil (Scrum/Kanban) e removendo quaisquer impedimentos que possam atrapalhar seu progresso. O Scrum Master é o guardião do processo.",
        "principais_responsabilidades": [
            "Facilitar todas as cerimônias ágeis (Daily, Planning, Review, Retrospective), garantindo que sejam produtivas e mantenham o foco.",
            "Identificar, endereçar e escalar impedimentos que estejam bloqueando ou desacelerando o time.",
            "Proteger o time de interrupções externas e garantir que possam trabalhar em um ritmo sustentável.",
            "Promover uma cultura de melhoria contínua, colaboração e auto-organização na squad.",
            "Coletar e dar visibilidade às métricas ágeis (Velocity, Cycle Time, etc.) para apoiar a previsibilidade e a melhoria do fluxo de trabalho.",
            "Atuar como um coach de agilidade para o time, o PO e, quando necessário, para o cliente."
        ]
    },
    "SDM": {
        "missao": "Garantir a entrega de serviços de TI com excelência, gerenciando o relacionamento com o cliente do ponto de vista operacional e contratual. O SDM assegura que os acordos de nível de serviço (SLAs) sejam cumpridos e que o cliente esteja satisfeito com a qualidade geral do serviço prestado pela Gauge.",
        "principais_responsabilidades": [
            "Ser o principal ponto de contato do cliente para questões operacionais, contratuais e de governança.",
            "Garantir o cumprimento dos SLAs e KPIs definidos em contrato.",
            "Conduzir reuniões de governança (ex: comitês estratégicos e táticos) para reportar a performance do serviço.",
            "Gerenciar crises e atuar como ponto de escalação para incidentes críticos.",
            "Supervisionar o processo de gestão de mudanças, problemas e incidentes.",
            "Identificar oportunidades de melhoria contínua no serviço (CSI - Continual Service Improvement)."
        ]
    },
    "SRM": {
        "missao": "Gerenciar o ciclo de vida de todas as requisições de serviço, desde a abertura até o fechamento, garantindo que sejam atendidas de forma eficiente, dentro dos prazos acordados (SLAs) e com alta qualidade, proporcionando uma excelente experiência ao usuário.",
        "principais_responsabilidades": [
            "Receber, categorizar e priorizar todas as requisições de serviço (tickets, chamados) em uma plataforma de ITSM.",
            "Garantir que as requisições sejam atribuídas corretamente às equipes ou indivíduos responsáveis.",
            "Monitorar o progresso das requisições, identificando e atuando em possíveis violações de SLA.",
            "Manter o cliente/usuário informado sobre o status de suas solicitações.",
            "Analisar dados sobre requisições para identificar tendências, problemas recorrentes e oportunidades de automação ou melhoria no catálogo de serviços."
        ]
    },
    "SQUAD_LEADER": {
        "missao": "Liderar tecnicamente a squad, garantindo a qualidade, a excelência técnica e a viabilidade das soluções desenvolvidas. É responsável por guiar e mentorar os membros do time de desenvolvimento, promovendo o crescimento técnico e um ambiente de trabalho colaborativo e de alta performance.",
        "principais_responsabilidades": [
            "Liderar as decisões de arquitetura e design técnico das soluções, em conjunto com o time.",
            "Garantir a qualidade do código e das entregas através de práticas como Code Review, testes automatizados e pair programming.",
            "Remover impedimentos de natureza técnica que afetem a squad.",
            "Mentorar e apoiar o desenvolvimento técnico dos membros do time.",
            "Atuar como o principal ponto de referência técnico, colaborando com o PO para refinar requisitos e garantir a viabilidade técnica das histórias.",
            "Promover a inovação e a adoção de novas tecnologias e boas práticas de engenharia de software."
        ]
    }
}

# ==============================================================================
# --- LÓGICA DA PÁGINA ---
# ==============================================================================

def get_all_competencies_from_framework(framework):
    """Junta Hard e Soft skills numa lista única de dicionários."""
    all_competencies = []
    hard_skills = framework.get('hard_skills', [])
    soft_skills = framework.get('soft_skills', [])
    all_competencies.extend(hard_skills)
    all_competencies.extend(soft_skills)
    return all_competencies

def sync_evaluations_with_framework():
    """Garante que a estrutura de avaliação de cada membro corresponde ao framework global."""
    if 'competency_framework' not in st.session_state or st.session_state.membros.empty:
        return

    framework = st.session_state.competency_framework
    all_competencies = get_all_competencies_from_framework(framework)
    current_competency_names = [comp.get('Competência') for comp in all_competencies if comp.get('Competência')]
    
    membros_atuais = st.session_state.membros['Nome'].tolist()
    
    for member_name in membros_atuais:
        if member_name not in st.session_state.avaliacoes:
            st.session_state.avaliacoes[member_name] = {}
        
        evaluations = st.session_state.avaliacoes[member_name]
        
        # Adiciona competências que estão no framework mas não na avaliação do membro
        for comp_name in current_competency_names:
            if comp_name not in evaluations:
                evaluations[comp_name] = {"leader": {"level": 0, "pdi": ""}, "member": {"level": 0, "pdi": ""}}
        
        # Remove competências da avaliação do membro que não existem mais no framework
        for comp_name in list(evaluations.keys()):
            if comp_name not in current_competency_names:
                del evaluations[comp_name]
        
        st.session_state.avaliacoes[member_name] = evaluations

def load_data():
    """Carrega todos os dados necessários para o Hub, priorizando configurações globais."""
    if 'hub_data_loaded' not in st.session_state:
        global_configs = get_global_configs()
        st.session_state.competency_framework = global_configs.get('competency_framework', {})
        st.session_state.playbooks = global_configs.get('playbooks', DEFAULT_PLAYBOOKS)

        user_hub_data = get_user_product_hub_data(st.session_state['email'])
        
        membros_data = user_hub_data.get('membros')
        # --- INÍCIO DA CORREÇÃO ---
        # Trata o caso de 'membros_data' ser None ou uma lista vazia de forma segura
        if membros_data is not None:
            st.session_state.membros = pd.DataFrame(membros_data)
        else:
            st.session_state.membros = pd.DataFrame(columns=["Nome", "Papel"])
        # --- FIM DA CORREÇÃO ---
        
        st.session_state.avaliacoes = user_hub_data.get('avaliacoes', {})
        st.session_state.one_on_ones = user_hub_data.get('one_on_ones', {})
        st.session_state.cases_sucesso = user_hub_data.get('cases_sucesso', [])
        
        # Garante que as colunas 'Nome' e 'Papel' existam
        if st.session_state.membros.empty:
             st.session_state.membros = pd.DataFrame(columns=["Nome", "Papel"])
        else:
            if 'Nome' not in st.session_state.membros.columns:
                st.session_state.membros['Nome'] = ""
            if 'Papel' not in st.session_state.membros.columns:
                st.session_state.membros['Papel'] = ""
            st.session_state.membros = st.session_state.membros[['Nome', 'Papel']]
             
        st.session_state.hub_data_loaded = True
        sync_evaluations_with_framework()

load_data()

def save_and_rerun():
    """Salva os dados do Hub específicos do utilizador (membros, avaliações, etc.)."""
    user_hub_data = {
        'membros': st.session_state.membros.to_dict('records'),
        'avaliacoes': st.session_state.avaliacoes,
        'one_on_ones': st.session_state.one_on_ones,
        'cases_sucesso': st.session_state.cases_sucesso,
    }
    save_user_product_hub_data(st.session_state['email'], user_hub_data)
    st.success("Dados do Hub guardados com sucesso!")
    if 'hub_data_loaded' in st.session_state:
        del st.session_state['hub_data_loaded']
    st.rerun()

# --- Interface Principal ---
st.title("🔖 Product Hub")
st.markdown("Bem-vindo ao centro de conhecimento e padrões do seu produto.")

tab_playbook, tab_papeis, tab_competencias, tab_gestao, tab_cases = st.tabs([
    "📖 Playbook", "🎭 Papéis", "⚙️ Competências",
    "👥 Gestão de Pessoas", "🏆 Cases de Sucesso"
])

with tab_playbook:
    st.header("O Playbook de Produto da Gauge")

    if not st.session_state.playbooks:
        st.warning("Nenhum playbook foi configurado ainda. Peça a um administrador para adicionar conteúdo.")
    else:
        playbook_tabs = st.tabs(list(st.session_state.playbooks.keys()))
        for i, theme_name in enumerate(st.session_state.playbooks.keys()):
            with playbook_tabs[i]:
                st.markdown(st.session_state.playbooks[theme_name])

with tab_papeis:
    st.header("Papéis e Responsabilidades")
    
    role_keys = list(ROLES.keys())
    papeis_tabs = st.tabs([key for key in role_keys])
    
    for i, role_key in enumerate(role_keys):
        with papeis_tabs[i]:
            role_data = ROLES[role_key]
            
            st.subheader("Missão")
            st.markdown(role_data["missao"])
            
            st.subheader("Principais Responsabilidades")
            for resp in role_data["principais_responsabilidades"]:
                st.markdown(f"- {resp}")

with tab_competencias:
    st.header("🚀 Framework de Competências", divider='rainbow')
    st.caption("O nosso modelo de competências, servindo como um guia para o desenvolvimento e avaliação das nossas equipas.")

    framework = st.session_state.competency_framework
    if not framework or (not framework.get('hard_skills') and not framework.get('soft_skills')):
        st.info("O Framework de Competências ainda não foi definido. Por favor, peça a um administrador para o configurar.")
    else:
        tab_hard, tab_soft = st.tabs(["🛠️ Hard Skills", "🧠 Soft Skills"])

        with tab_hard:
            hard_skills = framework.get('hard_skills', [])
            if not hard_skills:
                st.write("Nenhuma Hard Skill definida.")
            else:
                df_hard = pd.DataFrame(hard_skills)
                if 'Pilar' in df_hard.columns:
                    for pilar, group in df_hard.groupby('Pilar'):
                        with st.expander(f"**Pilar: {pilar}**", expanded=True):
                            for i, (_, row) in enumerate(group.iterrows()):
                                st.markdown(f"**{row['Competência']}**")
                                st.caption(row.get('Descrição', 'Nenhuma descrição fornecida.'))
                                if i < len(group) - 1: st.divider()
                else:
                    st.warning("Dados de competências antigos detetados. Peça a um admin para adicionar os 'Pilares'.")
                    for _, row in df_hard.iterrows():
                        st.markdown(f"**{row['Competência']}**")
                        st.caption(row.get('Descrição', 'Nenhuma descrição fornecida.'))
                        st.divider()

        with tab_soft:
            soft_skills = framework.get('soft_skills', [])
            if not soft_skills:
                st.write("Nenhuma Soft Skill definida.")
            else:
                df_soft = pd.DataFrame(soft_skills)
                if 'Pilar' in df_soft.columns:
                    for pilar, group in df_soft.groupby('Pilar'):
                        with st.expander(f"**Pilar: {pilar}**", expanded=True):
                            for i, (_, row) in enumerate(group.iterrows()):
                                st.markdown(f"**{row['Competência']}**")
                                st.caption(row.get('Descrição', 'Nenhuma descrição fornecida.'))
                                if i < len(group) - 1: st.divider()
                else:
                    st.warning("Dados de competências antigos detetados. Peça a um admin para adicionar os 'Pilares'.")
                    for _, row in df_soft.iterrows():
                        st.markdown(f"**{row['Competência']}**")
                        st.caption(row.get('Descrição', 'Nenhuma descrição fornecida.'))
                        st.divider()

with tab_gestao:
    st.header("Gestão de Pessoas (Chapter)")
    sub_tab_membros, sub_tab_matriz, sub_tab_1on1s = st.tabs(["Membros do Time", "Matriz de Competências", "Acompanhamento de 1-on-1s"])
    
    with sub_tab_membros:
        st.subheader("Cadastro de Membros")
        with st.form("novo_membro_form", clear_on_submit=True):
            nome = st.text_input("Nome do Membro")
            papel = st.selectbox("Papel", list(ROLES.keys()))
            if st.form_submit_button("Adicionar Membro"):
                if nome and nome not in st.session_state.membros['Nome'].tolist():
                    novo_membro = pd.DataFrame([{"Nome": nome, "Papel": papel}])
                    st.session_state.membros = pd.concat([st.session_state.membros, novo_membro], ignore_index=True)
                    sync_evaluations_with_framework()
                    save_and_rerun()
        st.subheader("Time Atual")
        st.dataframe(st.session_state.membros, use_container_width=True)

    with sub_tab_matriz:
        st.subheader("Matriz de Competências")
        if st.session_state.membros.empty:
            st.warning("Adicione membros ao time na aba 'Membros' para começar.")
        else:
            sub_tab_aval, sub_tab_dash = st.tabs(["Avaliação Individual", "Visão Geral do Time"])
            with sub_tab_aval:
                nomes_membros = st.session_state.membros['Nome'].tolist()
                membro_selecionado = st.selectbox("Selecione um membro para avaliar:", nomes_membros, key="aval_member_select")
                
                if membro_selecionado:
                    sync_evaluations_with_framework()
                    aval_lider, aval_membro, aval_comp = st.tabs(["Avaliação do Líder", "Autoavaliação", "Comparativo & PDI"])
                    
                    framework = st.session_state.competency_framework
                    hard_skills = framework.get('hard_skills', [])
                    soft_skills = framework.get('soft_skills', [])

                    def render_evaluation_ui(eval_type, skills_list, member_name):
                        if not skills_list: return
                        df_skills = pd.DataFrame(skills_list)
                        if 'Pilar' in df_skills.columns:
                            for pilar, group in df_skills.groupby('Pilar'):
                                with st.container(border=True):
                                    st.markdown(f"##### Pilar: {pilar}")
                                    for _, row in group.iterrows():
                                        comp = row['Competência']
                                        st.markdown(f"**{comp}**")
                                        level = st.slider("Nível", 0, 5, value=st.session_state.avaliacoes[member_name][comp][eval_type]['level'], key=f"level_{eval_type}_{member_name}_{comp}")
                                        st.info(f"**{SKILL_LEVELS[level]['name']}:** {SKILL_LEVELS[level]['desc']}")
                                        pdi_text = "Plano de Desenvolvimento (Líder)" if eval_type == 'leader' else "Comentários / Autoavaliação (Membro)"
                                        pdi = st.text_area(pdi_text, value=st.session_state.avaliacoes[member_name][comp][eval_type]['pdi'], key=f"pdi_{eval_type}_{member_name}_{comp}", height=100)
                                        st.session_state.avaliacoes[member_name][comp][eval_type]['level'] = level
                                        st.session_state.avaliacoes[member_name][comp][eval_type]['pdi'] = pdi
                        else:
                            for _, row in df_skills.iterrows():
                                comp = row['Competência']
                                st.markdown(f"**{comp}**")
                                level = st.slider("Nível", 0, 5, value=st.session_state.avaliacoes[member_name][comp][eval_type]['level'], key=f"level_{eval_type}_{member_name}_{comp}")
                                st.info(f"**{SKILL_LEVELS[level]['name']}:** {SKILL_LEVELS[level]['desc']}")
                                pdi_text = "Plano de Desenvolvimento (Líder)" if eval_type == 'leader' else "Comentários / Autoavaliação (Membro)"
                                pdi = st.text_area(pdi_text, value=st.session_state.avaliacoes[member_name][comp][eval_type]['pdi'], key=f"pdi_{eval_type}_{member_name}_{comp}", height=100)
                                st.session_state.avaliacoes[member_name][comp][eval_type]['level'] = level
                                st.session_state.avaliacoes[member_name][comp][eval_type]['pdi'] = pdi

                    with aval_lider:
                        st.subheader("🛠️ Hard Skills")
                        render_evaluation_ui('leader', hard_skills, membro_selecionado)
                        st.subheader("🧠 Soft Skills")
                        render_evaluation_ui('leader', soft_skills, membro_selecionado)

                    with aval_membro:
                        st.subheader("🛠️ Hard Skills")
                        render_evaluation_ui('member', hard_skills, membro_selecionado)
                        st.subheader("🧠 Soft Skills")
                        render_evaluation_ui('member', soft_skills, membro_selecionado)
                    
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
        st.subheader("Registro de 1-on-1s")
        if not st.session_state.membros.empty:
            membro_1on1 = st.selectbox("Selecione o membro:", st.session_state.membros['Nome'], key="1on1_membro")
            with st.form("form_1on1", clear_on_submit=True):
                data_1on1 = st.date_input("Data da Conversa")
                anotacoes = st.text_area("Pontos discutidos, ações e próximos passos:", height=200)
                if st.form_submit_button("Salvar Registro"):
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
            st.warning("Adicione membros ao time primeiro na aba 'Membros do Time'.")
            
with tab_cases:
    st.header("Nossos Cases de Sucesso")
    with st.form("novo_case_form", clear_on_submit=True):
        st.subheader("Registrar Novo Case de Sucesso")
        cliente = st.text_input("Nome do Cliente")
        nome_case = st.text_input("Nome do Case/Iniciativa", help="Ex: Lançamento do App de Fidelidade")
        desafio = st.text_area("O Desafio", help="Qual era o problema de negócio ou a dor do cliente?")
        solucao = st.text_area("Solução Implementada", help="O que nós construímos ou que processo implementamos?")
        resultados = st.text_area("Resultados Quantitativos", help="Quais métricas provam o nosso sucesso?")
        if st.form_submit_button("Adicionar Case"):
            if cliente and nome_case and resultados:
                novo_case = {"cliente": cliente, "nome_case": nome_case, "desafio": desafio, "solucao": solucao, "resultados": resultados}
                st.session_state.cases_sucesso.append(novo_case)
                save_and_rerun()
    st.subheader("Cases Registrados")
    if not st.session_state.cases_sucesso:
        st.warning("Nenhum case de sucesso registrado ainda.")
    else:
        for case in st.session_state.cases_sucesso:
            with st.expander(f"**{case['cliente']}** - {case['nome_case']}"):
                st.markdown("#### Desafio"); st.write(case['desafio'])
                st.markdown("#### Solução Implementada"); st.write(case['solucao'])
                st.markdown("#### Resultados"); st.success(f"**{case['resultados']}**")