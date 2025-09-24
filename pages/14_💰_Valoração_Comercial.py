# pages/15_💰_Valoração_Comercial.py

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

st.set_page_config(page_title="Valoração Comercial", page_icon="💰", layout="wide")

# --- LÓGICA PRINCIPAL DA PÁGINA ---
st.header("💰 Valoração Comercial e Geração de OS", divider='rainbow')

# --- Bloco de Autenticação e Conexão ---
if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para acessar."); st.page_link("1_🔑_Autenticação.py", label="Ir para Autenticação", icon="🔑"); st.stop()
if 'jira_client' not in st.session_state:
    st.warning("⚠️ Nenhuma conexão Jira ativa."); st.page_link("pages/8_🔗_Conexões_Jira.py", label="Ativar uma Conexão", icon="🔗"); st.stop()

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

    st.header("Seleção de Projeto")
    
    projects = st.session_state.get('projects', {})
    project_names = list(projects.keys())
    
    last_project_key = find_user(st.session_state['email']).get('last_project_key')
    default_index = project_names.index(next((name for name, key in projects.items() if key == last_project_key), None)) if last_project_key and projects else 0
    
    selected_project_name = st.selectbox(
        "Selecione um Projeto para gerir o catálogo:",
        options=project_names,
        index=default_index
    )
    if st.button("Logout", use_container_width=True, type='secondary'):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.switch_page("1_🔑_Autenticação.py")
        
if not selected_project_name:
    st.info("⬅️ Na barra lateral, selecione um projeto para começar.")
    st.stop()

project_key = projects[selected_project_name]
project_config = get_project_config(project_key) or {}
valuation_config = project_config.get('commercial_valuation', {})
os_layouts = project_config.get('os_layouts', {})

if 'editing_field_key' not in st.session_state:
    st.session_state.editing_field_key = None
if 'ai_prefilled_data' not in st.session_state:
    st.session_state.ai_prefilled_data = {}

# --- ESTRUTURA DE ABAS PRINCIPAL---
tab_config, tab_os = st.tabs(["**⚙️ Configurações**", "**📄 Gerar OS**"])

