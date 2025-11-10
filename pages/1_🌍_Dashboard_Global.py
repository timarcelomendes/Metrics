import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import pytz

# --- Funções de Cache (Definidas Globalmente) ---

@st.cache_data(ttl=3600, show_spinner="Buscando lista de projetos...")
def get_all_available_projects(_jira): # <--- CORREÇÃO 1: Adicionado o underscore
    """Busca e cacheia a lista de todos os projetos visíveis."""
    try:
        # Usa a variável com underscore
        projects = _jira.projects() # <--- CORREÇÃO 1
        project_list = sorted([proj.key for proj in projects])
        return project_list
    except Exception as e:
        st.error(f"Não foi possível buscar a lista de projetos: {e}")
        return []

@st.cache_data(ttl=3600, show_spinner="Buscando dados globais de issues...")
def load_global_data(_jira_conn, project_keys_tuple, done_statuses_tuple): # <--- CORREÇÃO 2: Adicionado o underscore
    """
    Busca todas as issues para uma lista de projetos e aplica cálculos básicos.
    """
    
    # (Já que 'parse_jira_issue' não existe no seu jira_connector.py)
    def _parse_issue_simple(issue):
        """Parser local simples para esta página."""
        
        fields = issue.fields
        
        # Obter a lista de nomes de status "Done"
        done_status_names = [s.lower() for s in done_statuses_tuple]

        # Lógica de Data de Conclusão (simplificada)
        completion_date = None
        if hasattr(fields, 'status') and fields.status.name.lower() in done_status_names:
            # Tenta 'resolutiondate' primeiro
            if hasattr(fields, 'resolutiondate') and fields.resolutiondate:
                completion_date = pd.to_datetime(fields.resolutiondate, utc=True)
            else:
                # Fallback para 'updated' se já estiver em status "Done"
                completion_date = pd.to_datetime(fields.updated, utc=True)
        elif hasattr(fields, 'resolutiondate') and fields.resolutiondate:
            # Fallback se o status foi revertido mas a data de resolução existe
             completion_date = pd.to_datetime(fields.resolutiondate, utc=True)

        return {
            'ID': issue.key,
            'Project': fields.project.key if hasattr(fields, 'project') else None,
            'Issue Type': fields.issuetype.name if hasattr(fields, 'issuetype') else None,
            'Status': fields.status.name if hasattr(fields, 'status') else None,
            'Created': pd.to_datetime(fields.created, utc=True),
            'DataConclusao': completion_date,
            # --- NOVO CAMPO ADICIONADO ---
            'Description': fields.description if hasattr(fields, 'description') else None
        }

    if not project_keys_tuple:
        return pd.DataFrame()

    project_keys = list(project_keys_tuple)
    done_statuses = list(done_statuses_tuple)
    
    jql_query = f'project IN ({", ".join(f'"{key}"' for key in project_keys)}) ORDER BY created DESC'
    
    try:
        # --- NOVO CAMPO ADICIONADO ---
        fields_necessarios = ['summary', 'status', 'issuetype', 'created', 
                            'updated', 'resolutiondate', 'project', 'description']
        
        # Usa a variável com underscore
        issues_list = _jira_conn.search_issues( # <--- CORREÇÃO 2
            jql_query, 
            maxResults=False,  # Busca todos
            fields=fields_necessarios
        )
        
        if not issues_list:
            return pd.DataFrame()

        # Processamento usando a função de parse local
        parsed_data = [_parse_issue_simple(issue) for issue in issues_list]
        df = pd.DataFrame(parsed_data)

        if 'Created' not in df.columns:
            df['Created'] = pd.NaT
        if 'Status' not in df.columns:
            df['Status'] = 'Desconhecido'

        return df
    except Exception as e:
        st.error(f"Erro ao buscar dados do Jira: {e}")
        return pd.DataFrame()

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
        # Cálculo padrão: (Criados - Encerrados) / Criados
        return (balanco / criados) * 100
    
    if criados == 0 and balanco < 0:
        # Nenhum item criado, mas itens foram encerrados (ótimo cenário)
        # Retorna um valor simbólico de "redução"
        return -100.0 
    
    # Nenhum item criado e nenhum encerrado, ou
    # Itens criados = 0 e balanço > 0 (impossível)
    return 0.0
# --- FIM DA NOVA FUNÇÃO ---


# --- Função Principal da Página (ATUALIZADA) ---
def run_dashboard_global():
    """
    Função principal para encapsular a lógica da página.
    """
    
    st.set_page_config(
        page_title="Dashboard Global",
        page_icon="🌍",
        layout="wide"
    )

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

    # --- Interface da Página ---
    st.title("🌍 Dashboard Global")
    st.markdown("Análise de *todos* os projetos selecionados, focada em itens criados e encerrados recentemente.")

    # --- Obter Conexão (Requer Imports) ---
    try:
        from security import get_project_config
        
        if 'jira_client' not in st.session_state:
            st.error("Conexão Jira não encontrada na sessão. Por favor, autentique-se novamente.")
            st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑")
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
        st.error(f"Falha ao processar as configurações do Jira: {e}")
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

    all_projects_list = get_all_available_projects(jira)
    selected_projects = st.sidebar.multiselect(
        "Selecione os Projetos:",
        options=all_projects_list,
        default=all_projects_list # Default para todos os projetos
    )

    if not selected_projects:
        st.warning("Por favor, selecione pelo menos um projeto na barra lateral para começar.")
        st.stop()

    # --- Lógica de Datas e Filtragem (ATUALIZADA) ---
    utc_tz = pytz.UTC
    date_now = datetime.now(utc_tz)
    
    # Período Atual
    date_start_atual = date_now - timedelta(days=days_to_subtract)
    
    # Período Anterior
    date_end_anterior = date_start_atual
    date_start_anterior = date_end_anterior - timedelta(days=days_to_subtract)
    
    # Carrega TODOS os dados (isto está correto, pois usa o cache)
    df_global = load_global_data(jira, tuple(selected_projects), tuple(done_statuses))

    if df_global.empty:
        st.info("Nenhum dado encontrado para os projetos e filtros selecionados.")
        st.stop()

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

    # --- Exibição de KPIs (Métricas Principais) (ATUALIZADO) ---
    st.subheader(f"Métricas para: {selected_period_name}")
    
    # --- MUDANÇA 1: Adicionada col4 ---
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
    
    # --- Novo Indicador ---
    col4.metric(
        "Balanço Percentual",
        f"{balanco_pct_atual:.1f}%",
        delta=f"{delta_balanco_pct:.1f}% vs. período anterior",
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
                # Importa a função de IA (deve estar em utils.py)
                from utils import get_ai_global_dashboard_analysis
                
                user_data = find_user(st.session_state['email'])
                provider = user_data.get('ai_provider_preference', 'Google Gemini')
                
                with st.spinner("A IA está a analisar o conteúdo das issues..."):
                    response = get_ai_global_dashboard_analysis(
                        df_criados_atual,   # Passa o DF do período atual
                        df_encerrados_atual, # Passa o DF do período atual
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