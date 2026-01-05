import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz  # Biblioteca para fuso horário

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 4.0", layout="wide")

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏭 Painel de Controle")
    st.success("Status: Online 🟢")
    
    # FORÇAR FUSO HORÁRIO DE SÃO PAULO
    fuso_br = pytz.timezone('America/Sao_Paulo')
    agora = datetime.now(fuso_br)
    
    st.write(f"📅 {agora.strftime('%d/%m/%Y')}")
    st.write(f"⏰ {agora.strftime('%H:%M')}")
    st.divider()

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
        # Lê a configuração do Excel (Receitas e Materiais)
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

# --- BANCO DE DADOS SQL (CONFIGURAÇÃO) ---

def init_db():
    """Cria a tabela no banco de dados se ela não existir"""
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    # Criamos colunas para guardar o histórico
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
    """Salva o lote dentro do arquivo fabrica.db com horário correto"""
    try:
        conn = sqlite3.connect('fabrica.db')
        c = conn.cursor()
        
        # Define o fuso horário de SP para a data do registro
        fuso_br = pytz.timezone('America/Sao_Paulo')
        data_hora_br = datetime.now(fuso_br).strftime("%Y-%m-%d %H:%M:%S")
        
        # Insere os dados de forma segura
        c.execute('''
            INSERT INTO historico (data, operador, produto
