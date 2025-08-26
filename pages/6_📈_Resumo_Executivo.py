# pages/8_📈_Resumo_Executivo.py

import streamlit as st
import pandas as pd
import os, json
from datetime import datetime
from jira_connector import *
from metrics_calculator import *
from security import *
from config import *
from pathlib import Path
from utils import *

st.set_page_config(page_title="Resumo Executivo", page_icon="📈", layout="wide")

# --- CSS e Funções Auxiliares (sem alterações) ---
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
    emoji = status_text.strip()[0] if status_text.strip() else '⚪'
    color_class = color_map.get(emoji, "grey")
    st.markdown(f'<div style="text-align: right;"><span class="rag-pill rag-{color_class}">{status_text}</span></div>', unsafe_allow_html=True)

# --- Bloco de Autenticação e Conexão (sem alterações) ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/2_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

# --- BARRA LATERAL (sem alterações) ---
with st.sidebar:
    # ... (código da sua barra lateral, que já estava funcional)
    pass

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("📈 Resumo Executivo do Portfólio", divider='rainbow')

df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')

if df is None or df.empty or not current_project_key:
    st.info("⬅️ Por favor, carregue os dados de um projeto em 'Meu Dashboard' ou 'Métricas de Fluxo' para ver esta análise.")
    st.stop()

# --- Seletor de Cliente ---
st.subheader("Seleção de Contexto")
CLIENT_FIELD_NAME = "Cliente" 
if CLIENT_FIELD_NAME not in df.columns:
    st.error(f"O campo '{CLIENT_FIELD_NAME}' não foi encontrado nos dados carregados. Por favor, ative-o em 'Minha Conta'.")
    st.stop()

client_list = ["— Visão Agregada do Projeto —"] + sorted(df[CLIENT_FIELD_NAME].dropna().unique())
selected_client = st.selectbox("Selecione um Cliente para Análise:", options=client_list)

# --- Filtra os dados com base no cliente selecionado ---
if selected_client == "— Visão Agregada do Projeto —":
    scope_df = df
    scope_issues = st.session_state.get('raw_issues_for_fluxo', [])
else:
    scope_df = df[df[CLIENT_FIELD_NAME] == selected_client]
    scope_issue_keys = scope_df['Issue'].tolist()
    all_raw_issues = st.session_state.get('raw_issues_for_fluxo', [])
    scope_issues = [issue for issue in all_raw_issues if issue.key in scope_issue_keys]

# --- Preparação dos Dados para as Abas ---
project_config = get_project_config(current_project_key) or {}
auto_metrics = calculate_executive_summary_metrics(scope_issues, project_config)
rag_status = get_ai_rag_status(selected_client, json.dumps(auto_metrics))

client_summary_data = project_config.get('client_summaries', {}).get(selected_client, {})
profile_data = client_summary_data.get('profile', {})
kpi_data = client_summary_data.get('kpis', {})

st.divider()

# ===== NOVA ESTRUTURA DE ABAS =====
tab_view, tab_edit = st.tabs(["📊 Análise do Projeto/Cliente", "📝 Editar Perfil e KPIs"])

