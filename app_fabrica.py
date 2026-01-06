import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 4.0", layout="wide")

# --- 1. FUNÇÕES DE BANCO DE DADOS ---

def init_db():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    
    # Tabela Histórico
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
    
    # Tabela Estoque
    c.execute('''
        CREATE TABLE IF NOT EXISTS estoque (
            nome TEXT PRIMARY KEY,
            quantidade REAL
        )
    ''')
    
    conn.commit()
    conn.close()

def sinc_estoque_inicial(lista_materiais_excel):
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    for material in lista_materiais_excel:
        c.execute("SELECT nome FROM estoque WHERE nome = ?", (material,))
        if not c.fetchone():
            c.execute("INSERT INTO estoque (nome, quantidade) VALUES (?, ?)", (material, 1000.0))
    conn.commit()
    conn.close()

def get_estoque_dataframe():
    """Retorna o estoque como um DataFrame do Pandas para facilitar a exibição"""
    conn = sqlite3.connect('fabrica.db')
    df = pd.read_sql_query("SELECT nome as Material, quantidade as Saldo_Kg FROM estoque", conn)
    conn.close()
    return df

def baixar_estoque(consumo_real):
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        for material, qtd in consumo_real.items():
            c.execute("UPDATE estoque SET quantidade = quantidade - ? WHERE nome = ?", (qtd, material))
        conn.commit()
        return True, "Estoque atualizado!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
    try:
        conn = sqlite3.connect('fabrica.db')
        c = conn.cursor()
        try:
            fuso_br = pytz.timezone('America/Sao_Paulo')
            data_hora = datetime.now(fuso_br).strftime("%Y-%m-%d %H:%M:%S")
        except:
            data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        c.execute('''
            INSERT INTO historico (data, operador, produto, custo_planejado, custo_real, diferenca, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data_hora, operador, produto, custo_planejado, custo_real, diferenca, 
              "PREJUÍZO" if diferenca < 0 else "LUCRO/ECONOMIA"))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- INICIALIZAÇÃO ---
init_db()

# --- 2. LÓGICA DE NEGÓCIO ---
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
        if not os.path.exists('dados_fabrica.xlsx'):
            return None, None, "Excel não encontrado."

        df_mat = pd.read_excel('dados_fabrica.xlsx', sheet_name='Materiais')
        df_rec = pd.read_excel('dados_fabrica.xlsx', sheet_name='Receitas')
        
        estoque_objs = {}
        produtos_db = {}
        lista_nomes_materiais = []

        for _, row in df_mat.iterrows():
            nome_mat = row['Nome']
            estoque_objs[nome_mat] = Material(nome_mat, row['Custo_Kg'], row['CAS_Number'], row['Riscos'])
            lista_nomes_materiais.append(nome_mat)

        for _, row in df_rec.iterrows():
            p_nome = row['Nome_Produto']
            m_nome = row['Material_Usado']
            qtd = row['Qtd_Receita_Kg']
            
            if p_nome not in produtos_db:
                produtos_db[p_nome] = Produto(p_nome)
            
            if m_nome in estoque_objs:
                produtos_db[p_nome].adicionar_ingrediente(estoque_objs[m_nome], qtd)
                
        return produtos_db, estoque_objs, lista_nomes_materiais, None
    except Exception as e:
        return None, None, None, str(e)

# --- 3. FRONTEND ---

produtos_db, estoque_objs, lista_materiais, erro = carregar_dados()

if erro:
    st.error(f"Erro Crítico: {erro}")
    st.stop()

if lista_materiais:
    sinc_estoque_inicial(lista_materiais)

# SIDEBAR (Mais limpa agora)
with st.sidebar:
    st.header("🏭 Painel de Controle")
    try:
        agora = datetime.now(pytz.timezone('America/Sao_Paulo'))
    except:
        agora = datetime.now()
    st.write(f"📅 {agora.strftime('%d/%m/%Y')} | ⏰ {agora.strftime('%H:%M')}")
    st.divider()
    st.info("💡 Dica: Verifique a aba 'Estoque' para alertas de reposição.")

# TÍTULO E ABAS (Agora são 3)
st.title("🏭 Monitor de Produção Inteligente")
aba_operacao, aba_estoque, aba_gestao = st.tabs(["🔨 Operação", "📦 Estoque", "📈 Gestão"])

# --- ABA 1: OPERAÇÃO ---
with aba_operacao:
    col_config, col_simulacao = st.columns([1, 2])
    
    with col_config:
        st.subheader("Configuração")
        operador = st.text_input("Operador", value="João Silva")
        
        if produtos_db:
            produto_selecionado = st.selectbox("Produto", list(produtos_db.keys()))
        else:
            st.warning("Sem produtos.")
            st.stop()

    with col_simulacao:
        st.subheader(f"Produzindo: {produto_selecionado}")
        produto_obj = produtos_db[produto_selecionado]
        
        consumo_real = {}
        custo_planejado = 0
        custo_real = 0
        
        for nome_mp, dados in produto_obj.receita_padrao.items():
            qtd_meta = dados['qtd_teorica']
            custo_meta_item = qtd_meta * dados['objeto'].custo
            custo_planejado += custo_meta_item
            
            c1, c2 = st.columns([2, 1])
            c1.markdown(f"**{nome_mp}** (Meta: {qtd_meta}kg)")
            
            qtd_digitada = c2.number_input(
                f"Real ({nome_mp})", 
                value=float(qtd_meta), step=0.1, key=f"in_{nome_mp}"
            )
            
            custo_real_item = qtd_digitada * dados['objeto'].custo
            custo_real += custo_real_item
            consumo_real[nome_mp] = qtd_digitada

        st.divider()
        
        dif = custo_planejado - custo_real
        k1, k2, k3 = st.columns(3)
        k1.metric("Planejado", f"R$ {custo_planejado:.2f}")
        k2.metric("Realizado", f"R$ {custo_real:.2f}", delta=f"{dif:.2f}")
        
        if dif >= 0:
            k3.success("✅ OK")
        else:
            k3.error("🚨 GASTOU MAIS")
        
        if st.button("💾 FINALIZAR LOTE", type="primary"):
            salvar_historico(operador, produto_selecionado, custo_planejado, custo_real, dif)
            sucesso, msg = baixar_estoque(consumo_real)
            
            if sucesso:
                st.toast("Lote salvo e estoque atualizado!", icon="✅")
            else:
                st.error(msg)
            time.sleep(1.5)
            st.rerun()

# --- ABA 2: ESTOQUE (NOVA E MELHORADA) ---
with aba_estoque:
    st.header("📦 Controle de Almoxarifado")
    
    # Busca dados atuais
    df_estoque = get_estoque_dataframe()
    
    # LÓGICA DE ALERTA (Ponto de Reposição)
    LIMITE_ALERTA = 300 # kg
    
    # Filtra quem está abaixo do limite
    materiais_baixos = df_estoque[df_estoque['Saldo_Kg'] < LIMITE_ALERTA]
    
    col_kpi1, col_kpi2 = st.columns(2)
    col_kpi1.metric("Total de Itens Cadastrados", len(df_estoque))
    col_kpi2.metric("Itens Críticos", len(materiais_baixos), delta_color="inverse")
    
    st.divider()

    # Se tiver material acabando, mostra aviso grande
    if not materiais_baixos.empty:
        st.error(f"🚨 ATENÇÃO: {len(materiais_baixos)} materiais precisam de reposição urgente!")
        # Mostra apenas os críticos primeiro
        for index, row in materiais_baixos.iterrows():
            st.markdown(f"- **{row['Material']}**: Restam apenas **{row['Saldo_Kg']:.1f} Kg**")
        st.divider()
    
    # TABELA VISUAL
    st.subheader("Visão Geral do Estoque")
    
    # Configuração visual da tabela (Barra de progresso)
    st.dataframe(
        df_estoque,
        use_container_width=True,
        column_config={
            "Saldo_Kg": st.column_config.ProgressColumn(
                "Nível do Tanque (Kg)",
                help="Volume atual disponível",
                format="%.1f kg",
                min_value=0,
                max_value=1200, # Ajustei um máximo visual para a barra ficar bonita
            ),
        },
        hide_index=True
    )

# --- ABA 3: GESTÃO ---
with aba_gestao:
    st.header("Histórico Gerencial")
    
    conn = sqlite3.connect('fabrica.db')
    try:
        df_hist = pd.read_sql_query("SELECT * FROM historico", conn)
    except:
        df_hist = pd.DataFrame()
    conn.close()
    
    if not df_hist.empty:
        prod_filter = st.multiselect("Filtrar Produto", df_hist['produto'].unique())
        if prod_filter:
            df_hist = df_hist[df_hist['produto'].isin(prod_filter)]
            
        kp1, kp2, kp3 = st.columns(3)
        kp1.metric("Lotes", len(df_hist))
        kp2.metric("Financeiro (Economia/Prejuízo)", f"R$ {df_hist['diferenca'].sum():.2f}")
        kp3.metric("Última Produção", pd.to_datetime(df_hist['data']).max().strftime('%d/%m %H:%M'))
        
        st.divider()
        g1, g2 = st.columns(2)
        g1.subheader("Tendência")
        g1.line_chart(df_hist['diferenca'])
        g2.subheader("Custo por Produto")
        g2.bar_chart(df_hist.groupby('produto')[['custo_planejado', 'custo_real']].sum())
        
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Nenhum histórico ainda.")
