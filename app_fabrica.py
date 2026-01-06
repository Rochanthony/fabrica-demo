import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF # Nova biblioteca para o PDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 5.0", layout="wide")

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

# --- FUNÇÕES DE OPERAÇÃO (DB) ---
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
        fuso = pytz.timezone('America/Sao_Paulo')
        data_hora = datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
        status = "PREJUÍZO" if diferenca < 0 else "LUCRO"
        c.execute("INSERT INTO historico (data, operador, produto, custo_planejado, custo_real, diferenca, status) VALUES (?,?,?,?,?,?,?)",
                  (data_hora, operador, produto, custo_planejado, custo_real, diferenca, status))
        conn.commit()
        conn.close()
        return data_hora # Retorna a data para usar no PDF
    except Exception as e: return None

def cadastrar_material(nome, custo, estoque):
    conn = sqlite3.connect('fabrica.db')
    try:
        conn.execute("INSERT INTO materiais VALUES (?, ?, ?)", (nome, custo, estoque))
        conn.commit(); conn.close(); return True, "Sucesso"
    except Exception as e: conn.close(); return False, str(e)

def adicionar_ingrediente(produto, ingrediente, qtd):
    conn = sqlite3.connect('fabrica.db')
    try:
        conn.execute("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", (produto, ingrediente, qtd))
        conn.commit(); conn.close(); return True, "Sucesso"
    except Exception as e: conn.close(); return False, str(e)

# --- FUNÇÃO GERADORA DE PDF ---
def gerar_pdf_lote(data, operador, produto, itens_realizados, custo_plan, custo_real, diferenca):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabeçalho
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"RELATÓRIO DE PRODUÇÃO - {produto}", ln=True, align='C')
    pdf.ln(10)
    
    # Informações Gerais
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Data/Hora: {data}", ln=True)
    pdf.cell(0, 10, f"Operador Responsável: {operador}", ln=True)
    pdf.ln(5)
    
    # Tabela de Materiais
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(80, 10, "Material", 1)
    pdf.cell(60, 10, "Qtd Real (Kg)", 1)
    pdf.ln()
    
    pdf.set_font("Arial", '', 12)
    for mat, qtd in itens_realizados.items():
        # Encode latin-1 para lidar com acentos básicos se necessário, ou usar string simples
        try:
            mat_txt = mat.encode('latin-1', 'replace').decode('latin-1')
        except:
            mat_txt = mat
        pdf.cell(80, 10, mat_txt, 1)
        pdf.cell(60, 10, f"{qtd:.2f}", 1)
        pdf.ln()
        
    pdf.ln(10)
    
    # Resultados Financeiros
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Resumo Financeiro", ln=True)
    
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Custo Planejado: R$ {custo_plan:.2f}", ln=True)
    pdf.cell(0, 10, f"Custo Realizado: R$ {custo_real:.2f}", ln=True)
    
    # Destaque do Resultado
    if diferenca >= 0:
        pdf.set_text_color(0, 128, 0) # Verde
        status = f"ECONOMIA: R$ {diferenca:.2f}"
    else:
        pdf.set_text_color(255, 0, 0) # Vermelho
        status = f"DESVIO (PREJUÍZO): R$ {diferenca:.2f}"
        
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, status, ln=True)
    
    # Retorna o binário do PDF
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
    st.info("Sistema v5.0 - PDF Report")

# --- APP PRINCIPAL ---
st.title("🏭 Fabrica 4.0 - ERP Industrial")
aba_operacao, aba_estoque, aba_gestao, aba_cadastros = st.tabs(["🔨 Produção", "📦 Estoque", "📈 Gestão", "⚙️ Cadastros"])