with tab_view:
    st.subheader(f"Análise para: {selected_client}")

    with st.container(border=True):
        st.markdown("**Perfil do Projeto/Cliente**")
        p_kpi1, p_kpi2, p_kpi3, p_kpi4 = st.columns(4)
        p_kpi1.metric("Cliente", selected_client if selected_client != "— Visão Agregada do Projeto —" else "Todos")
        p_kpi2.metric("Responsável", profile_data.get('responsavel', 'N/A'))
        p_kpi3.metric("Data de Início", pd.to_datetime(profile_data.get('start_date')).strftime('%d/%m/%Y') if profile_data.get('start_date') else 'N/A')
        p_kpi4.metric("Data de Fim Prevista", pd.to_datetime(profile_data.get('end_date')).strftime('%d/%m/%Y') if profile_data.get('end_date') else 'N/A')

        st.markdown("**Dimensão Financeira**")
        f_kpi1, f_kpi2, f_kpi3, f_kpi4 = st.columns(4)
        receita_total = kpi_data.get('mrr', 0.0) + kpi_data.get('receita_nao_recorrente', 0.0)
        total_geral = receita_total - kpi_data.get('total_despesas', 0.0)
        f_kpi1.metric("Receita Recorrente (MRR)", f"R$ {kpi_data.get('mrr', 0.0):,.2f}")
        f_kpi2.metric("Receitas Não Recorrentes", f"R$ {kpi_data.get('receita_nao_recorrente', 0.0):,.2f}")
        f_kpi3.metric("Total de Despesas", f"R$ {kpi_data.get('total_despesas', 0.0):,.2f}")
        f_kpi4.metric("Resultado (Receita - Despesa)", f"R$ {total_geral:,.2f}")

        st.markdown("**Dimensão Operacional**")
        o_kpi1, o_kpi2, o_kpi3, o_kpi4 = st.columns(4)
        o_kpi1.metric("% Concluído", f"{auto_metrics.get('completion_pct', 0):.0f}%")
        o_kpi2.metric("Entregas no Mês", auto_metrics.get('deliveries_month', 0))
        o_kpi3.metric("Adesão ao Cronograma", f"{auto_metrics.get('schedule_adherence', 0):.1f}%")
        o_kpi4.metric("Desvio Médio de Prazo", f"{auto_metrics.get('avg_deadline_diff', 0):+.1f}d")

        st.markdown("**Dimensão de Relacionamento com o Cliente**")
        r_kpi1, r_kpi2 = st.columns(2)
        r_kpi1.metric("NPS (Net Promoter Score)", kpi_data.get('nps', 'N/A'))
        r_kpi2.metric("Status RAG (IA)", rag_status)

with tab_edit:
    with st.form(f"edit_form_{current_project_key}_{selected_client}"):
        st.info(f"A editar os dados para: **{selected_client}** (no projeto {st.session_state.project_name})")
        
        st.markdown("**1. Dados do Projeto/Cliente**")
        c1, c2 = st.columns(2)
        responsavel = c1.text_input("Responsável", value=profile_data.get('responsavel', ''))
        
        start_date_val = pd.to_datetime(profile_data.get('start_date')).date() if profile_data.get('start_date') else None
        end_date_val = pd.to_datetime(profile_data.get('end_date')).date() if profile_data.get('end_date') else None
        
        start_date = c1.date_input("Data de Início", value=start_date_val)
        end_date = c2.date_input("Data de Fim Prevista", value=end_date_val)

        st.divider()
        st.markdown("**2. KPIs de Negócio**")
        c1, c2, c3 = st.columns(3)
        mrr = c1.number_input("Receita Recorrente Mensal (MRR)", min_value=0.0, value=kpi_data.get('mrr', 0.0), format="%.2f")
        receita_nao_recorrente = c2.number_input("Receitas Não Recorrentes", min_value=0.0, value=kpi_data.get('receita_nao_recorrente', 0.0), format="%.2f")
        total_despesas = c3.number_input("Total de Despesas", min_value=0.0, value=kpi_data.get('total_despesas', 0.0), format="%.2f")
        
        margem = c1.number_input("Margem de Contribuição (%)", min_value=0.0, value=kpi_data.get('margem', 0.0), format="%.1f")
        nps = c2.number_input("NPS (Net Promoter Score)", min_value=-100, max_value=100, value=kpi_data.get('nps', 0))

        if st.form_submit_button("Salvar Perfil e KPIs", use_container_width=True):
            if 'client_summaries' not in project_config:
                project_config['client_summaries'] = {}
            
            project_config['client_summaries'][selected_client] = {
                'profile': {
                    'responsavel': responsavel,
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                },
                'kpis': {
                    'mrr': mrr, 
                    'receita_nao_recorrente': receita_nao_recorrente,
                    'total_despesas': total_despesas,
                    'margem': margem, 
                    'nps': nps
                }
            }
            save_project_config(current_project_key, project_config)
            st.success(f"Dados para '{selected_client}' guardados com sucesso!")
            st.rerun()