import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS TeCHemical v7.1 (Estoque Min)", layout="wide")

# --- 0. SISTEMA DE LOGIN (MVP) ---
def check_password():
    """Retorna True se o usuário estiver logado."""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><h2 style='text-align: center;'>🔐 Acesso Restrito</h2>", unsafe_allow_html=True)
        st.info("Sistema exclusivo para teste piloto.")
        
        user = st.text_input("Usuário")
        pwd = st.text_input("Senha", type="password")
        
        if st.button("Entrar", type="primary", use_container_width=True):
            try:
                # Tenta usar st.secrets se configurado
                secrets_pass = st.secrets["passwords"]
                if user in secrets_pass and pwd == secrets_pass[user]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("Acesso negado.")
            except:
                # Fallback local
                if user == "admin" and pwd == "1234":
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("Acesso negado.")
    return False

if not check_password():
    st.stop()

# --- 1. GERENCIAMENTO DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    
    # Tabela Histórico
    c.execute('''CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, operador TEXT,
            produto TEXT, custo_planejado REAL, custo_real REAL, diferenca REAL, status TEXT)''')
    
    # Tabela Materiais (AGORA COM ESTOQUE MINIMO)
    # Se a tabela já existe sem a coluna, o ideal é resetar o banco pelo botão na sidebar
    c.execute('''CREATE TABLE IF NOT EXISTS materiais (
            nome TEXT PRIMARY KEY, custo REAL, estoque REAL, unidade TEXT, estoque_minimo REAL)''')
            
    # Tabela Receitas
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
            # Dados padrão para teste (Nome, Custo, Estoque, Unidade, Estoque Mínimo)
            materiais = [
                ('Resina', 15.0, 1000.0, 'kg', 200.0), 
                ('Solvente', 8.5, 800.0, 'L', 150.0), 
                ('Pigmento', 25.0, 200.0, 'kg', 50.0), 
                ('Aditivo', 45.0, 100.0, 'L', 20.0),
                ('Embalagem 18L', 12.0, 500.0, 'un', 100.0)
            ]
            c.executemany("INSERT INTO materiais VALUES (?, ?, ?, ?, ?)", materiais)
            
            # Receita Padrão
            receita = [
                ('Tinta Base', 'Resina', 60.0), 
                ('Tinta Base', 'Solvente', 30.0), 
                ('Tinta Base', 'Pigmento', 10.0),
                ('Tinta Base', 'Embalagem 18L', 1.0)
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
        df['custo'] = pd.to_numeric(df['custo'], errors='coerce').fillna(0.0)
        df['estoque'] = pd.to_numeric(df['estoque'], errors='coerce').fillna(0.0)
        
        # Garante que as colunas novas existam (fallback para evitar erro se não resetar banco)
        if 'unidade' not in df.columns: df['unidade'] = 'kg'
        if 'estoque_minimo' not in df.columns: df['estoque_minimo'] = 0.0
        
    except:
        df = pd.DataFrame(columns=['nome', 'custo', 'estoque', 'unidade', 'estoque_minimo'])
    finally:
        conn.close()
    return df

def get_receita_produto(nome_produto):
    conn = sqlite3.connect('fabrica.db')
    # Traz também a unidade do material
    query = """SELECT r.ingrediente, r.qtd_teorica, m.custo, m.unidade FROM receitas r
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

# --- FUNÇÕES DE CADASTRO (ATUALIZADAS E CORRIGIDAS) ---
def cadastrar_material(nome, custo, estoque, unidade, estoque_min):
    conn = sqlite3.connect('fabrica.db')
    try:
        # Inserindo com 5 valores (incluindo estoque mínimo)
        conn.execute("INSERT INTO materiais VALUES (?, ?, ?, ?, ?)", 
                     (str(nome), float(custo), float(estoque), str(unidade), float(estoque_min)))
        conn.commit()
        conn.close()
        return True, "Sucesso"
    except Exception as e:
        conn.close()
        return False, str(e)

def atualizar_material_db(nome, novo_custo, novo_estoque, novo_minimo):
    conn = sqlite3.connect('fabrica.db')
    try:
        conn.execute("UPDATE materiais SET custo = ?, estoque = ?, estoque_minimo = ? WHERE nome = ?", 
                     (float(novo_custo), float(novo_estoque), float(novo_minimo), nome))
        conn.commit()
        conn.close()
        return True, "Atualizado"
    except Exception as e:
        conn.close()
        return False, str(e)

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
        conn.commit()
        conn.close()
        return True, "Sucesso"
    except Exception as e:
        conn.close()
        return False, str(e)

# --- PDF GENERATOR ---
def gerar_pdf_lote(data, operador, produto, itens_realizados, unidades_dict, custo_plan, custo_real, diferenca):
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
    pdf.cell(70, 10, "Material", 1); pdf.cell(30, 10, "Qtd Real", 1); pdf.cell(30, 10, "Unid.", 1); pdf.ln()
    pdf.set_font("Arial", '', 12)
    for mat, qtd in itens_realizados.items():
        uni = unidades_dict.get(mat, '-')
        try: mat_txt = str(mat).encode('latin-1', 'replace').decode('latin-1')
        except: mat_txt = str(mat)
        pdf.cell(70, 10, mat_txt, 1); pdf.cell(30, 10, f"{float(qtd):.2f}", 1); pdf.cell(30, 10, str(uni), 1); pdf.ln()
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
    try:
        fuso_br = pytz.timezone('America/Sao_Paulo')
        agora = datetime.now(fuso_br)
    except:
        agora = datetime.now()
    st.write(f"📅 {agora.strftime('%d/%m/%Y')} | ⏰ {agora.strftime('%H:%M')}")
    
    if st.button("Sair / Logout"):
        st.session_state["password_correct"] = False
        st.rerun()

    st.divider()
    if st.button("🔴 RESETAR BANCO DE DADOS", help="Clique aqui se deu erro após atualização"):
        try:
            if os.path.exists("fabrica.db"):
                os.remove("fabrica.db")
                st.warning("Banco deletado.
