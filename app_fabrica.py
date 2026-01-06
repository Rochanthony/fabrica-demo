import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 4.0", layout="wide")

# --- 1. FUNÇÕES DE BANCO DE DADOS (COM ESTOQUE) ---

def init_db():
    """Cria as tabelas (Histórico e Estoque) se não existirem"""
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    
    # Tabela 1: Histórico de Produção
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
    
    # Tabela 2: Estoque (NOVA)
    c.execute('''
        CREATE TABLE IF NOT EXISTS estoque (
            nome TEXT PRIMARY KEY,
            quantidade REAL
        )
    ''')
    
    conn.commit()
    conn.close()

def sinc_estoque_inicial(lista_materiais_excel):
    """
    Sincroniza o Excel com o Banco de Dados.
    Se um material do Excel não existir no Banco, cria ele com 1000kg (para teste).
    """
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    
    for material in lista_materiais_excel:
        # Tenta buscar o material no banco
        c.execute("SELECT nome FROM estoque WHERE nome = ?", (material,))
        data = c.fetchone()
        
        # Se não existir, insere com saldo inicial de 1000kg
        if not data:
            c.execute("INSERT INTO estoque (nome, quantidade) VALUES (?, ?)", (material, 1000.0))
    
    conn.commit()
    conn.close()

def get_estoque_atual():
    """Pega o saldo atual de todos os materiais para mostrar na tela"""
    conn = sqlite3.connect('fabrica.db')
    df_estoque = pd.read_sql_query("SELECT * FROM estoque", conn)
    conn.close()
    # Transforma em um dicionário para ficar fácil de usar: {'Resina': 1000, 'Xileno': 900}
    return df_estoque.set_index('nome')['quantidade'].to_dict()

def baixar_estoque(consumo_real):
    """
    Recebe {'Resina': 50.0, 'Xileno': 10.0} e abate do banco de dados.
    """
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        for material, qtd in consumo_real.items():
            c.execute("UPDATE estoque SET quantidade = quantidade - ? WHERE nome = ?", (qtd, material))
        conn.commit()
        return True, "Estoque atualizado com sucesso!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
    """Salva o lote no histórico"""
    try:
        conn = sqlite3.connect('fabrica.db')
        c = conn.cursor()
        
        # Fuso Horário
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
        st.error(f"Erro ao salvar histórico: {e}")

# --- INICIALIZAÇÃO ---
init_db()

# --- 2. LÓGICA DE NEGÓCIO (CLASSES E EXCEL) ---
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
            return None, None, "Arquivo Excel não encontrado."

        df_mat = pd.read_excel('dados_fabrica.xlsx', sheet_name='Materiais')
        df_rec = pd.read_excel('dados_fabrica.xlsx', sheet_name='Receitas')
        
        estoque_objs = {}
        produtos_db = {}
        lista_nomes_materiais = [] # Para criar o estoque no banco

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

# --- 3. FRONTEND (VISUAL) ---

# Carrega dados do Excel
produtos_db, estoque_objs, lista_materiais, erro = carregar_dados()

if erro:
    st.error(f"Erro Crítico: {erro}")
    st.stop()

# Sincroniza o Banco de Dados com os materiais do Excel (Roda sempre que abre)
if lista_materiais:
    sinc_estoque_inicial(lista_materiais)

# SIDEBAR: Painel de Controle e Estoque
with st.sidebar:
    st.header("🏭 Painel de Controle")
    
    # Relógio
    try:
        agora = datetime.now(pytz.timezone('America/Sao_Paulo'))
    except:
        agora = datetime.now()
    st.write(f"📅 {agora.strftime('%d/%m/%Y')} | ⏰ {agora.strftime('%H:%M')}")
    st.divider()
    
    # --- MONITOR DE ESTOQUE (NOVO!) ---
    st.subheader("📦 Nível de Estoque (SQL)")
    saldos = get_estoque_atual() # Busca no banco
    
    # Mostra uma tabelinha simples na lateral
    if saldos:
        df_saldo = pd.DataFrame(list(saldos.items()), columns=['Material', 'Kg'])
        st.dataframe(df_saldo, hide_index=True, use_container_width=True, height=300)
    else:
        st.warning("Estoque vazio.")

