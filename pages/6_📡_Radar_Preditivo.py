# pages/6_📡_Radar_Preditivo.py
# (Baseado no 6_📈_Resumo_Executivo.py, com correção do KeyError)

import streamlit as st
import pandas as pd
import os, json
from datetime import datetime, timedelta
from jira_connector import *

# --- Importações Corretas do metrics_calculator.py ---
# Estas funções SÃO encontradas no seu arquivo
from metrics_calculator import (
    calculate_executive_summary_metrics,
    find_completion_date,
    calculate_schedule_adherence # Usado por calculate_executive_summary_metrics
)
# NOTA: A função de FORECAST (find_completion_date para backlog) 
# e a de VAZÃO SEMANAL não estão no seu metrics_calculator.py
# ----------------------------------------------------

from security import *
from pathlib import Path
from utils import *
from config import SESSION_TIMEOUT_MINUTES

# --- Funções de UI (sem alterações) ---

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

# --- FUNÇÕES DE INSIGHT (LÓGICA REAL) ---

def get_field_id_from_name(field_name, configs):
    """Busca o ID do custom field (ex: 'customfield_1001') a partir do nome (ex: 'Cliente')."""
    if 'custom_fields' in configs:
        for field in configs['custom_fields']:
            if field.get('name') == field_name:
                return field.get('id')
    # Fallback se não for um custom field (ex: 'Priority')
    return field_name

def get_issue_context_value(issue, field_id):
    """Pega o valor de um campo de um objeto issue do Jira, lidando com objetos aninhados."""
    try:
        value = getattr(issue.fields, field_id, None)
        
        if value is None:
            return None
        
        # Lida com campos que são objetos (ex: {'value': 'Cliente A'})
        if hasattr(value, 'value'):
            return str(value.value)
        # Lida com campos que são listas (ex: labels)
        if isinstance(value, list):
            return ", ".join(value)
        # Lida com campos de nome (ex: priority.name)
        if hasattr(value, 'name'):
            return str(value.name)
            
        return str(value)
    except Exception:
        return None

# --- FUNÇÃO CORRIGIDA ---
def gerar_insights_risco_projeto(scope_df):
    """
    Gera insights de Risco (Módulo 1) com base no DataFrame de itens completos.
    CORRIGIDO: Procura dinamicamente pela coluna de data de conclusão.
    """
    insights = []
    
    if scope_df.empty:
        insights.append({"tipo": "info", "texto": "Não há dados concluídos suficientes para análise de risco de fluxo."})
        return insights

    # --- INÍCIO DA CORREÇÃO ---
    # Tenta encontrar a coluna de data de conclusão correta
    possible_date_cols = ['Data de Conclusão', 'Completion Date', 'Resolution Date', 'Data de Resolução', 'Done Date']
    date_col_name = None
    for col in possible_date_cols:
        if col in scope_df.columns:
            date_col_name = col
            break
    
    if date_col_name is None:
        insights.append({
            "tipo": "alerta", 
            "texto": (
                f"**Erro de Configuração:** Não foi possível encontrar uma coluna de data de conclusão "
                f"(ex: 'Data de Conclusão', 'Resolution Date') no DataFrame. "
                f"Não é possível analisar o risco de fluxo."
            )
        })
        return insights
    # --- FIM DA CORREÇÃO ---

    # Garantir que a data de resolução é datetime
    # USA A COLUNA ENCONTRADA
    try:
        scope_df[date_col_name] = pd.to_datetime(scope_df[date_col_name])
    except Exception as e:
        insights.append({"tipo": "alerta", "texto": f"Erro ao converter coluna de data '{date_col_name}': {e}"})
        return insights
        
    today = pd.to_datetime('today').normalize()
    
    # 1. Análise de Tendência do Lead Time
    try:
        # USA A COLUNA ENCONTRADA
        df_recent = scope_df[scope_df[date_col_name] >= (today - timedelta(days=14))]
        df_previous = scope_df[
            (scope_df[date_col_name] >= (today - timedelta(days=28))) &
            (scope_df[date_col_name] < (today - timedelta(days=14)))
        ]
        
        lt_recent_mean = df_recent['Lead Time'].mean()
        lt_previous_mean = df_previous['Lead Time'].mean()

        if pd.notna(lt_recent_mean) and pd.notna(lt_previous_mean) and lt_previous_mean > 0:
            if lt_recent_mean > (lt_previous_mean * 1.25): # Aumento de 25%
                lt_percent_increase = ((lt_recent_mean / lt_previous_mean) - 1) * 100
                insights.append({
                    "tipo": "alerta", 
                    "texto": f"**Alerta de Atraso:** O 'Lead Time' médio aumentou **{lt_percent_increase:.0f}%** nas últimas 2 semanas (de {lt_previous_mean:.1f} para {lt_recent_mean:.1f} dias)."
                })
    except Exception as e:
        print(f"Erro ao calcular tendência de Lead Time: {e}") # Log de erro

    # 2. Análise de Taxa de Bugs
    try:
        total_done = scope_df.shape[0]
        # Assumindo que 'Issue Type' é a coluna correta.
        total_bugs = scope_df[scope_df['Issue Type'].str.lower() == 'bug'].shape[0]
        
        if total_done > 0:
            bug_rate_percent = (total_bugs / total_done) * 100
            if bug_rate_percent > 10: # Limite de 10%
                insights.append({
                    "tipo": "risco",
                    "texto": f"**Risco de Qualidade:** A 'Taxa de Bugs' está em **{bug_rate_percent:.0f}%** ({total_bugs} bugs de {total_done} itens), indicando potenciais problemas de QA."
                })
    except Exception as e:
        print(f"Erro ao calcular taxa de bugs: {e}") # Log de erro

    if not insights:
        insights.append({"tipo": "info", "texto": "Nenhum risco de fluxo (Lead Time, Bugs) detectado com base nas regras atuais."})
        
    return insights