with tab_config:
    st.subheader(f"Configurações para o Projeto: {selected_project_name}")
    
    # --- INÍCIO DA REESTRUTURAÇÃO COM SUB-ABAS ---
    sub_tab_catalogo, sub_tab_layouts = st.tabs(["**Catálogo de Serviços**", "**Construtor de Layouts de OS**"])

    # --- SUB-ABA: CATÁLOGO E MOEDA ---
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
                                    try:
                                        df_imported = pd.read_csv(uploaded_file, encoding='utf-8', header=1)
                                    except UnicodeDecodeError:
                                        uploaded_file.seek(0)
                                        df_imported = pd.read_csv(uploaded_file, encoding='latin-1', header=1)
                                    st.session_state.df_for_mapping = df_imported
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Não foi possível ler o ficheiro CSV: {e}")
                        else:
                            st.warning("Por favor, carregue um ficheiro CSV.")

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
                                except Exception as e:
                                    st.error(f"Não foi possível importar o catálogo: {e}")
                        else:
                            st.warning("Por favor, insira um URL.")

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
                                except Exception as e:
                                    st.error(f"Não foi possível importar a planilha: {e}")
                        else:
                            st.warning("Por favor, insira um URL.")

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
                if st.form_submit_button("Salvar Configurações do Catálogo", use_container_width=True, type="primary"):
                    project_config['commercial_valuation'] = {
                        'currency_name': currency_name,
                        'conversion_rate': conversion_rate,
                        'service_catalog': edited_catalog.to_dict('records')
                    }
                    save_project_config(project_key, project_config)
                    if 'imported_catalog_items' in st.session_state:
                        del st.session_state['imported_catalog_items']
                    st.success("Configurações de valoração salvas com sucesso!")
                    st.rerun()

    # --- SUB-ABA: CONSTRUTOR DE LAYOUTS ---
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
                    if st.button("❌ Excluir Layout", use_container_width=True, type="secondary", help=f"Apagar permanentemente o layout '{selected_layout_to_edit}'"):
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
                                    if edited_type == "Número":
                                        edited_num_type = st.radio("Formato do Número", ["Inteiro", "Decimal"], key=f"edit_num_type_{field_key}", horizontal=True, index=["Inteiro", "Decimal"].index(edited_num_type))
                                        if edited_num_type == "Decimal":
                                            edited_precision = st.number_input("Casas Decimais", min_value=1, max_value=4, value=edited_precision, step=1, key=f"edit_precision_{field_key}")
                                    
                                    allow_images = False
                                    if edited_type == "Texto Longo":
                                        allow_images = st.checkbox("Permitir upload de imagens", value=field.get('allow_images', False))
                                    
                                    edited_options = ""
                                    if edited_type in ["Seleção Única", "Seleção Múltipla", "Tabela"]:
                                        edited_options = st.text_area("Opções (para seleção ou colunas de tabela)", value=field.get('options', ''))
                                    
                                    c1, c2 = st.columns(2)
                                    if c1.form_submit_button("Salvar Alterações", use_container_width=True, type="primary"):
                                        if edited_name:
                                            existing_field_names = [f['field_name'] for idx, f in enumerate(os_layouts[selected_layout_to_edit]) if idx != i]
                                            if edited_name in existing_field_names:
                                                st.error(f"O nome de campo '{edited_name}' já está em uso neste layout. Por favor, escolha outro nome.")
                                            else:
                                                updated_field = { "field_name": edited_name, "field_type": edited_type, "options": edited_options }
                                                if edited_type == "Texto Longo":
                                                    updated_field["allow_images"] = allow_images
                                                
                                                if edited_type == "Número":
                                                    updated_field['number_type'] = edited_num_type
                                                    if edited_num_type == "Decimal":
                                                        updated_field['precision'] = edited_precision
                                                
                                                os_layouts[selected_layout_to_edit][i] = updated_field
                                                project_config['os_layouts'] = os_layouts
                                                save_project_config(project_key, project_config)
                                                st.session_state.editing_field_key = None
                                                st.success("Campo atualizado com sucesso!")
                                                st.rerun()
                                    if c2.form_submit_button("Cancelar", use_container_width=True):
                                        st.session_state.editing_field_key = None
                                        st.rerun()
                            else:
                                col1, col_up, col_down, col_edit, col_remove = st.columns([4, 1, 1, 1, 1])
                                field_display = f"Campo: {field['field_name']} (Tipo: {field['field_type']})"
                                if field.get('field_type') == 'Texto Longo' and field.get('allow_images'):
                                    field_display += " 🖼️"
                                col1.text(field_display)

                                if i > 0:
                                    if col_up.button("⬆️", key=f"up_btn_{field_key}", use_container_width=True, help="Mover para cima"):
                                        current_layout_fields[i], current_layout_fields[i-1] = current_layout_fields[i-1], current_layout_fields[i]
                                        project_config['os_layouts'][selected_layout_to_edit] = current_layout_fields
                                        save_project_config(project_key, project_config)
                                        st.rerun()
                                else:
                                    col_up.write("")

                                if i < len(current_layout_fields) - 1:
                                    if col_down.button("⬇️", key=f"down_btn_{field_key}", use_container_width=True, help="Mover para baixo"):
                                        current_layout_fields[i], current_layout_fields[i+1] = current_layout_fields[i+1], current_layout_fields[i]
                                        project_config['os_layouts'][selected_layout_to_edit] = current_layout_fields
                                        save_project_config(project_key, project_config)
                                        st.rerun()
                                else:
                                    col_down.write("")

                                if col_edit.button("✏️ Editar", key=f"edit_btn_{field_key}", use_container_width=True):
                                    st.session_state.editing_field_key = field_key
                                    st.rerun()
                                if col_remove.button("❌ Remover", key=f"del_btn_{field_key}", use_container_width=True):
                                    current_layout_fields.pop(i)
                                    project_config['os_layouts'][selected_layout_to_edit] = current_layout_fields
                                    save_project_config(project_key, project_config)
                                    st.rerun()

                    with st.form(f"add_field_form_{selected_layout_to_edit}"):
                        st.markdown("**Adicionar Novo Campo**")
                        field_name = st.text_input("Nome do Campo*")
                        field_type = st.selectbox("Tipo de Campo*", options=field_types_options)
                        
                        number_type = "Inteiro"
                        precision = 2
                        if field_type == "Número":
                            number_type = st.radio("Formato do Número", ["Inteiro", "Decimal"], key="add_num_type", horizontal=True)
                            if number_type == "Decimal":
                                precision = st.number_input("Casas Decimais", min_value=1, max_value=4, value=2, step=1, key="add_precision")
                        
                        allow_images_new = False
                        if field_type == "Texto Longo":
                            allow_images_new = st.checkbox("Permitir upload de imagens")
                        
                        options_str = ""
                        if field_type in ["Seleção Única", "Seleção Múltipla", "Tabela"]:
                            options_str = st.text_area("Opções (para seleção ou colunas de tabela, separadas por vírgula)")
                        
                        if st.form_submit_button("Adicionar Campo ao Layout"):
                            if field_name:
                                existing_field_names = [f['field_name'] for f in os_layouts[selected_layout_to_edit]]
                                if field_name in existing_field_names:
                                    st.warning(f"O campo '{field_name}' já existe neste layout. Por favor, escolha um nome diferente.")
                                else:
                                    new_field = { "field_name": field_name, "field_type": field_type, "options": options_str }
                                    if field_type == "Texto Longo":
                                        new_field["allow_images"] = allow_images_new
                                    
                                    if field_type == "Número":
                                        new_field['number_type'] = number_type
                                        if number_type == "Decimal":
                                            new_field['precision'] = precision
                                    
                                    os_layouts[selected_layout_to_edit].append(new_field)
                                    project_config['os_layouts'] = os_layouts
                                    save_project_config(project_key, project_config)
                                    st.success(f"Campo '{field_name}' adicionado ao layout!")
                                    st.rerun()
                                    
