# pages/7_👤_Minha_Conta.py

import streamlit as st
import os
from pathlib import Path
from security import find_user 

st.set_page_config(page_title="Minha Conta", page_icon="👤", layout="wide")

st.header("👤 Minha Conta", divider='rainbow')

# --- Bloco de Autenticação ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder a esta página.")
    st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑")
    st.stop()

# --- Conteúdo da Página ---
st.info(f"**Utilizador:** {st.session_state['email']}")

st.divider()

st.subheader("Gestão de Conexões com o Jira")
st.markdown("Para adicionar, remover ou ativar as suas contas do Jira, por favor, aceda à página dedicada de conexões.")

st.page_link(
    "pages/2_🔗_Conexões_Jira.py",
    label="Gerir Minhas Conexões Jira",
    icon="🔗"
)

# Futuramente, podemos adicionar aqui outras funcionalidades, como "Mudar Senha".