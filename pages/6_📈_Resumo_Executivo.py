# pages/8_📈_Resumo_Executivo.py

import streamlit as st
import pandas as pd
import os, json
from jira_connector import *
from metrics_calculator import *
from security import *
from config import *
from pathlib import Path
from utils import *

st.set_page_config(page_title="Resumo Executivo", page_icon="📈", layout="wide")

# --- CSS para o design dos cartões ---
st.markdown("""
<style>
.rag-pill {
    padding: 0.25em 0.7em; border-radius: 0.75em; font-weight: 600;
    font-size: 0.8em; color: white; display: inline-block;
}
.rag-green { background-color: #28a745; }
.rag-amber { background-color: #ffc107; color: #333;}
.rag-red { background-color: #dc3545; }
.rag-grey { background-color: #6c757d; }
</style>
""", unsafe_allow_html=True)

def display_rag_status(status_text):
    """Exibe um selo colorido para o status RAG."""
    color_map = {"🟢": "green", "🟡": "amber", "🔴": "red", "⚪": "grey"}
    emoji = status_text.strip()[0]
    color_class = color_map.get(emoji, "grey")
    st.markdown(f'<div style="text-align: right;"><span class="rag-pill rag-{color_class}">{status_text}</span></div>', unsafe_allow_html=True)

st.header("📈 Resumo Executivo do Portfólio", divider='rainbow')

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

# --- Bloco de Autenticação e Conexão ---
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

projects = st.session_state.get('projects', {})
if not projects:
    st.warning("Nenhum projeto encontrado ou carregado."); st.stop()

# --- Lógica de carregamento dos dados com cache (sem alterações) ---
@st.cache_data(ttl=600, show_spinner="Aguarde... estamos preparando sua visão")
def load_all_projects_summary(_project_keys):
    summary_list = []
    progress_bar = st.progress(0, "A carregar e analisar resumos dos projetos...")
    for i, project_name in enumerate(_project_keys.keys()):
        project_key = _project_keys[project_name]
        project_issues = get_all_project_issues(st.session_state.jira_client, project_key)
        auto_metrics = calculate_executive_summary_metrics(project_issues)
        metrics_summary_for_rag = f"- Percentual Concluído: {auto_metrics['completion_pct']:.0f}%\n- Desvio Médio de Prazo: {auto_metrics['avg_deadline_diff']:.1f} dias"
        rag_status_from_ai = get_ai_rag_status(project_name, metrics_summary_for_rag)
        summary_list.append({
            "project_name": project_name, "project_key": project_key,
            "auto_metrics": auto_metrics, "rag_status": rag_status_from_ai
        })
        progress_bar.progress((i + 1) / len(_project_keys), f"A processar: {project_name}")
    progress_bar.empty()
    return summary_list

projects_summary = load_all_projects_summary(projects)

st.divider()
st.subheader("Visão Geral dos Projetos")

# --- NOVO LAYOUT DE CARTÕES INDIVIDUAIS ---
for project_data in projects_summary:
    project_name = project_data["project_name"]
    auto_metrics = project_data["auto_metrics"]
    rag_status = project_data["rag_status"]
    
    with st.container(border=True):
        # --- Cabeçalho do Cartão ---
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader(f"🚀 {project_name}")
        with col2:
            display_rag_status(rag_status)
        
        # --- Barra de Progresso ---
        completion_pct = auto_metrics['completion_pct']
        st.progress(int(completion_pct), text=f"{completion_pct:.0f}% Concluído ({auto_metrics['completed_issues']} de {auto_metrics['total_issues']} itens)")
        
        st.divider()
        
        # --- Grelha de KPIs ---
        kpi_cols = st.columns(4)
        deadline_diff = auto_metrics['avg_deadline_diff']
        delta_text_prazo = "Atraso" if deadline_diff > 0 else None
        
        # Carrega a análise de risco guardada
        project_config = get_project_config(project_data['project_key']) or {}
        manual_data = project_config.get('executive_summary', {})
        ai_risks_data = manual_data.get('ai_risks', {})
        risk_level = ai_risks_data.get('risk_level', 'N/A')
        risks_count = len(ai_risks_data.get('risks', []))

        kpi_cols[0].metric(label="📦 Entregas no Mês", value=auto_metrics['deliveries_month'])
        kpi_cols[1].metric(label="⏱️ Desvio de Prazo", value=f"{deadline_diff:+.1f}d", delta=delta_text_prazo, delta_color=("inverse" if deadline_diff > 0 else "normal"))
        kpi_cols[2].metric(label="🚨 Nível de Risco (IA)", value=risk_level)
        kpi_cols[3].metric(label="Riscos Mapeados", value=risks_count)
        
        # --- Análise de Risco Expansível ---
        with st.expander("Ver Análise de Riscos Detalhada"):
            st.info("Clique no botão para que a IA analise as métricas e identifique riscos potenciais.")
            if st.button("🤖 Gerar Análise de Riscos", key=f"risk_analysis_{project_data['project_key']}"):
                with st.spinner("A IA está a analisar os dados..."):
                    metrics_summary = f"- Percentual Concluído: {auto_metrics['completion_pct']:.0f}%\n- Entregas no Mês: {auto_metrics['deliveries_month']}\n- Desvio Médio de Prazo: {auto_metrics['avg_deadline_diff']:.1f} dias"
                    ai_risk_assessment = generate_ai_risk_assessment(project_name, metrics_summary)
                    
                    if 'executive_summary' not in project_config: project_config['executive_summary'] = {}
                    project_config['executive_summary']['ai_risks'] = ai_risk_assessment
                    save_project_config(project_data['project_key'], project_config)
                    st.rerun()

            if ai_risks_data and ai_risks_data.get('risks'):
                for risk in ai_risks_data['risks']:
                    st.markdown(f"- {risk}")
            else:
                st.caption("Nenhuma análise de risco gerada ou guardada.")