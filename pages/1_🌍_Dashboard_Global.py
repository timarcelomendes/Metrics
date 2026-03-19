import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz
from utils import load_and_process_project_data # Import não utilizado, mas mantido
from jira_connector import get_project_issues # Import não utilizado, mas mantido

# --- Funções de Cache (Definidas Globalmente) ---

@st.cache_data(ttl=3600, show_spinner="Buscando lista de projetos...")
def get_all_available_projects(_jira):
    """Busca e cacheia a lista de todos os projetos visíveis."""
    try:
        projects = _jira.projects()
        project_list = sorted([proj.key for proj in projects])
        return project_list
    except Exception as e:
        # Lança o erro para ser apanhado pela interface
        raise e

@st.cache_data(ttl=3600, show_spinner="Buscando dados globais de issues...")
def load_global_data(_jira_conn, project_keys_tuple, done_statuses_tuple):
    """
    Busca todas as issues para uma lista de projetos e aplica cálculos básicos.
    """
    
    def _parse_issue_simple(issue):
        """Parser local simples para esta página."""
        fields = issue.fields
        done_status_names = [s.lower() for s in done_statuses_tuple]

        completion_date = None
        if hasattr(fields, 'status') and fields.status.name.lower() in done_status_names:
            if hasattr(fields, 'resolutiondate') and fields.resolutiondate:
                completion_date = pd.to_datetime(fields.resolutiondate, utc=True)
            else:
                completion_date = pd.to_datetime(fields.updated, utc=True)
        elif hasattr(fields, 'resolutiondate') and fields.resolutiondate:
             completion_date = pd.to_datetime(fields.resolutiondate, utc=True)

        return {
            'ID': issue.key,
            'Project': fields.project.key if hasattr(fields, 'project') else None,
            'Issue Type': fields.issuetype.name if hasattr(fields, 'issuetype') else None,
            'Status': fields.status.name if hasattr(fields, 'status') else None,
            'Created': pd.to_datetime(fields.created, utc=True),
            'DataConclusao': completion_date,
            'Description': fields.description if hasattr(fields, 'description') else None
        }

    if not project_keys_tuple:
        return pd.DataFrame()

    project_keys = list(project_keys_tuple)
    
    sanitized_project_keys = [str(key).replace('"', '\\"') for key in project_keys]
    quoted_project_keys = ", ".join(f'"{key}"' for key in sanitized_project_keys)
    jql_query = f'project IN ({quoted_project_keys}) ORDER BY created DESC'
    
    # --- CORREÇÃO: O 'try/except' foi removido daqui ---
    # A exceção será agora tratada na função 'run_dashboard_global'
    
    fields_necessarios = ['summary', 'status', 'issuetype', 'created', 
                        'updated', 'resolutiondate', 'project', 'description']
    
    issues_list = _jira_conn.search_issues(
        jql_query, 
        maxResults=False,
        fields=fields_necessarios
    )
    
    if not issues_list:
        return pd.DataFrame()

    parsed_data = [_parse_issue_simple(issue) for issue in issues_list]
    df = pd.DataFrame(parsed_data)

    if 'Created' not in df.columns:
        df['Created'] = pd.NaT
    if 'Status' not in df.columns:
        df['Status'] = 'Desconhecido'

    return df


def plot_counts_chart(df, column_name, title):
    """Renderiza um gráfico de barras de contagem."""
    if df.empty or column_name not in df or df[column_name].isnull().all():
        st.caption(f"Nenhum dado para '{title}'.")
        return
    
    counts_series = df[column_name].dropna().value_counts()
    if counts_series.empty:
        st.caption(f"Nenhum dado para '{title}'.")
        return
        
    counts = counts_series.reset_index()
    counts.columns = [column_name, 'Contagem']
    
    fig = px.bar(
        counts, 
        x=column_name, 
        y='Contagem', 
        title=title,
        text='Contagem',
        color=column_name
    )
    fig.update_layout(xaxis_title=None)
    st.plotly_chart(fig, use_container_width=True)

# --- NOVA FUNÇÃO AUXILIAR ---
def _safe_pct_balanco(criados, encerrados):
    """Calcula o balanço percentual de forma segura, evitando divisão por zero."""
    balanco = criados - encerrados
    
    if criados > 0:
        return (balanco / criados) * 100
    
    if criados == 0 and balanco < 0:
        return -100.0 
    
    return 0.0

