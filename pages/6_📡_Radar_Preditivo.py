# pages/6_📡_Radar_Preditivo.py
# (Versão Corrigida para carregar dados EXATAMENTE como a pág. 3_Métricas_de_Fluxo)

import streamlit as st
import pandas as pd
import os, json
from datetime import datetime, timedelta
# Importa a barra de progresso
from stqdm import stqdm 

# --- Importações Corretas ---
from jira_connector import (
    get_jira_projects, 
    load_and_process_project_data # A função que a pág. 3 usa
)
from metrics_calculator import (
    calculate_executive_summary_metrics,
    find_completion_date,
    calculate_schedule_adherence,
    calculate_lead_time,
    calculate_cycle_time
)
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
    return field_name

def get_issue_context_value(issue, field_id):
    """Pega o valor de um campo de um objeto issue do Jira, lidando com objetos aninhados."""
    try:
        value = getattr(issue.fields, field_id, None)
        if value is None: return None
        if hasattr(value, 'value'): return str(value.value)
        if isinstance(value, list): return ", ".join(value)
        if hasattr(value, 'name'): return str(value.name)
        return str(value)
    except Exception:
        return None

def gerar_insights_risco_projeto(scope_df_concluidos):
    """
    Gera insights de Risco (Módulo 1) com base no DataFrame de itens completos.
    Esta função espera receber *apenas* itens concluídos.
    """
    insights = []
    
    if scope_df_concluidos.empty:
        insights.append({"tipo": "info", "texto": "Não há dados concluídos suficientes para análise de risco de fluxo."})
        return insights

    # --- Encontrar Coluna de Data de Conclusão ---
    possible_date_cols = ['Data de Conclusão', 'Completion Date', 'Resolution Date', 'Data de Resolução', 'Done Date']
    date_col_name = None
    for col in possible_date_cols:
        if col in scope_df_concluidos.columns:
            date_col_name = col
            break
    
    if date_col_name is None:
        insights.append({
            "tipo": "alerta", 
            "texto": f"**Erro de Configuração:** Não foi possível encontrar uma coluna de data de conclusão (ex: 'Data de Conclusão')."
        })
        return insights 

    # --- Análises de Risco (Lead Time e Bugs) ---
    try:
        scope_df_copy = scope_df_concluidos.copy() 
        scope_df_copy[date_col_name] = pd.to_datetime(scope_df_copy[date_col_name], errors='coerce')
        scope_df_copy = scope_df_copy.dropna(subset=[date_col_name]) 
        
        if scope_df_copy.empty:
             insights.append({"tipo": "info", "texto": "Não há dados concluídos com data válida para análise de risco de fluxo."})
             return insights

        today = pd.to_datetime('today').normalize()
        
        # 1. Análise de Tendência do Lead Time
        df_recent = scope_df_copy[scope_df_copy[date_col_name] >= (today - timedelta(days=14))]
        df_previous = scope_df_copy[
            (scope_df_copy[date_col_name] >= (today - timedelta(days=28))) &
            (scope_df_copy[date_col_name] < (today - timedelta(days=14)))
        ]
        
        lead_time_col = 'Lead Time' if 'Lead Time' in df_recent.columns else 'Lead Time (dias)'
        if lead_time_col not in df_recent.columns:
             print(f"Aviso: Coluna '{lead_time_col}' não encontrada para análise de Lead Time.")
        else:
            lt_recent_mean = df_recent[lead_time_col].mean()
            lt_previous_mean = df_previous[lead_time_col].mean()

            if pd.notna(lt_recent_mean) and pd.notna(lt_previous_mean) and lt_previous_mean > 0:
                if lt_recent_mean > (lt_previous_mean * 1.25): 
                    lt_percent_increase = ((lt_recent_mean / lt_previous_mean) - 1) * 100 
                    insights.append({
                        "tipo": "alerta", 
                        "texto": f"**Alerta de Atraso:** O '{lead_time_col}' médio aumentou **{lt_percent_increase:.0f}%** nas últimas 2 semanas (de {lt_previous_mean:.1f} para {lt_recent_mean:.1f} dias)."
                    })
        
        # 2. Análise de Taxa de Bugs
        total_done = scope_df_copy.shape[0]
        type_col = 'Tipo de Issue' if 'Tipo de Issue' in scope_df_copy.columns else 'Issue Type'
        if type_col in scope_df_copy.columns:
            total_bugs = scope_df_copy[scope_df_copy[type_col].str.lower() == 'bug'].shape[0]
            
            if total_done > 0:
                bug_rate_percent = (total_bugs / total_done) * 100
                if bug_rate_percent > 10: 
                    insights.append({
                        "tipo": "risco",
                        "texto": f"**Risco de Qualidade:** A 'Taxa de Bugs' está em **{bug_rate_percent:.0f}%** ({total_bugs} bugs de {total_done} itens), indicando potenciais problemas de QA."
                    })
        else:
            print(f"Aviso: Coluna '{type_col}' não encontrada. Pulando análise de bugs.")
            
    except Exception as e:
        print(f"Erro ao calcular Risco de Fluxo: {e}")
        insights.append({"tipo": "alerta", "texto": f"Erro ao analisar risco de fluxo: {e}"})

    # --- LÓGICA DE BURNOUT ---
    created_col = 'Data de Criação' if 'Data de Criação' in scope_df_concluidos.columns else 'Created'
    
    if created_col not in scope_df_concluidos.columns:
        print(f"Aviso: Coluna '{created_col}' não encontrada. Pulando análise de Burnout.")
    else:
        try:
            created_dates = pd.to_datetime(scope_df_concluidos[created_col], errors='coerce')
            created_dates = created_dates.dropna() 
            
            if not created_dates.empty:
                today = pd.to_datetime('today').normalize() 
                after_hours = (created_dates.dt.hour < 8) | (created_dates.dt.hour > 19)
                weekends = (created_dates.dt.dayofweek >= 5)
                
                recent_mask = (created_dates >= (today - timedelta(days=30)))
                total_tickets_recentes = recent_mask.sum()
                
                if total_tickets_recentes > 10: 
                    tickets_fora_de_hora = ((after_hours | weekends) & recent_mask).sum()
                    percent_fora_de_hora = (tickets_fora_de_hora / total_tickets_recentes) * 100
                    
                    if percent_fora_de_hora > 20: 
                        insights.append({
                            "tipo": "alerta",
                            "texto": f"**Risco de Burnout:** **{percent_fora_de_hora:.0f}%** dos tickets nos últimos 30 dias foram criados fora do horário comercial, indicando potencial sobrecarga da equipe."
                        })
        except Exception as e:
            print(f"Erro ao calcular Risco de Burnout: {e}")
    # --- FIM DA LÓGICA ---

    if not insights or all(i['tipo'] == 'alerta' and 'Erro' in i['texto'] for i in insights):
        if not any('Erro' in i['texto'] for i in insights):
            insights.append({"tipo": "info", "texto": "Nenhum risco de fluxo (Lead Time, Bugs, Burnout) detectado com base nas regras atuais."})

    return insights

