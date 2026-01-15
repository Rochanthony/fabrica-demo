import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS TeCHemical v12.0", layout="wide")

# --- 0. SISTEMA DE LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><h2 style='text-align: center;'>🔐 Login Admin</h2>", unsafe_allow_html=True)
        user = st.text_input("Usuário", placeholder="admin")
        pwd = st.text_input("Senha", type="password", placeholder="admin")
        
        if st.button("Entrar", type="primary", use_container_width=True):
            if user == "admin" and pwd == "admin":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Senha incorreta (tente admin/admin)")
    return False

if not check_password():
    st.stop()

# --- 1. BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
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
            # Lista corrigida com fechamento de colchetes
            materiais = [
                ('Resina Epóxi', 15.0, 1000.0, 'kg', 'MP-101', 300.0), 
                ('Solvente X', 8.5, 800.0, 'L', 'MP-102', 200.0), 
                ('Pigmento Azul', 25.0, 200.0, 'kg', 'MP-103', 50.0), 
                ('Aditivo Secante', 45.0, 100.0, 'L', 'MP-104', 20.0),
                ('Lata 18L', 12.0, 500.0, 'un', 'EM-001', 100.0)
            ]
            c.executemany("INSERT INTO materiais VALUES (?, ?, ?, ?, ?, ?)", materiais)
            
            c.execute("INSERT OR IGNORE INTO produtos_codigos VALUES (?, ?)", ('Tinta Piso Premium', 'PA-500'))
            
            receita = [
                ('Tinta Piso Premium', 'Resina Epóxi', 60.0), 
                ('Tinta Piso Premium', 'Solvente X', 30.0), 
                ('Tinta Piso Premium', 'Pigmento Azul', 10.0), 
                ('Tinta Piso Premium', 'Lata 18L', 1.0)
            ]
            c.executemany("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", receita)
            conn.commit()
    except Exception as e:
        print(f"Erro DB: {e}")
    finally: 
        conn
