import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta  # Adicionado timedelta para o fuso horário
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 4.0", layout="wide")

# --- BARRA LATERAL (NOVO) ---
with st.sidebar:
    st.header("🏭 Fabrica 4.0")
    st.write("Sistema de Controle v1.0")
    st.markdown("---")
    st.success("Status: Online")
    st.markdown("---")
    # Mostra a data atual ajustada
    data_hoje = (datetime.now() - timedelta(hours=3)).strftime('%d/%m/%Y')
    st.caption(f"Data: {data_hoje}")
    st.caption("Desenvolvido por Você")

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

# Função para Salvar no 'Banco de Dados' (CSV)
def salvar_historico(operador, produto, custo_planejado, custo_real, diferenca):
    arquivo_db = 'historico_producao.csv'
    
    # AJUSTE DE FUSO HORÁRIO AQUI (UTC - 3 horas)
    data_hora_br = (datetime.now() - timedelta(hours=3)).strftime("%d/%m/%Y %H:%M:%S")
    
    novo_registro = {
        'Data': [data_hora_br],
        'Operador': [operador],
        'Produto': [produto],
        'Custo_Planejado': [custo_planejado],
        'Custo_Real': [custo_real],
        'Diferenca_R$': [diferenca],
        'Status': ["PREJUÍZO" if diferenca < 0 else "LUCRO/ECONOMIA"]
    }
    
    df_novo = pd.DataFrame(novo_registro)
    
    if not os.path.isfile(arquivo_db):
        df_novo.to_csv(arquivo_db, index=False, sep=';')
    else:
        df_novo.to_csv(arquivo_db, mode='a', header=False, index=False, sep=';')

# --- 2. O VISUAL (FRONTEND) ---
st.title("🏭 Monitor de Produção Inteligente")

# Navegação entre abas
aba_operacao, aba_gestao = st.tabs(["🔨 Operação (Chão
