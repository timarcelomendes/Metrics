# pages/10_📝_Gerar_OS.py

import streamlit as st
import pandas as pd
from datetime import datetime
from security import get_global_configs
from utils import create_os_pdf

st.set_page_config(page_title="Gerar Ordem de Serviço", page_icon="📝", layout="wide")

st.header("📝 Gerador de Ordem de Serviço (OS)", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder a esta página."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()

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
    numero_contrato = col2.text_input("Número do Contrato*", value=os_defaults.get('fornecedor', '')) # Usando o campo 'fornecedor' como padrão

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

# --- Lógica de Exibição e Envio ---
if submitted:
    # Filtra itens vazios das listas dinâmicas
    entregaveis_validos = [ent for ent in entregaveis if ent.get("Item", "").strip()]
    premissas_validas = [p for p in premissas if p.get("Item", "").strip()]
    clausulas_validas = [c for c in clausulas if c.get("Item", "").strip()]

    # Validação completa de todos os campos obrigatórios
    campos_obrigatorios = [
        area_demandante, demandante, lider_projeto_apex, numero_contrato, 
        valor_estimado, justificativa, objetivo
    ]

    if not all(campos_obrigatorios) or not entregaveis_validos:
        st.error("Por favor, preencha todos os campos marcados com *.")
    else:
        st.divider()
        st.subheader("✅ Minuta da Ordem de Serviço Gerada")
        
        os_data = {
            'area_demandante': area_demandante, 'demandante': demandante,
            'numero_contrato': numero_contrato, 'gestor_contrato': gestor_contrato,
            'fornecedor': os_defaults.get('fornecedor', 'N/A'), # Pega o fornecedor dos padrões
            'lider_fornecedor': lider_fornecedor, 'justificativa': justificativa,
            'objetivo': objetivo, 'entregaveis': entregaveis_validos,
            'premissas': premissas_validas, 'clausulas': clausulas_validas,
            'valor_estimado': valor_estimado, 'previsao_inicio': previsao_inicio,
            'previsao_termino': previsao_termino
        }
        
        pdf_bytes = create_os_pdf(os_data)
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.download_button(
                label="⬇️ Descarregar Minuta em PDF",
                data=pdf_bytes,
                file_name=f"OS_{area_demandante.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with col2:
            if st.button("Enviar para Aprovação no Skills Workflow", use_container_width=True):
                with st.spinner("A enviar dados para o sistema de workflow..."):
                    st.success("Ordem de Serviço enviada para o fluxo de aprovação com sucesso! (Simulação)")

        st.divider()
        st.markdown("##### Pré-visualização da Minuta")
        with st.container(border=True):
            st.markdown(f"**OS para:** {area_demandante} (A/C {demandante})")
            st.markdown(f"**Número do Contrato:** {numero_contrato}")
            st.markdown(f"**Gestor do Contrato:** {gestor_contrato}")
            st.markdown(f"**Líder do Projeto (Fornecedor):** {lider_fornecedor}")
            
            kpi1, kpi2, kpi3 = st.columns(3)
            kpi1.metric("Valor Estimado", f"R$ {valor_estimado:,.2f}")
            kpi2.metric("Início Previsto", previsao_inicio.strftime('%d/%m/%Y'))
            kpi3.metric("Término Previsto", previsao_termino.strftime('%d/%m/%Y'))
            
            st.markdown("**Justificativa:**"); st.markdown(justificativa)
            st.markdown("**Objetivo:**"); st.markdown(objetivo)
            st.markdown("**Entregáveis:**")
            for i, ent in enumerate(entregaveis_validos): st.markdown(f"- {ent['Item']}")
            if premissas_validas:
                st.markdown("**Premissas:**")
                for i, p in enumerate(premissas_validas): st.markdown(f"- {p['Item']}")
            if clausulas_validas:
                st.markdown("**Cláusulas Adicionais:**")
                for i, c in enumerate(clausulas_validas): st.markdown(f"- {c['Item']}")