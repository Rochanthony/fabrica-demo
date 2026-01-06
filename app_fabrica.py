import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 4.0", layout="wide")

# --- 1. GERENCIAMENTO DE BANCO DE DADOS (NOVA ESTRUTURA) ---

def init_db():
    """Inicializa o banco com tabelas completas para substituir o Excel"""
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    
    # 1. Tabela Histórico (Mantida)
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
    
    # 2. Tabela Materiais (Agora guarda Custo e Estoque juntos)
    c.execute('''
        CREATE TABLE IF NOT EXISTS materiais (
            nome TEXT PRIMARY KEY,
            custo REAL,
            estoque REAL
        )
    ''')

    # 3. Tabela Receitas (Substitui a aba Receitas do Excel)
    c.execute('''
        CREATE TABLE IF NOT EXISTS receitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_produto TEXT,
            ingrediente TEXT,
            qtd_teorica REAL,
            FOREIGN KEY(ingrediente) REFERENCES materiais(nome)
        )
    ''')
    
    conn.commit()
    conn.close()

def popular_dados_iniciais():
    """Popula o banco com dados de teste se estiver vazio (Bootstrapping)"""
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    
    # Verifica se tem materiais
    c.execute("SELECT count(*) FROM materiais")
    if c.fetchone()[0] == 0:
        # Cria materiais padrão
        materiais = [
            ('Resina', 15.0, 1000.0),
            ('Solvente', 8.5, 800.0),
            ('Pigmento', 25.0, 200.0),
            ('Aditivo', 45.0, 100.0)
        ]
        c.executemany("INSERT INTO materiais (nome, custo, estoque) VALUES (?, ?, ?)", materiais)
        
        # Cria uma receita padrão (Tinta Base)
        receita = [
            ('Tinta Base', 'Resina', 60.0),
            ('Tinta Base', 'Solvente', 30.0),
            ('Tinta Base', 'Pigmento', 10.0)
        ]
        c.executemany("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", receita)
        
        conn.commit()
    conn.close()

# --- FUNÇÕES DE OPERAÇÃO ---

def get_materiais_db():
    conn = sqlite3.connect('fabrica.db')
    df = pd.read_sql("SELECT * FROM materiais", conn)
    conn.close()
    return df

def get_receita_produto(nome_produto):
    conn = sqlite3.connect('fabrica.db')
    query = """
    SELECT r.ingrediente, r.qtd_teorica, m.custo 
    FROM receitas r
    JOIN materiais m ON r.ingrediente = m.nome
    WHERE r.nome_produto = ?
    """
    df = pd.read_sql_query(query, conn, params=(nome_produto,))
    conn.close()
    return df

def get_lista_produtos():
    conn = sqlite3.connect('fabrica.db')
    produtos = pd.read_sql("SELECT DISTINCT nome_produto FROM receitas", conn)
    conn.close()
    return produtos['nome_produto'].tolist()

def baixar_estoque(consumo_real):
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        for material, qtd in consumo_real.items():
            c.execute("UPDATE materiais SET estoque = estoque - ? WHERE nome = ?", (qtd, material))
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

# --- FUNÇÕES DE CADASTRO (NOVO) ---
def cadastrar_material(nome, custo, estoque_inicial):
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO materiais (nome, custo, estoque) VALUES (?, ?, ?)", (nome, custo, estoque_inicial))
        conn.commit()
        return True, "Material cadastrado!"
    except sqlite3.IntegrityError:
        return False, "Material já existe!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def adicionar_ingrediente_receita(produto, ingrediente, qtd):
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", (produto, ingrediente, qtd))
        conn.commit()
        return True, "Ingrediente adicionado!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# --- INICIALIZAÇÃO ---
init_db()
popular_dados_iniciais() # Cria dados fictícios se o banco for novo

# --- FRONTEND ---
st.title("🏭 Fabrica 4.0 - ERP Integrado")
aba_operacao, aba_estoque, aba_gestao, aba_cadastros = st.tabs(["🔨 Produção", "📦 Estoque", "📈 Gestão", "⚙️ Cadastros"])

# --- ABA 1: PRODUÇÃO (Refatorada para ler do SQL) ---
with aba_operacao:
    col_config, col_simulacao = st.columns([1, 2])
    
    lista_produtos = get_lista_produtos()
    
    with col_config:
        st.subheader("Setup")
        operador = st.text_input("Operador", value="João Silva")
        
        if lista_produtos:
            produto_selecionado = st.selectbox("Selecione o Produto", lista_produtos)
        else:
            st.warning("Nenhum produto cadastrado. Vá em 'Cadastros'.")
            st.stop()

    with col_simulacao:
        st.subheader(f"Ordem: {produto_selecionado}")
        
        # Puxa a receita do banco
        df_receita = get_receita_produto(produto_selecionado)
        
        if df_receita.empty:
            st.warning("Este produto não tem ingredientes cadastrados.")
        else:
            consumo_real = {}
            custo_planejado = 0
            custo_real = 0
            
            # Loop pelos ingredientes vindos do SQL
            for index, row in df_receita.iterrows():
                ingrediente = row['ingrediente']
                qtd_meta = row['qtd_teorica']
                custo_unit = row['custo']
                
                custo_item_meta = qtd_meta * custo_unit
                custo_planejado += custo_item_meta
                
                c1, c2 = st.columns([2, 1])
                c1.markdown(f"**{ingrediente}** (Meta: {qtd_meta}kg)")
                
                qtd_digitada = c2.number_input(
                    f"Real ({ingrediente})", 
                    value=float(qtd_meta), step=0.1, key=f"in_{ingrediente}"
                )
                
                custo_real += (qtd_digitada * custo_unit)
                consumo_real[ingrediente] = qtd_digitada
            
            st.divider()
            
            dif = custo_planejado - custo_real
            k1, k2, k3 = st.columns(3)
            k1.metric("Planejado", f"R$ {custo_planejado:.2f}")
            k2.metric("Realizado", f"R$ {custo_real:.2f}", delta=f"{dif:.2f}")
            
            if dif >= 0:
                k3.success("✅ OK")
            else:
                k3.error("🚨 DESVIO")
                
            if st.button("💾 ENCERRAR ORDEM", type="primary"):
                salvar_historico(operador, produto_selecionado, custo_planejado, custo_real, dif)
                sucesso, msg = baixar_estoque(consumo_real)
                if sucesso:
                    st.toast("Produção registrada e Estoque baixado!", icon="🏭")
                else:
                    st.error(msg)
                time.sleep(1.5)
                st.rerun()

