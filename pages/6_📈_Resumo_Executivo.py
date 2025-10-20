# pages/6_📈_Resumo_Executivo.py

import streamlit as st
import pandas as pd
import os, json
from datetime import datetime
from jira_connector import *
from metrics_calculator import *
from security import *
from pathlib import Path
from utils import *
from config import SESSION_TIMEOUT_MINUTES
from security import get_global_configs, get_project_config, save_project_config # Garante importações corretas

st.set_page_config(page_title="Resumo Executivo", page_icon="📈", layout="wide")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("📈 Resumo Executivo do Portfólio", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()

# --- LÓGICA DE VERIFICAÇÃO DE CONEXÃO CORRIGIDA ---
if 'jira_client' not in st.session_state:
    user_connections = get_users_collection(st.session_state['email']) # Corrigido para get_user_connections
    
    if not user_connections:
        st.warning("Nenhuma conexão Jira foi configurada ainda.", icon="🔌")
        st.info("Para começar, você precisa de adicionar as suas credenciais do Jira.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Configurar sua Primeira Conexão", icon="🔗")
        st.stop()
    else:
        st.warning("Nenhuma conexão Jira está ativa para esta sessão.", icon="⚡")
        st.info("Por favor, ative uma das suas conexões guardadas para carregar os dados.")
        st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗")
        st.stop()

# --- CSS e Funções Auxiliares ---
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

.metric-container {
    background-color: #F8F9FA; border: 1px solid #E0E0E0;
    border-radius: 0.5rem; padding: 1rem; text-align: center;
}
.metric-label {
    font-size: 0.9rem; color: #555; margin-bottom: 0.5rem;
}
.metric-value {
    font-size: 1.5rem; font-weight: 600; line-height: 1.2;
}
.metric-value-blue { color: #007bff; }
.metric-value-red { color: #dc3545; }
.metric-value-green { color: #28a745; }
.metric-value-amber { color: #fd7e14; } /* Laranja/Âmbar */
</style>
""", unsafe_allow_html=True)

def display_custom_metric(label, value, color_class):
    """Exibe uma métrica personalizada com um valor colorido."""
    st.markdown(f"""
    <div class="metric-container">
        <div class="metric-label">{label}</div>
        <div class="metric-value {color_class}">{value}</div>
    </div>
    """, unsafe_allow_html=True)

def display_rag_status(status_text):
    """Exibe um selo colorido para o status RAG."""
    color_map = {"🟢": "green", "🟡": "amber", "🔴": "red", "⚪": "grey"}
    emoji = status_text.strip()[0] if status_text.strip() else '⚪'
    color_class = color_map.get(emoji, "grey")
    st.markdown(f'<div style="text-align: right;"><span class="rag-pill rag-{color_class}">{status_text}</span></div>', unsafe_allow_html=True)

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(str(logo_path))
    except:
        st.write("Gauge Metrics") 
    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")
    st.divider()
    # Adicionar aqui a seleção de projetos se necessário, 
    # mas a lógica principal assume que os dados já estão em 'dynamic_df'

df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')

if df is None or df.empty or not current_project_key:
    st.info("⬅️ Por favor, carregue os dados de um projeto em 'Meu Dashboard' ou 'Métricas de Fluxo' para ver esta análise.")
    st.stop()

# --- Seletor de Contexto (REFINADO) ---
st.subheader("Seleção de Contexto")

# Carrega a configuração global para o campo estratégico
global_configs = get_global_configs()
STRATEGIC_FIELD_NAME = global_configs.get('strategic_grouping_field')

# Variável para guardar o contexto selecionado
selected_context = "— Visão Agregada do Projeto —"
can_filter_by_context = False # Flag para controlar se a filtragem é possível

# Verifica se o campo estratégico foi definido E se existe no DataFrame
if not STRATEGIC_FIELD_NAME:
    st.warning(
        "Nenhum campo de agrupamento estratégico foi definido.",
        icon="⚠️"
    )
    st.info("A análise será apresentada de forma agregada. Configure um campo em **Configurações > Estimativa** se desejar agrupar.")
    st.selectbox(f"Contexto para Análise:", options=[selected_context], disabled=True) # Mostra desativado

elif STRATEGIC_FIELD_NAME not in df.columns or df[STRATEGIC_FIELD_NAME].dropna().empty:
    st.warning(
        f"O campo estratégico configurado ('{STRATEGIC_FIELD_NAME}') não foi encontrado ou está vazio nos dados carregados.",
        icon="⚠️"
    )
    st.info("Verifique se o campo está ativo em 'Minha Conta' ou se é preenchido no projeto. A análise será agregada.")
    st.selectbox(f"Contexto para Análise:", options=[selected_context], disabled=True) # Mostra desativado

else:
    # O campo está configurado, existe E tem valores, exibe o seletor
    context_list = ["— Visão Agregada do Projeto —"] + sorted(df[STRATEGIC_FIELD_NAME].dropna().unique())
    selected_context = st.selectbox(f"Selecione um {STRATEGIC_FIELD_NAME} para Análise:", options=context_list)
    can_filter_by_context = True # Ativa a flag

# --- Filtra os dados com base no contexto selecionado (REFINADO) ---
if selected_context == "— Visão Agregada do Projeto —" or not can_filter_by_context:
    # Usa todos os dados se for visão agregada OU se a filtragem não for possível
    scope_df = df
    scope_issues = st.session_state.get('raw_issues_for_fluxo', []) # Pega as issues brutas guardadas
    # Garante que scope_issues seja sempre uma lista
    if scope_issues is None: scope_issues = []
    
    st.subheader(f"Análise Agregada do Projeto: {st.session_state.get('project_name', '')}") # Título genérico com nome do projeto

else:
    # Filtra apenas se um contexto específico foi selecionado E a filtragem é possível
    scope_df = df[df[STRATEGIC_FIELD_NAME] == selected_context]
    scope_issue_keys = scope_df['ID'].tolist() # Usa a coluna 'ID' correta
    
    all_raw_issues = st.session_state.get('raw_issues_for_fluxo', [])
    # Garante que all_raw_issues seja sempre uma lista antes de filtrar
    if all_raw_issues is None: all_raw_issues = []
        
    scope_issues = [issue for issue in all_raw_issues if issue.key in scope_issue_keys]
    st.subheader(f"Análise para: {STRATEGIC_FIELD_NAME} = {selected_context}") # Título específico

# Verifica se scope_issues foi preenchido corretamente
if not scope_issues:
     st.warning("Não foram encontradas issues brutas correspondentes aos filtros aplicados. As métricas operacionais podem estar incompletas.")
     # Define auto_metrics com valores padrão para evitar erros
     auto_metrics = {'completion_pct': 0, 'deliveries_month': 0, 'avg_deadline_diff': 0, 'schedule_adherence': 0}
else:
    # Calcula as métricas apenas se houver issues
    project_config = get_project_config(current_project_key) or {}
    auto_metrics = calculate_executive_summary_metrics(scope_issues, project_config)


# --- Preparação dos Dados para as Abas (REFINADO) ---
project_config = get_project_config(current_project_key) or {} # Recarrega caso não tenha sido carregado antes

# Usa o contexto selecionado para buscar o RAG e os dados do perfil/KPI
try:
    # Tenta obter o status RAG
    rag_status = get_ai_rag_status(selected_context, json.dumps(auto_metrics)) # Passa o contexto selecionado
except Exception as e:
    rag_status = "N/A (Erro IA)"
    print(f"Erro ao obter RAG status: {e}") # Loga o erro para debug

client_summary_data = project_config.get('client_summaries', {}).get(selected_context, {}) # Busca pelo contexto selecionado
profile_data = client_summary_data.get('profile', {})
kpi_data = client_summary_data.get('kpis', {})

st.divider()

# ===== ESTRUTURA DE ABAS =====
tab_view, tab_edit = st.tabs(["📊 Análise", "📝 Editar Perfil e KPIs"]) # Título da aba genérico

with tab_view:
    # st.subheader(f"Análise para: {selected_context}") # Título movido para cima

    with st.container(border=True):
        st.markdown("**Perfil**")
        p_kpi1, p_kpi2, p_kpi3, p_kpi4 = st.columns(4)
        
        # Adapta o label do primeiro kpi
        context_label = STRATEGIC_FIELD_NAME if STRATEGIC_FIELD_NAME and selected_context != "— Visão Agregada do Projeto —" else "Contexto"
        context_value = selected_context if selected_context != "— Visão Agregada do Projeto —" else "Agregado"
        p_kpi1.metric(context_label, context_value)
        
        p_kpi2.metric("Responsável", profile_data.get('responsavel', 'N/A'))
        # Adiciona verificação para datas antes de formatar
        start_date_display = pd.to_datetime(profile_data.get('start_date')).strftime('%d/%m/%Y') if profile_data.get('start_date') else 'N/A'
        end_date_display = pd.to_datetime(profile_data.get('end_date')).strftime('%d/%m/%Y') if profile_data.get('end_date') else 'N/A'
        p_kpi3.metric("Data de Início", start_date_display)
        p_kpi4.metric("Data de Fim Prevista", end_date_display)

        st.markdown("**Dimensão Financeira**")
        f_kpi1, f_kpi2, f_kpi3 = st.columns(3)
        receita_total = kpi_data.get('mrr', 0.0) + kpi_data.get('receita_nao_recorrente', 0.0)
        total_despesas = kpi_data.get('total_despesas', 0.0)
        resultado_geral = receita_total - total_despesas
        margem_contribuicao = (resultado_geral / receita_total * 100) if receita_total > 0 else 0.0

        target_margin = global_configs.get('target_contribution_margin', 25.0) # Usa a config global carregada no início

        margin_color_class = "metric-value-red"
        if margem_contribuicao >= target_margin:
            margin_color_class = "metric-value-green"
        elif margem_contribuicao >= 0:
            margin_color_class = "metric-value-amber"

        with f_kpi1:
            display_custom_metric("Receita Recorrente (MRR)", f"R$ {kpi_data.get('mrr', 0.0):,.2f}", "metric-value-blue")
        with f_kpi2:
            display_custom_metric("Receitas Não Recorrentes", f"R$ {kpi_data.get('receita_nao_recorrente', 0.0):,.2f}", "metric-value-blue")
        with f_kpi3:
            display_custom_metric("Total de Despesas", f"R$ {total_despesas:,.2f}", "metric-value-red")
        
        f_kpi4, f_kpi5 = st.columns(2)
        with f_kpi4:
            display_custom_metric("Resultado (Receita - Despesa)", f"R$ {resultado_geral:,.2f}", "metric-value-green")
        with f_kpi5:
            display_custom_metric("Margem de Contribuição", f"{margem_contribuicao:.1f}%", margin_color_class)
        
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
    # Desativa a aba de edição se estiver na visão agregada
    if selected_context == "— Visão Agregada do Projeto —":
        st.info("A edição de Perfil e KPIs só está disponível ao selecionar um contexto específico (ex: Cliente).")
    else:
        with st.form(f"edit_form_{current_project_key}_{selected_context}"): # Usa selected_context na chave do form
            st.info(f"A editar os dados para: **{selected_context}** (no projeto {st.session_state.get('project_name', '')})")
            
            st.markdown(f"**1. Dados do {STRATEGIC_FIELD_NAME or 'Contexto'}**") # Label dinâmico
            c1, c2 = st.columns(2)
            responsavel = c1.text_input("Responsável", value=profile_data.get('responsavel', ''))
            
            # Converte para objeto date se existir, senão None
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
            
            nps = c1.number_input("NPS (Net Promoter Score)", min_value=-100, max_value=100, value=kpi_data.get('nps', 0)) # Pode ser 0 ou outro default

            if st.form_submit_button("Salvar Perfil e KPIs", use_container_width=True):
                if 'client_summaries' not in project_config:
                    project_config['client_summaries'] = {}
                
                # Salva usando o contexto selecionado como chave
                project_config['client_summaries'][selected_context] = {
                    'profile': {
                        'responsavel': responsavel,
                        'start_date': start_date.isoformat() if start_date else None,
                        'end_date': end_date.isoformat() if end_date else None
                    },
                    'kpis': {
                        'mrr': mrr, 
                        'receita_nao_recorrente': receita_nao_recorrente,
                        'total_despesas': total_despesas,
                        'nps': nps
                    }
                }
                save_project_config(current_project_key, project_config)
                st.success(f"Dados para '{selected_context}' guardados com sucesso!")
                st.rerun()