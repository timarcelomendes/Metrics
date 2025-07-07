# pages/2_⚙️_Configurações.py
import streamlit as st
import json, os
from config import *

st.set_page_config(page_title="Configurações Globais", page_icon="⚙️", layout="wide")

def load_config(file_path, default_value):
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return default_value
    return default_value

def save_config(data, file_path):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

if 'email' not in st.session_state:
    st.warning("Por favor, faça login para aceder às configurações.")
    st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑")
    st.stop()

with st.sidebar:
    try: st.image("images/gauge-logo.png", width=150)
    except Exception: pass
st.header("⚙️ Configurações Globais da Aplicação")
st.markdown("As configurações definidas aqui afetam todos os utilizadores e todas as análises.")
st.divider()

tab1, tab2, tab3 = st.tabs(["Mapeamento de Status", "Campos Padrão", "Campos Personalizados"])
with tab1:
    st.subheader("Mapeamento de Status do Workflow")
    status_mapping = load_config(STATUS_MAPPING_FILE, {})
    initial_states_str = st.text_area("Status Iniciais", value=", ".join(status_mapping.get('initial', DEFAULT_INITIAL_STATES)))
    done_states_str = st.text_area("Status Finais", value=", ".join(status_mapping.get('done', DEFAULT_DONE_STATES)))
    if st.button("Salvar Mapeamento de Status"):
        new_initial = [s.strip().lower() for s in initial_states_str.split(',') if s.strip()]
        new_done = [s.strip().lower() for s in done_states_str.split(',') if s.strip()]
        save_config({'initial': new_initial, 'done': new_done}, STATUS_MAPPING_FILE); st.success("Mapeamento guardado!")
with tab2:
    st.subheader("Seleção de Campos Padrão do Jira")
    selected_standard_fields = load_config(STANDARD_FIELDS_FILE, [])
    toggles = {}
    for name, field_id in AVAILABLE_STANDARD_FIELDS.items():
        toggles[name] = st.toggle(name, value=(name in selected_standard_fields), key=f"std_{field_id}")
    if st.button("Salvar Seleção de Campos Padrão"):
        new_selection = [name for name, toggled in toggles.items() if toggled]; save_config(new_selection, STANDARD_FIELDS_FILE)
        st.success("Seleção guardada!"); st.rerun()
with tab3:
    st.subheader("Gestão de Campos Personalizados")
    custom_fields = load_config(CUSTOM_FIELDS_FILE, [])
    if custom_fields:
        for i, field in enumerate(custom_fields):
            col1, col2, col3 = st.columns([2, 2, 1]); col1.text_input("Nome", value=field['name'], key=f"name_{i}", disabled=True); col2.text_input("ID", value=field['id'], key=f"id_{i}", disabled=True)
            if col3.button("Remover", key=f"del_{field['id']}"): custom_fields.pop(i); save_config(custom_fields, CUSTOM_FIELDS_FILE); st.rerun()
    with st.form("new_custom_field_form", clear_on_submit=True):
        st.markdown("**Adicionar Novo Campo:**"); col1, col2 = st.columns(2)
        new_name = col1.text_input("Nome do Campo"); new_id = col2.text_input("ID do Campo (ex: customfield_10050)")
        if st.form_submit_button("➕ Adicionar Campo"):
            if new_name and new_id:
                if any(f['id'] == new_id for f in custom_fields): st.error(f"O ID '{new_id}' já existe.")
                else: custom_fields.append({'name': new_name, 'id': new_id}); save_config(custom_fields, CUSTOM_FIELDS_FILE); st.success(f"Campo '{new_name}' adicionado!"); st.rerun()
            else: st.error("Por favor, preencha o Nome e o ID.")