# --- ABA 2: ESTOQUE ---
with aba_estoque:
    st.header("Monitoramento de Tanques")
    
    df_estoque = get_materiais_db()
    
    if not df_estoque.empty:
        # Alerta
        criticos = df_estoque[df_estoque['estoque'] < 300]
        if not criticos.empty:
            st.error(f"🚨 {len(criticos)} materiais abaixo do nível mínimo!")
            
        st.dataframe(
            df_estoque[['nome', 'custo', 'estoque']],
            use_container_width=True,
            column_config={
                "estoque": st.column_config.ProgressColumn(
                    "Estoque (Kg)", format="%.1f kg", min_value=0, max_value=2000
                ),
                "custo": st.column_config.NumberColumn("Custo/Kg", format="R$ %.2f")
            },
            hide_index=True
        )
    else:
        st.info("Nenhum material cadastrado.")

# --- ABA 3: GESTÃO ---
with aba_gestao:
    st.header("KPIs Financeiros")
    conn = sqlite3.connect('fabrica.db')
    try:
        df_hist = pd.read_sql_query("SELECT * FROM historico", conn)
    except:
        df_hist = pd.DataFrame()
    conn.close()
    
    if not df_hist.empty:
        kp1, kp2, kp3 = st.columns(3)
        kp1.metric("Ordens Produzidas", len(df_hist))
        kp2.metric("Performance Financeira", f"R$ {df_hist['diferenca'].sum():.2f}")
        kp3.metric("Último Lote", pd.to_datetime(df_hist['data']).max())
        st.dataframe(df_hist, use_container_width=True)
    else:
        st.info("Sem dados históricos.")

# --- ABA 4: CADASTROS (A NOVIDADE) ---
with aba_cadastros:
    st.header("⚙️ Central de Cadastros")
    
    tab_mat, tab_rec = st.tabs(["Novo Material", "Nova Receita"])
    
    # 1. Cadastro de Materiais
    with tab_mat:
        st.caption("Cadastre matérias-primas que chegam no estoque.")
        with st.form("form_material"):
            novo_nome = st.text_input("Nome do Material (Ex: Resina Epóxi)")
            novo_custo = st.number_input("Custo por Kg (R$)", min_value=0.01)
            novo_estoque = st.number_input("Estoque Inicial (Kg)", min_value=0.0)
            
            if st.form_submit_button("💾 Salvar Material"):
                if novo_nome:
                    ok, msg = cadastrar_material(novo_nome, novo_custo, novo_estoque)
                    if ok:
                        st.success(f"Material '{novo_nome}' cadastrado!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.warning("Preencha o nome.")

    # 2. Cadastro de Receitas
    with tab_rec:
        st.caption("Crie produtos combinando materiais existentes.")
        
        # Passo 1: Definir ou Escolher Produto
        col_p1, col_p2 = st.columns(2)
        prod_existentes = get_lista_produtos()
        
        with col_p1:
            prod_novo = st.text_input("Criar Novo Produto (Nome)")
        with col_p2:
            prod_sel = st.selectbox("Ou editar existente:", ["Selecione..."] + prod_existentes)
        
        produto_ativo = prod_novo if prod_novo else (prod_sel if prod_sel != "Selecione..." else None)
        
        if produto_ativo:
            st.divider()
            st.subheader(f"Editando: {produto_ativo}")
            
            # Adicionar Ingrediente
            df_mats = get_materiais_db()
            if not df_mats.empty:
                c1, c2, c3 = st.columns([2,1,1])
                ingrediente_escolhido = c1.selectbox("Escolha o Ingrediente", df_mats['nome'].unique())
                qtd_receita = c2.number_input("Qtd na Receita (Kg)", min_value=0.1)
                
                if c3.button("➕ Adicionar"):
                    ok, msg = adicionar_ingrediente_receita(produto_ativo, ingrediente_escolhido, qtd_receita)
                    if ok:
                        st.success("Ingrediente adicionado!")
                        time.sleep(0.5)
                        st.rerun()
            
            # Mostrar Receita Atual
            st.markdown("### Composição Atual:")
            receita_atual = get_receita_produto(produto_ativo)
            if not receita_atual.empty:
                st.table(receita_atual)
            else:
                st.info("Nenhum ingrediente adicionado ainda.")
