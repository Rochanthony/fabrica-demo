import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 5.3", layout="wide")

# --- 1. GERENCIAMENTO DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, operador TEXT,
            produto TEXT, custo_planejado REAL, custo_real REAL, diferenca REAL, status TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS materiais (
            nome TEXT PRIMARY KEY, custo REAL, estoque REAL)''')
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
            materiais = [('Resina', 15.0, 1000.0), ('Solvente', 8.5, 800.0), 
                         ('Pigmento', 25.0, 200.0), ('Aditivo', 45.0, 100.0)]
            c.executemany("INSERT INTO materiais VALUES (?, ?, ?)", materiais)
            receita = [('Tinta Base', 'Resina', 60.0), ('Tinta Base', 'Solvente', 30.0), ('Tinta Base', 'Pigmento', 10.0)]
            c.executemany("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", receita)
            conn.commit()
    except: pass
    finally: conn.close()

# --- FUNÇÕES DE LEITURA/ESCRITA ---
def get_materiais_db():
    conn = sqlite3.connect('fabrica.db')
    df = pd.read_sql("SELECT * FROM materiais", conn)
    conn.close()
    return df

def get_receita_produto(nome_produto):
    conn = sqlite3.connect('fabrica.db')
    query = """SELECT r.ingrediente, r.qtd_teorica, m.custo FROM receitas r
               JOIN materiais m ON r.ingrediente = m.nome WHERE r.nome_produto = ?"""
    df = pd.read_sql_query(query, conn, params=(nome_produto,))
    conn.close()
    return df

def get_lista_produtos():
    conn = sqlite3.connect('fabrica.db')
    df = pd.read_sql("SELECT DISTINCT nome_produto FROM receitas", conn)
    conn.close()
    return df['nome_produto'].tolist()

def baixar_estoque(consumo_real):
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        for material, qtd in consumo_real.items():
            c.execute("UPDATE materiais SET estoque = estoque - ? WHERE nome = ?", (qtd, material))
        conn.commit()
        return True, "Estoque atualizado!"
    except Exception as e: return False, str(e)
    finally: conn.close()

def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
    try:
        conn = sqlite3.connect('fabrica.db')
        c = conn.cursor()
        try: fuso = pytz.timezone('America/Sao_Paulo')
        except: fuso = pytz.utc
        data_hora = datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
        status = "PREJUÍZO" if diferenca < 0 else "LUCRO"
        c.execute("INSERT INTO historico (data, operador, produto, custo_planejado, custo_real, diferenca, status) VALUES (?,?,?,?,?,?,?)",
                  (data_hora, operador, produto, custo_planejado, custo_real, diferenca, status))
        conn.commit()
        conn.close()
        return data_hora
    except Exception as e: return None

# --- NOVAS FUNÇÕES DE EDIÇÃO ---
def cadastrar_material(nome, custo, estoque):
    conn = sqlite3.connect('fabrica.db')
    try:
        conn.execute("INSERT INTO materiais VALUES (?, ?, ?)", (nome, custo, estoque))
        conn.commit(); conn.close(); return True, "Sucesso"
    except Exception as e: conn.close(); return False, str(e)

def atualizar_material_db(nome, novo_custo, novo_estoque):
    conn = sqlite3.connect('fabrica.db')
    try:
        conn.execute("UPDATE materiais SET custo = ?, estoque = ? WHERE nome = ?", (novo_custo, novo_estoque, nome))
        conn.commit(); conn.close(); return True, "Atualizado"
    except Exception as e: conn.close(); return False, str(e)

def adicionar_ingrediente(produto, ingrediente, qtd):
    conn = sqlite3.connect('fabrica.db')
    try:
        # Verifica se já existe para atualizar ou inserir novo
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM receitas WHERE nome_produto=? AND ingrediente=?", (produto, ingrediente))
        exists = cursor.fetchone()[0]
        
        if exists > 0:
            cursor.execute("UPDATE receitas SET qtd_teorica = ? WHERE nome_produto=? AND ingrediente=?", (qtd, produto, ingrediente))
        else:
            cursor.execute("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", (produto, ingrediente, qtd))
        
        conn.commit(); conn.close(); return True, "Sucesso"
    except Exception as e: conn.close(); return False, str(e)

# --- PDF GENERATOR ---
def gerar_pdf_lote(data, operador, produto, itens_realizados, custo_plan, custo_real, diferenca):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"RELATÓRIO DE PRODUÇÃO - {produto}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Data: {data}", ln=True)
    pdf.cell(0, 10, f"Operador: {operador}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(80, 10, "Material", 1); pdf.cell(60, 10, "Qtd Real (Kg)", 1); pdf.ln()
    pdf.set_font("Arial", '', 12)
    for mat, qtd in itens_realizados.items():
        try: mat_txt = mat.encode('latin-1', 'replace').decode('latin-1')
        except: mat_txt = mat
        pdf.cell(80, 10, mat_txt, 1); pdf.cell(60, 10, f"{qtd:.2f}", 1); pdf.ln()
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Financeiro", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Planejado: R$ {custo_plan:.2f}", ln=True)
    pdf.cell(0, 10, f"Realizado: R$ {custo_real:.2f}", ln=True)
    if diferenca >= 0:
        pdf.set_text_color(0, 128, 0)
        status = f"ECONOMIA: R$ {diferenca:.2f}"
    else:
        pdf.set_text_color(255, 0, 0)
        status = f"PREJUÍZO: R$ {diferenca:.2f}"
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, status, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- INICIALIZAÇÃO ---
init_db()
popular_dados_iniciais()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏭 Painel de Controle")
    agora = datetime.now()
    st.write(f"📅 {agora.strftime('%d/%m/%Y')} | ⏰ {agora.strftime('%H:%M')}")
    st.divider()
    st.info("Sistema v5.3 - Edição Total")

st.title("🏭 Fabrica 4.0 - ERP Industrial")
aba_operacao, aba_estoque, aba_gestao, aba_cadastros = st.tabs(["🔨 Produção", "📦 Estoque", "📈 Gestão", "⚙️ Cadastros"])

# --- ABA 1: PRODUÇÃO ---
with aba_operacao:
    col_config, col_simulacao = st.columns([1, 2])
    lista_produtos = get_lista_produtos()
    
    with col_config:
        st.subheader("Setup")
        operador = st.text_input("Operador", value="João Silva")
        produto_selecionado = st.selectbox("Selecione o Produto", lista_produtos) if lista_produtos else None

    with col_simulacao:
        if produto_selecionado:
            st.subheader(f"Ordem: {produto_selecionado}")
            df_receita = get_receita_produto(produto_selecionado)
            
            if not df_receita.empty:
                consumo_real = {}
                custo_planejado = 0
                custo_real = 0
                
                for index, row in df_receita.iterrows():
                    ingrediente = row['ingrediente']
                    qtd_meta = row['qtd_teorica']
                    custo_unit = row['custo']
                    custo_planejado += (qtd_meta * custo_unit)
                    
                    c1, c2 = st.columns([2, 1])
                    c1.markdown(f"**{ingrediente}** (Meta: {qtd_meta}kg)")
                    val = c2.number_input(f"Real ({ingrediente})", value=float(qtd_meta), step=0.1, key=f"in_{ingrediente}_{produto_selecionado}")
                    custo_real += (val * custo_unit)
                    consumo_real[ingrediente] = val
                
                st.divider()
                dif = custo_planejado - custo_real
                col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
                col_kpi1.metric("Custo Meta", f"R$ {custo_planejado:.2f}")
                col_kpi2.metric("C
