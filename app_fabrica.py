import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS TeCHemical v11.0", layout="wide")

# --- 0. SISTEMA DE LOGIN (SIMPLIFICADO PARA EVITAR ERROS) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><h2 style='text-align: center;'>🔐 Login Seguro</h2>", unsafe_allow_html=True)
        user = st.text_input("Usuário", placeholder="admin")
        pwd = st.text_input("Senha", type="password", placeholder="admin")
        
        if st.button("Entrar", type="primary", use_container_width=True):
            # Login padrão para evitar erro de secrets
            if user == "admin" and pwd == "admin":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    return False

if not check_password():
    st.stop()

# --- 1. GERENCIAMENTO DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    
    # Criação de Tabelas
    c.execute('''CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, operador TEXT,
            produto TEXT, custo_planejado REAL, custo_real REAL, diferenca REAL, status TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS materiais (
            nome TEXT PRIMARY KEY, custo REAL, estoque REAL, unidade TEXT, codigo TEXT, estoque_minimo REAL)''')
            
    c.execute('''CREATE TABLE IF NOT EXISTS produtos_codigos (
            nome_produto TEXT PRIMARY KEY, codigo TEXT)''')

    c.execute('''CREATE TABLE IF NOT EXISTS receitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome_produto TEXT, ingrediente TEXT,
            qtd_teorica REAL, FOREIGN KEY(ingrediente) REFERENCES materiais(nome))''')
    conn.commit()
    conn.close()

def popular_dados_iniciais():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        c.execute("SELECT count(*) FROM materiais")
        if c.fetchone()[0] == 0:
            materiais = [
                ('Resina Epóxi', 15.0, 1000.0, 'kg', 'MP-101', 300.0), 
                ('Solvente X', 8.5, 800.0, 'L', 'MP-102', 200.0), 
                ('Pigmento Azul', 25.0, 200.0, 'kg', 'MP-103', 50.0), 
                ('Aditivo Secante', 45.0, 100.0, 'L', 'MP-104', 20.0),
                ('Lata 18L', 12.0, 500.0, 'un', 'EM-001', 100.0)
            ]
            c.executemany("INSERT INTO materiais VALUES (?, ?, ?, ?, ?, ?)", materiais)
            
            # Inserção segura
            c.execute("INSERT OR IGNORE INTO produtos_codigos VALUES (?, ?)", ('Tinta Piso Premium', 'PA-500'))
            
            # A lista receita deve ser definida ANTES de usar
            receita = [
                ('Tinta Piso Premium', 'Resina Epóxi', 60.0), 
                ('Tinta Piso Premium', 'Solvente X', 30.0), 
                ('Tinta Piso Premium', 'Pigmento Azul', 10.0), 
                ('Tinta Piso Premium', 'Lata 18L', 1.0)
            ]
            c.executemany("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", receita)
            conn.commit()
    except Exception as e:
        print(f"Erro ao popular: {e}")
    finally: 
        conn.close()

# --- FUNÇÕES AUXILIARES ---
def get_materiais_db():
    conn = sqlite3.connect('fabrica.db')
    try:
        df = pd.read_sql("SELECT * FROM materiais", conn)
        cols_num = ['custo', 'estoque', 'estoque_minimo']
        for col in cols_num:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        if 'codigo' not in df.columns: df['codigo'] = '-'
    except:
        df = pd.DataFrame(columns=['nome', 'custo', 'estoque', 'unidade', 'codigo', 'estoque_minimo'])
    finally: conn.close()
    return df

def get_prod_code(nome_prod):
    conn = sqlite3.connect('fabrica.db')
    try:
        c = conn.cursor()
        c.execute("SELECT codigo FROM produtos_codigos WHERE nome_produto=?", (nome_prod,))
        res = c.fetchone()
        return res[0] if res else "S/C"
    except: return "-"
    finally: conn.close()

def save_prod_code(nome_prod, codigo):
    conn = sqlite3.connect('fabrica.db')
    try:
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO produtos_codigos (nome_produto, codigo) VALUES (?, ?)", (nome_prod, codigo))
        conn.commit()
    except: pass
    finally: conn.close()

def get_receita_produto(nome_produto):
    conn = sqlite3.connect('fabrica.db')
    try:
        query = "SELECT r.ingrediente, r.qtd_teorica, m.custo, m.unidade, m.codigo FROM receitas r JOIN materiais m ON r.ingrediente = m.nome WHERE r.nome_produto = ?"
        df = pd.read_sql_query(query, conn, params=(nome_produto,))
    except: df = pd.DataFrame()
    finally: conn.close()
    return df

