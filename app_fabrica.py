import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA (OBRIGATÓRIO SER A PRIMEIRA LINHA) ---
st.set_page_config(page_title="SaaS TeCHemical v9.4", layout="wide")

# --- 1. GERENCIAMENTO DE BANCO DE DADOS (COM PROTEÇÃO) ---
def init_db():
    try:
        conn = sqlite3.connect('fabrica.db')
        c = conn.cursor()
        
        # Tabelas
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
    except Exception as e:
        st.error(f"Erro ao iniciar banco de dados: {e}")

def popular_dados_iniciais():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        # FIX DA LINHA 50: Verifica se a tabela existe antes de contar
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='materiais'")
        tabela_existe = c.fetchone()
        
        if tabela_existe:
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
                
                # Tenta inserir produtos
                try:
                    c.execute("INSERT OR IGNORE INTO produtos_codigos VALUES (?, ?)", ('Tinta Piso Premium', 'PA-500'))
                    receita =
