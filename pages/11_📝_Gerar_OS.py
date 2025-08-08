# pages/10_📝_Gerar_OS.py

import streamlit as st
import pandas as pd
from datetime import datetime
from security import get_global_configs
from utils import create_os_pdf, send_email_with_attachment
from pathlib import Path

st.set_page_config(page_title="Gerar Ordem de Serviço", page_icon="📝", layout="wide")

st.header("📝 Gerador de Ordem de Serviço (OS)", divider='rainbow')

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

# --- Bloco de Autenticação ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

# --- Carrega os valores padrão das configurações globais ---
global_configs = st.session_state.get('global_configs', get_global_configs())
os_defaults = global_configs.get('os_defaults', {})

# --- Formulário Principal para Criação da OS ---
with st.form("os_form"):
    st.subheader("1. Detalhes do Solicitante e Contrato")
    col1, col2 = st.columns(2)
    area_demandante = col1.text_input("Área Demandante*")
    demandante = col2.text_input("Nome do Demandante*")
    lider_projeto_apex = col1.text_input("Líder do Projeto na ApexBrasil*")
    numero_contrato = col2.text_input("Número do Contrato*", value=os_defaults.get('fornecedor', ''))

    st.divider()
    st.subheader("2. Prazos e Valores")
    col1, col2 = st.columns(2)
    previsao_inicio = col1.date_input("Previsão de Início da OS*")
    previsao_termino = col2.date_input("Previsão de Término da OS*")
    valor_estimado = st.number_input("Valor Estimado da OS (R$)*", min_value=0.0, format="%.2f")

    st.divider()
    st.subheader("3. Pessoas e Fornecedor")
    col1, col2 = st.columns(2)
    gestor_contrato = col1.text_input("Gestor do Contrato", value=os_defaults.get('gestor_contrato', ''))
    lider_fornecedor = col2.text_input("Líder do Projeto (Fornecedor)", value=os_defaults.get('lider_fornecedor', ''))
    
    st.divider()
    st.subheader("4. Detalhes do Escopo")
    justificativa = st.text_area("Justificativa*")
    objetivo = st.text_area("Objetivo Principal*")
    
    st.markdown("**Entregáveis Principais***")
    entregaveis = st.data_editor([{"Item": ""}], num_rows="dynamic", use_container_width=True, key="entregaveis_editor", column_config={"Item": st.column_config.TextColumn(required=True)})
    
    st.markdown("**Premissas Gerais**")
    premissas = st.data_editor([{"Item": ""}], num_rows="dynamic", use_container_width=True, key="premissas_editor", column_config={"Item": st.column_config.TextColumn(required=True)})

    st.markdown("**Cláusulas Adicionais**")
    clausulas = st.data_editor([{"Item": ""}], num_rows="dynamic", use_container_width=True, key="clausulas_editor", column_config={"Item": st.column_config.TextColumn(required=True)})

    submitted = st.form_submit_button("Gerar Minuta da OS", use_container_width=True, type="primary")

# --- Lógica de Processamento e Armazenamento na Sessão ---
if submitted:
    entregaveis_validos = [ent for ent in entregaveis if ent.get("Item", "").strip()]
    campos_obrigatorios = [area_demandante, demandante, lider_projeto_apex, numero_contrato, valor_estimado, justificativa, objetivo]

    if not all(campos_obrigatorios) or not entregaveis_validos:
        st.error("Por favor, preencha todos os campos marcados com *.")
        if 'generated_os_data' in st.session_state: del st.session_state['generated_os_data']
    else:
        with st.spinner("A gerar a minuta..."):
            premissas_validas = [p for p in premissas if p.get("Item", "").strip()]
            clausulas_validas = [c for c in clausulas if c.get("Item", "").strip()]

            st.session_state.generated_os_data = {
                'area_demandante': area_demandante, 'demandante': demandante,
                'lider_projeto_apex': lider_projeto_apex, 'numero_contrato': numero_contrato,
                'valor_estimado': valor_estimado, 'previsao_inicio': previsao_inicio,
                'previsao_termino': previsao_termino, 'gestor_contrato': gestor_contrato,
                'lider_fornecedor': lider_fornecedor, 'justificativa': justificativa,
                'objetivo': objetivo, 'entregaveis': entregaveis_validos,
                'premissas': premissas_validas, 'clausulas': clausulas_validas,
                'fornecedor': os_defaults.get('fornecedor', 'N/A')
            }
            st.session_state.generated_pdf_bytes = create_os_pdf(st.session_state.generated_os_data)
            st.success("Minuta gerada com sucesso!")

# --- Lógica de Exibição (lê sempre da sessão) ---
if 'generated_os_data' in st.session_state:
    os_data = st.session_state.generated_os_data
    pdf_bytes = st.session_state.generated_pdf_bytes
    
    st.divider()
    st.subheader("✅ Pré-visualização e Ações")
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="⬇️ Descarregar Minuta em PDF",
            data=pdf_bytes,
            file_name=f"OS_{os_data.get('area_demandante', '').replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    with col2:
        # --- CORREÇÃO AQUI ---
        with st.popover("📧 Enviar por E-mail", use_container_width=True):
            with st.form("email_form"):
                recipient_email = st.text_input("Email do Destinatário")
                if st.form_submit_button("Enviar", type="primary"):
                    if recipient_email:
                        with st.spinner("A enviar..."):
                            subject = f"Minuta da Ordem de Serviço: {os_data.get('area_demandante', '')}"
                            body = f"Segue em anexo a minuta da Ordem de Serviço para o seu conhecimento."
                            success, message = send_email_with_attachment(
                                to_address=recipient_email, subject=subject, body=body,
                                attachment_bytes=pdf_bytes, attachment_filename=f"OS_{os_data.get('area_demandante', '').replace(' ', '_')}.pdf"
                            )
                            if success: st.success(message)
                            else: st.error(message)
                    else:
                        st.warning("Por favor, insira um e-mail.")

    with st.container(border=True):
        st.markdown(f"**OS para:** {os_data['area_demandante']} (A/C {os_data['demandante']})")
        st.markdown(f"**Número do Contrato:** {os_data['numero_contrato']}")
        st.markdown(f"**Gestor do Contrato:** {os_data['gestor_contrato']}")
        st.markdown(f"**Líder do Projeto (Fornecedor):** {os_data['lider_fornecedor']}")
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Valor Estimado", f"R$ {os_data['valor_estimado']:,.2f}")
        kpi2.metric("Início Previsto", os_data['previsao_inicio'].strftime('%d/%m/%Y'))
        kpi3.metric("Término Previsto", os_data['previsao_termino'].strftime('%d/%m/%Y'))
        
        st.markdown("**Justificativa:**"); st.markdown(os_data['justificativa'])
        st.markdown("**Objetivo:**"); st.markdown(os_data['objetivo'])
        
        st.markdown("**Entregáveis:**")
        for ent in os_data['entregaveis']: st.markdown(f"- {ent['Item']}")
        
        if os_data['premissas']:
            st.markdown("**Premissas:**")
            for p in os_data['premissas']: st.markdown(f"- {p['Item']}")
        
        if os_data['clausulas']:
            st.markdown("**Cláusulas Adicionais:**")
            for c in os_data['clausulas']: st.markdown(f"- {c['Item']}")