# --- Função Principal da Página ---
def run_dashboard_global():
    """
    Função principal para encapsular a lógica da página.
    """
    
    # --- Título e Page Config ---
    st.set_page_config(
        page_title="Dashboard Global",
        page_icon="🌍",
        layout="wide"
    )
    st.title("🌍 Dashboard Global")
    st.markdown("Análise de *todos* os projetos selecionados, focada em itens criados e encerrados recentemente.")

    # --- Lógica de Autenticação (Requer Imports) ---
    try:
        from security import check_session_timeout, find_user
        from config import SESSION_TIMEOUT_MINUTES
    except ImportError as e:
        st.error(f"Erro crítico de importação: {e}. Verifique se os arquivos 'security.py' e 'config.py' estão corretos.")
        st.stop()
        
    if 'email' not in st.session_state:
        st.warning("⚠️ Por favor, faça login para acessar.")
        st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑") 
        st.stop()

    if check_session_timeout():
        st.warning(f"Sua sessão expirou por inatividade de {SESSION_TIMEOUT_MINUTES} minutos. Por favor, faça login novamente.")
        st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
        st.stop()

    # --- Obter Conexão (Requer Imports) ---
    try:
        from security import get_project_config
        
        if 'jira_client' not in st.session_state:
            st.error("Conexão Jira não encontrada na sessão. Por favor, autentique-se novamente.")
            st.page_link("0_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
            st.stop()
            
        jira = st.session_state.jira_client

        done_statuses = ['Done', 'Concluído', 'Encerrado', 'Resolvido'] # Fallback
        
        project_key_to_check = st.session_state.get('project_key')
        
        if not project_key_to_check and 'projects' in st.session_state and st.session_state.projects:
             first_project_name = list(st.session_state.projects.keys())[0]
             project_key_to_check = st.session_state.projects[first_project_name]

        if project_key_to_check:
             project_config = get_project_config(project_key_to_check)
             
             if project_config:
                if project_config.get('done_status_names'):
                    done_statuses = project_config.get('done_status_names')
                elif project_config.get('status_mapping', {}).get('done'):
                    done_names = [s['name'] for s in project_config['status_mapping']['done'] if 'name' in s]
                    if done_names:
                        done_statuses = done_names
                        
    except Exception as e: 
        # --- INÍCIO DO TRATAMENTO DE ERRO (Configurações) ---
        st.warning("ℹ️ Isto pode ser um erro de rede ou falha na ligação à base de dados de configurações.")
        
        if st.button("Tentar Novamente 🔂", use_container_width=True, type="primary"):
            get_project_config.clear() 
            st.rerun() 
            
        st.stop()

    # --- Filtros na Sidebar ---
    st.sidebar.header("Filtros do Dashboard Global")

    period_options = {
        "Último dia": 1,
        "Últimos 7 dias": 7,
        "Últimos 14 dias": 14,
        "Últimos 21 dias": 21,
        "Últimos 28 dias": 28,
        "Último mês (30 dias)": 30,
    }
    selected_period_name = st.sidebar.selectbox(
        "Selecione o Período de Análise:",
        list(period_options.keys()),
        index=1 # Default para "Últimos 7 dias"
    )
    days_to_subtract = period_options[selected_period_name]

    try:
        all_projects_list = get_all_available_projects(jira)
        if not all_projects_list:
            st.sidebar.warning("Nenhum projeto encontrado para esta conexão.")
            st.warning("Nenhum projeto encontrado.")
            st.stop()
            
    except Exception as e:
        st.sidebar.warning("Isso pode ser um timeout temporário ou erro de rede.")
        
        if st.sidebar.button("Tentar Carregar Projetos", use_container_width=True, type="primary"):
            get_all_available_projects.clear() 
            st.rerun() 
            
        st.warning("Não foi possível carregar a lista de projetos. Tente novamente na barra lateral.")
        st.stop() 
    # --- FIM DO TRATAMENTO DE ERRO ---

    selected_projects = st.sidebar.multiselect(
        "Selecione os Projetos:",
        options=all_projects_list,
        default=all_projects_list 
    )

    if not selected_projects:
        st.warning("Por favor, selecione pelo menos um projeto na barra lateral para começar.")
        st.stop()

    # --- Lógica de Datas e Filtragem ---
    utc_tz = pytz.UTC
    date_now = datetime.now(utc_tz)
    
    date_start_atual = date_now - timedelta(days=days_to_subtract)
    date_end_anterior = date_start_atual
    date_start_anterior = date_end_anterior - timedelta(days=days_to_subtract)
    
    # --- INÍCIO DO TRATAMENTO DE ERRO (Dados das Issues) ---
    try:
        df_global = load_global_data(jira, tuple(selected_projects), tuple(done_statuses))
        
    except Exception as e:
        # Este é o erro que você está a ver (Read timed out)
        st.warning("Oops! Parece que a conexão com o servidor Jira falhou ou demorou demais (timeout).")
        st.info("Isto pode ser um problema temporário de rede ou do servidor Jira. Por favor, tente novamente.")
        
        # Adiciona o botão "Tentar Novamente"
        if st.button("Recarregar Dados", use_container_width=True, type="primary"):
            load_global_data.clear() 
            st.rerun() 
        st.stop() 

    if df_global.empty:
        st.info("Nenhum dado encontrado para os projetos e filtros selecionados.")
        st.stop()

    # (O restante do seu código da função continua aqui...)
    
    # Filtragem para o Período ATUAL
    df_criados_atual = df_global[df_global['Created'] >= date_start_atual]
    df_encerrados_atual = df_global[
        (df_global['DataConclusao'].notna()) &
        (df_global['DataConclusao'] >= date_start_atual)
    ]
    
    # Filtragem para o Período ANTERIOR
    df_criados_anterior = df_global[
        (df_global['Created'] >= date_start_anterior) &
        (df_global['Created'] < date_end_anterior)
    ]
    df_encerrados_anterior = df_global[
        (df_global['DataConclusao'].notna()) &
        (df_global['DataConclusao'] >= date_start_anterior) &
        (df_global['DataConclusao'] < date_end_anterior)
    ]

    # --- Exibição de KPIs (Métricas Principais) ---
    st.subheader(f"Métricas para: {selected_period_name}")
    
    col1, col2, col3, col4 = st.columns(4)

    # Cálculos Atuais
    total_criados_atual = len(df_criados_atual)
    total_encerrados_atual = len(df_encerrados_atual)
    balanco_atual = total_criados_atual - total_encerrados_atual
    balanco_pct_atual = _safe_pct_balanco(total_criados_atual, total_encerrados_atual)

    # Cálculos Anteriores
    total_criados_anterior = len(df_criados_anterior)
    total_encerrados_anterior = len(df_encerrados_anterior)
    balanco_pct_anterior = _safe_pct_balanco(total_criados_anterior, total_encerrados_anterior)

    # Cálculo do Delta (Variação)
    delta_balanco_pct = balanco_pct_atual - balanco_pct_anterior

    col1.metric("Itens Criados no Período", f"{total_criados_atual:,.0f}")
    col2.metric("Itens Encerrados no Período", f"{total_encerrados_atual:,.0f}")
    col3.metric(
        "Balanço (Absoluto)", 
        f"{balanco_atual:,.0f}",
        help="Itens Criados vs. Encerrados no período."
    )
    
    col4.metric(
        "Balanço Percentual",
        f"{balanco_pct_atual:.1f}%",
        delta=f"{delta_balanco_pct:.1f}% vs. período anterior",
        delta_color="inverse", 
        help="Variação percentual do backlog em relação aos itens criados. (Criados - Encerrados) / Criados."
    )

    st.divider()

    # --- Abas de Análise Detalhada ---
    tab1, tab2, tab_ia = st.tabs([
        f"📊 Itens Criados ({total_criados_atual})", 
        f"🏁 Itens Encerrados ({total_encerrados_atual})",
        "🤖 Análise IA"
    ])

    # Aba 1: Itens Criados
    with tab1:
        if total_criados_atual == 0:
            st.info("Nenhum item foi criado no período selecionado.")
        else:
            st.header("Análise de Itens Criados")
            col_tipo_criado, col_proj_criado = st.columns(2)
            
            with col_tipo_criado:
                plot_counts_chart(
                    df_criados_atual, 
                    'Issue Type', 
                    'Tipos de Itens Mais Criados'
                )
            
            with col_proj_criado:
                plot_counts_chart(
                    df_criados_atual, 
                    'Project', 
                    'Itens Criados por Projeto'
                )

    # Aba 2: Itens Encerrados
    with tab2:
        if total_encerrados_atual == 0:
            st.info("Nenhum item foi encerrado no período selecionado.")
        else:
            st.header("Análise de Itens Encerrados")
            col_tipo_enc, col_proj_enc = st.columns(2)
            
            with col_tipo_enc:
                plot_counts_chart(
                    df_encerrados_atual, 
                    'Issue Type', 
                    'Tipos de Itens Mais Encerrados'
                )
            
            with col_proj_enc:
                plot_counts_chart(
                    df_encerrados_atual, 
                    'Project', 
                    'Itens Encerrados por Projeto'
                )

    # --- Lógica da Aba de IA ---
    with tab_ia:
        st.header("Análise Qualitativa com IA")
        st.markdown(f"Analisando uma amostra de até 30 itens criados e 30 encerrados no período ({selected_period_name}).")
        
        if st.button("🤖 Gerar Análise de Segregação", key="gerar_analise_ia_global"):
            try:
                from utils import get_ai_global_dashboard_analysis
                
                user_data = find_user(st.session_state['email'])
                provider = user_data.get('ai_provider_preference', 'Google Gemini')
                
                with st.spinner("A IA está a analisar o conteúdo das issues..."):
                    response = get_ai_global_dashboard_analysis(
                        df_criados_atual,
                        df_encerrados_atual,
                        provider
                    )
                    st.markdown(response)
            
            except ImportError:
                st.error("Erro: A função `get_ai_global_dashboard_analysis` não foi encontrada. "
                         "Certifique-se de que a adicionou ao seu arquivo `utils.py`.")
            except Exception as e:
                st.error(f"Ocorreu um erro inesperado ao comunicar com a IA: {e}")

    # Exibição opcional dos dados brutos
    with st.expander(f"Ver dados brutos (Total: {len(df_global)} issues)"):
        st.dataframe(df_global, use_container_width=True)

# --- Ponto de Entrada: Chama a função principal ---
if __name__ == "__main__":
    run_dashboard_global()
