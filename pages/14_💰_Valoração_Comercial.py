# pages/14_💰_Valoração_Comercial.py

import streamlit as st
import pandas as pd
import requests
from io import StringIO
import base64
from datetime import datetime
from security import find_user, get_project_config, save_project_config
from jira_connector import get_projects, get_issue_as_dict
from utils import create_os_pdf, get_ai_os_from_jira_issue
from pathlib import Path
import uuid
import json
import copy
from streamlit_jodit import st_jodit

st.set_page_config(page_title="Valoração Comercial", page_icon="💰", layout="wide")

# --- FUNÇÃO AUXILIAR PARA RENDERIZAR CAMPOS (EVITA REPETIÇÃO) ---
def render_os_field(field, custom_field_data, index):
    """Função auxiliar para renderizar um único campo do formulário da OS."""
    field_name = field.get('field_name')
    field_type = field.get('field_type')
    if not field_name or not field_type: return

    widget_key = f"{field_name}_{index}"
    ai_value = st.session_state.ai_prefilled_data.get(field_name, {})
    
    field_data = {}
    
    if field_type == "Valor Calculado":
        value_to_display = ai_value.get('value', '') if isinstance(ai_value, dict) else ai_value
        field_data['value'] = st.text_input(field_name, value=value_to_display, key=widget_key, disabled=True, help="Este valor é calculado automaticamente.")
    elif field_type == "Texto Curto":
        value_to_display = ai_value.get('value', '') if isinstance(ai_value, dict) else ai_value
        field_data['value'] = st.text_input(field_name, value=value_to_display, key=widget_key)
    elif field_type == "Texto Longo":
        value_to_display = ai_value.get('value', '') if isinstance(ai_value, dict) else ai_value
        st.write(f"**{field_name}**")
        field_data['value'] = st_jodit(
            value=value_to_display,
            key=f"jodit_{widget_key}",
            config={
                'minHeight': 300,
                'buttons': [
                    'source', '|',
                    'bold', 'italic', 'underline', 'strikethrough', '|',
                    'ul', 'ol', '|',
                    'font', 'fontsize', 'brush', 'paragraph', '|',
                    'image', 'table', 'link', '|',
                    'align', 'undo', 'redo', '|',
                    'hr', 'eraser', 'fullsize'
                ]
            }
        )
    elif field_type == "Data":
        value_to_display = ai_value.get('value', None) if isinstance(ai_value, dict) else ai_value
        date_val = None
        if isinstance(value_to_display, str) and value_to_display:
            try: date_val = datetime.fromisoformat(value_to_display.replace("Z", "")).date()
            except: date_val = None
        elif isinstance(value_to_display, datetime):
            date_val = value_to_display.date()
        field_data['value'] = st.date_input(field_name, value=date_val, key=widget_key)
    elif field_type == "Toggle (Sim/Não)":
        value_to_display = ai_value.get('value', False) if isinstance(ai_value, dict) else ai_value
        field_data['value'] = st.toggle(field_name, value=bool(value_to_display), key=widget_key)
    elif field_type == "Seleção Única":
        options = [opt.strip() for opt in field.get('options', '').split(',')]
        value_to_display = ai_value.get('value', '') if isinstance(ai_value, dict) else ai_value
        field_data['value'] = st.radio(field_name, options=options, index=options.index(value_to_display) if value_to_display in options else 0, key=widget_key)
    elif field_type == "Seleção Múltipla":
        options = [opt.strip() for opt in field.get('options', '').split(',')]
        value_to_display = ai_value.get('value', []) if isinstance(ai_value, dict) else ai_value
        default_values = [v for v in value_to_display if v in options] if isinstance(value_to_display, list) else []
        field_data['value'] = st.multiselect(field_name, options=options, default=default_values, key=widget_key)
    elif field_type == "Tabela":
        cols = [col.strip() for col in field.get('options', 'Coluna 1').split(',')]
        table_data = ai_value.get('value', [{}]) if isinstance(ai_value, dict) else ai_value
        df_val = pd.DataFrame(table_data) if isinstance(table_data, list) and table_data else pd.DataFrame([{}], columns=cols)
        field_data['value'] = st.data_editor(df_val, num_rows="dynamic", use_container_width=True, key=widget_key)
    elif field_type == "Imagem":
        field_data['value'] = st.file_uploader(f"Imagens para '{field_name}'", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=widget_key)
        
    custom_field_data[field_name] = field_data

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("💰 Valoração Comercial e Geração de OS", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try: st.logo(str(logo_path), size="large")
    except: st.write("Gauge Metrics")

    if st.session_state.get("email"): st.markdown(f"🔐 Logado como: **{st.session_state['email']}**")
    else: st.info("⚠️ Usuário não conectado!")

    st.header("Seleção de Projeto")
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects and last_project_key in projects.values() else 0

    selected_project_name = st.selectbox("Selecione um Projeto para gerir o catálogo:", options=project_names, index=default_index)

    if st.button("Logout", width='stretch', type='secondary'):
        email_to_remember = st.session_state.get('remember_email', '')
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        if email_to_remember:
            st.session_state['remember_email'] = email_to_remember
        st.switch_page("1_🔑_Autenticação.py")

if not selected_project_name:
    st.info("⬅️ Na barra lateral, selecione um projeto para começar.")
    st.stop()

project_key = projects[selected_project_name]
project_config = get_project_config(project_key) or {}
valuation_config = project_config.get('commercial_valuation', {})
os_layouts = project_config.get('os_layouts', {})

if 'editing_field_key' not in st.session_state: st.session_state.editing_field_key = None
if 'ai_prefilled_data' not in st.session_state: st.session_state.ai_prefilled_data = {}

if 'active_tab' not in st.session_state:
    st.session_state.active_tab = "⚙️ Configurações"

def set_active_tab(tab_name):
    st.session_state.active_tab = tab_name

tab_options = ["⚙️ Configurações", "📄 Gerar OS"]
cols = st.columns(len(tab_options))
for i, tab_name in enumerate(tab_options):
    button_type = "primary" if st.session_state.active_tab == tab_name else "secondary"
    cols[i].button(tab_name, key=f"tab_{i}", on_click=set_active_tab, args=(tab_name,), use_container_width=True, type=button_type)

st.markdown("---") 

if st.session_state.active_tab == "⚙️ Configurações":
    st.subheader(f"Configurações para o Projeto: {selected_project_name}")
    sub_tab_catalogo, sub_tab_layouts = st.tabs(["**Catálogo de Serviços**", "**Construtor de Layouts de OS**"])

    with sub_tab_catalogo:
        with st.container(border=True):
            st.markdown("#### Catálogo de Serviços e Moeda")
            with st.expander("⬇️ Importar Catálogo de Serviços (CSV)"):
                import_source = st.radio("Selecione a fonte de importação:", ["Carregar Ficheiro CSV", "Via Link do SharePoint", "Via Link do Google Planilhas"], horizontal=True)

                if import_source == "Carregar Ficheiro CSV":
                    uploaded_file = st.file_uploader("Selecione o seu ficheiro CSV local:", type="csv")
                    if st.button("Processar Ficheiro"):
                        if uploaded_file:
                            with st.spinner("A processar o seu catálogo..."):
                                try:
                                    try: df_imported = pd.read_csv(uploaded_file, encoding='utf-8', header=1)
                                    except UnicodeDecodeError:
                                        uploaded_file.seek(0)
                                        df_imported = pd.read_csv(uploaded_file, encoding='latin-1', header=1)
                                    st.session_state.df_for_mapping = df_imported
                                    st.rerun()
                                except Exception as e: st.error(f"Não foi possível ler o ficheiro CSV: {e}")
                        else: st.warning("Por favor, carregue um ficheiro CSV.")

                elif import_source == "Via Link do SharePoint":
                    sharepoint_url = st.text_input("Cole o link de partilha do seu ficheiro CSV no SharePoint:")
                    if st.button("Importar de Link (SharePoint)"):
                        if sharepoint_url:
                            with st.spinner("A descarregar e a processar o seu catálogo..."):
                                try:
                                    encoded_url = base64.b64encode(sharepoint_url.encode()).decode().rstrip("=")
                                    direct_download_url = f"https://api.sharepoint.com/v1.0/shares/u!{encoded_url}/root/content"
                                    response = requests.get(direct_download_url)
                                    response.raise_for_status()
                                    csv_data = StringIO(response.content.decode('utf-8-sig'))
                                    df_imported = pd.read_csv(csv_data, header=1)
                                    st.session_state.df_for_mapping = df_imported
                                    st.rerun()
                                except Exception as e: st.error(f"Não foi possível importar o catálogo: {e}")
                        else: st.warning("Por favor, insira um URL.")

                elif import_source == "Via Link do Google Planilhas":
                    g_sheet_url = st.text_input("Cole o link da sua Google Planilha:")
                    if st.button("Importar de Link (Google)"):
                        if g_sheet_url:
                            with st.spinner("A descarregar e a processar a sua planilha..."):
                                try:
                                    csv_export_url = g_sheet_url.replace('/edit?usp=sharing', '/export?format=csv')
                                    df_imported = pd.read_csv(csv_export_url, header=1)
                                    st.session_state.df_for_mapping = df_imported
                                    st.rerun()
                                except Exception as e: st.error(f"Não foi possível importar a planilha: {e}")
                        else: st.warning("Por favor, insira um URL.")

            if 'df_for_mapping' in st.session_state:
                st.subheader("3. Mapeamento de Colunas")
                st.info("'Diga' à aplicação quais colunas do seu ficheiro correspondem aos campos do catálogo.")
                df_to_map = st.session_state.df_for_mapping
                available_columns = df_to_map.columns.tolist()
                with st.form("mapping_form"):
                    c1, c2, c3 = st.columns(3)
                    col_item = c1.selectbox("Coluna para 'Item'*:", options=available_columns)
                    col_valor = c2.selectbox("Coluna para 'Valor'*:", options=available_columns)
                    col_desc = c3.selectbox("Coluna para 'Descrição'*:", options=available_columns)
                    if st.form_submit_button("Confirmar Mapeamento", type="primary"):
                        st.session_state.imported_catalog_items = df_to_map.rename(columns={
                            col_item: "Item", col_valor: "Valor", col_desc: "Descrição"
                        })[['Item', 'Valor', 'Descrição']].to_dict('records')
                        del st.session_state.df_for_mapping
                        st.success("Mapeamento concluído com sucesso! Verifique e salve o catálogo abaixo.")
                        st.rerun()

            with st.form("valuation_config_form"):
                st.markdown("**1. Moeda Personalizada e Conversão**")
                c1, c2 = st.columns(2)
                currency_name = c1.text_input("Nome da Moeda", value=valuation_config.get('currency_name', 'UPs'))
                conversion_rate = c2.number_input("Valor de 1 unidade da moeda em R$", value=valuation_config.get('conversion_rate', 1.0), format="%.2f")
                st.divider()
                st.markdown("**2. Catálogo de Serviços**")
                catalog_items = st.session_state.get('imported_catalog_items', valuation_config.get('service_catalog', [{"Item": "Exemplo", "Valor": 10, "Descrição": "N/A"}]))
                edited_catalog = st.data_editor(pd.DataFrame(catalog_items), num_rows="dynamic", use_container_width=True,
                    column_config={
                        "Item": st.column_config.TextColumn("Item do Catálogo*", required=True),
                        "Valor": st.column_config.NumberColumn(f"Valor (em {currency_name})*", required=True),
                        "Descrição": st.column_config.TextColumn("Descrição", width="large")
                    }
                )
                if st.form_submit_button("Salvar Configurações do Catálogo", width='stretch', type="primary"):
                    project_config['commercial_valuation'] = {
                        'currency_name': currency_name,
                        'conversion_rate': conversion_rate,
                        'service_catalog': edited_catalog.to_dict('records')
                    }
                    save_project_config(project_key, project_config)
                    if 'imported_catalog_items' in st.session_state:
                        del st.session_state.imported_catalog_items
                    st.success("Configurações de valoração salvas com sucesso!")
                    st.rerun()

    with sub_tab_layouts:
        with st.container(border=True):
            st.markdown("#### Construtor de Layouts de Ordem de Serviço")
            st.info("Crie modelos para as suas Ordens de Serviço.")

            with st.expander("➕ Criar Novo Layout de OS"):
                with st.form("new_layout_form", clear_on_submit=True):
                    new_layout_name = st.text_input("Nome do Novo Layout*")
                    if st.form_submit_button("Criar Layout"):
                        if new_layout_name and new_layout_name not in os_layouts:
                            os_layouts[new_layout_name] = []
                            project_config['os_layouts'] = os_layouts
                            save_project_config(project_key, project_config)
                            st.success(f"Layout '{new_layout_name}' criado com sucesso!")
                            st.rerun()

            st.divider()

            if not os_layouts:
                st.warning("Nenhum layout de OS foi criado ainda.")
            else:
                layout_cols = st.columns([3, 1])
                with layout_cols[0]:
                    selected_layout_to_edit = st.selectbox("Selecione um layout para editar:", options=list(os_layouts.keys()), label_visibility="collapsed")
                with layout_cols[1]:
                    if st.button("❌ Excluir Layout", width='stretch', type="secondary", help=f"Apagar permanentemente o layout '{selected_layout_to_edit}'"):
                        if selected_layout_to_edit in os_layouts:
                            del os_layouts[selected_layout_to_edit]
                            project_config['os_layouts'] = os_layouts
                            save_project_config(project_key, project_config)
                            st.success(f"Layout '{selected_layout_to_edit}' excluído com sucesso!")
                            st.rerun()

                if selected_layout_to_edit and selected_layout_to_edit in os_layouts:
                    st.markdown(f"**Editando os campos do layout:** `{selected_layout_to_edit}`")

                    current_layout_fields = os_layouts.get(selected_layout_to_edit, [])
                    field_types_options = ["Texto Curto", "Texto Longo", "Data", "Toggle (Sim/Não)", "Seleção Única", "Seleção Múltipla", "Tabela", "Número", "Imagem", "Valor Calculado"]
                    for i, field in enumerate(current_layout_fields):
                        field_key = f"{selected_layout_to_edit}_{i}"
                        with st.container(border=True):
                            if st.session_state.editing_field_key == field_key:
                                with st.form(f"edit_field_form_{field_key}"):
                                    st.markdown("**Editando Campo**")
                                    edited_name = st.text_input("Nome do Campo*", value=field['field_name'])
                                    edited_type = st.selectbox("Tipo de Campo*", options=field_types_options, index=field_types_options.index(field['field_type']))
                                    
                                    edited_num_type = field.get('number_type', 'Inteiro')
                                    edited_precision = field.get('precision', 2)
                                    edited_options = field.get('options', '')
                                    edited_two_cols = field.get('two_columns', False)

                                    if edited_type == "Número":
                                        edited_num_type = st.radio("Formato do Número", ["Inteiro", "Decimal"], key=f"edit_num_type_{field_key}", horizontal=True, index=["Inteiro", "Decimal"].index(edited_num_type))
                                        if edited_num_type == "Decimal":
                                            edited_precision = st.number_input("Casas Decimais", min_value=1, max_value=4, value=edited_precision, step=1, key=f"edit_precision_{field_key}")
                                    
                                    if edited_type in ["Seleção Única", "Seleção Múltipla"]:
                                        edited_options = st.text_area("Opções (separadas por vírgula)", value=edited_options, key=f"edit_options_{field_key}")
                                    elif edited_type == "Tabela":
                                        edited_options = st.text_area("Nomes das Colunas (separados por vírgula)", value=edited_options, key=f"edit_table_cols_{field_key}")

                                    st.markdown("---")
                                    edited_two_cols = st.toggle("Duas Colunas", value=edited_two_cols, key=f"edit_twocols_{field_key}")
                                    st.markdown("---")
                                    
                                    c1, c2 = st.columns(2)
                                    if c1.form_submit_button("Salvar Alterações", width='stretch', type="primary"):
                                        if edited_name:
                                            current_layout_fields[i].update({
                                                "field_name": edited_name, "field_type": edited_type,
                                                "options": edited_options, "two_columns": edited_two_cols,
                                                "number_type": edited_num_type,
                                                "precision": edited_precision
                                            })
                                            project_config['os_layouts'][selected_layout_to_edit] = current_layout_fields
                                            save_project_config(project_key, project_config)
                                            st.session_state.editing_field_key = None
                                            st.success("Campo atualizado com sucesso!")
                                            st.rerun()
                                    if c2.form_submit_button("Cancelar", width='stretch'):
                                        st.session_state.editing_field_key = None
                                        st.rerun()
                            else:
                                col1, col_first, col_up, col_down, col_last, col_edit, col_remove = st.columns([4, 1, 1, 1, 1, 1, 1])
                                field_display = f"Campo: {field['field_name']} (Tipo: {field['field_type']})"
                                if field.get('two_columns'): field_display += " | Layout: Duas Colunas"
                                col1.text(field_display)

                                if col_first.button("⏫", key=f"first_btn_{field_key}", width='stretch', help="Mover para o início", disabled=(i == 0)):
                                    current_layout_fields.insert(0, current_layout_fields.pop(i)); save_project_config(project_key, project_config); st.rerun()
                                if col_up.button("🔼", key=f"up_btn_{field_key}", width='stretch', help="Mover para cima", disabled=(i == 0)):
                                    current_layout_fields[i], current_layout_fields[i-1] = current_layout_fields[i-1], current_layout_fields[i]; save_project_config(project_key, project_config); st.rerun()
                                if col_down.button("🔽", key=f"down_btn_{field_key}", width='stretch', help="Mover para baixo", disabled=(i == len(current_layout_fields) - 1)):
                                    current_layout_fields[i], current_layout_fields[i+1] = current_layout_fields[i+1], current_layout_fields[i]; save_project_config(project_key, project_config); st.rerun()
                                if col_last.button("⏬", key=f"last_btn_{field_key}", width='stretch', help="Mover para o fim", disabled=(i == len(current_layout_fields) - 1)):
                                    current_layout_fields.append(current_layout_fields.pop(i)); save_project_config(project_key, project_config); st.rerun()
                                if col_edit.button("✏️", key=f"edit_btn_{field_key}", width='stretch'):
                                    st.session_state.editing_field_key = field_key; st.rerun()
                                if col_remove.button("❌", key=f"del_btn_{field_key}", width='stretch'):
                                    current_layout_fields.pop(i); save_project_config(project_key, project_config); st.rerun()

                    with st.form(f"add_field_form_{selected_layout_to_edit}"):
                        st.markdown("**Adicionar Novo Campo**")
                        field_name = st.text_input("Nome do Campo*")
                        field_type = st.selectbox("Tipo de Campo*", options=field_types_options, key="add_field_type")
                        
                        options_str = ""
                        if st.session_state.add_field_type in ["Seleção Única", "Seleção Múltipla"]:
                            options_str = st.text_area("Opções (separadas por vírgula)", key="add_options")
                        elif st.session_state.add_field_type == "Tabela":
                            options_str = st.text_area("Nomes das Colunas (separados por vírgula)", key="add_table_cols")

                        number_type = "Inteiro"; precision = 2
                        if st.session_state.add_field_type == "Número":
                            number_type = st.radio("Formato do Número", ["Inteiro", "Decimal"], key="add_num_type", horizontal=True)
                            if number_type == "Decimal":
                                precision = st.number_input("Casas Decimais", min_value=1, max_value=4, value=2, step=1, key="add_precision")
                        
                        st.markdown("---")
                        two_cols_new = st.toggle("Duas Colunas", key=f"add_twocols_{selected_layout_to_edit}")

                        if st.form_submit_button("Adicionar Campo ao Layout"):
                            if field_name:
                                new_field = {
                                    "field_name": field_name, "field_type": st.session_state.add_field_type,
                                    "options": options_str, "two_columns": two_cols_new,
                                    "number_type": number_type, "precision": precision
                                }
                                current_config = get_project_config(project_key) or {}
                                current_layouts = current_config.get('os_layouts', {})
                                current_layouts.setdefault(selected_layout_to_edit, []).append(new_field)
                                current_config['os_layouts'] = current_layouts
                                save_project_config(project_key, current_config)
                                st.success(f"Campo '{field_name}' adicionado ao layout!")
                                st.rerun()

elif st.session_state.active_tab == "📄 Gerar OS":
    project_config = get_project_config(project_key) or {}
    os_layouts = project_config.get('os_layouts', {})
    valuation_config = project_config.get('commercial_valuation', {})
    
    st.subheader("Gerador de Ordem de Serviço")

    if not os_layouts:
        st.warning("Nenhum layout de OS foi criado. Por favor, crie um na aba de 'Configurações' primeiro.")
    else:
        os_templates = project_config.get('os_templates', {})
        template_names = [""] + list(os_templates.keys())

        col1, col2 = st.columns([3, 1], vertical_alignment="bottom") 

        selected_template = col1.selectbox(
            "Carregar um modelo de OS preenchido:", 
            options=template_names, 
            format_func=lambda x: "Nenhum (começar do zero)" if x == "" else x, 
            key="template_selector"
        )

        def load_template():
            template_data = os_templates.get(st.session_state.template_selector)
            if template_data:
                st.session_state.ai_prefilled_data = {}
                st.session_state.os_items = []
                st.session_state.selected_layout_name = template_data.get('layout_name')
                st.session_state.ai_prefilled_data = template_data.get('custom_fields', {})
                st.session_state.os_items = template_data.get('items', [])
                
                loaded_signatories = template_data.get('assinantes', [])
                st.session_state.os_signatories = loaded_signatories if loaded_signatories else [{"Nome": "", "Papel": ""}]
                
                for i, sig in enumerate(st.session_state.os_signatories):
                    st.session_state[f"assinante_nome_{i}"] = sig.get("Nome", "")
                    st.session_state[f"assinante_papel_{i}"] = sig.get("Papel", "")
                
                st.success(f"Modelo '{st.session_state.template_selector}' carregado com sucesso!")

        col2.button(
            "Carregar Modelo", 
            on_click=load_template, 
            disabled=not selected_template, 
            use_container_width=True # use_container_width é o novo nome para 'width=stretch'
        )

        st.divider()

        selected_layout_name = st.selectbox("Selecione o Layout da OS:", options=list(os_layouts.keys()), key='selected_layout_name', on_change=lambda: st.session_state.update(ai_prefilled_data={}, os_items=[], os_signatories=[{"Nome": "", "Papel": ""}]))

        if selected_layout_name:
            layout_to_render = os_layouts.get(selected_layout_name, [])

            with st.expander("🤖 Preencher com IA a partir do Jira"):
                c1, c2 = st.columns([3, 1])
                jira_issue_key = c1.text_input("Insira a chave da Issue do Jira (ex: PROJ-123)")
                if c2.button("Buscar e Preencher", width='stretch'):
                    if jira_issue_key:
                        with st.spinner(f"A buscar dados da issue {jira_issue_key}..."):
                            try:
                                issue_data_dict = get_issue_as_dict(st.session_state.jira_client, jira_issue_key)
                                ai_result = get_ai_os_from_jira_issue(issue_data_dict, layout_to_render)
                                if "error" in ai_result: st.session_state.ai_feedback = {"type": "error", "message": f"Erro da IA: {ai_result['error']}"}
                                elif ai_result and any(ai_result.values()):
                                    st.session_state.ai_prefilled_data = ai_result
                                    st.session_state.ai_feedback = {"type": "success", "message": "Dados extraídos com sucesso!"}
                                else:
                                    st.session_state.ai_prefilled_data = {}
                                    st.session_state.ai_feedback = {"type": "warning", "message": "A IA não conseguiu extrair dados."}
                                st.rerun()
                            except Exception as e: st.error(f"Não foi possível processar a issue {jira_issue_key}: {e}")
                    else: st.warning("Por favor, insira uma chave de issue.")

            if 'ai_feedback' in st.session_state:
                feedback = st.session_state.ai_feedback
                if feedback["type"] == "success": st.success(feedback["message"])
                elif feedback["type"] == "warning": st.warning(feedback["message"])
                elif feedback["type"] == "error": st.error(feedback["message"])
                del st.session_state.ai_feedback

            if st.session_state.ai_prefilled_data:
                with st.expander("🔍 Dados Recebidos da IA (Depuração)"): st.json(st.session_state.ai_prefilled_data)
            
            if 'os_signatories' not in st.session_state:
                st.session_state.os_signatories = [{"Nome": "", "Papel": ""}]
                
            def add_signatory():
                st.session_state.os_signatories.append({"Nome": "", "Papel": ""})

            def remove_signatory(i):
                if len(st.session_state.os_signatories) > 1:
                    st.session_state.os_signatories.pop(i)
            
            with st.form("os_form"):
                st.markdown(f"**Preencha os dados para a OS:** `{selected_layout_name}`")
                custom_field_data = {}
                i = 0
                while i < len(layout_to_render):
                    field = layout_to_render[i]
                    is_two_col = field.get('two_columns', False)
                    next_field_is_two_col = (i + 1 < len(layout_to_render)) and layout_to_render[i+1].get('two_columns', False)
                    if is_two_col and next_field_is_two_col:
                        cols = st.columns(2)
                        with cols[0]: render_os_field(field, custom_field_data, i)
                        i += 1
                        field2 = layout_to_render[i]
                        with cols[1]: render_os_field(field2, custom_field_data, i)
                    else: render_os_field(field, custom_field_data, i)
                    i += 1

                st.divider()
                st.markdown("**Itens do Catálogo (Opcional)**")
                catalog = valuation_config.get('service_catalog', [])
                currency_name = valuation_config.get('currency_name', 'UPs')
                item_options = {f"{item['Item']} ({item['Valor']} {currency_name})": item for item in catalog}
                default_items = []
                if st.session_state.get('os_items'):
                    for item in st.session_state.os_items:
                        desc = f"{item.get('Item')} ({item.get('Valor')} {currency_name})"
                        if desc in item_options: default_items.append(desc)
                selected_items_desc = st.multiselect("Selecione os itens do catálogo para a OS:", options=item_options.keys(), default=default_items, key="catalog_items_multiselect")
                
                st.divider()
                st.markdown("**Assinantes**")
                for i, signatory in enumerate(st.session_state.os_signatories):
                    # Inicializa o estado do widget SE ele não existir
                    if f"assinante_nome_{i}" not in st.session_state:
                        st.session_state[f"assinante_nome_{i}"] = signatory.get("Nome", "")
                    if f"assinante_papel_{i}" not in st.session_state:
                        st.session_state[f"assinante_papel_{i}"] = signatory.get("Papel", "")

                    st.markdown("---")
                    c1, c2 = st.columns(2)
                    # Agora o widget lê o seu valor diretamente da session_state através da key
                    c1.text_input(f"Nome do Assinante {i+1}*", key=f"assinante_nome_{i}")
                    c2.text_input(f"Papel do Assinante {i+1}*", key=f"assinante_papel_{i}")

                preview_button = st.form_submit_button("Pré-visualizar OS", width='stretch')
                
            col1, col2, _ = st.columns([1.5, 1, 4])
            col1.button("Adicionar Assinante", on_click=add_signatory, use_container_width=True)
            if len(st.session_state.os_signatories) > 1:
                col2.button("Remover Último", on_click=lambda: st.session_state.os_signatories.pop(), use_container_width=True)

            if preview_button:
                st.session_state.ai_prefilled_data = {}
                processed_custom_data = {}
                selected_items_data = [item_options[desc] for desc in selected_items_desc]
                
                total_catalog_value = sum(float(item.get('Valor', 0)) for item in selected_items_data)
                final_brl_value = total_catalog_value * valuation_config.get('conversion_rate', 1.0)

                for field in layout_to_render:
                    field_name, field_type = field['field_name'], field['field_type']
                    data = custom_field_data.get(field_name, {})
                    
                    if field_type == 'Valor Calculado':
                        processed_custom_data[field_name] = {'value': f"R$ {final_brl_value:,.2f}"}
                        continue

                    processed_entry = {}
                    value = data.get('value')
                    if field_type == "Tabela":
                        processed_entry['value'] = pd.DataFrame(value).dropna(how='all').to_dict('records')
                    elif field_type == "Imagem" and value:
                        if len(value) > 5:
                            st.warning(f"Apenas 5 imagens por campo são permitidas."); value = value[:5]
                        processed_entry['value'] = [file.getvalue() for file in value]
                    else: processed_entry['value'] = value
                    
                    processed_custom_data[field_name] = processed_entry
    
                assinantes_list = []
                for i in range(len(st.session_state.os_signatories)):
                    nome = st.session_state.get(f"assinante_nome_{i}", "")
                    papel = st.session_state.get(f"assinante_papel_{i}", "")
                    if nome and papel:
                        assinantes_list.append({"Nome": nome, "Papel": papel})
                
                st.session_state.os_preview_data = {
                    'layout_name': selected_layout_name, 'custom_fields': processed_custom_data,
                    'custom_fields_layout': layout_to_render, 'items': selected_items_data,
                    'assinantes': assinantes_list
                }
                st.rerun()

if 'os_preview_data' in st.session_state:
    st.divider()
    st.subheader("🔍 Pré-visualização da OS")
    
    preview_data = st.session_state.os_preview_data

    default_os_title = f"Ordem de Serviço: {preview_data.get('layout_name', 'N/A')}"
        
    # Passo 1: Inicializa o valor na session_state APENAS se ele não existir
    if 'editable_os_title' not in st.session_state:
        st.session_state.editable_os_title = default_os_title
            
    # Passo 2: Cria o widget usando a key. O Streamlit irá gerir o valor automaticamente.
    # Não atribua o resultado do widget de volta para a session_state.
    st.text_input(
        "**Título da OS (para o PDF):**",
        key="editable_os_title" 
    )

    with st.container(border=True):
        st.markdown(f"**Layout:** {preview_data['layout_name']}")
        st.divider()
        
        layout_for_preview = preview_data['custom_fields_layout']
        fields_for_preview = preview_data['custom_fields']
        
        i = 0
        while i < len(layout_for_preview):
            field1_data = layout_for_preview[i]
            is_two_col = field1_data.get('two_columns', False)
            next_field_is_two_col = (i + 1 < len(layout_for_preview)) and layout_for_preview[i+1].get('two_columns', False)

            def display_field(field_info):
                field_name = field_info['field_name']
                st.markdown(f"**{field_name}:**")
                field_content = fields_for_preview.get(field_name, {})
                value = field_content.get('value')
                
                if value is not None and (not isinstance(value, list) or len(value) > 0):
                    if field_info.get('field_type') == "Tabela": st.dataframe(pd.DataFrame(value))
                    elif field_info.get('field_type') == "Toggle (Sim/Não)": st.markdown("Sim" if value else "Não")
                    elif isinstance(value, list): st.markdown(", ".join(map(str, value)))
                    else: st.markdown(value, unsafe_allow_html=True)
                else: st.caption("-")

            if is_two_col and next_field_is_two_col:
                field2_data = layout_for_preview[i+1]
                col1, col2 = st.columns(2)
                with col1: display_field(field1_data)
                with col2: display_field(field2_data)
                i += 2
            else:
                display_field(field1_data)
                i += 1
        
        if preview_data.get('items'):
            st.markdown("**Itens do Catálogo:**"); st.dataframe(pd.DataFrame(preview_data['items'])[["Item", "Valor"]])
        if preview_data.get('assinantes'):
            st.markdown("**Assinantes:**"); st.dataframe(pd.DataFrame(preview_data['assinantes']))

    with st.form("save_template_form"):
        st.subheader("💾 Salvar como Modelo (Opcional)")
        template_name = st.text_input("Nome para o novo modelo")
        if st.form_submit_button("Salvar OS como Modelo", use_container_width=True):
            if template_name:
                os_templates = project_config.get('os_templates', {})
                os_templates[template_name] = {
                    'layout_name': preview_data['layout_name'], 'custom_fields': preview_data['custom_fields'],
                    'items': preview_data.get('items', []), 'assinantes': preview_data.get('assinantes', [])
                }
                project_config['os_templates'] = os_templates
                save_project_config(project_key, project_config)
                st.success(f"Modelo '{template_name}' salvo com sucesso!")
            else: st.warning("Por favor, dê um nome ao modelo.")

    st.divider()
    if st.button("Confirmar e Gerar PDF", type="primary", use_container_width=True):
        with st.spinner("A gerar o PDF..."):
            pdf_data = copy.deepcopy(preview_data)

            final_os_title = st.session_state.get('editable_os_title', default_os_title)
            pdf_bytes = create_os_pdf(pdf_data, os_title=final_os_title)
            
            # Pega o título editado e passa para a função
            final_os_title = st.session_state.get('editable_os_title', default_os_title)
            pdf_bytes = create_os_pdf(pdf_data, os_title=final_os_title)
            
            st.session_state.generated_os_pdf = pdf_bytes
            st.session_state.generated_os_data = preview_data
            st.session_state.pdf_generation_success = True
            del st.session_state.os_preview_data
            del st.session_state.editable_os_title # Limpa o título da sessão
            st.rerun()

if st.session_state.get('pdf_generation_success'):
    st.success("PDF gerado com sucesso! Clique no botão abaixo para descarregar.")
    st.session_state.pdf_generation_success = False

# Verifica se os dados e o PDF existem na sessão antes de tentar usá-los
if 'generated_os_pdf' in st.session_state and 'generated_os_data' in st.session_state:
    
    # Define a variável 'os_data' DENTRO do bloco seguro
    os_data = st.session_state.generated_os_data

    if os_data:
        st.download_button(
            label="⬇️ Descarregar OS em PDF",
            data=st.session_state.generated_os_pdf,
            file_name=f"OS_{os_data.get('layout_name', 'SemNome').replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary"
        )