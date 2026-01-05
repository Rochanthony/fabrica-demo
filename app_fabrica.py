import streamlit as st
import pandas as pd
from datetime import datetime
import time
from datetime import datetime
import os
import sqlite3

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 4.0", layout="wide")

# --- SIDEBAR (Mudei apenas isto) ---
with st.sidebar:
    st.header("🏭 Painel de Controle")
    st.success("Status: Online 🟢")
    
    # Pega data e hora atual
    agora = datetime.now()
    st.write(f"📅 {agora.strftime('%d/%m/%Y')}")
    st.write(f"⏰ {agora.strftime('%H:%M')}")
    st.divider()
# -----------------------------------

# --- 1. A LÓGICA (BACKEND) ---
class Material:
    def __init__(self, nome, custo, cas, riscos):
        self.nome = nome
        self.custo = custo
        self.cas = cas
        self.riscos = riscos

class Produto:
    def __init__(self, nome):
        self.nome = nome
        self.receita_padrao = {} 

    def adicionar_ingrediente(self, material_obj, qtd):
        self.receita_padrao[material_obj.nome] = {
            'objeto': material_obj,
            'qtd_teorica': qtd
        }

@st.cache_data
def carregar_dados():
    try:
        df_mat = pd.read_excel('dados_fabrica.xlsx', sheet_name='Materiais')
        df_rec = pd.read_excel('dados_fabrica.xlsx', sheet_name='Receitas')
        
        estoque = {}
        produtos_db = {}

        for _, row in df_mat.iterrows():
            estoque[row['Nome']] = Material(row['Nome'], row['Custo_Kg'], row['CAS_Number'], row['Riscos'])

        for _, row in df_rec.iterrows():
            p_nome = row['Nome_Produto']
            m_nome = row['Material_Usado']
            qtd = row['Qtd_Receita_Kg']
            
            if p_nome not in produtos_db:
                produtos_db[p_nome] = Produto(p_nome)
            
            if m_nome in estoque:
                produtos_db[p_nome].adicionar_ingrediente(estoque[m_nome], qtd)
                
        return produtos_db, estoque
    except Exception as e:
        return None, str(e)

# --- BANCO DE DADOS SQL (NOVO) ---

def init_db():
    """Cria a tabela no banco de dados se ela não existir"""
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    # Criamos colunas para guardar exatamente o que você já usava
    c.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            operador TEXT,
            produto TEXT,
            custo_planejado REAL,
            custo_real REAL,
            diferenca REAL,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Inicia o banco assim que o código roda
init_db()