def get_lista_produtos():
    conn = sqlite3.connect('fabrica.db')
    try:
        df = pd.read_sql("SELECT DISTINCT nome_produto FROM receitas", conn)
        return df['nome_produto'].tolist()
    except: return []
    finally: conn.close()

def baixar_estoque(consumo_real):
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        for material, qtd in consumo_real.items():
            c.execute("UPDATE materiais SET estoque = estoque - ? WHERE nome = ?", (float(qtd), material))
        conn.commit()
        return True, "Estoque atualizado!"
    except Exception as e: return False, str(e)
    finally: conn.close()

def salvar_historico(operador, produto, custo_plan, custo_real, diferenca):
    try:
        conn = sqlite3.connect('fabrica.db')
        c = conn.cursor()
        try: 
            fuso = pytz.timezone('America/Sao_Paulo')
            data_hora = datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
        except: 
            data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        status = "PREJUÍZO" if diferenca < 0 else "LUCRO"
        c.execute("INSERT INTO historico (data, operador, produto, custo_planejado, custo_real, diferenca, status) VALUES (?,?,?,?,?,?,?)", 
                  (data_hora, operador, produto, custo_plan, custo_real, diferenca, status))
        conn.commit()
        conn.close()
        return data_hora
    except: return None

def cadastrar_material(nome, custo, estoque, unidade, codigo, est_min):
    conn = sqlite3.connect('fabrica.db')
    try:
        conn.execute("INSERT INTO materiais VALUES (?, ?, ?, ?, ?, ?)", (str(nome), float(custo), float(estoque), str(unidade), str(codigo), float(est_min)))
        conn.commit(); conn.close(); return True, "Sucesso"
    except Exception as e: conn.close(); return False, str(e)

def adicionar_ingrediente(produto, ingrediente, qtd):
    conn = sqlite3.connect('fabrica.db')
    try:
        c = conn.cursor()
        c.execute("SELECT count(*) FROM receitas WHERE nome_produto=? AND ingrediente=?", (produto, ingrediente))
        if c.fetchone()[0] > 0:
            c.execute("UPDATE receitas SET qtd_teorica = ? WHERE nome_produto=? AND ingrediente=?", (float(qtd), produto, ingrediente))
        else:
            c.execute("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", (produto, ingrediente, float(qtd)))
        conn.commit(); conn.close(); return True, "Sucesso"
    except Exception as e: conn.close(); return False, str(e)

def gerar_pdf_lote(data, operador, produto, itens_realizados, unidades_dict, codigos_dict, custo_plan, custo_real, diferenca):
    cod_prod = get_prod_code(produto)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "RELATORIO DE PRODUCAO", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Produto: {produto} (Cod: {cod_prod})", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(0, 10, f"Data: {data}", ln=True)
    pdf.cell(0, 10, f"Operador: {operador}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(30, 10, "Cod.", 1)
    pdf.cell(60, 10, "Material", 1)
    pdf.cell(30, 10, "Qtd Real", 1)
    pdf.cell(20, 10, "Unid.", 1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 11)
    for mat, qtd in itens_realizados.items():
        uni = unidades_dict.get(mat, '-')
        cod = codigos_dict.get(mat, '-')
        try: mat_txt = str(mat).encode('latin-1', 'replace').decode('latin-1')
        except: mat_txt = str(mat)
        
        pdf.cell(30, 10, str(cod), 1)
        pdf.cell(60, 10, mat_txt, 1)
        pdf.cell(30, 10, f"{float(qtd):.2f}", 1)
        pdf.cell(20, 10, str(uni), 1)
        pdf.ln()
        
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Realizado: R$ {custo_real:.2f}", ln=True)
    
    if diferenca >= 0:
        pdf.set_text_color(0, 128, 0)
        status_txt = f"ECONOMIA: R$ {diferenca:.2f}"
    else:
        pdf.set_text_color(255, 0, 0)
        status_txt = f"PREJUIZO: R$ {diferenca:.2f}"
        
    pdf.cell(0, 10, status_txt, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- INICIALIZAÇÃO ---
init_db()
popular_dados_iniciais()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏭 Painel")
    
    try:
        fuso_br = pyt
