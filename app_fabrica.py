import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS TeCHemical v5.5", layout="wide")

# --- 1. GERENCIAMENTO DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    # Tabela Histórico
    c.execute('''CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, operador TEXT,
            produto TEXT, custo_planejado REAL, custo_real REAL, diferenca REAL, status TEXT)''')
    # Tabela Materiais
    c.execute('''CREATE TABLE IF NOT EXISTS materiais (
            nome TEXT PRIMARY KEY, custo REAL, estoque REAL)''')
    # Tabela Receitas
    c.execute('''CREATE TABLE IF NOT EXISTS receitas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome_produto TEXT, ingrediente TEXT,
            qtd_teorica REAL, FOREIGN KEY(ingrediente) REFERENCES materiais(nome))''')
    conn.commit()
    conn.close()

def popular_dados_iniciais():
    # Só popula se o banco estiver vazio
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        c.execute("SELECT count(*) FROM materiais")
        if c.fetchone()[0] == 0:
            # Dados padrão para teste
            materiais = [
                ('Resina', 15.0, 1000.0), 
                ('Solvente', 8.5, 800.0), 
                ('Pigmento', 25.0, 200.0), 
                ('Aditivo', 45.0, 100.0)
            ]
            c.executemany("INSERT INTO materiais VALUES (?, ?, ?)", materiais)
            
            # Receita Padrão
            receita = [
                ('Tinta Base', 'Resina', 60.0), 
                ('Tinta Base', 'Solvente', 30.0), 
                ('Tinta Base', 'Pigmento', 10.0)
            ]
            c.executemany("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", receita)
            conn.commit()
    except: pass
    finally: conn.close()

# --- FUNÇÕES DE LEITURA/ESCRITA ---
def get_materiais_db():
    conn = sqlite3.connect('fabrica.db')
    try:
        df = pd.read_sql("SELECT * FROM materiais", conn)
        # Proteção contra dados corrompidos
        df['custo'] = pd.to_numeric(df['custo'], errors='coerce').fillna(0.0)
        df['estoque'] = pd.to_numeric(df['estoque'], errors='coerce').fillna(0.0)
    except:
        df = pd.DataFrame(columns=['nome', 'custo', 'estoque'])
    finally:
        conn.close()
    return df

def get_receita_produto(nome_produto):
    conn = sqlite3.connect('fabrica.db')
    query = """SELECT r.ingrediente, r.qtd_teorica, m.custo FROM receitas r
               JOIN materiais m ON r.ingrediente = m.nome WHERE r.nome_produto = ?"""
    try:
        df = pd.read_sql_query(query, conn, params=(nome_produto,))
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def get_lista_produtos():
    conn = sqlite3.connect('fabrica.db')
    try:
        df = pd.read_sql("SELECT DISTINCT nome_produto FROM receitas", conn)
        return df['nome_produto'].tolist()
    except:
        return []
    finally:
        conn.close()

def baixar_estoque(consumo_real):
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        for material, qtd in consumo_real.items():
            qtd_float = float(qtd)
            c.execute("UPDATE materiais SET estoque = estoque - ? WHERE nome = ?", (qtd_float, material))
        conn.commit()
        return True, "Estoque atualizado!"
    except Exception as e: return False, str(e)
    finally: conn.close()

def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
    try:
        conn = sqlite3.connect('fabrica.db')
        c = conn.cursor()
        # CORREÇÃO DE FUSO HORÁRIO AQUI
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

# --- NOVAS FUNÇÕES DE EDIÇÃO E CADASTRO ---
def cadastrar_material(nome, custo, estoque):
    conn = sqlite3.connect('fabrica.db')
    try:
        conn.execute("INSERT INTO materiais VALUES (?, ?, ?)", (str(nome), float(custo), float(estoque)))
        conn.commit(); conn.close(); return True, "Sucesso"
    except Exception as e: conn.close(); return False, str(e)

def atualizar_material_db(nome, novo_custo, novo_estoque):
    conn = sqlite3.connect('fabrica.db')
    try:
        conn.execute("UPDATE materiais SET custo = ?, estoque = ? WHERE nome = ?", (float(novo_custo), float(novo_estoque), nome))
        conn.commit(); conn.close(); return True, "Atualizado"
    except Exception as e: conn.close(); return False, str(e)

def adicionar_ingrediente(produto, ingrediente, qtd):
    conn = sqlite3.connect('fabrica.db')
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM receitas WHERE nome_produto=? AND ingrediente=?", (produto, ingrediente))
        exists = cursor.fetchone()[0]
        
        if exists > 0:
            cursor.execute("UPDATE receitas SET qtd_teorica = ? WHERE nome_produto=? AND ingrediente=?", (float(qtd), produto, ingrediente))
        else:
            cursor.execute("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", (produto, ingrediente, float(qtd)))
        
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
        try: mat_txt = str(mat).encode('latin-1', 'replace').decode('latin-1')
        except: mat_txt = str(mat)
        pdf.cell(80, 10, mat_txt, 1); pdf.cell(60, 10, f"{float(qtd):.2f}", 1); pdf.ln()
    pdf
