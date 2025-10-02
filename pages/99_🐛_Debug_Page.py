# pages/99_🐛_Debug_Page.py

import streamlit as st
import pandas as pd
from security import get_project_config
from jira_connector import load_and_process_project_data

st.set_page_config(page_title="Página de Depuração", page_icon="🐛")

st.title("🐛 Página de Teste e Depuração")
st.warning("Esta página é temporária e serve para isolar e testar o carregamento de dados.")

# Verifica se o login foi feito e se o cliente Jira existe
if 'jira_client' not in st.session_state or 'projects' not in st.session_state:
    st.error("Por favor, faça o login na página de Autenticação primeiro.")
    st.stop()

st.header("1. Verificação da Configuração do Projeto")

projects = st.session_state.get('projects', {})
project_names = list(projects.keys())

if not project_names:
    st.error("Nenhum projeto encontrado na sessão.")
    st.stop()

# Selector de projeto
selected_project_name = st.selectbox(
    "Selecione o projeto para testar:",
    options=project_names
)
project_key = projects[selected_project_name]

# Botão para carregar e mostrar a configuração
if st.button("Verificar Configuração Salva"):
    with st.spinner("A ler a configuração..."):
        project_config = get_project_config(project_key) or {}
        st.subheader(f"Configuração para o projeto '{selected_project_name}' ({project_key})")
        
        # Extrai e mostra o valor da flag que nos interessa
        calculate_flag = project_config.get('calculate_time_in_status', 'NÃO ENCONTRADA')
        
        st.write(f"A flag 'calculate_time_in_status' está definida como: `{calculate_flag}`")

        if calculate_flag is True:
            st.success("CORRETO: A configuração para calcular o tempo em status está ativa (True).")
        else:
            st.error(f"INCORRETO: A configuração não está ativa. O valor atual é '{calculate_flag}'. Por favor, vá à página de Configurações, ative a opção e salve novamente.")
        
        st.json(project_config) # Mostra a configuração completa

st.divider()

st.header("2. Teste de Execução da Função")
st.info("Este teste irá chamar diretamente a função 'load_and_process_project_data'. Verifique o terminal onde o Streamlit está a correr para ver as mensagens de 'print'.")

if st.button("Executar Teste de Carregamento de Dados", type="primary"):
    st.session_state.debug_df_result = None # Limpa resultados antigos
    with st.spinner("A executar 'load_and_process_project_data'... Por favor, aguarde."):
        try:
            # Chamada direta à função
            df = load_and_process_project_data(
                st.session_state.jira_client,
                project_key
            )
            st.session_state.debug_df_result = df
            st.success("A função foi executada com sucesso!")
        except Exception as e:
            st.error(f"A função falhou com um erro: {e}")
            st.exception(e)

# Mostra o resultado do teste após a execução
if 'debug_df_result' in st.session_state and st.session_state.debug_df_result is not None:
    st.subheader("Resultado da Execução")
    df = st.session_state.debug_df_result
    
    st.write("Abaixo estão as primeiras 5 linhas do DataFrame retornado:")
    st.dataframe(df.head())
    
    st.write("Verificação das colunas 'Tempo em Status':")
    tempo_em_status_cols = [col for col in df.columns if col.startswith('Tempo em:')]
    
    if tempo_em_status_cols:
        st.success(f"SUCESSO FINAL: {len(tempo_em_status_cols)} colunas de 'Tempo em Status' foram encontradas no DataFrame!")
        st.write(tempo_em_status_cols)
    else:
        st.error("FALHA FINAL: Nenhuma coluna 'Tempo em Status' foi encontrada.")