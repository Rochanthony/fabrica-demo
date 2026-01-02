import streamlit as st
import pandas as pd

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Fábrica 4.0",
    page_icon="🏭",
    layout="wide"
)

# --- FUNÇÃO DE CARREGAMENTO (CORRIGIDA: SEM @st.cache) ---
def carregar_dados():
    # Tenta ler o arquivo Excel. 
    # IMPORTANTE: Confirme se o nome do arquivo aqui é o mesmo que está no seu GitHub.
    # Pela sua imagem, parece ser 'dados_fabrica.xlsx' para o app principal.
    arquivo_excel = "dados_fabrica.xlsx"
    
    try:
        df = pd.read_excel(arquivo_excel)
        return df, None  # Retorna os dados e "Nenhum erro"
    except Exception as e:
        return None, str(e) # Retorna vazio e a mensagem de erro

# --- INTERFACE PRINCIPAL ---
st.title("🏭 Monitor de Produção Inteligente")
st.markdown("---")

# Carrega os dados
df, erro = carregar_dados()

# Verifica se deu erro ou se carregou certo
if erro:
    st.error(f"🚨 Erro ao carregar a planilha!")
    st.warning(f"O sistema tentou ler o arquivo: 'dados_fabrica.xlsx'. Verifique se o nome está correto no GitHub.")
    st.code(f"Detalhe do erro: {erro}")
else:
    # Se deu certo, mostra o Dashboard
    if df is not None and not df.empty:
        # Cria abas para organizar
        tab1, tab2 = st.tabs(["📊 Visão Geral", "📋 Dados Brutos"])

        with tab1:
            st.subheader("Indicadores da Fábrica")
            # Exemplo de métricas (ajuste conforme as colunas do seu Excel)
            col1, col2 = st.columns(2)
            col1.metric("Total de Registros", len(df))
            col2.metric("Status do Sistema", "Online")
            
        with tab2:
            st.subheader("Tabela de Dados")
            st.dataframe(df, use_container_width=True)
    else:
        st.info("O arquivo Excel foi lido, mas parece estar vazio.")

# --- BARRA LATERAL ---
st.sidebar.header("Navegação")
st.sidebar.info("Utilize o menu acima para acessar o **Gerador de FDS**.")
