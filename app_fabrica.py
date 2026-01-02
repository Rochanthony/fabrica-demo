import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta  # Adicionado timedelta para o fuso horário
from datetime import datetime, timedelta
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 4.0", layout="wide")

# --- BARRA LATERAL (NOVO) ---
# --- BARRA LATERAL ---
with st.sidebar:
    st.header("🏭 Fabrica 4.0")
    st.write("Sistema de Controle v1.0")
    st.write("Sistema de Controle v1.1")
    st.markdown("---")
    st.success("Status: Online")
    st.markdown("---")
    # Mostra a data atual ajustada
    # Mostra a data atual ajustada (Brasília)
    data_hoje = (datetime.now() - timedelta(hours=3)).strftime('%d/%m/%Y')
    st.caption(f"Data: {data_hoje}")
    st.caption("Desenvolvido por Você")

# --- 1. A LÓGICA (BACKEND) ---

class Material:
    def __init__(self, nome, custo, cas, riscos):
        self.nome = nome
def adicionar_ingrediente(self, material_obj, qtd):
            'qtd_teorica': qtd
        }

# --- FUNÇÃO NOVA: ALERTA DE SEGURANÇA (FDS) ---
def verificar_riscos_fds(produto_obj):
    riscos_detectados = set()
    detalhes = []

    for nome_mp, dados in produto_obj.receita_padrao.items():
        # Converte para texto e minúsculo para evitar erros com números ou vazio
        risco_txt = str(dados['objeto'].riscos).lower()
        
        if risco_txt != "nan" and risco_txt != "nenhum":
            # Mapeamento de ícones e palavras-chave
            icone = "⚠️"
            if "inflamável" in risco_txt or "inflamavel" in risco_txt:
                icone = "🔥"
                riscos_detectados.add("INFLAMÁVEL")
            elif "tóxico" in risco_txt or "toxico" in risco_txt:
                icone = "☠️"
                riscos_detectados.add("TÓXICO")
            elif "irritante" in risco_txt:
                icone = "👀"
                riscos_detectados.add("IRRITANTE")
            elif "corrosivo" in risco_txt:
                icone = "🧪"
                riscos_detectados.add("CORROSIVO")
            
            detalhes.append(f"{icone} **{nome_mp}**: {dados['objeto'].riscos}")

    return riscos_detectados, detalhes

@st.cache_data
def carregar_dados():
    try:
        # Carrega as abas do Excel
        df_mat = pd.read_excel('dados_fabrica.xlsx', sheet_name='Materiais')
        df_rec = pd.read_excel('dados_fabrica.xlsx', sheet_name='Receitas')

        estoque = {}
        produtos_db = {}

        # Cria os objetos de Material
        for _, row in df_mat.iterrows():
            estoque[row['Nome']] = Material(row['Nome'], row['Custo_Kg'], row['CAS_Number'], row['Riscos'])

        # Cria os objetos de Produto e monta a receita
        for _, row in df_rec.iterrows():
            p_nome = row['Nome_Produto']
            m_nome = row['Material_Usado']
@@ -65,11 +98,11 @@ def carregar_dados():
    except Exception as e:
        return None, str(e)

# Função para Salvar no 'Banco de Dados' (CSV)
# Função para Salvar no 'Banco de Dados' (CSV) com ajuste de hora
def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
    arquivo_db = 'historico_producao.csv'

    # AJUSTE DE FUSO HORÁRIO AQUI (UTC - 3 horas)
    # AJUSTE DE FUSO HORÁRIO (UTC - 3 horas = Brasília)
    data_hora_br = (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")

    novo_registro = {
@@ -108,12 +141,30 @@ def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
        st.subheader("Configuração da OP")
        operador = st.text_input("Nome do Operador", value="João Silva")
        produto_selecionado = st.selectbox("Produto a Produzir", list(produtos_db.keys()))
        st.info("👆 Selecione o produto e simule os gastos reais ao lado.")
        st.info("👆 Selecione o produto. O sistema alertará sobre riscos automaticamente.")

    with col_simulacao:
        st.subheader(f"Execução: {produto_selecionado}")
        produto_obj = produtos_db[produto_selecionado]

        # --- BLOCO DE SEGURANÇA (NOVO) ---
        lista_riscos, lista_detalhes = verificar_riscos_fds(produto_obj)
        
        if lista_riscos:
            if "INFLAMÁVEL" in lista_riscos or "TÓXICO" in lista_riscos:
                st.error(f"🚨 ATENÇÃO: MANUSEIO PERIGOSO ({', '.join(lista_riscos)})")
            else:
                st.warning(f"⚠️ CUIDADO: {', '.join(lista_riscos)}")
            
            with st.expander("📖 Ver Ficha de Segurança (Detalhes)"):
                for item in lista_detalhes:
                    st.markdown(item)
                st.info("Consulte a FISPQ completa antes do manuseio.")
        else:
            st.success("✅ Nenhum risco químico grave identificado nesta receita.")
        st.markdown("---")
        # ---------------------------------

        consumo_real_simulado = {}
        custo_planejado_total = 0
        custo_real_total = 0
@@ -155,7 +206,7 @@ def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
            time.sleep(1)
            st.rerun()

# --- ABA 2: GESTÃO (AGORA COM GRÁFICOS) ---
# --- ABA 2: GESTÃO ---
with aba_gestao:
    st.header("Histórico Gerencial")

@@ -167,7 +218,7 @@ def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
        if filtro_prod:
            df_hist = df_hist[df_hist['Produto'].isin(filtro_prod)]

        # 1. INDICADORES NO TOPO
        # 1. INDICADORES
        total_lotes = len(df_hist)
        total_prejuizo = df_hist[df_hist['Diferenca_R$'] < 0]['Diferenca_R$'].sum()
        total_economia = df_hist[df_hist['Diferenca_R$'] > 0]['Diferenca_R$'].sum()
@@ -181,23 +232,23 @@ def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):

        st.markdown("---")

        # 2. GRÁFICOS LADO A LADO
        # 2. GRÁFICOS
        col_graf1, col_graf2 = st.columns(2)

        with col_graf1:
            st.subheader("📈 Desempenho por Lote (Linha do Tempo)")
            st.subheader("📈 Desempenho por Lote")
            st.line_chart(df_hist['Diferenca_R$'])
            st.caption("Valores acima de 0 são Economia. Abaixo de 0 são Prejuízo.")

        with col_graf2:
            st.subheader("📊 Custo Planejado vs. Real (Por Produto)")
            st.subheader("📊 Planejado vs. Real")
            df_agrupado = df_hist.groupby('Produto')[['Custo_Planejado', 'Custo_Real']].sum()
            st.bar_chart(df_agrupado)
            st.caption("Comparativo acumulado: Azul Claro (Real) vs Azul Escuro (Planejado)")
            st.caption("Barras comparativas de custo.")

        st.markdown("---")
        st.subheader("📋 Detalhamento dos Registros")
        st.subheader("📋 Detalhamento")
        st.dataframe(df_hist, use_container_width=True)

    else:
        st.info("Nenhum dado histórico encontrado. Produza alguns lotes na aba 'Operação' para ver os gráficos!")
        st.info("Nenhum dado histórico encontrado. Produza lotes na aba Operação.")