def gerar_insights_financeiros_preditivos(contexto_selecionado, global_configs, scope_df, all_context_issues):
    """
    Gera insights Financeiros Preditivos (Módulo 2).
    Informa sobre as funções de forecast ausentes.
    """
    insights = []
    
    dados_financeiros_globais = global_configs.get('dados_financeiros_preditivos', {})
    dados_financeiros_contexto = dados_financeiros_globais.get(contexto_selecionado, {})
    orcamento = dados_financeiros_contexto.get('orcamento', 0)
    custo_time_mes = dados_financeiros_contexto.get('custo_time_mes', 0)
    
    if orcamento == 0 or custo_time_mes == 0:
        return [{"tipo": "info", "texto": f"Dados de Orçamento/Custo Preditivo não cadastrados para '{contexto_selecionado}' no painel de Administração."}]

    insights.append({
        "tipo": "info",
        "texto": (
            "**Módulo de Forecast Pendente:** Para ativar a previsão de custo e data, "
            "as funções de forecast (ex: `find_completion_date` para Múltiplos Itens) "
            "e de cálculo de vazão semanal (ex: `calculate_throughput_series`) "
            "precisam ser adicionadas ao `metrics_calculator.py`."
        )
    })
        
    return insights
# --- FIM DAS FUNÇÕES DE INSIGHT ---


