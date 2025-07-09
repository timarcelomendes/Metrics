import streamlit as st
import os
from security import get_global_configs, save_global_configs
from config import AVAILABLE_STANDARD_FIELDS, DEFAULT_INITIAL_STATES, DEFAULT_DONE_STATES
from utils import load_config, save_config

st.set_page_config(page_title="Configurações Globais", page_icon="⚙️", layout="wide")
st.header("⚙️ Configurações Globais da Aplicação", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder."); st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑"); st.stop()

st.info("As configurações definidas aqui afetam **todos os utilizadores** e todas as análises.")
configs = get_global_configs()

tab1, tab2 = st.tabs(["Gestão de Campos do Jira", "Mapeamento de Status do Workflow"])

with tab1:
    st.subheader("Campos Disponíveis para Análise")
    
    col1, col2 = st.columns(2, gap="large")
    
    with col1:
        with st.container(border=True):
            st.markdown("**Campos Padrão do Jira**")
            st.caption("Adicione ou remova os campos padrão disponíveis para os utilizadores.")
            available_fields = configs.get('available_standard_fields', {})
            
            with st.form("new_std_field_form", clear_on_submit=True):
                f_col1, f_col2, f_col3 = st.columns(3)
                new_name = f_col1.text_input("Nome Amigável")
                new_id = f_col2.text_input("ID do Atributo")
                new_type = f_col3.selectbox("Tipo de Dado", ["Texto", "Data"], key="new_std_type")
                if st.form_submit_button("➕ Adicionar Campo Padrão", use_container_width=True):
                    if new_name and new_id:
                        available_fields[new_name] = {'id': new_id, 'type': new_type}
                        configs['available_standard_fields'] = available_fields
                        save_global_configs(configs); st.success(f"Campo '{new_name}' adicionado!"); st.rerun()
                    else: st.error("Nome e ID são obrigatórios.")

            if available_fields:
                st.markdown("---")
                for name, details in list(available_fields.items()):
                    disp_col1, disp_col2, disp_col3, disp_col4 = st.columns([2, 2, 1, 1])
                    disp_col1.text(name)
                    disp_col2.text(details.get('id', 'N/A'))
                    disp_col3.text(details.get('type', 'N/A'))
                    if disp_col4.button("Remover", key=f"del_std_{details.get('id')}", type="secondary", use_container_width=True):
                        del available_fields[name]; configs['available_standard_fields'] = available_fields
                        save_global_configs(configs); st.success(f"Campo '{name}' removido!"); st.rerun()

    with col2:
        with st.container(border=True):
            st.markdown("**Campos Personalizados (Custom Fields)**")
            st.caption("Adicione campos específicos do seu Jira (ex: Story Points).")
            custom_fields = configs.get('custom_fields', [])
            
            with st.form("new_custom_field_form", clear_on_submit=True):
                f_col1, f_col2, f_col3 = st.columns(3)
                new_name = f_col1.text_input("Nome do Campo")
                new_id = f_col2.text_input("ID do Campo (ex: customfield_10016)")
                new_type = f_col3.selectbox("Tipo de Dado", ["Número", "Texto", "Data"], key="new_custom_type")
                if st.form_submit_button("➕ Adicionar Campo Personalizado", use_container_width=True):
                    if new_name and new_id:
                        if any(f['id'] == new_id for f in custom_fields): st.error(f"O ID '{new_id}' já existe.")
                        else: custom_fields.append({'name': new_name, 'id': new_id, 'type': new_type}); configs['custom_fields'] = custom_fields; save_global_configs(configs); st.success(f"Campo '{new_name}' adicionado!"); st.rerun()
                    else: st.error("Por favor, preencha o Nome e o ID.")
            
            if custom_fields:
                st.markdown("---")
                st.markdown("**Campos Atuais:**")
                for i, field in enumerate(custom_fields):
                    disp_col1, disp_col2, disp_col3, disp_col4 = st.columns([2, 2, 1, 1])
                    disp_col1.text(field['name']); disp_col2.text(field['id']); disp_col3.text(field['type'])
                    if disp_col4.button("Remover", key=f"del_custom_{field['id']}", type="secondary", use_container_width=True):
                        custom_fields.pop(i); configs['custom_fields'] = custom_fields; save_global_configs(configs); st.rerun()

with tab2:
    st.subheader("Mapeamento de Status do Workflow")
    status_mapping = configs.get('status_mapping', {})
    initial_states_str = st.text_area("Status Iniciais (separados por vírgula)", value=", ".join(status_mapping.get('initial', DEFAULT_INITIAL_STATES)))
    done_states_str = st.text_area("Status Finais (separados por vírgula)", value=", ".join(status_mapping.get('done', DEFAULT_DONE_STATES)))
    if st.button("Salvar Mapeamento de Status", use_container_width=True):
        configs['status_mapping'] = {'initial': [s.strip().lower() for s in initial_states_str.split(',') if s.strip()], 'done': [s.strip().lower() for s in done_states_str.split(',') if s.strip()]}
        save_global_configs(configs); st.success("Mapeamento guardado!"); st.rerun()