# pages/12_🔮_Insights_AI.py

import streamlit as st
import pandas as pd
import json
from jira_connector import *
from metrics_calculator import calculate_executive_summary_metrics
from security import *
from utils import get_ai_strategic_diagnosis, get_ai_chat_response, load_and_process_project_data
from pathlib import Path
from config import SESSION_TIMEOUT_MINUTES

st.set_page_config(page_title="Insights AI", page_icon="🔮", layout="wide")

st.header("🔮 Insights Estratégicos com Gauge AI", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if check_session_timeout():
    # Usa uma f-string para formatar a mensagem com o valor da variável
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()

# --- LÓGICA DE VERIFICAÇÃO DE CONEXÃO CORRIGIDA ---
if 'jira_client' not in st.session_state:
    # Verifica se o utilizador tem alguma conexão guardada na base de dados
    user_connections = get_users_collection(st.session_state['email'])
    
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

# --- BARRA LATERAL ---
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

    st.divider()
    st.header("Configurações de Análise")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else 0
    
    selected_project_name = st.selectbox("1. Selecione o Projeto Principal", options=project_names, index=default_index, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]
        
        other_projects = [p_name for p_name in project_names if p_name != selected_project_name]
        selected_context_projects = st.multiselect(
            "2. Selecione Projetos para Contextualização (Opcional)",
            options=other_projects
        )
        
        # --- BOTÃO PARA CARREGAR OS DADOS ---
        if st.button("Processar Análise", use_container_width=True, type="primary"):
            # Garanta que a linha abaixo está a desempacotar em DUAS variáveis
            df_from_func, issues_from_func = load_and_process_project_data(st.session_state.jira_client, st.session_state.project_key)
            
            # Armazena cada objeto na sua respetiva variável de sessão
            st.session_state.strategic_df = df_from_func
            st.session_state.raw_issues_for_fluxo = issues_from_func
            
            # Guarda os outros estados da sessão
            st.session_state.selected_project_name_for_diag = selected_project_name
            st.session_state.selected_context_projects_for_diag = selected_context_projects
            st.session_state.strategic_data_loaded = True
            
            # Limpa o diagnóstico antigo
            if 'strategic_diagnosis' in st.session_state:
                del st.session_state['strategic_diagnosis']
            st.rerun()

# --- LÓGICA PRINCIPAL DA PÁGINA ---
if not st.session_state.get('strategic_data_loaded'):
    st.info("⬅️ Na barra lateral, selecione os parâmetros e clique em 'Carregar Dados' para começar.")
    st.stop()

df = st.session_state.strategic_df
current_project_key = st.session_state.project_key
selected_project_name = st.session_state.selected_project_name_for_diag
selected_context_projects = st.session_state.selected_context_projects_for_diag
projects = st.session_state.get('projects', {})

# Bloco Novo e Corrigido
CLIENT_FIELD_NAME = "Cliente"

# Verifica se a coluna 'Cliente' existe e se tem algum valor preenchido
if CLIENT_FIELD_NAME in df.columns and not df[CLIENT_FIELD_NAME].dropna().empty:
    # Se sim, mostra o seletor de cliente normalmente
    st.info(f"Dados carregados para o projeto **{selected_project_name}**. Agora, selecione um cliente ou a visão agregada para gerar o diagnóstico.", icon="✅")
    client_list = ["— Visão Agregada do Projeto —"] + sorted(df[CLIENT_FIELD_NAME].dropna().unique())
    selected_client = st.selectbox("Selecione um Cliente para Análise:", options=client_list)
else:
    # Se não, informa o utilizador e assume a visão agregada por defeito
    st.info(f"O campo '{CLIENT_FIELD_NAME}' não está em uso neste projeto. A análise será feita na **Visão Agregada**.", icon="ℹ️")
    selected_client = "— Visão Agregada do Projeto —"
    # Mostra o seletor desativado para o utilizador entender a seleção atual
    st.selectbox("Cliente para Análise:", options=[selected_client], disabled=True)

if st.button("Gerar Diagnóstico com IA", use_container_width=True):
    # Filtra os dados com base no cliente selecionado
    if selected_client == "— Visão Agregada do Projeto —":
        scope_issues = st.session_state.get('raw_issues_for_fluxo', [])
    else:
        scope_df = df[df[CLIENT_FIELD_NAME] == selected_client]
        scope_issue_keys = scope_df['Issue'].tolist()
        all_raw_issues = st.session_state.get('raw_issues_for_fluxo', [])
        scope_issues = [issue for issue in all_raw_issues if issue.key in scope_issue_keys]
    
    if not scope_issues:
        st.session_state.strategic_diagnosis = "Nenhuma tarefa encontrada neste contexto para análise."
    else:
        with st.spinner("A IA está a cruzar os dados do ecossistema..."):
            project_config = get_project_config(current_project_key) or {}

            auto_metrics = calculate_executive_summary_metrics(scope_issues, project_config)
            
            flow_metrics_summary_text = f"- Percentual Concluído: {auto_metrics['completion_pct']:.0f}%\n- Entregas no Mês: {auto_metrics['deliveries_month']}\n- Desvio Médio de Prazo: {auto_metrics['avg_deadline_diff']:.1f} dias\n- Adesão ao Cronograma: {auto_metrics['schedule_adherence']:.1f}%"
            
            client_summary_data = project_config.get('client_summaries', {}).get(selected_client, {})
            profile_data = client_summary_data.get('profile', {})
            kpi_data = client_summary_data.get('kpis', {})
            project_profile_summary_text = f"- Cliente: {selected_client}\n- Responsável: {profile_data.get('responsavel', 'N/A')}\n- MRR: R$ {kpi_data.get('mrr', 0.0):,.2f}\n- NPS: {kpi_data.get('nps', 'N/A')}"

            contextual_summaries = []
            for context_project_name in selected_context_projects:
                context_project_key = projects[context_project_name]
                context_issues = get_all_project_issues(st.session_state.jira_client, context_project_key)
                context_tasks = [f"{i.fields.issuetype.name}: {i.fields.summary}" for i in context_issues[:5]]
                contextual_summaries.append(f"Projeto '{context_project_name}': " + "; ".join(context_tasks))

            issues_data_for_ai = [{"Título": i.fields.summary, "Tipo": i.fields.issuetype.name} for i in scope_issues]
            
            st.session_state.issues_for_chat = [{
                "Key": i.key,
                "Título": i.fields.summary,
                "Status": i.fields.status.name,
                "Responsável": getattr(i.fields.assignee, 'displayName', 'Ninguém')
            } for i in scope_issues]
            
            st.session_state.strategic_diagnosis = get_ai_strategic_diagnosis(
                project_name=f"{selected_project_name}",
                client_name=selected_client,
                issues_data=issues_data_for_ai,
                flow_metrics_summary=flow_metrics_summary_text,
                project_profile_summary=project_profile_summary_text,
                contextual_projects_summary=contextual_summaries
            )
            st.rerun()

# --- Exibição do Resultado e do Chat ---
if 'strategic_diagnosis' in st.session_state:
    st.divider()
    
    diagnosis_data = st.session_state.strategic_diagnosis
    
    # --- LÓGICA DE VERIFICAÇÃO DE ERRO ---
    if isinstance(diagnosis_data, dict) and "error" in diagnosis_data:
        st.error(f"Ocorreu um erro ao gerar o diagnóstico da IA: {diagnosis_data['error']}")
    
    # Se não houver erro, exibe as abas com os resultados
    else:
        tab_diag, tab_chat = st.tabs(["**🔮 Insights Estratégicos**", "**💬 Converse com a Análise**"])

        with tab_diag:
            # Exibe o diagnóstico principal
            st.subheader("Análise Geral")
            st.markdown(diagnosis_data.get('diagnostico_estrategico', 'N/A'))
            
            # Exibe a análise da natureza do trabalho
            st.subheader("Análise da Natureza do Trabalho")
            st.markdown(diagnosis_data.get('analise_natureza_trabalho', 'N/A'))
            
            # Exibe o plano de ação de forma organizada
            st.subheader("Plano de Ação Recomendado")
            action_plan = diagnosis_data.get('plano_de_acao_recomendado', [])
            if isinstance(action_plan, list) and action_plan:
                for i, item in enumerate(action_plan):
                    st.markdown(f"**{i+1}. {item.get('acao', 'Ação não especificada')}**")
                    with st.expander("Ver Justificativa"):
                        st.markdown(f"**Justificativa:** {item.get('justificativa', 'Justificativa não especificada.')}")
            else:
                st.markdown("Nenhum plano de ação foi gerado pela IA.")
                
        with tab_chat:
            # Inicializa o histórico do chat na memória da sessão
            if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
            
            # Exibe as mensagens antigas
            for message in st.session_state.chat_history:
                role = message["role"]
                display_name = "Você" if role == "user" else "Gauge AI"
                avatar = "👤" if role == "user" else "🤖"
                with st.chat_message(display_name, avatar=avatar):
                    st.markdown(message["content"])

            # Input para a nova pergunta do utilizador
            if prompt := st.chat_input("Faça uma pergunta sobre o diagnóstico..."):
                # Adiciona e exibe a pergunta do utilizador
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("Você", avatar="👤"):
                    st.markdown(prompt)
                    
                # Gera e exibe a resposta do Gauge AI
                with st.chat_message("Gauge AI", avatar="🤖"):
                    with st.spinner("Gauge AI está a pensar..."):
                        response = get_ai_chat_response(
                            initial_diagnosis=st.session_state.strategic_diagnosis,
                            chat_history=st.session_state.chat_history,
                            user_question=prompt,
                            issues_context=st.session_state.get('issues_for_chat', [])
                        )
                        st.markdown(response)
                
                st.session_state.chat_history.append({"role": "assistant", "content": response})
                st.rerun()