# --- ABA 1: PRODUÇÃO (COM PDF) ---
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
                
                # Formulário Dinâmico
                with st.form("form_producao"):
                    for index, row in df_receita.iterrows():
                        ingrediente = row['ingrediente']
                        qtd_meta = row['qtd_teorica']
                        custo_unit = row['custo']
                        
                        custo_planejado += (qtd_meta * custo_unit)
                        
                        c1, c2 = st.columns([2, 1])
                        c1.markdown(f"**{ingrediente}** (Meta: {qtd_meta}kg)")
                        val = c2.number_input(f"Real ({ingrediente})", value=float(qtd_meta), step=0.1)
                        
                        custo_real += (val * custo_unit)
                        consumo_real[ingrediente] = val
                    
                    submitted = st.form_submit_button("✅ CALCULAR E FINALIZAR")
                
                if submitted:
                    dif = custo_planejado - custo_real
                    # 1. Salva no DB
                    data_salva = salvar_historico(operador, produto_selecionado, custo_planejado, custo_real, dif)
                    # 2. Baixa Estoque
                    ok, msg = baixar_estoque(consumo_real)
                    
                    if ok:
                        st.success("Produção Finalizada com Sucesso!")
                        
                        # 3. Gera o PDF
                        pdf_bytes = gerar_pdf_lote(data_salva, operador, produto_selecionado, consumo_real, custo_planejado, custo_real, dif)
                        
                        # Botão de Download
                        col_d1, col_d2 = st.columns(2)
                        col_d1.metric("Resultado Financeiro", f"R$ {dif:.2f}")
                        col_d2.download_button(
                            label="📄 Baixar Relatório PDF",
                            data=pdf_bytes,
                            file_name=f"relatorio_{produto_selecionado}_{int(time.time())}.pdf",
                            mime="application/pdf"
                        )
                        
                        # Atualiza a página após baixar (opcional, ou deixa o usuário ver o botão)
                        st.balloons()
                    else:
                        st.error(msg)
            else:
                st.warning("Produto sem receita.")
        else:
            st.info("Cadastre produtos primeiro.")

# --- ABA 2: ESTOQUE ---
with aba_estoque:
    st.header("Monitoramento de Tanques")
    df_estoque = get_materiais_db()
    if not df_estoque.empty:
        criticos = df_estoque[df_estoque['estoque'] < 300]
        if not criticos.empty: st.error(f"🚨 {len(criticos)} materiais críticos!")
        st.dataframe(df_estoque[['nome', 'custo', 'estoque']], use_container_width=True, hide_index=True)
    else: st.info("Vazio.")

# --- ABA 3: GESTÃO ---
with aba_gestao:
    st.header("Dashboard")
    conn = sqlite3.connect('fabrica.db')
    try: df_hist = pd.read_sql_query("SELECT * FROM historico", conn)
    except: df_hist = pd.DataFrame()
    conn.close()
    
    if not df_hist.empty:
        k1, k2 = st.columns(2)
        k1.metric("Total Lotes", len(df_hist))
        k2.metric("Saldo Geral", f"R$ {df_hist['diferenca'].sum():.2f}")
        st.dataframe(df_hist.sort_values(by='id', ascending=False), use_container_width=True)

# --- ABA 4: CADASTROS ---
with aba_cadastros:
    st.header("⚙️ Configurações")
    t1, t2 = st.tabs(["Material", "Receita"])
    with t1:
        with st.form("new_mat"):
            n = st.text_input("Nome"); c = st.number_input("Custo"); e = st.number_input("Estoque")
            if st.form_submit_button("Salvar") and n:
                ok, m = cadastrar_material(n, c, e)
                if ok: st.success("Salvo!"); time.sleep(1); st.rerun()
                else: st.error(m)
    with t2:
        prod = st.text_input("Nome do Produto (Existente ou Novo)")
        mats = get_materiais_db()['nome'].unique() if not get_materiais_db().empty else []
        if prod:
            c1, c2, c3 = st.columns([2,1,1])
            ing = c1.selectbox("Ingrediente", mats)
            qtd = c2.number_input("Qtd (Kg)")
            if c3.button("Add") and qtd > 0:
                adicionar_ingrediente(prod, ing, qtd)
                st.success("Adicionado!"); time.sleep(0.5); st.rerun()
            st.table(get_receita_produto(prod))