def gerar_insights_financeiros_preditivos(contexto_selecionado, global_configs, scope_df, all_context_issues):
    """
    Gera insights Financeiros Preditivos (Módulo 2).
    Esta versão informa sobre as funções de forecast ausentes.
    """
    insights = []
    
    # 1. Busca os dados financeiros do config global
    dados_financeiros_globais = global_configs.get('dados_financeiros_preditivos', {})
    dados_financeiros_contexto = dados_financeiros_globais.get(contexto_selecionado, {})
    
    orcamento = dados_financeiros_contexto.get('orcamento', 0)
    custo_time_mes = dados_financeiros_contexto.get('custo_time_mes', 0)
    
    if orcamento == 0 or custo_time_mes == 0:
        return [{"tipo": "info", "texto": f"Dados de Orçamento/Custo Preditivo não cadastrados para '{contexto_selecionado}' no painel de Administração."}]

    # --- LÓGICA DE FORECAST (MODIFICADA) ---
    # Informa ao usuário que a lógica de forecast está pendente
    insights.append({
        "tipo": "info",
        "texto": (
            "**Módulo de Forecast Pendente:** Para ativar a previsão de custo e data, "
            "as funções de forecast (ex: `find_completion_date` para Múltiplos Itens) "
            "e de cálculo de vazão semanal (ex: `calculate_throughput_series`) "
            "precisam ser adicionadas ao `metrics_calculator.py`."
        )
    })
    
    # A lógica de forecast original foi removida pois as funções não existem no seu arquivo.
        
    return insights
# --- FIM DAS FUNÇÕES DE INSIGHT ---


st.set_page_config(page_title="Radar Preditivo", page_icon="📡", layout="wide")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("📡 Radar Preditivo AI", divider='rainbow')
st.markdown("Respostas diretas sobre riscos, finanças e alinhamento estratégico.")

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

if check_session_timeout():
    st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
    st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
    st.stop()

if 'jira_client' not in st.session_state:
    user_connections = get_users_collection(st.session_state['email'])
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

# --- CSS (Copiado do seu Resumo Executivo) ---
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

# --- Carregamento de Dados ---
df = st.session_state.get('dynamic_df')
current_project_key = st.session_state.get('project_key')
all_raw_issues = st.session_state.get('raw_issues_for_fluxo', []) # Assume que isso contém TUDO (pending+done)

if df is None or df.empty or not current_project_key or not all_raw_issues:
    st.info("⬅️ Por favor, carregue os dados de um projeto em 'Meu Dashboard' ou 'Métricas de Fluxo' para ver esta análise.")
    st.stop()

# --- Carrega Configurações ---
global_configs = get_global_configs()
project_config = get_project_config(current_project_key) or {}

# --- Seletor de Contexto ---
st.subheader("Seleção de Contexto")
STRATEGIC_FIELD_NAME = global_configs.get('strategic_grouping_field') # Ex: "Cliente"
selected_context = "— Visão Agregada do Projeto —"
can_filter_by_context = False 

if not STRATEGIC_FIELD_NAME:
    st.warning("Nenhum campo de agrupamento estratégico foi definido.", icon="⚠️")
    st.info("A análise será agregada. Configure um campo em **Administração > Configurações > Campos Jira**.")
    st.selectbox(f"Contexto para Análise:", options=[selected_context], disabled=True)

