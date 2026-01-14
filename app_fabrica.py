import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# CONFIGURACAO INICIAL
st.set_page_config(page_title="SaaS TeCHemical V10", layout="wide")

# --- FUNCOES DE BANCO DE DADOS SIMPLIFICADAS ---
def get_connection():
    return sqlite3.connect('fabrica.db')

def init_db():
    conn = get_connection()
    c = conn.cursor()
    # Cria tabelas se nao existirem
    c.execute("CREATE TABLE IF NOT EXISTS historico (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, operador TEXT, produto TEXT, custo_planejado REAL, custo_real REAL, diferenca REAL, status TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS materiais (nome TEXT PRIMARY KEY, custo REAL, estoque REAL, unidade TEXT, codigo TEXT, estoque_minimo REAL)")
    c.execute("CREATE TABLE IF NOT EXISTS produtos_codigos (nome_produto TEXT PRIMARY KEY, codigo TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS receitas (id INTEGER PRIMARY KEY AUTOINCREMENT, nome_produto TEXT, ingrediente TEXT, qtd_teorica REAL)")
    conn.commit()
    conn.close()

def popular_banco_se_vazio():
    conn = get_connection()
    c = conn.cursor()
    try:
        # Verifica se tem materiais
        c.execute("SELECT count(*) FROM materiais")
        qtd = c.fetchone()[0]
        if qtd == 0:
            lista_materiais = [
                ('Resina Epoxi', 15.0, 1000.0, 'kg', 'MP-101', 300.0),
                ('Solvente X', 8.5, 800.0, 'L', 'MP-102', 200.0),
                ('Pigmento Azul', 25.0, 200.0, 'kg', 'MP-103', 50.0),
                ('Lata 18L', 12.0, 500.0, 'un', 'EM-001', 100.0)
            ]
            c.executemany("INSERT INTO materiais VALUES (?,?,?,?,?,?)", lista_materiais)
            
            # Cria Produto Padrao
            c.execute("INSERT OR IGNORE INTO produtos_codigos VALUES (?,?)", ('Tinta Piso', 'PA-500'))
            
            # Cria Receita Padrao
            lista_receita = [
                ('Tinta Piso', 'Resina Epoxi', 60.0),
                ('Tinta Piso', 'Solvente X', 30.0),
                ('Tinta Piso', 'Pigmento Azul', 10.0),
                ('Tinta Piso', 'Lata 18L', 1.0)
            ]
            c.executemany("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?,?,?)", lista_receita)
            conn.commit()
    except Exception as e:
        st.error(f"Erro ao popular: {e}")
    finally:
        conn.close()

# --- FUNCOES LOGICAS ---
def carregar_dados_materiais():
    conn = get_connection()
    try:
        df = pd.read_sql("SELECT * FROM materiais", conn)
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def pegar_receita(produto):
    conn = get_connection()
    query = """
    SELECT r.ingrediente, r.qtd_teorica, m.custo, m.unidade, m.codigo 
    FROM receitas r 
    LEFT JOIN materiais m ON r.ingrediente = m.nome 
    WHERE r.nome_produto = ?
    """
    try:
        df = pd.read_sql_query(query, conn, params=(produto,))
    except:
        df = pd.DataFrame()
    conn.close()
    return df

def salvar_producao(operador, produto, plan, real, diff):
    try:
        conn = get_connection()
        c = conn.cursor()
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "LUCRO" if diff >= 0 else "PREJUIZO"
        c.execute("INSERT INTO historico (data, operador, produto, custo_planejado, custo_real, diferenca, status) VALUES (?,?,?,?,?,?,?)", 
                 (agora, operador, produto, plan, real, diff, status))
        conn.commit()
        conn.close()
        return agora
    except:
        return None

def atualizar_estoque_banco(consumo):
    conn = get_connection()
    c = conn.cursor()
    try:
        for item, qtd in consumo.items():
            c.execute("UPDATE materiais SET estoque = estoque - ? WHERE nome = ?", (qtd, item))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

# --- EXECUCAO INICIAL ---
init_db()
popular_banco_se_vazio()

# --- INTERFACE ---
st.title("🏭 Sistema de Produção V10")

# Abas
aba1, aba2, aba3 = st.tabs(["Produção", "Estoque", "Histórico"])

with aba1:
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.subheader("Configuração")
        op_nome = st.text_input("Nome do Operador", "Joao Silva")
        
        # Carrega produtos
        conn = get_connection()
        prods = pd.read_sql("SELECT DISTINCT nome_produto FROM receitas", conn)['nome_produto'].tolist()
        conn.close()
        
        prod_sel = st.selectbox("Selecione Produto", prods) if prods else None

    with c2:
        if prod_sel:
            st.subheader(f"Ordem: {prod_sel}")
            df_rec = pegar_receita(prod_sel)
            
            if not df_rec.empty:
                custo_plan = 0.0
                custo_real = 0.0
                consumo_map = {}
                
                # Formulario de producao
                for idx, row in df_rec.iterrows():
                    ing = row['ingrediente']
                    meta = float(row['qtd_teorica'])
                    custo_u = float(row['custo']) if pd.notnull(row['custo']) else 0.0
                    unid = row['unidade']
                    
                    custo_plan += (meta * custo_u)
                    
                    col_txt, col_input = st.columns([2, 1])
                    col_txt.write(f"**{ing}** (Meta: {meta} {unid})")
                    qtd_digitada = col_input.number_input(f"Qtd Real ({ing})", value=meta, key=f"key_{ing}")
                    
                    custo_real += (qtd_digitada * custo_u)
                    consumo_map[ing] = qtd_digitada
                
                st.divider()
                dif_final = custo_plan - custo_real
                
                # Exibicao de Valores
                m1, m2, m3 = st.columns(3)
                m1.metric("Planejado", f"R$ {custo_plan:.2f}")
                m2.metric("Realizado", f"R$ {custo_real:.2f}")
                m3.metric("Diferença", f"R$ {dif_final:.2f}")
                
                if st.button("FINALIZAR ORDEM", type="primary"):
                    data_hora = salvar_producao(op_nome, prod_sel, custo_plan, custo_real, dif_final)
                    ok = atualizar_estoque_banco(consumo_map)
                    
                    if ok:
                        st.success("Produção Registrada e Estoque Atualizado!")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("Erro ao atualizar estoque.")

with aba2:
    st.header("Estoque Atual")
    df_est = carregar_dados_materiais()
    if not df_est.empty:
        st.dataframe(df_est, use_container_width=True)
    else:
        st.warning("Sem materiais cadastrados.")

with aba3:
    st.header("Histórico de Ordens")
    conn = get_connection()
    try:
        df_h = pd.read_sql("SELECT * FROM historico ORDER BY id DESC", conn)
        st.dataframe(df_h, use_container_width=True)
    except:
        st.info("Nenhum histórico ainda.")
    conn.close()
