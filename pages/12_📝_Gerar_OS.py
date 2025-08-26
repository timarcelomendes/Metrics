# pages/11_📝_Gerador_de_OS.py

import streamlit as st
import pandas as pd
from datetime import datetime
from utils import get_ai_os_from_context_and_contract, create_os_pdf, send_email_with_attachment, load_and_process_project_data
from security import find_user, get_project_config, save_project_config
from jira_connector import get_projects
from pathlib import Path

st.set_page_config(page_title="Gerador de OS com IA", page_icon="📝", layout="wide")

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/2_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

# --- BARRA LATERAL ---
with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(logo_path, size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics")
    
    if st.session_state.get("email"):
        st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else:
        st.info("⚠️ Usuário não conectado!")

    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else None
    
    selected_project_name = st.selectbox("Selecione um Projeto", options=project_names, index=default_index, placeholder="Escolha um projeto...")
    
    if selected_project_name:
        st.session_state.project_key = projects[selected_project_name]
        st.session_state.project_name = selected_project_name
        is_data_loaded = 'dynamic_df' in st.session_state and st.session_state.dynamic_df is not None
        
        with st.expander("Carregar Dados", expanded=not is_data_loaded):
            if st.button("Carregar / Atualizar Dados", use_container_width=True, type="primary"):
                df_loaded = load_and_process_project_data(st.session_state.jira_client, st.session_state.project_key)
                st.session_state.dynamic_df = df_loaded
                st.rerun()

    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("📝 Gerador de Ordem de Serviço com IA", divider='rainbow')

df = st.session_state.get('dynamic_df')
if df is None or df.empty:
    st.info("⬅️ Na barra lateral, selecione um projeto e clique em 'Carregar / Atualizar Dados' para carregar a lista de clientes.")
    st.stop()

# --- Etapa 1: Contextualização ---
st.subheader("1. Contexto e Documento de Apoio")
user_context = st.text_area(
    "Contexto da OS*", 
    placeholder="Descreva o objetivo principal e o escopo desta Ordem de Serviço...",
    height=200
)
uploaded_file = st.file_uploader("Contrato de Apoio (PDF)", type="pdf")

if st.button("Gerar Rascunho da OS com Gauge AI", use_container_width=True):
    if not user_context or not uploaded_file:
        st.warning("Por favor, preencha o contexto e carregue o ficheiro do contrato.")
    else:
        with st.spinner("Gauge AI está a ler o seu contexto e a analisar o contrato..."):
            pdf_bytes = uploaded_file.getvalue()
            analysis_result = get_ai_os_from_context_and_contract(user_context, pdf_bytes)
            
            if "error" in analysis_result:
                st.error(analysis_result["error"])
            else:
                st.session_state.os_form_data = analysis_result
                st.success("Rascunho gerado com sucesso! Verifique e complete os campos abaixo.")
                if 'generated_os_pdf' in st.session_state:
                    del st.session_state['generated_os_pdf']

st.divider()

# --- Etapa 2: Formulário da Ordem de Serviço ---
st.subheader("2. Revise e Complete a Ordem de Serviço")

form_data = st.session_state.get('os_form_data', {})

with st.form("os_form"):
    if not form_data:
        st.info("Comece por carregar um contrato e gerar o rascunho na secção acima.")
    
    # --- Seção de Cabeçalho ---
    st.markdown("**Dados Gerais**")
    CLIENT_FIELD_NAME = "Cliente"
    client_list = sorted(df[CLIENT_FIELD_NAME].dropna().unique())
    
    c1, c2 = st.columns(2)
    cliente = c1.selectbox("Cliente*", options=client_list)
    setor_demandante = c2.text_input("Setor Demandante", value=form_data.get('setor_demandante', ''))
    
    c1, c2 = st.columns(2)
    responsavel_demandante = c1.text_input("Responsável Demandante*", value=form_data.get('responsavel_demandante', ''))
    email_demandante = c2.text_input("E-mail do Demandante*", value=form_data.get('email_demandante', ''))
    
    lider_projeto_gauge = st.text_input("Líder do Projeto (Gauge)*", value=form_data.get('lider_projeto_gauge', ''))
    
    # --- Seção de Prazos ---
    st.divider()
    st.markdown("**Prazos e Datas**")
    c1, c2, c3 = st.columns(3)
    data_emissao = c1.text_input("Data de Emissão", value=form_data.get('data_emissao', ''))
    previsao_inicio = c2.text_input("Previsão de Início", value=form_data.get('previsao_inicio', ''))
    previsao_conclusao = c3.text_input("Previsão de Conclusão", value=form_data.get('previsao_conclusao', ''))
    
    # --- Seção de Conteúdo ---
    st.divider()
    st.markdown("**Detalhes do Projeto**")
    justificativa_objetivo = st.text_area("Justificativa & Objetivo", value=form_data.get('justificativa_objetivo', ''), height=150)
    escopo_tecnico = st.text_area("Escopo Técnico", value=form_data.get('escopo_tecnico', ''), height=200)
    premissas = st.text_area("Premissas", value=form_data.get('premissas', ''), height=100)
    
    # --- Seção Financeira ---
    st.divider()
    st.markdown("**Financeiro e Alocação**")
    alocacao = st.text_area("Alocação (perfis, nº de dias, etc.)", height=150)
    orcamento = st.text_input("Orçamento", value=form_data.get('orcamento', ''))
    pagamento = st.text_area("Condições de Pagamento", value=form_data.get('pagamento', ''), height=150)
    
    # --- Seção de Assinaturas ---
    st.divider()
    st.markdown("**Assinaturas**")
    c1, c2 = st.columns(2)
    assinante1 = c1.text_input("Assinante 1 (Nome e Cargo)")
    assinante2 = c2.text_input("Assinante 2 (Nome e Cargo)")
    
    if st.form_submit_button("Gerar Documento da OS", use_container_width=True, type="primary"):
        os_data_to_generate = {
            'cliente': cliente, 'setor_demandante': setor_demandante,
            'responsavel_demandante': responsavel_demandante, 'email_demandante': email_demandante,
            'lider_projeto_gauge': lider_projeto_gauge, 'data_emissao': data_emissao,
            'previsao_inicio': previsao_inicio, 'previsao_conclusao': previsao_conclusao,
            'justificativa_objetivo': justificativa_objetivo, 'escopo_tecnico': escopo_tecnico,
            'premissas': premissas, 'alocacao': alocacao, 'orcamento': orcamento,
            'pagamento': pagamento, 'assinante1': assinante1, 'assinante2': assinante2
        }
        
        with st.spinner("A gerar o PDF..."):
            pdf_bytes_generated = create_os_pdf(os_data_to_generate)
            st.session_state.generated_os_pdf = pdf_bytes_generated
            st.session_state.generated_os_data_final = os_data_to_generate
            st.success("Documento PDF gerado com sucesso!")

# --- Etapa 3: Ações com o Documento Gerado ---
if 'generated_os_pdf' in st.session_state:
    st.divider()
    st.subheader("3. Ações")
    
    pdf_bytes = st.session_state.generated_os_pdf
    os_data = st.session_state.generated_os_data_final
    file_name = f"OS_{os_data['cliente'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

    c1, c2 = st.columns(2)
    c1.download_button(
        label="⬇️ Descarregar PDF", data=pdf_bytes, file_name=file_name,
        mime="application/pdf", use_container_width=True
    )

    with c2.popover("📧 Enviar por E-mail", use_container_width=True):
        with st.form("email_form"):
            recipient_email = st.text_input("E-mail do Destinatário", value=os_data.get('email_demandante', ''))
            with st.spinner("A Gauge AI está a enviar o E-mail..."):
                if st.form_submit_button("Enviar"):
                    if recipient_email:
                        subject = f"Ordem de Serviço: {os_data['cliente']}"
                        body = f"Segue em anexo a minuta da Ordem de Serviço para o projeto de {os_data['cliente']}."
                        success, message = send_email_with_attachment(
                            to_address=recipient_email,
                            subject=subject,
                            body=body,
                            attachment_bytes=pdf_bytes,
                            attachment_filename=file_name
                        )
                        if success: st.success(message)
                        else: st.error(message)