elif STRATEGIC_FIELD_NAME not in df.columns or df[STRATEGIC_FIELD_NAME].dropna().empty:
    st.warning(
        f"O campo estratégico configurado ('{STRATEGIC_FIELD_NAME}') não foi encontrado ou está vazio nos dados *concluídos*.",
        icon="⚠️"
    )
    st.info("Verifique se o campo está ativo em 'Minha Conta' ou se é preenchido no projeto. A análise será agregada.")
    st.selectbox(f"Contexto para Análise:", options=[selected_context], disabled=True)

else:
    # O campo existe, exibe o seletor
    context_list = ["— Visão Agregada do Projeto —"] + sorted(df[STRATEGIC_FIELD_NAME].dropna().unique())
    selected_context = st.selectbox(f"Selecione um {STRATEGIC_FIELD_NAME} para Análise:", options=context_list)
    can_filter_by_context = True

# --- Filtra os dados (LÓGICA REAL E CORRIGIDA) ---
# Encontra o ID do campo (ex: 'customfield_1001')
strategic_field_id = get_field_id_from_name(STRATEGIC_FIELD_NAME, global_configs)

if selected_context == "— Visão Agregada do Projeto —" or not can_filter_by_context:
    scope_df = df # Todos os CONCLUÍDOS do projeto
    scope_issues = all_raw_issues # TODOS (brutos) do projeto
    st.subheader(f"Análise Agregada do Projeto: {st.session_state.get('project_name', '')}")
else:
    # Filtra o DataFrame de CONCLUÍDOS (para métricas de fluxo)
    scope_df = df[df[STRATEGIC_FIELD_NAME] == selected_context]
    
    # Filtra TODOS os issues (brutos) para obter o backlog
    scope_issues = []
    if strategic_field_id:
        for issue in all_raw_issues:
            context_value = get_issue_context_value(issue, strategic_field_id)
            if context_value == selected_context:
                scope_issues.append(issue)
    
    st.subheader(f"Análise para: {STRATEGIC_FIELD_NAME} = {selected_context}")

# --- Cálculos de Métricas ---
if not scope_issues and selected_context != "— Visão Agregada do Projeto —":
     st.warning(f"Não foram encontradas issues brutas para o contexto '{selected_context}'. Verifique o mapeamento do campo em Administração.")
     auto_metrics = {'completion_pct': 0, 'deliveries_month': 0, 'avg_deadline_diff': 0, 'schedule_adherence': 0}
else:
    # 'scope_issues' aqui são os issues brutos *filtrados* pelo contexto
    # 'calculate_executive_summary_metrics' vem do seu 'metrics_calculator.py' (linha 427)
     auto_metrics = calculate_executive_summary_metrics(scope_issues, project_config)


# --- Busca dados de RAG e KPIs Manuais ---
try:
    rag_status = get_ai_rag_status(selected_context, json.dumps(auto_metrics)) # 'security.py'
except Exception as e:
    rag_status = "N/A (Erro IA)"
    print(f"Erro ao obter RAG status: {e}")

# Estes são os KPIs manuais (MRR, NPS) do 'project_config'
# (Que eram preenchidos na aba 'Editar' do antigo Resumo Executivo)
client_summary_data = project_config.get('client_summaries', {}).get(selected_context, {})
profile_data = client_summary_data.get('profile', {})
kpi_data = client_summary_data.get('kpis', {}) 

st.divider()

# ===== ESTRUTURA DE ABAS (MODIFICADA) =====
# REMOVEMOS A ABA 'tab_edit'

st.subheader("Módulo 1: Radar de Risco Preditivo (Saúde do Fluxo)")
with st.container(border=True):
    with st.spinner("Analisando riscos do fluxo..."):
        # Passa o DataFrame de itens *concluídos* e *filtrados*
        insights_risco = gerar_insights_risco_projeto(scope_df)
    
    if not insights_risco:
        st.info("Nenhuma análise de risco de fluxo gerada.")
    else:
        for insight in insights_risco:
            if insight['tipo'] == 'alerta':
                st.warning(f"⚠️ {insight['texto']}")
            elif insight['tipo'] == 'info':
                st.info(f"ℹ️ {insight['texto']}")
            else: # 'risco'
                st.error(f"🚨 {insight['texto']}")