# CORPO PRINCIPAL
st.title("🏭 Monitor de Produção Inteligente")
aba_operacao, aba_gestao = st.tabs(["🔨 Operação", "📈 Gestão"])

# --- ABA 1: OPERAÇÃO ---
with aba_operacao:
    col_config, col_simulacao = st.columns([1, 2])
    
    with col_config:
        st.subheader("Configuração")
        operador = st.text_input("Operador", value="João Silva")
        
        if produtos_db:
            produto_selecionado = st.selectbox("Produto", list(produtos_db.keys()))
            st.info("O estoque será descontado automaticamente ao salvar.")
        else:
            st.warning("Sem produtos cadastrados.")
            st.stop()

    with col_simulacao:
        st.subheader(f"Produzindo: {produto_selecionado}")
        produto_obj = produtos_db[produto_selecionado]
        
        consumo_real = {}
        custo_planejado = 0
        custo_real = 0
        
        # Formulário de Pesagem
        for nome_mp, dados in produto_obj.receita_padrao.items():
            qtd_meta = dados['qtd_teorica']
            custo_meta_item = qtd_meta * dados['objeto'].custo
            custo_planejado += custo_meta_item
            
            c1, c2 = st.columns([2, 1])
            c1.markdown(f"**{nome_mp}** (Meta: {qtd_meta}kg)")
            
            # Input de quantidade real
            qtd_digitada = c2.number_input(
                f"Real ({nome_mp})", 
                value=float(qtd_meta), step=0.1, key=f"in_{nome_mp}"
            )
            
            custo_real_item = qtd_digitada * dados['objeto'].custo
            custo_real += custo_real_item
            consumo_real[nome_mp] = qtd_digitada

        st.divider()
        
        # Totais
        dif = custo_planejado - custo_real
        k1, k2, k3 = st.columns(3)
        k1.metric("Planejado", f"R$ {custo_planejado:.2f}")
        k2.metric("Realizado", f"R$ {custo_real:.2f}", delta=f"{dif:.2f}")
        
        # CORREÇÃO AQUI (IF/ELSE TRADICIONAL)
        if dif >= 0:
            k3.success("✅ OK")
        else:
            k3.error("🚨 GASTOU MAIS")
        
        # BOTÃO SALVAR (A MÁGICA ACONTECE AQUI)
        if st.button("💾 FINALIZAR LOTE (BAIXAR ESTOQUE)", type="primary"):
            # 1. Salva Histórico
            salvar_historico(operador, produto_selecionado, custo_planejado, custo_real, dif)
            
            # 2. Baixa Estoque
            sucesso, msg_estoque = baixar_estoque(consumo_real)
            
            if sucesso:
                st.toast(f"Lote salvo e Estoque atualizado!", icon="📉")
            else:
                st.error(f"Erro no estoque: {msg_estoque}")
                
            time.sleep(1.5)
            st.rerun()

# --- ABA 2: GESTÃO ---
with aba_gestao:
    st.header("Histórico Gerencial")
    
    conn = sqlite3.connect('fabrica.db')
    try:
        df_hist = pd.read_sql_query("SELECT * FROM historico", conn)
    except:
        df_hist = pd.DataFrame()
    conn.close()
    
    if not df_hist.empty:
        # Filtros e KPIs
        prod_filter = st.multiselect("Filtrar Produto", df_hist['produto'].unique())
        if prod_filter:
            df_hist = df_hist[df_hist['produto'].isin(prod_filter)]
            
        kp1, kp2, kp3 = st.columns(3)
        kp1.metric("Lotes", len(df_hist))
        kp2.metric("Saldo Financeiro", f"R$ {df_hist['diferenca'].sum():.2f}")
        kp3.metric("Última Produção", pd.to_datetime(df_hist['data']).max().strftime('%d/%m %H:%M'))
        
        st.divider()
        
        g1, g2 = st.columns(2)
        g1.subheader("Tendência (R$)")
        g1.line_chart(df_hist['diferenca'])
        
        g2.subheader("Comparativo Custo")
        g2.bar_chart(df_hist.groupby('produto')[['custo_planejado', 'custo_real']].sum())
        
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Nenhum histórico ainda.")
