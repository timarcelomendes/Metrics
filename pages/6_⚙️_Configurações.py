# pages/6_⚙️_Configurações.py

import streamlit as st
import pandas as pd
from security import get_global_configs, save_global_configs
from config import DEFAULT_INITIAL_STATES, DEFAULT_DONE_STATES
from utils import load_config, save_config
from pathlib import Path

st.set_page_config(page_title="Configurações Globais", page_icon="⚙️", layout="wide")

st.header("⚙️ Configurações Globais da Aplicação", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder a esta página.")
    st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑")
    st.stop()

st.info("As configurações definidas aqui afetam **todos os utilizadores** e todas as análises.")
configs = get_global_configs()

with st.sidebar:
    # Constrói o caminho para da logo a partir da raiz do projeto
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(
            logo_path, 
            size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 
    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Login.py")

# --- Abas para Organização ---
tab1, tab2, tab3 = st.tabs(["Gestão de Campos", "Mapeamento de Status", "Parâmetros Scrum"])

with tab1:
    st.subheader("Campos Disponíveis para Análise")
    col1, col2 = st.columns(2, gap="large")

    with col1:
        with st.container(border=True):
            st.markdown("**Campos Padrão do Jira**")
            st.caption("Adicione ou remova os campos padrão que os utilizadores podem ativar.")
            available_fields = configs.get('available_standard_fields', {})
            
            with st.form("new_std_field_form", clear_on_submit=True):
                f_col1, f_col2, f_col3 = st.columns(3)
                new_name = f_col1.text_input("Nome Amigável", placeholder="Ex: Data de Vencimento")
                new_id = f_col2.text_input("ID do Atributo", placeholder="Ex: duedate")
                new_type = f_col3.selectbox("Tipo de Dado", ["Texto", "Data"], key="new_std_type")
                if st.form_submit_button("➕ Adicionar Campo Padrão", use_container_width=True, type="primary"):
                    if new_name and new_id:
                        available_fields[new_name] = {'id': new_id, 'type': new_type}
                        configs['available_standard_fields'] = available_fields
                        save_global_configs(configs); st.success(f"Campo '{new_name}' adicionado!"); st.rerun()
                    else: st.error("Nome e ID são obrigatórios.")

            if available_fields:
                st.markdown("---")
                st.markdown("**Campos Atuais:**")
                df_std = pd.DataFrame([{'Nome': name, 'ID': details.get('id'), 'Tipo': details.get('type')} for name, details in available_fields.items()])
                st.dataframe(df_std, use_container_width=True, hide_index=True)
                
                name_to_delete = st.selectbox("Selecione um campo padrão para remover", options=[""] + list(available_fields.keys()), format_func=lambda x: "Selecione..." if x == "" else x)
                if st.button("Remover Campo Padrão Selecionado", disabled=(not name_to_delete), use_container_width=True):
                    del available_fields[name_to_delete]
                    configs['available_standard_fields'] = available_fields
                    save_global_configs(configs)
                    st.success(f"Campo '{name_to_delete}' removido!")
                    st.rerun()

    with col2:
        with st.container(border=True):
            st.markdown("**Campos Personalizados (Custom Fields)**")
            st.caption("Adicione campos específicos do seu Jira (ex: Story Points).")
            custom_fields = configs.get('custom_fields', [])
            
            with st.form("new_custom_field_form", clear_on_submit=True):
                f_col1, f_col2, f_col3 = st.columns(3)
                new_name = f_col1.text_input("Nome do Campo", placeholder="Ex: Story Points")
                new_id = f_col2.text_input("ID do Campo", placeholder="Ex: customfield_10016")
                new_type = f_col3.selectbox("Tipo de Dado", ["Número", "Texto", "Data"], key="new_custom_type")
                if st.form_submit_button("➕ Adicionar Campo Personalizado", use_container_width=True, type="primary"):
                    if new_name and new_id:
                        if any(f['id'] == new_id for f in custom_fields): st.error(f"O ID '{new_id}' já existe.")
                        else: custom_fields.append({'name': new_name, 'id': new_id, 'type': new_type}); configs['custom_fields'] = custom_fields; save_global_configs(configs); st.success(f"Campo '{new_name}' adicionado!"); st.rerun()
                    else: st.error("Por favor, preencha o Nome e o ID.")
            
            if custom_fields:
                st.markdown("---")
                st.markdown("**Campos Atuais:**")
                df_custom = pd.DataFrame(custom_fields)
                st.dataframe(df_custom, use_container_width=True, hide_index=True)
                
                field_id_to_delete = st.selectbox("Selecione um campo personalizado para remover", options=[""] + [f['id'] for f in custom_fields], format_func=lambda x: next((f['name'] for f in custom_fields if f['id'] == x), "Selecione...") )
                if st.button("Remover Campo Personalizado Selecionado", disabled=(not field_id_to_delete), use_container_width=True):
                    custom_fields = [f for f in custom_fields if f['id'] != field_id_to_delete]
                    configs['custom_fields'] = custom_fields
                    save_global_configs(configs)
                    st.success("Campo removido!"); st.rerun()
                    
with tab2:
    with st.container(border=True):
        st.subheader("Mapeamento de Status do Workflow")
        st.caption("Defina os nomes dos status que correspondem a estados iniciais (backlog) e finais (concluído).")
        status_mapping = configs.get('status_mapping', {})
        
        col1, col2 = st.columns(2)
        initial_states_str = col1.text_area("Status Iniciais (separados por vírgula)", value=", ".join(status_mapping.get('initial', DEFAULT_INITIAL_STATES)), height=150)
        done_states_str = col2.text_area("Status Finais (separados por vírgula)", value=", ".join(status_mapping.get('done', DEFAULT_DONE_STATES)), height=150)
        
        if st.button("Salvar Mapeamento de Status", use_container_width=True, type="primary"):
            configs['status_mapping'] = {'initial': [s.strip().lower() for s in initial_states_str.split(',') if s.strip()], 'done': [s.strip().lower() for s in done_states_str.split(',') if s.strip()]}
            save_global_configs(configs)
            st.success("Mapeamento de status guardado!")
            st.rerun()

with tab3:
    st.subheader("Parâmetros de Análise Scrum")
    with st.container(border=True):
        st.markdown("**Taxa de Sucesso do Objetivo da Sprint**")
        st.caption("Defina o percentual mínimo de itens concluídos para que uma sprint seja considerada um 'sucesso'.")
        
        threshold = st.slider(
            "Percentual Mínimo (%)", 
            min_value=50, 
            max_value=100, 
            value=configs.get('sprint_goal_threshold', 90),
            step=5
        )
        
        if st.button("Salvar Parâmetro de Sucesso", use_container_width=True):
            configs['sprint_goal_threshold'] = threshold
            save_global_configs(configs)
            st.session_state['global_configs']['sprint_goal_threshold'] = threshold
            st.success("Parâmetro guardado com sucesso!")