with tab_os:
    st.subheader("Gerador de Ordem de Serviço")
    
    if not os_layouts:
        st.warning("Nenhum layout de OS foi criado. Por favor, crie um na aba de 'Configurações' primeiro.")
    else:
        selected_layout_name = st.selectbox("Selecione o Layout da OS:", options=list(os_layouts.keys()), 
                                            on_change=lambda: st.session_state.update(ai_prefilled_data={}))
        
        if selected_layout_name:
            layout_to_render = os_layouts.get(selected_layout_name, [])
            
            with st.expander("🤖 Preencher com IA a partir do Jira"):
                c1, c2 = st.columns([3, 1])
                jira_issue_key = c1.text_input("Insira a chave da Issue do Jira (ex: PROJ-123)")
                if c2.button("Buscar e Preencher", use_container_width=True):
                    if jira_issue_key:
                        with st.spinner(f"A buscar todos os dados da issue {jira_issue_key} e a analisar com a IA..."):
                            try:
                                issue_data_dict = get_issue_as_dict(st.session_state.jira_client, jira_issue_key)
                                ai_result = get_ai_os_from_jira_issue(issue_data_dict, layout_to_render)
                                
                                if "error" in ai_result:
                                    st.error(f"Erro da IA: {ai_result['error']}")
                                else:
                                    st.session_state.ai_prefilled_data = ai_result
                                    st.success("Dados extraídos com sucesso! O formulário abaixo foi preenchido.")
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Não foi possível encontrar ou processar a issue {jira_issue_key}: {e}")
                    else:
                        st.warning("Por favor, insira uma chave de issue.")

            with st.form("os_form"):
                st.markdown(f"**Preencha os dados para a OS:** `{selected_layout_name}`")
                
                custom_field_data = {}
                for i, field in enumerate(layout_to_render):
                    field_name = field.get('field_name')
                    field_type = field.get('field_type')
                    if not field_name or not field_type: continue
                    
                    if field_type == "Valor Calculado":
                        continue
                    
                    widget_key = f"{field_name}_{i}"
                    ai_value = st.session_state.ai_prefilled_data.get(field_name, '')

                    if field_type == "Texto Curto":
                        custom_field_data[field_name] = st.text_input(field_name, value=ai_value, key=widget_key)
                    elif field_type == "Texto Longo":
                        text_area = st.text_area(f"{field_name} (suporta Markdown)", value=ai_value, key=f"text_{widget_key}")
                        images_uploader = None
                        if field.get('allow_images', False):
                            images_uploader = st.file_uploader(f"Adicionar imagens para '{field_name}'", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=f"img_uploader_{widget_key}")
                        custom_field_data[field_name] = {"text": text_area, "images": images_uploader}
                    elif field_type == "Data":
                        custom_field_data[field_name] = st.date_input(field_name, value=None, key=widget_key)
                    elif field_type == "Toggle (Sim/Não)":
                        custom_field_data[field_name] = st.toggle(field_name, value=bool(ai_value), key=widget_key)
                    elif field_type == "Seleção Única":
                        options = [opt.strip() for opt in field.get('options', '').split(',')]
                        custom_field_data[field_name] = st.radio(field_name, options=options, index=options.index(ai_value) if ai_value in options else 0, key=widget_key)
                    elif field_type == "Seleção Múltipla":
                        options = [opt.strip() for opt in field.get('options', '').split(',')]
                        default_values = [v for v in ai_value if v in options] if isinstance(ai_value, list) else []
                        custom_field_data[field_name] = st.multiselect(field_name, options=options, default=default_values, key=widget_key)
                    elif field_type == "Tabela":
                        cols = [col.strip() for col in field.get('options', 'Coluna 1').split(',')]
                        df_val = pd.DataFrame(ai_value) if isinstance(ai_value, list) and ai_value else pd.DataFrame([{}], columns=cols)
                        custom_field_data[field_name] = st.data_editor(df_val, num_rows="dynamic", use_container_width=True, key=widget_key)
                    # --- INÍCIO DA ALTERAÇÃO 5: RENDERIZAR CAMPO NUMÉRICO COM FORMATO ---
                    elif field_type == "Número":
                        num_type = field.get('number_type', 'Inteiro')
                        num_val = None
                        try:
                            if ai_value and str(ai_value).strip():
                                num_val = float(ai_value)
                        except (ValueError, TypeError):
                            num_val = None

                        if num_type == 'Inteiro':
                            default_int = int(num_val) if num_val is not None else 0
                            custom_field_data[field_name] = st.number_input(field_name, value=default_int, step=1, format="%d", key=widget_key)
                        else: # Decimal
                            precision = field.get('precision', 2)
                            step = 1 / (10 ** precision)
                            default_float = num_val if num_val is not None else 0.0
                            custom_field_data[field_name] = st.number_input(field_name, value=default_float, step=step, format=f"%.{precision}f", key=widget_key)
                    # --- FIM DA ALTERAÇÃO 5 ---
                    elif field_type == "Imagem":
                        custom_field_data[field_name] = st.file_uploader(f"{field_name} (máx. 5)", type=["png", "jpg", "jpeg"], accept_multiple_files=True, key=widget_key)
                
                st.divider()
                st.markdown("**Itens do Catálogo (Opcional)**")
                catalog = valuation_config.get('service_catalog', [])
                currency_name = valuation_config.get('currency_name', 'UPs')
                item_options = {f"{item['Item']} ({item['Valor']} {currency_name})": item for item in catalog}
                selected_items_desc = st.multiselect("Selecione os itens do catálogo para a OS:", options=item_options.keys(), key="catalog_items_multiselect")
                
                st.divider()
                st.markdown("**Assinaturas**")
                
                assinantes_df = st.data_editor(pd.DataFrame([{"Nome": "", "Cargo": ""}]), num_rows="dynamic", use_container_width=True, key="assinantes_editor", column_config={"Nome": st.column_config.TextColumn("Nome*", required=True), "Cargo": st.column_config.TextColumn("Cargo*", required=True)})
                
                preview_button = st.form_submit_button("Pré-visualizar OS", use_container_width=True)

            if preview_button:
                st.session_state.ai_prefilled_data = {}
                selected_items_data = [item_options[desc] for desc in selected_items_desc]
                assinantes_validos = pd.DataFrame(assinantes_df).dropna(how='all').to_dict('records')
                
                total_catalog_value = sum(float(item.get('Valor', 0)) for item in selected_items_data)
                conversion_rate = valuation_config.get('conversion_rate', 1.0)
                final_brl_value = total_catalog_value * conversion_rate
                currency_name = valuation_config.get('currency_name', 'UPs')
                
                for field in layout_to_render:
                    if field.get('field_type') == 'Valor Calculado':
                        custom_field_data[field['field_name']] = f"R$ {final_brl_value:,.2f}"
                
                for field in layout_to_render:
                    field_name = field.get('field_name'); field_type = field.get('field_type')
                    if field_type == "Texto Longo":
                        text_longo_data = custom_field_data.get(field_name, {"text": "", "images": None})
                        if text_longo_data.get("images"): text_longo_data["images"] = [file.getvalue() for file in text_longo_data["images"]]
                        else: text_longo_data["images"] = []
                        custom_field_data[field_name] = text_longo_data
                    elif field_type == "Imagem" and custom_field_data.get(field_name) is not None:
                        uploaded_files = custom_field_data[field_name]
                        if len(uploaded_files) > 5:
                            st.warning(f"Apenas as primeiras 5 imagens do campo '{field_name}' serão processadas."); uploaded_files = uploaded_files[:5]
                        custom_field_data[field_name] = [file.getvalue() for file in uploaded_files]
                    elif field_type == "Tabela":
                        custom_field_data[field_name] = pd.DataFrame(custom_field_data.get(field_name)).to_dict('records')

                st.session_state.os_preview_data = {
                    'layout_name': selected_layout_name, 'custom_fields': custom_field_data,
                    'custom_fields_layout': layout_to_render, 'items': selected_items_data,
                    'assinantes': assinantes_validos
                }

    if 'os_preview_data' in st.session_state:
        st.divider()
        st.subheader("🔍 Pré-visualização da OS")
        
        preview_data = st.session_state.os_preview_data
        
        with st.container(border=True):
            st.markdown(f"**Layout:** {preview_data['layout_name']}")
            st.divider()
            for field_data in preview_data['custom_fields_layout']:
                field_name = field_data['field_name']; field_type = field_data['field_type']
                value = preview_data['custom_fields'].get(field_name)
                
                if value is not None and value != '' and (not isinstance(value, list) or len(value) > 0):
                    st.markdown(f"**{field_name}:**")
                    if field_type == "Tabela":
                        st.dataframe(pd.DataFrame(value))
                    elif field_type == "Imagem" and isinstance(value, list):
                        for img_bytes in value:
                            st.image(img_bytes)
                    elif field_type == "Texto Longo" and isinstance(value, dict):
                        if value.get("text"):
                            st.markdown(value["text"], help="Este campo suporta formatação Markdown.")
                        if value.get("images"):
                            for img_bytes in value["images"]:
                                st.image(img_bytes)
                    elif field_type == "Toggle (Sim/Não)":
                        st.markdown("Sim" if value else "Não")
                    else:
                        if isinstance(value, list):
                            display_value = ", ".join(map(str, value))
                            st.markdown(display_value)
                        else:
                            st.markdown(str(value))
            
            if preview_data.get('items'):
                st.markdown("**Itens do Catálogo:**"); st.dataframe(pd.DataFrame(preview_data['items'])[["Item", "Valor"]])
            if preview_data.get('assinantes'):
                st.markdown("**Assinantes:**"); st.dataframe(pd.DataFrame(preview_data['assinantes']))

        if st.button("Confirmar e Gerar PDF", type="primary", use_container_width=True):
            with st.spinner("A gerar o PDF..."):
                pdf_data = copy.deepcopy(preview_data)
                
                pdf_bytes = create_os_pdf(pdf_data)
                st.session_state.generated_os_pdf = pdf_bytes
                st.session_state.generated_os_data = preview_data
                st.success("Minuta da OS gerada com sucesso!")
    
    if 'generated_os_pdf' in st.session_state:
        os_data = st.session_state.generated_os_data
        st.download_button(
            label="⬇️ Descarregar OS em PDF",
            data=st.session_state.generated_os_pdf,
            file_name=f"OS_{os_data['layout_name'].replace(' ', '_')}.pdf",
            mime="application/pdf"
        )