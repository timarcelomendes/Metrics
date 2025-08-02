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
from metrics_calculator import *

st.set_page_config(page_title="Resumo Executivo", page_icon="📈", layout="wide")

# --- CSS para o design dos cartões e da nova matriz ---
st.markdown("""
<style>
.project-card { /* ... (CSS do cartão) ... */ }
.rag-pill { /* ... (CSS do selo RAG) ... */ }
[data-testid="stMetricLabel"] { font-size: 0.9rem !important; }

/* Estilo para a Matriz de Risco */
.risk-matrix-table { border-collapse: collapse; width: 100%; height: 120px; }
.risk-matrix-table td { border: 1px solid #ddd; text-align: center; font-size: 2em; }
.risk-low { background-color: #d4edda; }
.risk-medium { background-color: #fff3cd; }
.risk-high { background-color: #f8d7da; }
.risk-critical { background-color: #e49a9a; }
</style>
""", unsafe_allow_html=True)


def display_risk_matrix(probability, impact):
    """Desenha uma matriz de risco 3x3 e marca a posição do projeto."""
    st.markdown("###### **Posicionamento na Matriz de Risco**")
    
    # Mapeamento de texto para índice (0=Baixa, 1=Média, 2=Alta)
    level_map = {'Baixa': 0, 'Média': 1, 'Alta': 2}
    prob_idx = level_map.get(probability, -1)
    impact_idx = level_map.get(impact, -1)

    # Cores da matriz (Impacto x Probabilidade)
    colors = [
        ['risk-low', 'risk-medium', 'risk-high'],      # Impacto Baixo
        ['risk-medium', 'risk-high', 'risk-critical'], # Impacto Médio
        ['risk-high', 'risk-critical', 'risk-critical']  # Impacto Alto
    ]
    
    matrix_html = "<table class='risk-matrix-table'>"
    for r in range(3): # Linhas = Impacto (invertido para visualização)
        row_idx = 2 - r
        matrix_html += "<tr>"
        for c in range(3): # Colunas = Probabilidade
            col_idx = c
            marker = "⚫" if row_idx == impact_idx and col_idx == prob_idx else ""
            color_class = colors[row_idx][col_idx]
            matrix_html += f"<td class='{color_class}'>{marker}</td>"
        matrix_html += "</tr>"
    matrix_html += "</table>"
    st.markdown(matrix_html, unsafe_allow_html=True)
    st.caption("Eixo Vertical: Impacto (baixo para cima), Eixo Horizontal: Probabilidade (esquerda para direita).")

def display_rag_status(status_text):
    """Exibe um selo colorido para o status RAG."""
    color_map = {"🟢": "green", "🟡": "amber", "🔴": "red", "⚪": "grey"}
    emoji = status_text.strip()[0]
    color_class = color_map.get(emoji, "grey")
    st.markdown(f'<div style="text-align: right;"><span class="rag-pill rag-{color_class}">{status_text}</span></div>', unsafe_allow_html=True)