def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
    """Salva o lote dentro do arquivo fabrica.db"""
    try:
        conn = sqlite3.connect('fabrica.db')
        c = conn.cursor()
        
        # Insere os dados de forma segura
        c.execute('''
            INSERT INTO historico (data, operador, produto, custo_planejado, custo_real, diferenca, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            operador,
            produto,
            custo_planejado,
            custo_real,
            diferenca,
            "PREJUÍZO" if diferenca < 0 else "LUCRO/ECONOMIA"
        ))
        
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao salvar no banco: {e}")

# --- 2. O VISUAL (FRONTEND) ---
st.title("🏭 Monitor de Produção Inteligente")

# Navegação entre abas
aba_operacao, aba_gestao = st.tabs(["🔨 Operação (Chão de Fábrica)", "📈 Gestão (Dashboard)"])

produtos_db, erro = carregar_dados()
if erro and not produtos_db:
    st.error(f"Erro no Excel: {erro}")
    st.stop()

# --- ABA 1: OPERAÇÃO ---
with aba_operacao:
    col_config, col_simulacao = st.columns([1, 2])
    
    with col_config:
        st.subheader("Configuração da OP")
        operador = st.text_input("Nome do Operador", value="João Silva")
        produto_selecionado = st.selectbox("Produto a Produzir", list(produtos_db.keys()))
        st.info("👆 Selecione o produto e simule os gastos reais ao lado.")

    with col_simulacao:
        st.subheader(f"Execução: {produto_selecionado}")
        produto_obj = produtos_db[produto_selecionado]
        
        consumo_real_simulado = {}
        custo_planejado_total = 0
        custo_real_total = 0
        
        for nome_mp, dados in produto_obj.receita_padrao.items():
            qtd_ideal = dados['qtd_teorica']
            custo_item = qtd_ideal * dados['objeto'].custo
            custo_planejado_total += custo_item
            
            cols = st.columns([2, 1, 1])
            cols[0].markdown(f"**{nome_mp}** (Meta: {qtd_ideal}kg)")
            
            qtd_digitada = cols[1].number_input(
                f"Real ({nome_mp})", 
                value=float(qtd_ideal),
                step=0.1,
                key=f"input_{nome_mp}"
            )
            
            custo_real_item = qtd_digitada * dados['objeto'].custo
            custo_real_total += custo_real_item
            consumo_real_simulado[nome_mp] = qtd_digitada

        st.markdown("---")
        diferenca = custo_planejado_total - custo_real_total
        
        col_res1, col_res2, col_res3 = st.columns(3)
        col_res1.metric("Planejado", f"R$ {custo_planejado_total:.2f}")
        col_res2.metric("Realizado", f"R$ {custo_real_total:.2f}", delta=f"{diferenca:.2f}")
        
        if diferenca < 0:
            col_res3.error("🚨 PREJUÍZO")
        else:
            col_res3.success("✅ EFICIENTE")
            
        if st.button("💾 FINALIZAR E SALVAR LOTE", type="primary"):
            salvar_historico(operador, produto_selecionado, custo_planejado_total, custo_real_total, diferenca)
            st.toast(f"Lote de {produto_selecionado} salvo com sucesso!", icon="✅")
            time.sleep(1)
            st.rerun()

# --- ABA 2: GESTÃO (ATUALIZADO PARA SQL) ---
with aba_gestao:
    st.header("Histórico Gerencial (SQL)")
    
    # 1. Tenta ler do Banco de Dados
    conn = sqlite3.connect('fabrica.db')
    try:
        df_hist = pd.read_sql_query("SELECT * FROM historico", conn)
    except:
        df_hist = pd.DataFrame() # Se der erro ou banco vazio
    conn.close()
    
    # 2. Verifica se tem dados
    if not df_hist.empty:
        
        # Filtros
        filtro_prod = st.multiselect("Filtrar por Produto", df_hist['produto'].unique())
        if filtro_prod:
            df_hist = df_hist[df_hist['produto'].isin(filtro_prod)]
        
        # --- INDICADORES ---
        total_lotes = len(df_hist)
        saldo_geral = df_hist['diferenca'].sum()
        total_prejuizo = df_hist[df_hist['diferenca'] < 0]['diferenca'].sum()
        total_economia = df_hist[df_hist['diferenca'] > 0]['diferenca'].sum()

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Lotes Produzidos", total_lotes)
        kpi2.metric("Desperdício", f"R$ {total_prejuizo:.2f}")
        kpi3.metric("Economia", f"R$ {total_economia:.2f}")
        kpi4.metric("Saldo Geral", f"R$ {saldo_geral:.2f}", delta=f"{saldo_geral:.2f}")

        st.markdown("---")

        # --- GRÁFICOS ---
        col_graf1, col_graf2 = st.columns(2)

        with col_graf1:
            st.subheader("📈 Tendência Financeira")
            st.line_chart(df_hist['diferenca'])

        with col_graf2:
            st.subheader("📊 Planejado vs Real")
            df_agrupado = df_hist.groupby('produto')[['custo_planejado', 'custo_real']].sum()
            st.bar_chart(df_agrupado)

        st.markdown("---")
        st.subheader("📋 Tabela Completa")
        st.dataframe(df_hist, use_container_width=True)
        
    else:
        st.info("Nenhum dado encontrado no Banco SQL. Produza o primeiro lote!")
