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

# --- CSS para adicionar sombra e estilo aos cartões ---
st.markdown("""
<style>
div[data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="stVerticalBlock"] > [data-testid="stElementToolbar"] {
    display: none;
}
.rag-pill {
    padding: 0.25em 0.6em;
    border-radius: 0.75em;
    font-weight: 600;
    font-size: 0.8em;
    color: white;
    display: inline-block;
}
.rag-green { background-color: #28a745; }
.rag-amber { background-color: #ffc107; color: #333;}
.rag-red { background-color: #dc3545; }
.rag-grey { background-color: #6c757d; }
</style>
""", unsafe_allow_html=True)


def display_rag_status(status_text):
    """Exibe um selo colorido para o status RAG."""
    color_map = {
        "🟢": "green",
        "🟡": "amber",
        "🔴": "red",
        "⚪": "grey"
    }
    # Extrai o emoji para encontrar a cor
    emoji = status_text.strip()[0]
    color_class = color_map.get(emoji, "grey")
    st.markdown(f'<span class="rag-pill rag-{color_class}">{status_text}</span>', unsafe_allow_html=True)


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
            
            rag_options = ["🟢 No prazo", "🟡 Atraso moderado", "🔴 Atrasado", "⚪ Não definido"]
            rag_index = rag_options.index(summary_data_manual.get('rag_status', '⚪ Não definido')) if summary_data_manual.get('rag_status') in rag_options else 3
            
            col1, col2 = st.columns(2)
            rag = col1.selectbox("Status RAG", options=rag_options, index=rag_index)
            risks = col2.number_input("Riscos Ativos", min_value=0, value=summary_data_manual.get('active_risks', 0))
            
            if st.form_submit_button("Salvar Resumo do Projeto", type="primary"):
                project_config['executive_summary'] = {'rag_status': rag, 'active_risks': risks}
                save_project_config(project_key_to_edit, project_config)
                st.success(f"Resumo para '{selected_project_name_to_edit}' guardado com sucesso!")
                st.rerun()


# --- EXIBIÇÃO DOS CARTÕES EXECUTIVOS ---
st.divider()
st.subheader("Visão Geral dos Projetos")

projects = st.session_state.get('projects', {})
project_keys = list(projects.keys())
summary_cards_data = []

# Coleta todos os dados primeiro para não sobrecarregar a interface
with st.spinner("A carregar e processar dados de todos os projetos..."):
    for i, project_name in enumerate(project_keys):
        project_key = projects[project_name]
        project_issues = get_all_project_issues(st.session_state.jira_client, project_key)
        
        auto_metrics = calculate_executive_summary_metrics(project_issues)
        manual_data = (get_project_config(project_key) or {}).get('executive_summary', {})
        
        # Novo: Calcula os dados para o mini-gráfico
        throughput_trend_df = calculate_throughput_trend(project_issues)
        
        card_data = {
            "Projeto": project_name,
            **auto_metrics,
            **manual_data,
            "throughput_trend": throughput_trend_df
        }
        summary_cards_data.append(card_data)

# --- NOVO LAYOUT DE CARTÃO COM MINI-GRÁFICO ---
for card_data in summary_cards_data:
    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            st.subheader(f"🚀 {card_data['Projeto']}")
        with col2:
            display_rag_status(card_data.get('rag_status', '⚪ Não definido'))

        completion_pct = card_data['completion_pct']
        st.progress(int(completion_pct), text=f"{completion_pct:.0f}% Concluído")
        
        st.divider()

        # Nova divisão em colunas para KPIs e mini-gráfico
        kpi_col, chart_col = st.columns([1, 1], gap="large")

        with kpi_col:
            st.markdown("###### **Indicadores Chave**")
            deadline_diff = card_data['avg_deadline_diff']
            prazo_str = f"{deadline_diff:+.1f} dias"
            
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Entregas no Mês", f"{card_data['deliveries_month']}")
            kpi2.metric("Desvio de Prazo", prazo_str, delta_color=("inverse" if deadline_diff > 0 else "normal"))
            kpi3.metric("Riscos Ativos", f"{card_data.get('active_risks', 0)}")
            
        with chart_col:
            st.markdown("###### **Entregas nas Últimas 4 Semanas**")
            trend_df = card_data["throughput_trend"]
            if not trend_df.empty:
                st.bar_chart(trend_df, x="Semana", y="Entregas", height=150)
            else:
                st.caption("Nenhuma entrega nas últimas 4 semanas.")