st.subheader("Módulo 2: Performance Financeira & Forecast Preditivo")
with st.container(border=True):
    with st.spinner("Analisando performance financeira..."):
        # Passa o DF de concluídos (para vazão) e os issues brutos (para backlog)
        insights_fin = gerar_insights_financeiros_preditivos(selected_context, global_configs, scope_df, scope_issues)

    if not insights_fin:
        st.info("Nenhuma análise de forecast financeiro gerada.")
    else:
        for insight in insights_fin:
            if insight['tipo'] == 'alerta_grave':
                st.error(f"🚨 {insight['texto']}")
            elif insight['tipo'] == 'sucesso':
                st.success(f"✅ {insight['texto']}")
            else: # 'info' ou 'alerta'
                st.info(f"ℹ️ {insight['texto']}")

st.subheader("Módulo 3: KPIs de Negócio e Operacionais (Visão Atual)")
with st.container(border=True):
    st.markdown("**Perfil**")
    p_kpi1, p_kpi2, p_kpi3, p_kpi4 = st.columns(4)
    
    context_label = STRATEGIC_FIELD_NAME if STRATEGIC_FIELD_NAME and selected_context != "— Visão Agregada do Projeto —" else "Contexto"
    context_value = selected_context if selected_context != "— Visão Agregada do Projeto —" else "Agregado"
    p_kpi1.metric(context_label, context_value)
    
    # KPIs Manuais (de 'client_summaries' no project_config)
    p_kpi2.metric("Responsável", profile_data.get('responsavel', 'N/A'))
    start_date_display = pd.to_datetime(profile_data.get('start_date')).strftime('%d/%m/%Y') if profile_data.get('start_date') else 'N/A'
    end_date_display = pd.to_datetime(profile_data.get('end_date')).strftime('%d/%m/%Y') if profile_data.get('end_date') else 'N/A'
    p_kpi3.metric("Data de Início", start_date_display)
    p_kpi4.metric("Data de Fim Prevista", end_date_display)

    st.markdown("**Dimensão Financeira (KPIs de Negócio Manuais)**")
    f_kpi1, f_kpi2, f_kpi3 = st.columns(3)
    receita_total = kpi_data.get('mrr', 0.0) + kpi_data.get('receita_nao_recorrente', 0.0)
    total_despesas = kpi_data.get('total_despesas', 0.0)
    resultado_geral = receita_total - total_despesas
    margem_contribuicao = (resultado_geral / receita_total * 100) if receita_total > 0 else 0.0
    target_margin = global_configs.get('target_contribution_margin', 25.0)

    margin_color_class = "metric-value-red"
    if margem_contribuicao >= target_margin:
        margin_color_class = "metric-value-green"
    elif margem_contribuicao >= 0:
        margin_color_class = "metric-value-amber"

    with f_kpi1: display_custom_metric("Receita Recorrente (MRR)", f"R$ {kpi_data.get('mrr', 0.0):,.2f}", "metric-value-blue")
    with f_kpi2: display_custom_metric("Receitas Não Recorrentes", f"R$ {kpi_data.get('receita_nao_recorrente', 0.0):,.2f}", "metric-value-blue")
    with f_kpi3: display_custom_metric("Total de Despesas", f"R$ {total_despesas:,.2f}", "metric-value-red")
    
    f_kpi4, f_kpi5 = st.columns(2)
    with f_kpi4:
        display_custom_metric("Resultado (Receita - Despesa)", f"R$ {resultado_geral:,.2f}", "metric-value-green" if resultado_geral > 0 else "metric-value-red")
    with f_kpi5:
        display_custom_metric("Margem de Contribuição", f"{margem_contribuicao:.1f}%", margin_color_class)
    
    st.markdown("**Dimensão Operacional (Métricas Automáticas)**")
    o_kpi1, o_kpi2, o_kpi3, o_kpi4 = st.columns(4)
    # KPIs Automáticos (de 'calculate_executive_summary_metrics')
    o_kpi1.metric("% Concluído", f"{auto_metrics.get('completion_pct', 0):.0f}%")
    o_kpi2.metric("Entregas no Mês", auto_metrics.get('deliveries_month', 0))
    o_kpi3.metric("Adesão ao Cronograma", f"{auto_metrics.get('schedule_adherence', 0):.1f}%")
    o_kpi4.metric("Desvio Médio de Prazo", f"{auto_metrics.get('avg_deadline_diff', 0):+.1f}d")

    st.markdown("**Dimensão de Relacionamento com o Cliente**")
    r_kpi1, r_kpi2 = st.columns(2)
    # KPI Manual (NPS) e Automático (RAG)
    r_kpi1.metric("NPS (Net Promoter Score)", kpi_data.get('nps', 'N/A'))
    r_kpi2.metric("Status RAG (IA)", rag_status)