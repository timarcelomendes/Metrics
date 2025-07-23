# pages/8_📈_Resumo_Executivo.py

import streamlit as st
import pandas as pd
import os
from jira_connector import *
from metrics_calculator import *
from security import *
from config import *
from pathlib import Path
from utils import *

st.set_page_config(page_title="Resumo Executivo", page_icon="📈", layout="wide")

# --- CSS para o selo RAG e ajuste fino dos KPIs ---
st.markdown("""
<style>
/* Estilo do selo RAG */
.rag-pill {
    padding: 0.25em 0.7em;
    border-radius: 0.75em;
    font-weight: 600;
    font-size: 0.8em;
    color: white;
    display: inline-block;
    text-align: center;
}
.rag-green { background-color: #28a745; }
.rag-amber { background-color: #ffc107; color: #333;}
.rag-red { background-color: #dc3545; }
.rag-grey { background-color: #6c757d; }

/* Ajuste fino nos títulos dos KPIs */
[data-testid="stMetricLabel"] { font-size: 0.9rem !important; }
</style>
""", unsafe_allow_html=True)

def display_rag_status(status_text):
    """Exibe um selo colorido para o status RAG."""
    color_map = {"🟢": "green", "🟡": "amber", "🔴": "red", "⚪": "grey"}
    emoji = status_text.strip()[0]
    color_class = color_map.get(emoji, "grey")
    st.markdown(f'<div style="text-align: right;"><span class="rag-pill rag-{color_class}">{status_text}</span></div>', unsafe_allow_html=True)

st.header("📈 Resumo Executivo do Portfólio", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    # (Lógica de conexão com o Jira)
    pass

projects = st.session_state.get('projects', {})
if not projects:
    st.warning("Nenhum projeto encontrado ou carregado."); st.stop()

# --- INTERFACE DE EDIÇÃO ---
with st.expander("📝 Editar Resumo Executivo de um Projeto"):
    projects_list = list(projects.keys())
    selected_project_name_to_edit = st.selectbox("Selecione um projeto para editar:", options=projects_list)
    
    if selected_project_name_to_edit:
        project_key_to_edit = projects[selected_project_name_to_edit]
        project_config = get_project_config(project_key_to_edit) or {}
        summary_data_manual = project_config.get('executive_summary', {})
        
        with st.form(key=f"edit_form_{project_key_to_edit}"):
            st.markdown(f"**Editando dados para: {selected_project_name_to_edit}**")
            rag_options = ["⚪ Não definido", "🟢 No prazo", "🟡 Atraso moderado", "🔴 Atrasado"]
            rag_index = rag_options.index(summary_data_manual.get('rag_status', '⚪ Não definido')) if summary_data_manual.get('rag_status') in rag_options else 0
            
            col1, col2 = st.columns(2)
            rag = col1.selectbox("Status RAG", options=rag_options, index=rag_index)
            risks = col2.number_input("Riscos Ativos", min_value=0, value=summary_data_manual.get('active_risks', 0))
            
            if st.form_submit_button("Salvar Resumo do Projeto", type="primary"):
                project_config['executive_summary'] = {'rag_status': rag, 'active_risks': risks}
                save_project_config(project_key_to_edit, project_config)
                st.success(f"Resumo para '{selected_project_name_to_edit}' guardado com sucesso!")
                st.rerun()

st.divider()
st.subheader("Visão Geral dos Projetos")

# --- LÓGICA DE CARREGAMENTO E EXIBIÇÃO ---
project_keys = list(projects.keys())
cols = st.columns(2, gap="large") # 2 Cartões por linha
col_idx = 0

for project_name in project_keys:
    current_col = cols[col_idx % 2]
    col_idx += 1

    with current_col:
        card_placeholder = st.empty()
        card_placeholder.info(f"A carregar dados para o projeto **{project_name}**...")

        project_key = projects[project_name]
        project_issues = get_all_project_issues(st.session_state.jira_client, project_key)
        
        auto_metrics = calculate_executive_summary_metrics(project_issues)
        manual_data = (get_project_config(project_key) or {}).get('executive_summary', {})
        throughput_trend_df = calculate_throughput_trend(project_issues)

        # --- Redesenha o cartão com os dados completos ---
        with card_placeholder.container(border=True):
            # Linha 1: Título e Status RAG
            title_col, rag_col = st.columns([3, 1])
            with title_col:
                st.subheader(f"🚀 {project_name}")
            with rag_col:
                display_rag_status(manual_data.get('rag_status', '⚪ Não definido'))
            
            # Linha 2: Percentual Concluído
            completion_pct = auto_metrics['completion_pct']
            st.progress(int(completion_pct), text=f"{completion_pct:.0f}% Concluído")
            
            st.divider()

            kpi1, kpi2, kpi3 = st.columns(3)
            
            deadline_diff = auto_metrics['avg_deadline_diff']
            risks = manual_data.get('active_risks', 0)
            
            kpi1.metric(label="📦 Entregas no Mês", value=f"{auto_metrics['deliveries_month']}")
            
            delta_text_prazo = "Atraso" if deadline_diff > 0 else None
            kpi2.metric(
                label="⏱️ Desvio de Prazo", 
                value=f"{deadline_diff:+.1f} dias", 
                delta=delta_text_prazo, 
                delta_color=("inverse" if deadline_diff > 0 else "normal")
            )
            
            kpi3.metric(label="🚨 Riscos Ativos", value=risks, delta_color="off" if risks == 0 else "inverse")
            
            # Linha 4: Mini-Gráfico
            st.caption("Entregas nas Últimas 4 Semanas")
            trend_df = throughput_trend_df
            if not trend_df.empty:
                st.bar_chart(trend_df, x="Semana", y="Entregas", height=120, color="#1c4e80")
            else:
                st.caption("Nenhuma entrega recente.")