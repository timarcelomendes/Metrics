import pymongo
import bcrypt
import getpass

# --- Cole aqui as suas configurações e funções ---

# Substitua pela sua string de conexão real do MongoDB
MONGO_URI = "mongodb+srv://timarcelomendes:B%40wzi280@cluster0.yjxkbq2.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "dashboard_metrics"

def verify_password(plain_password, hashed_password):
    """Verifica uma senha usando bcrypt, com o truncamento."""
    password_bytes = plain_password.encode('utf-8')
    # Aplicando o truncamento para consistência
    truncated_bytes = password_bytes[:72]
    hashed_password_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(truncated_bytes, hashed_password_bytes)

# --- Fim da secção de cópia ---

def run_check():
    """Função principal para executar a verificação."""
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client[DB_NAME]
        users_collection = db["users"]
        print("✅ Conexão com o MongoDB estabelecida com sucesso.")
    except Exception as e:
        print(f"❌ Erro ao conectar ao MongoDB: {e}")
        return

    email = input("Digite o seu e-mail de login: ")
    password = getpass.getpass("Digite a sua senha: ")

    print("\n--- A INICIAR VERIFICAÇÃO ---")

    # 1. Procurar o utilizador
    user_data = users_collection.find_one({'email': email})

    if not user_data:
        print(f"❌ RESULTADO: Utilizador com o e-mail '{email}' não foi encontrado na base de dados.")
        print("   Verifique se o e-mail está escrito corretamente.")
        return
    
    print(f"✔️ Utilizador '{email}' encontrado na base de dados.")

    # 2. Verificar a senha
    stored_hashed_password = user_data.get('hashed_password')
    if not stored_hashed_password:
        print("❌ ERRO: O utilizador encontrado não possui uma senha guardada (campo 'hashed_password' está vazio).")
        return

    print("   A verificar a correspondência da senha...")

    # Usamos a função verify_password do seu ficheiro security.py
    is_valid = verify_password(password, stored_hashed_password)

    if is_valid:
        print("✅ RESULTADO: SUCESSO! A senha corresponde.")
        print("   Isto significa que a lógica de verificação está correta, mas algo no Streamlit está a interferir.")
    else:
        print("❌ RESULTADO: FALHA. A senha não corresponde ao que está guardado.")
        print("   Isto confirma que há uma incompatibilidade entre como a senha foi guardada e como está a ser verificada.")

if __name__ == "__main__":
    run_check()