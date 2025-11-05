# pages/15_❓_Ajuda_e_Sobre.py
import streamlit as st
from pathlib import Path
import re
from utils import get_ai_page_summary_and_faq, save_help_topic, load_help_topics
from datetime import datetime

st.set_page_config(page_title="Ajuda & Sobre", page_icon="❓", layout="wide")

st.header("❓ Ajuda e Sobre a Aplicação", divider='rainbow')
st.markdown("""
Esta secção utiliza Inteligência Artificial para analisar o código de cada página da aplicação e gerar uma documentação e um FAQ contextualizados.
A documentação é guardada após a primeira geração e fica disponível para todos os utilizadores.
""")

# --- Lógica para encontrar as páginas da aplicação ---
def get_app_pages():
    pages = {}
    app_root = Path(__file__).parent.parent

    # Adiciona a página principal
    main_page_path = app_root / "1_🔑_Autenticação.py"
    if main_page_path.exists():
        pages["1_🔑_Autenticação"] = main_page_path

    # Adiciona as páginas da pasta 'pages'
    pages_dir = app_root / "pages"
    if pages_dir.exists():
        for f in sorted(pages_dir.glob("*.py")):
            # Extrai um nome mais limpo do ficheiro
            clean_name = re.sub(r'^\d+_\S*?_', '', f.stem)
            pages[clean_name] = f

    return pages

app_pages = get_app_pages()
page_names = list(app_pages.keys())

# --- Interface do Utilizador ---
selected_page_name = st.selectbox(
    "**Selecione a página para a qual deseja ver ou gerar a documentação:**",
    options=page_names,
    index=0
)

st.markdown("---")

if selected_page_name:
    page_path = app_pages[selected_page_name]
    topic_key = page_path.stem # Usa o nome do ficheiro como chave única

    # Carrega a documentação existente
    all_docs = load_help_topics()
    existing_doc = all_docs.get(topic_key)

    col1, col2 = st.columns([3, 1])

    with col1:
        st.subheader(f"Documentação para: `{selected_page_name}`")
        if existing_doc:
            last_updated = datetime.fromisoformat(existing_doc['last_updated']).strftime('%d/%m/%Y às %H:%M')
            st.caption(f"Última atualização: {last_updated}")

    with col2:
        if st.button("🔄 Gerar ou Atualizar Ajuda com IA", use_container_width=True, type="primary"):
            existing_doc = None # Força a re-geração

    if not existing_doc:
        with st.spinner(f"A Gauge AI está a ler o código da página '{selected_page_name}'..."):
            try:
                # Lê apenas o conteúdo da página selecionada
                page_content = page_path.read_text(encoding='utf-8')

                # Chama a IA e guarda o resultado
                ai_content = get_ai_page_summary_and_faq(selected_page_name, page_content)
                save_help_topic(topic_key, ai_content)
                st.session_state[f'doc_{topic_key}'] = ai_content
                st.rerun()

            except Exception as e:
                st.error(f"Ocorreu um erro inesperado: {e}")

    # Exibe a documentação (seja a recém-gerada ou a já existente)
    doc_to_display = existing_doc['content'] if existing_doc else None

    if doc_to_display:
        st.markdown(doc_to_display, unsafe_allow_html=True)
    else:
        st.info("Clique no botão 'Gerar ou Atualizar Ajuda com IA' para criar a documentação para esta página.")