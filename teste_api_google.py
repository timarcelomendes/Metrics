import google.generativeai as genai

# --- INSTRUÇÕES ---
# 1. Cole a sua chave de API do Google AI diretamente na linha abaixo.
# 2. Salve o ficheiro.
# 3. Execute o script no seu terminal com: python teste_api_google.py
# ------------------

# ▼▼▼ COLE A SUA CHAVE AQUI ▼▼▼
SUA_API_KEY = "AIzaSyAIchh0pzZVyPz3KqaX9tTlV8aPqWy6DmI"
# ▲▲▲ COLE A SUA CHAVE AQUI ▲▲▲

try:
    # --- LINHA CORRIGIDA ---
    # Agora ele verifica se a chave AINDA É o texto de exemplo original.
    if SUA_API_KEY == "COLE_SUA_CHAVE_DE_API_REAL_AQUI" or not SUA_API_KEY:
        raise ValueError("A chave de API não foi inserida no script.")

    genai.configure(api_key=SUA_API_KEY)

    print("✅ Conexão bem-sucedida! A listar modelos disponíveis para a sua chave...\n")

    model_list = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            model_list.append(m.name)

    if not model_list:
        print("⚠️ Nenhum modelo compatível foi encontrado para esta chave de API.")
        print("   Verifique se a API 'Generative Language' está ativa no seu projeto Google Cloud.")
    else:
        print("--- Modelos Compatíveis Encontrados ---")
        for model_name in sorted(model_list):
            print(f"- {model_name}")
        print("\n----------------------------------------")
        print("\n💡 Copie um dos nomes da lista acima (ex: 'gemini-1.5-flash-latest')")
        print("   e use-o no seu ficheiro utils.py, na função _get_ai_client_and_model.")
        print("   Lembre-se de remover a chave deste ficheiro após o teste por segurança!")


except Exception as e:
    print(f"\n❌ Ocorreu um erro ao testar a API: {e}")
    print("\n--- Possíveis Causas ---")
    print("1. A sua chave de API pode ser inválida, estar expirada ou ter restrições.")
    print("2. A API 'Generative Language' pode não estar ativada no seu projeto Google Cloud.")
    print("3. Pode haver um problema de rede ou firewall a bloquear a conexão com os servidores da Google.")