st.set_page_config(page_title="Radar Preditivo", page_icon="📡", layout="wide")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("📡 Radar Preditivo AI", divider='rainbow')
st.markdown("Respostas diretas sobre riscos, finanças e alinhamento estratégico.")

# --- Bloco de Autenticação e Conexão ---
try:
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
except Exception as e:
    st.error(f"Erro durante a verificação de autenticação: {e}")
    st.stop()

# --- CSS ---
st.markdown("""
<style>
/* ... (Seu CSS completo aqui) ... */
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
.metric-label { font-size: 0.9rem; color: #555; margin-bottom: 0.5rem; }
.metric-value { font-size: 1.5rem; font-weight: 600; line-height: 1.2; }
.metric-value-blue { color: #007bff; }
.metric-value-red { color: #dc3545; }
.metric-value-green { color: #28a745; }
.metric-value-amber { color: #fd7e14; }
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

# --- Bloco de Carregamento de Dados ---
# Lógica de expansão
expand_loader = True
if 'dynamic_df' in st.session_state:
    df_check = st.session_state['dynamic_df']
    if isinstance(df_check, pd.DataFrame) and not df_check.empty:
        expand_loader = False

with st.expander("Carregar Dados do Projeto", expanded=expand_loader):
    jira_client = st.session_state.get('jira_client')
    
    # 1. Seleção de Projeto (igual à pág. 3)
    try:
        projects = st.session_state.get('projects', {})
        if not projects:
            projects = get_jira_projects(jira_client)
            st.session_state['projects'] = projects 
            
        project_names = list(projects.keys())
        
        last_project_key = find_user(st.session_state['email']).get('last_project_key')
        default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and project_names else 0
        
        selected_project_name = st.selectbox(
            "Selecione o Projeto Jira:",
            options=project_names,
            index=default_index,
            key="radar_project_selector"
        )
        selected_project_key = projects[selected_project_name]

    except Exception as e:
        st.error(f"Não foi possível carregar os projetos do Jira. Erro: {e}")
        st.stop()

    # REMOVIDO: Seleção de Board e Data
    # A pág. 3 carrega o projeto inteiro, vamos fazer o mesmo.

    # 3. Botão de Carregar
    if st.button("Carregar Dados do Radar", type="primary", use_container_width=True, key="radar_load_button"):
        
        # Limpa dados antigos
        if 'dynamic_df' in st.session_state: del st.session_state['dynamic_df']
        if 'raw_issues_for_fluxo' in st.session_state: del st.session_state['raw_issues_for_fluxo']
        
        with st.spinner(f"Carregando e processando dados do projeto '{selected_project_name}'... (Isto pode demorar)"):
            try:
                # --- CHAMA A FUNÇÃO EXATAMENTE COMO A PÁG. 3 ---
                user_data = find_user(st.session_state['email'])
                
                # Assumindo que a sua pág. 3 chama com 3 argumentos
                df_loaded, raw_issues = load_and_process_project_data(
                    jira_client,
                    selected_project_key,
                    user_data 
                )
                
                # Salva o estado
                st.session_state['project_key'] = selected_project_key
                st.session_state['project_name'] = selected_project_name
                
                # --- CORREÇÃO: Salva os dados brutos como a Pág. 3 faz ---
                st.session_state['dynamic_df'] = df_loaded # Salva o DF COMPLETO
                st.session_state['raw_issues_for_fluxo'] = raw_issues
                # --- FIM DA CORREÇÃO ---
                
                if df_loaded is None or df_loaded.empty:
                    st.warning(f"Nenhuma issue foi processada para o projeto '{selected_project_name}'.")
                else:
                    st.success(f"{len(raw_issues)} issues carregadas e {len(df_loaded)} issues processadas!")

                st.rerun() 
            
            except TypeError as te:
                 if "takes 2 positional arguments but 3 were given" in str(te):
                    st.error("Erro de Versão: A função 'load_and_process_project_data' no seu 'jira_connector.py' (linha 351) está desatualizada. Ela precisa aceitar 3 argumentos (client, key, user_data) como a 'Página de Métricas' (pág. 3) está a chamar.")
                    st.info("Por favor, atualize a definição da função em `jira_connector.py` de `def load_and_process_project_data(jira_client, project_key):` para `def load_and_process_project_data(jira_client, project_key, user_data):` (mesmo que não use a variável `user_data`).")
                 else:
                     st.error(f"Erro ao carregar dados: {te}")
            except Exception as e:
                st.error(f"Erro ao carregar ou processar dados: {e}") 
                if 'dynamic_df' in st.session_state: del st.session_state['dynamic_df']
                if 'raw_issues_for_fluxo' in st.session_state: del st.session_state['raw_issues_for_fluxo']
# --- FIM DO BLOCO DE CARREGAMENTO ---


# --- LÓGICA DE ANÁLISE ---
df = st.session_state.get('dynamic_df') # Este DF agora deve conter TODOS os itens
current_project_key = st.session_state.get('project_key')
all_raw_issues = st.session_state.get('raw_issues_for_fluxo', []) # Este contém TODOS

if df is None or not current_project_key:
    st.info("⬅️ Por favor, selecione um projeto no menu 'Carregar Dados do Projeto' acima e clique em 'Carregar Dados' para iniciar a análise.")
elif df.empty and current_project_key:
     st.warning(f"✅ Dados carregados para '{st.session_state.get('project_name')}', mas nenhuma issue foi processada.")
     st.info("Verifique se o projeto tem issues ou se houve um erro no processamento.")
else:
    # --- Carrega Configurações ---
    global_configs = get_global_configs()
    project_config = get_project_config(current_project_key) or {} 

    # --- Seletor de Contexto ---
    st.subheader("Seleção de Contexto")
    STRATEGIC_FIELD_NAME = global_configs.get('strategic_grouping_field')
    selected_context = "— Visão Agregada do Projeto —"
    can_filter_by_context = False 

    if not STRATEGIC_FIELD_NAME:
        st.warning("Nenhum campo de agrupamento estratégico definido.", icon="⚠️")
        st.info("Configure em **Administração > Configurações > Campos Jira**.")
        st.selectbox(f"Contexto:", options=[selected_context], disabled=True)

    elif STRATEGIC_FIELD_NAME not in df.columns:
         st.warning(f"Campo estratégico '{STRATEGIC_FIELD_NAME}' não encontrado nos dados carregados.", icon="⚠️")
         st.info(f"Verifique se o campo está correto. Colunas disponíveis: {list(df.columns)}")
         st.selectbox(f"Contexto:", options=[selected_context], disabled=True)
         
    elif df[STRATEGIC_FIELD_NAME].dropna().empty:
        st.warning(f"Campo estratégico '{STRATEGIC_FIELD_NAME}' está vazio em todos os dados.", icon="⚠️")
        st.info("Análise será agregada.")
        st.selectbox(f"Contexto:", options=[selected_context], disabled=True)

    else:
        # CONSTRÓI O SELETOR A PARTIR DO DF COMPLETO
        context_list = ["— Visão Agregada do Projeto —"] + sorted(df[STRATEGIC_FIELD_NAME].dropna().unique())
        selected_context = st.selectbox(f"Selecione um {STRATEGIC_FIELD_NAME} para Análise:", options=context_list)
        can_filter_by_context = True

    # --- Filtra os dados ---
    strategic_field_id = get_field_id_from_name(STRATEGIC_FIELD_NAME, global_configs)

    # Define a coluna de data de conclusão (para o filtro)
    date_col_name_filter = None
    possible_date_cols_filter = ['Data de Conclusão', 'Completion Date', 'Resolution Date', 'Data de Resolução', 'Done Date']
    for col in possible_date_cols_filter:
        if col in df.columns:
            date_col_name_filter = col
            break
            
    if not date_col_name_filter:
        st.error("Erro Crítico: Nenhuma coluna de data de conclusão (ex: 'Data de Conclusão') foi encontrada no DataFrame. O Radar de Risco não pode funcionar.")
        st.stop()

    if selected_context == "— Visão Agregada do Projeto —" or not can_filter_by_context:
        # FILTRA O DF PARA CONCLUÍDOS
        scope_df = df[pd.notna(df[date_col_name_filter])].copy() # .copy() para evitar SettingWithCopyWarning
        scope_issues = all_raw_issues 
        st.subheader(f"Análise Agregada do Projeto: {st.session_state.get('project_name', '')}")
    else:
        # Filtra o DataFrame de todos os itens para o contexto
        if STRATEGIC_FIELD_NAME in df.columns:
           df_contexto = df[df[STRATEGIC_FIELD_NAME] == selected_context]
           # FILTRA O DF DE CONTEXTO PARA CONCLUÍDOS
           scope_df = df_contexto[pd.notna(df_contexto[date_col_name_filter])].copy() # .copy()
        else:
           scope_df = pd.DataFrame(columns=df.columns) 
           st.error(f"Erro interno: Campo estratégico '{STRATEGIC_FIELD_NAME}' desapareceu.")

        # Filtra a lista de issues brutas
        scope_issues = []
        if strategic_field_id:
            for issue in all_raw_issues:
                context_value = get_issue_context_value(issue, strategic_field_id)
                if context_value == selected_context:
                    scope_issues.append(issue)
        st.subheader(f"Análise para: {STRATEGIC_FIELD_NAME} = {selected_context}")

    # --- Cálculos de Métricas ---
    if not scope_issues and selected_context != "— Visão Agregada do Projeto —":
         st.warning(f"Não foram encontradas issues brutas para o contexto '{selected_context}'.")
         auto_metrics = {'completion_pct': 0, 'deliveries_month': 0, 'avg_deadline_diff': 0, 'schedule_adherence': 0}
    else:
         auto_metrics = calculate_executive_summary_metrics(scope_issues, project_config)

    # --- Busca dados de RAG e KPIs Manuais ---
    with st.spinner("Processamento IA em andamento..."): # Adiciona spinner personalizado
        try:
            # Cacheia a chamada da API (adicione @st.cache_data(ttl=3600) em get_ai_rag_status)
            rag_status = get_ai_rag_status(selected_context, json.dumps(auto_metrics)) 
        except Exception as e:
            rag_status = f"Erro IA: {e}"
            print(f"Erro ao obter RAG status: {e}")

    rag_status_str = str(rag_status)
    if "429" in rag_status_str or "quota" in rag_status_str.lower():
        rag_display = "N/A (Limite API)"
        rag_help = "Limite de uso da API (Free Tier) atingido. Tente novamente em 1 minuto."
    else:
        rag_display = rag_status
        rag_help = None

    client_summary_data = project_config.get('client_summaries', {}).get(selected_context, {})
    profile_data = client_summary_data.get('profile', {})
    kpi_data = client_summary_data.get('kpis', {}) 

    st.divider()

    # --- Módulo 1: Radar de Risco Preditivo ---
    st.subheader("Módulo 1: Radar de Risco Preditivo (Saúde do Fluxo)")
    with st.container(border=True):
        with st.spinner("Analisando riscos do fluxo..."):
            # scope_df agora SÓ tem concluídos (e filtrados por contexto, se aplicável)
            insights_risco = gerar_insights_risco_projeto(scope_df) 
        
        if not insights_risco:
            st.info("Nenhuma análise de risco de fluxo gerada.")
        else:
            for insight in insights_risco:
                if insight['tipo'] == 'alerta':
                    st.warning(f"⚠️ {insight['texto']}")
                elif insight['tipo'] == 'info':
                    st.info(f"ℹ️ {insight['texto']}")
                else: 
                    st.error(f"🚨 {insight['texto']}")

    # --- Módulo 2: Performance Financeira & Forecast ---
    st.subheader("Módulo 2: Performance Financeira & Forecast Preditivo")
    with st.container(border=True):
        with st.spinner("Analisando performance financeira..."):
            # scope_df (concluídos) e scope_issues (brutos)
            insights_fin = gerar_insights_financeiros_preditivos(selected_context, global_configs, scope_df, scope_issues)

        if not insights_fin:
            st.info("Nenhuma análise de forecast financeiro gerada.")
        else:
            for insight in insights_fin:
                if insight['tipo'] == 'alerta_grave':
                    st.error(f"🚨 {insight['texto']}")
                elif insight['tipo'] == 'sucesso':
                    st.success(f"✅ {insight['texto']}")
                else: 
                    st.info(f"ℹ️ {insight['texto']}")

    # --- Módulo 3: KPIs de Negócio e Operacionais ---
    st.subheader("Módulo 3: KPIs de Negócio e Operacionais (Visão Atual)")
    with st.container(border=True):
        st.markdown("**Perfil**")
        p_kpi1, p_kpi2, p_kpi3, p_kpi4 = st.columns(4)
        
        context_label = STRATEGIC_FIELD_NAME if STRATEGIC_FIELD_NAME and selected_context != "— Visão Agregada do Projeto —" else "Contexto"
        context_value = selected_context if selected_context != "— Visão Agregada do Projeto —" else "Agregado"
        p_kpi1.metric(context_label, context_value)
        
        p_kpi2.metric("Responsável", profile_data.get('responsavel', 'N/A'))
        start_date_display = pd.to_datetime(profile_data.get('start_date'), errors='coerce').strftime('%d/%m/%Y') if profile_data.get('start_date') else 'N/A'
        end_date_display = pd.to_datetime(profile_data.get('end_date'), errors='coerce').strftime('%d/%m/%Y') if profile_data.get('end_date') else 'N/A'
        p_kpi3.metric("Data de Início", start_date_display)
        p_kpi4.metric("Data de Fim Prevista", end_date_display)

        st.markdown("**Dimensão Financeira (KPIs de Negócio Manuais)**")
        f_kpi1, f_kpi2, f_kpi3 = st.columns(3)
        mrr = pd.to_numeric(kpi_data.get('mrr', 0.0), errors='coerce') or 0.0
        nao_recorrente = pd.to_numeric(kpi_data.get('receita_nao_recorrente', 0.0), errors='coerce') or 0.0
        total_despesas = pd.to_numeric(kpi_data.get('total_despesas', 0.0), errors='coerce') or 0.0
        
        receita_total = mrr + nao_recorrente
        resultado_geral = receita_total - total_despesas
        margem_contribuicao = (resultado_geral / receita_total * 100) if receita_total > 0 else 0.0
        target_margin = global_configs.get('target_contribution_margin', 25.0)

        margin_color_class = "metric-value-red"
        if margem_contribuicao >= target_margin:
            margin_color_class = "metric-value-green"
        elif margem_contribuicao >= 0:
            margin_color_class = "metric-value-amber"

        with f_kpi1: display_custom_metric("Receita Recorrente (MRR)", f"R$ {mrr:,.2f}", "metric-value-blue")
        with f_kpi2: display_custom_metric("Receitas Não Recorrentes", f"R$ {nao_recorrente:,.2f}", "metric-value-blue")
        with f_kpi3: display_custom_metric("Total de Despesas", f"R$ {total_despesas:,.2f}", "metric-value-red")
        
        f_kpi4, f_kpi5 = st.columns(2)
        with f_kpi4:
            display_custom_metric("Resultado (Receita - Despesa)", f"R$ {resultado_geral:,.2f}", "metric-value-green" if resultado_geral >= 0 else "metric-value-red")
        with f_kpi5:
            display_custom_metric("Margem de Contribuição", f"{margem_contribuicao:.1f}%", margin_color_class)
        
        st.markdown("**Dimensão Operacional (Métricas Automáticas)**")
        o_kpi1, o_kpi2, o_kpi3, o_kpi4 = st.columns(4)
        o_kpi1.metric("% Concluído", f"{auto_metrics.get('completion_pct', 0):.0f}%")
        o_kpi2.metric("Entregas no Mês", auto_metrics.get('deliveries_month', 0))
        o_kpi3.metric("Adesão ao Cronograma", f"{auto_metrics.get('schedule_adherence', 0):.1f}%")
        o_kpi4.metric("Desvio Médio de Prazo", f"{auto_metrics.get('avg_deadline_diff', 0):+.1f}d")

        st.markdown("**Dimensão de Relacionamento com o Cliente**")
        r_kpi1, r_kpi2 = st.columns(2)
        nps_value = kpi_data.get('nps', 'N/A')
        try:
             nps_display = int(nps_value) if nps_value != 'N/A' else 'N/A'
        except (ValueError, TypeError):
             nps_display = 'N/A' 
        r_kpi1.metric("NPS (Net Promoter Score)", nps_display)
        r_kpi2.metric("Status RAG (IA)", rag_display, help=rag_help) # Usa as variáveis de display