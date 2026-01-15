import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS TeCHemical v13.0", layout="wide")

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
        pass
    finally: 
        conn.close()

# --- FUNÇÕES ---
def get_materiais_db():
    conn = sqlite3.connect('fabrica.db')
    try:
        df = pd.read_sql("SELECT * FROM materiais", conn)
        df['custo'] = pd.to_numeric(df['custo'], errors='coerce').fillna(0.0)
        df['estoque'] = pd.to_numeric(df['estoque'], errors='coerce').fillna(0.0)
        df['estoque_minimo'] = pd.to_numeric(df['estoque_minimo'], errors='coerce').fillna(0.0)
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

# --- INICIALIZAÇÃO DO SISTEMA ---
init_db()
popular_dados_iniciais()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏭 Painel")
    if st.button("🔴 RESETAR DB"):
        try:
            if os.path.exists("fabrica.db"): os.remove("fabrica.db")
            st.warning("Deletado! Recarregue a página.")
        except: pass
    st.divider()
    st.info("Versão V13 - Modo Direto")

# --- CORPO PRINCIPAL ---
st.title("🏭 Fabrica 4.0 - ERP Industrial")
aba_operacao, aba_estoque, aba_gestao, aba_cadastros = st.tabs(["🔨 Produção", "📦 Estoque", "📈 Gestão", "⚙️ Cadastros"])

# 1. ABA PRODUÇÃO
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
                unidades_dict = {}
                codigos_dict = {}
                custo_planejado = 0.0
                custo_real = 0.0
                
                for index, row in df_receita.iterrows():
                    ingrediente = row['ingrediente']
                    qtd_meta = float(row['qtd_teorica'])
                    custo_unit = float(row['custo'])
                    unidade_mat = str(row['unidade'])
                    
                    unidades_dict[ingrediente] = unidade_mat
                    codigos_dict[ingrediente] = str(row['codigo'])
                    custo_planejado += (qtd_meta * custo_unit)
                    
                    c1, c2 = st.columns([2, 1])
                    c1.markdown(f"**{ingrediente}** <small>({row['codigo']})</small>", unsafe_allow_html=True)
                    val = c2.number_input(f"Real ({unidade_mat})", value=qtd_meta, step=0.1, key=f"in_{ingrediente}")
                    
                    custo_real += (val * custo_unit)
                    consumo_real[ingrediente] = val
                    
                st.divider()
                dif = custo_planejado - custo_real
                
                k1, k2, k3 = st.columns(3)
                k1.metric("Meta", f"R$ {custo_planejado:.2f}")
                k2.metric("Real", f"R$ {custo_real:.2f}", delta=f"{dif:.2f}")
                
                if dif >= 0: k3.success(f"ECONOMIA: R$ {dif:.2f}")
                else: k3.error(f"PREJUÍZO: R$ {abs(dif):.2f}")
                    
                if st.button("💾 FINALIZAR ORDEM"):
                    data_salva = salvar_historico(operador, produto_selecionado, custo_planejado, custo_real, dif)
                    ok, msg = baixar_estoque(consumo_real)
                    if ok:
                        st.toast("Sucesso! Estoque atualizado.")
                        time.sleep(1)
                        try:
                            pdf_bytes = gerar_pdf_lote(data_salva, operador, produto_selecionado, consumo_real, unidades_dict, codigos_dict, custo_planejado, custo_real, dif)
                            st.download_button("Baixar PDF", data=pdf_bytes, file_name="Relatorio.pdf", mime="application/pdf")
                        except: pass

# 2. ABA ESTOQUE
with aba_estoque:
    st.header("Monitoramento de Tanques")
    df_estoque = get_materiais_db()
    if not df_estoque.empty:
        cols = st.columns(3)
        for i, row in df_estoque.iterrows():
            col_atual = cols[i % 3]
            nome = str(row['nome'])
            est_atual = float(row['estoque'])
            est_min = float(row['estoque_minimo'])
            unidade = str(row['unidade'])
            
            cap_visual = max(est_atual * 1.5, est_min * 3, 100.0)
            pct = max(0, min(100, (est_atual / cap_visual) * 100))
            
            if est_atual < est_min: cor, status = "#ff4b4b", "CRÍTICO"
            elif est_atual < (est_min * 1.2): cor, status = "#ffa421", "ATENÇÃO"
            else: cor, status = "#21c354", "OK"
            
            html_code = f"""
<div style="border
