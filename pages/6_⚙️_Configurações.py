# pages/6_⚙️_Configurações.py

import streamlit as st
from security import get_global_configs, save_global_configs, get_project_config, save_project_config, get_project_configs_collection
from config import DEFAULT_INITIAL_STATES, DEFAULT_DONE_STATES
from pathlib import Path


st.set_page_config(page_title="Configurações Globais", page_icon="⚙️", layout="wide")

st.markdown("""
<style>
/* Alinha os itens dentro de um st.columns pela base (útil para botões ao lado de inputs) */
[data-testid="stHorizontalBlock"] {
    align-items: center;
}
</style>
""", unsafe_allow_html=True)

st.header("⚙️ Configurações da Aplicação", divider='rainbow')

if 'email' not in st.session_state:
    st.warning("⚠️ Por favor, faça login para aceder a esta página."); st.page_link("1_🔑_Login.py", label="Ir para Login", icon="🔑"); st.stop()

with st.sidebar:
    project_root = Path(__file__).parent.parent
    logo_path = project_root / "images" / "gauge-logo.svg"
    try:
        st.logo(
            logo_path, 
            size="large")
    except FileNotFoundError:
        st.write("Gauge Metrics") 

    st.markdown(f"Logado como: **{st.session_state.get('email', '')}**")

    if st.button("Logout", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.switch_page("1_🔑_Login.py")

configs = get_global_configs()
projects = st.session_state.get('projects', {})

tab_campos, tab_metricas, tab_projetos = st.tabs(["Gestão de Campos Globais", "Configurações de Métricas", "Configurações por Projeto"])

with tab_campos:
    st.subheader("Campos Disponíveis para Toda a Aplicação")
    
    # --- Gestão de Campos Padrão em um container próprio ---
    with st.container(border=True):
        st.markdown("**Campos Padrão do Jira**")
        st.caption("Adicione ou remova os campos padrão que os utilizadores poderão ativar nas suas configurações pessoais.")
        available_fields = configs.get('available_standard_fields', {})
        with st.form("new_std_field_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            new_name = f_col1.text_input("Nome Amigável", placeholder="Ex: Data de Vencimento")
            new_id = f_col2.text_input("ID do Atributo", placeholder="Ex: duedate")
            new_type = f_col3.selectbox("Tipo de Dado", ["Texto", "Data"], key="new_std_type")
            if st.form_submit_button("➕ Adicionar Campo Padrão", use_container_width=True):
                if new_name and new_id:
                    available_fields[new_name] = {'id': new_id, 'type': new_type}
                    configs['available_standard_fields'] = available_fields
                    save_global_configs(configs); st.success(f"Campo '{new_name}' adicionado!"); st.rerun()
                else: st.error("Nome e ID são obrigatórios.")

        if available_fields:
            st.markdown("---"); st.markdown("**Campos Atuais:**")
            c1, c2, c3, c4 = st.columns([3, 3, 2, 1]); c1.caption("Nome"); c2.caption("ID"); c3.caption("Tipo"); c4.caption("Ação")
            for name, details in list(available_fields.items()):
                disp_col1, disp_col2, disp_col3, disp_col4 = st.columns([3, 3, 2, 1])
                disp_col1.text_input("Nome", value=name, key=f"name_std_{details.get('id')}", disabled=True, label_visibility="collapsed")
                disp_col2.text_input("ID", value=details.get('id', 'N/A'), key=f"id_std_{details.get('id')}", disabled=True, label_visibility="collapsed")
                disp_col3.text_input("Tipo", value=details.get('type', 'N/A'), key=f"type_std_{details.get('id')}", disabled=True, label_visibility="collapsed")
                if disp_col4.button("❌", key=f"del_std_{details.get('id')}", help=f"Remover '{name}'", use_container_width=True):
                    del available_fields[name]; configs['available_standard_fields'] = available_fields
                    save_global_configs(configs); st.success(f"Campo '{name}' removido!"); st.rerun()
    
    st.divider() # Divisor visual entre as secções

    # --- Gestão de Campos Personalizados em um container próprio ---
    with st.container(border=True):
        st.markdown("**Campos Personalizados (Custom Fields)**")
        st.caption("Adicione campos específicos do seu Jira (ex: Story Points).")
        custom_fields = configs.get('custom_fields', [])
        with st.form("new_custom_field_form", clear_on_submit=True):
            f_col1, f_col2, f_col3 = st.columns(3)
            new_name = f_col1.text_input("Nome do Campo", placeholder="Ex: Story Points")
            new_id = f_col2.text_input("ID do Campo", placeholder="Ex: customfield_10016")
            new_type = f_col3.selectbox("Tipo de Dado", ["Número", "Texto", "Data"], key="new_custom_type")
            if st.form_submit_button("➕ Adicionar Campo Personalizado", use_container_width=True):
                if new_name and new_id:
                    if any(f['id'] == new_id for f in custom_fields): st.error(f"O ID '{new_id}' já existe.")
                    else: custom_fields.append({'name': new_name, 'id': new_id, 'type': new_type}); configs['custom_fields'] = custom_fields; save_global_configs(configs); st.success(f"Campo '{new_name}' adicionado!"); st.rerun()
                else: st.error("Por favor, preencha o Nome e o ID.")
        if custom_fields:
            st.markdown("---"); st.markdown("**Campos Atuais:**")
            c1, c2, c3, c4 = st.columns([3, 3, 2, 1]); c1.caption("Nome"); c2.caption("ID"); c3.caption("Tipo"); c4.caption("Ação")
            for i, field in enumerate(custom_fields):
                disp_col1, disp_col2, disp_col3, disp_col4 = st.columns([3, 3, 2, 1])
                disp_col1.text_input("Nome", value=field['name'], key=f"name_custom_{i}", disabled=True, label_visibility="collapsed")
                disp_col2.text_input("ID", value=field['id'], key=f"id_custom_{i}", disabled=True, label_visibility="collapsed")
                disp_col3.text_input("Tipo", value=field.get('type', 'N/A'), key=f"type_custom_{i}", disabled=True, label_visibility="collapsed")
                if disp_col4.button("❌", key=f"del_custom_{field['id']}", help=f"Remover '{field['name']}'", use_container_width=True):
                    custom_fields.pop(i); configs['custom_fields'] = custom_fields; save_global_configs(configs); st.rerun()

with tab_metricas:
    with st.container(border=True):
        st.subheader("🔁 Mapeamento de Status do Workflow")
        st.caption("Esta configuração é **global** e afeta como o Cycle Time e o CFD são calculados para todos.")
        status_mapping = configs.get('status_mapping', {}); col1, col2 = st.columns(2)
        initial_states_str = col1.text_area("Status Iniciais (separados por vírgula)", value=", ".join(status_mapping.get('initial', DEFAULT_INITIAL_STATES)))
        done_states_str = col2.text_area("Status Finais (separados por vírgula)", value=", ".join(status_mapping.get('done', DEFAULT_DONE_STATES)))
        if st.button("Salvar Mapeamento de Status", use_container_width=True):
            configs['status_mapping'] = {'initial': [s.strip().lower() for s in initial_states_str.split(',') if s.strip()], 'done': [s.strip().lower() for s in done_states_str.split(',') if s.strip()]}
            save_global_configs(configs); st.success("Mapeamento guardado!"); st.rerun()
    with st.container(border=True):
        st.subheader("🎯 Parâmetros de Análise Scrum")
        st.markdown("**Taxa de Sucesso do Objetivo da Sprint**")
        st.caption("Defina o percentual mínimo de previsibilidade para uma sprint ser considerada um 'sucesso'.")
        threshold = st.slider("Percentual Mínimo (%)", 50, 100, configs.get('sprint_goal_threshold', 90), 5)
        if st.button("Salvar Parâmetro de Sucesso", use_container_width=True):
            configs['sprint_goal_threshold'] = threshold
            save_global_configs(configs); st.success("Parâmetro de sucesso guardado!")

with tab_projetos:
    st.subheader("Configurações Específicas por Projeto")
    project_names = list(projects.keys())
    
    if not project_names:
        st.warning("Nenhum projeto encontrado. Conecte-se a uma conta Jira com projetos para configurar.")
    else:
        selected_project_name = st.selectbox("Selecione um projeto para configurar:", options=project_names)
        project_key = projects[selected_project_name]
        project_config = get_project_config(project_key) or {}

        with st.container(border=True):
            st.markdown(f"**Campo de Estimativa para o Projeto '{selected_project_name}'**")
            st.caption("Este campo será usado para cálculos de Velocidade, Burndown e Burnup neste projeto.")
            
            # --- LÓGICA DE OPÇÕES CORRIGIDA ---
            custom_fields = configs.get('custom_fields', [])
            numeric_custom_fields = {field['name']: {'id': field['id'], 'source': 'custom'} for field in custom_fields if field.get('type') == 'Número'}
            
            standard_time_fields = {
                "Estimativa Original (Horas)": {'id': 'timeoriginalestimate', 'source': 'standard_time'},
                "Tempo Gasto (Horas)": {'id': 'timespent', 'source': 'standard_time'}
            }
            
            # Combina todas as opções de estimativa
            all_estimation_options = {**numeric_custom_fields, **standard_time_fields}
            
            options = ["Nenhum (usar contagem de issues)"] + list(all_estimation_options.keys())
            
            saved_estimation_field = project_config.get('estimation_field', {})
            saved_field_name = saved_estimation_field.get('name')
            default_index = options.index(saved_field_name) if saved_field_name in options else 0

            selected_field_name = st.selectbox(
                "Selecione o Campo para Pontos/Estimativa:", 
                options=options, 
                index=default_index,
                key=f"select_est_{project_key}"
            )

            if st.button(f"Salvar Campo de Estimativa para {selected_project_name}", use_container_width=True):
                if selected_field_name == "Nenhum (usar contagem de issues)":
                    project_config['estimation_field'] = {}
                else:
                    project_config['estimation_field'] = {
                        'name': selected_field_name,
                        'id': all_estimation_options[selected_field_name]['id'],
                        'source': all_estimation_options[selected_field_name]['source']
                    }
                save_project_config(project_key, project_config)
                st.success("Configuração do projeto guardada!")
                st.rerun()
        
        # --- NOVA SECÇÃO DE RESUMO ---
        st.divider()
        st.subheader("Resumo das Configurações Atuais")
        
        all_project_configs_cursor = get_project_configs_collection().find({})
        all_project_configs = {p['_id']: p for p in all_project_configs_cursor}
        
        summary_data = []
        for name, key in projects.items():
            config = all_project_configs.get(key, {})
            est_field = config.get('estimation_field', {}).get('name', 'Nenhum / Contagem')
            summary_data.append({
                "Projeto": name,
                "Campo de Estimativa Configurado": est_field
            })
            
        st.dataframe(summary_data, use_container_width=True, hide_index=True)