st.header("📈 Resumo Executivo do Portfólio", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça autenticação para acessar esta página."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
    
if 'jira_client' not in st.session_state:
    # (Lógica de conexão com o Jira)
    pass

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
            
            # --- Status RAG e Matriz de Risco ---
            col1, col2, col3 = st.columns(3)
            rag_options = ["⚪ Não definido", "🟢 No prazo", "🟡 Atraso moderado", "🔴 Atrasado"]
            risk_options = ["Baixa", "Média", "Alta"]
            
            rag_idx = rag_options.index(summary_data_manual.get('rag_status', '⚪ Não definido')) if summary_data_manual.get('rag_status') in rag_options else 0
            risk_prob_idx = risk_options.index(summary_data_manual.get('risk_probability', 'Baixa')) if summary_data_manual.get('risk_probability') in risk_options else 0
            risk_impact_idx = risk_options.index(summary_data_manual.get('risk_impact', 'Baixa')) if summary_data_manual.get('risk_impact') in risk_options else 0

            rag = col1.selectbox("Status RAG", options=rag_options, index=rag_idx)
            risk_prob = col2.selectbox("Probabilidade de Risco", options=risk_options, index=risk_prob_idx)
            risk_impact = col3.selectbox("Impacto do Risco", options=risk_options, index=risk_impact_idx)
            
            # --- Nova Gestão de Descrição de Riscos ---
            st.markdown("**Descrição dos Riscos Ativos**")
            # Carrega os riscos existentes ou começa com um campo vazio
            risks_list = summary_data_manual.get('risks', [{'Descrição': ''}])
            edited_risks = st.data_editor(
                risks_list,
                num_rows="dynamic",
                use_container_width=True,
                column_config={"Descrição": st.column_config.TextColumn("Descrição do Risco", required=True)}
            )
            
            if st.form_submit_button("Salvar Resumo do Projeto", type="primary"):
                # Filtra descrições vazias antes de salvar
                final_risks = [r for r in edited_risks if r.get('Descrição', '').strip()]
                
                project_config['executive_summary'] = {
                    'rag_status': rag, 
                    'risk_probability': risk_prob, 
                    'risk_impact': risk_impact,
                    'risks': final_risks
                }
                save_project_config(project_key_to_edit, project_config)
                st.success(f"Resumo para '{selected_project_name_to_edit}' guardado com sucesso!")
                st.rerun()

st.divider()
st.subheader("Visão Geral dos Projetos")

# --- LÓGICA DE CARREGAMENTO E EXIBIÇÃO ---
project_keys = list(projects.keys())
cols = st.columns(2, gap="large") # 2 Cartões por linha
col_idx = 0

for project_name in projects.keys():
    card_placeholder = st.empty()
    with card_placeholder.container(border=True):
        st.subheader(f"🚀 {project_name}")
        st.caption("A carregar dados...")

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
            
    # Linha 3: KPIs e Matriz de Risco
    kpi_col, chart_col = st.columns(2, gap="large")
    with kpi_col:
        st.markdown("###### **Indicadores Chave**")
        kpi1_c, kpi2_c, kpi3_c = st.columns(3)
        
        # --- CÁLCULO E EXIBIÇÃO DO NOVO KPI DE RISCO ---
        risks_list = manual_data.get('risks', [])
        risks_count = len(risks_list)
        
        risk_prob = manual_data.get('risk_probability', 'Baixa')
        risk_impact = manual_data.get('risk_impact', 'Baixa')
        risk_level, risk_color = calculate_risk_level(risk_prob, risk_impact)

        deadline_diff = auto_metrics['avg_deadline_diff']
        
        kpi1_c.metric(label="📦 Entregas no Mês", value=f"{auto_metrics['deliveries_month']}")
        kpi2_c.metric(label="⏱️ Desvio de Prazo", value=f"{deadline_diff:+.1f} dias", delta_color=("inverse" if deadline_diff > 0 else "normal"))
        
        # O novo KPI de risco
        with kpi3_c:
            st.markdown("**🚨 Nível de Risco**")
            st.markdown(f"<h3 style='color: {risk_color};'>{risk_level}</h3>", unsafe_allow_html=True)
            st.caption(f"{risks_count} risco(s) mapeado(s)")
            
        if risks_list:
            with st.expander(f"Ver os {risks_count} risco(s) detalhado(s)"):
                for risk in risks_list:
                    st.markdown(f"- {risk['Descrição']}")
    
        with chart_col:
            display_risk_matrix(risk_prob, risk_impact)
            
            # Linha 4: Mini-Gráfico
            st.caption("Entregas nas Últimas 4 Semanas")
            trend_df = throughput_trend_df
            if not trend_df.empty:
                st.bar_chart(trend_df, x="Semana", y="Entregas", height=120, color="#1c4e80")
            else:
                st.caption("Nenhuma entrega recente.")