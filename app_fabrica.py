import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS TeCHemical v8.0 (Auto Requisicao)", layout="wide")

# --- 0. SISTEMA DE LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><h2 style='text-align: center;'>🔐 Acesso Restrito</h2>", unsafe_allow_html=True)
        user = st.text_input("Usuário")
        pwd = st.text_input("Senha", type="password")
        
        if st.button("Entrar", type="primary", use_container_width=True):
            try:
                secrets_pass = st.secrets["passwords"]
                if user in secrets_pass and pwd == secrets_pass[user]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("Acesso negado.")
            except:
                if user == "admin" and pwd == "1234":
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("Acesso negado.")
    return False

if not check_password():
    st.stop()

# --- 1. BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, operador TEXT,
            produto TEXT, qtd_lotes REAL, custo_total REAL, status TEXT)''')
    
    # Adicionando campo estoque_minimo
    c.execute('''CREATE TABLE IF NOT EXISTS materiais (
            nome TEXT PRIMARY KEY, custo REAL, estoque REAL, unidade TEXT, estoque_minimo REAL)''')
            
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
                ('Resina', 15.0, 1000.0, 'kg', 200.0), 
                ('Solvente', 8.5, 800.0, 'L', 150.0), 
                ('Pigmento', 25.0, 200.0, 'kg', 50.0), 
                ('Aditivo', 45.0, 100.0, 'L', 20.0),
                ('Embalagem 18L', 12.0, 500.0, 'un', 100.0)
            ]
            c.executemany("INSERT INTO materiais VALUES (?, ?, ?, ?, ?)", materiais)
            
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

# --- FUNÇÕES ---
def get_materiais_db():
    conn = sqlite3.connect('fabrica.db')
    try:
        df = pd.read_sql("SELECT * FROM materiais", conn)
        df['custo'] = pd.to_numeric(df['custo'], errors='coerce').fillna(0.0)
        df['estoque'] = pd.to_numeric(df['estoque'], errors='coerce').fillna(0.0)
        if 'unidade' not in df.columns: df['unidade'] = 'kg'
        if 'estoque_minimo' not in df.columns: df['estoque_minimo'] = 0.0
    except: df = pd.DataFrame()
    finally: conn.close()
    return df

def get_receita_produto(nome_produto):
    conn = sqlite3.connect('fabrica.db')
    query = """SELECT r.ingrediente, r.qtd_teorica, m.custo, m.unidade, m.estoque 
               FROM receitas r
               JOIN materiais m ON r.ingrediente = m.nome WHERE r.nome_produto = ?"""
    try: df = pd.read_sql_query(query, conn, params=(nome_produto,))
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

def baixar_estoque_automatico(lista_consumo):
    """
    Recebe uma lista de dicionários: [{'ingrediente': 'Resina', 'qtd': 60}, ...]
    """
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    try:
        for item in lista_consumo:
            c.execute("UPDATE materiais SET estoque = estoque - ? WHERE nome = ?", (item['qtd'], item['ingrediente']))
        conn.commit()
        return True, "Baixa realizada com sucesso!"
    except Exception as e: return False, str(e)
    finally: conn.close()

def salvar_historico_lote(operador, produto, qtd_lotes, custo_total):
    try:
        conn = sqlite3.connect('fabrica.db')
        c = conn.cursor()
        try: fuso = pytz.timezone('America/Sao_Paulo')
        except: fuso = pytz.utc
        data_hora = datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
        
        c.execute("INSERT INTO historico (data, operador, produto, qtd_lotes, custo_total, status) VALUES (?,?,?,?,?,?)",
                  (data_hora, operador, produto, qtd_lotes, custo_total, "OK"))
        conn.commit()
        conn.close()
        return data_hora
    except: return None

# --- FUNÇÕES DE CADASTRO ---
def cadastrar_material(nome, custo, estoque, unidade, estoque_min):
    conn = sqlite3.connect('fabrica.db')
    try:
        conn.execute("INSERT INTO materiais VALUES (?, ?, ?, ?, ?)", 
                     (str(nome), float(custo), float(estoque), str(unidade), float(estoque_min)))
        conn.commit()
        conn.close()
        return True, "Sucesso"
    except Exception as e:
        conn.close(); return False, str(e)

def adicionar_ingrediente(produto, ingrediente, qtd):
    conn = sqlite3.connect('fabrica.db')
    try:
        c = conn.cursor()
        c.execute("SELECT count(*) FROM receitas WHERE nome_produto=? AND ingrediente=?", (produto, ingrediente))
        if c.fetchone()[0] > 0:
            c.execute("UPDATE receitas SET qtd_teorica = ? WHERE nome_produto=? AND ingrediente=?", (float(qtd), produto, ingrediente))
        else:
            c.execute("INSERT INTO receitas (nome_produto, ingrediente, qtd_teorica) VALUES (?, ?, ?)", (produto, ingrediente, float(qtd)))
        conn.commit(); conn.close()
        return True, "Sucesso"
    except Exception as e: conn.close(); return False, str(e)

# --- PDF GENERATOR SIMPLIFICADO ---
def gerar_pdf_requisicao(data, operador, produto, lotes, lista_itens, custo_total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"ORDEM DE PRODUÇÃO - {produto}", ln=True, align='C')
    pdf.ln(5)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Data: {data} | Operador: {operador}", ln=True)
    pdf.cell(0, 10, f"Quantidade Produzida: {lotes} Lote(s)", ln=True)
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(80, 10, "Material", 1); pdf.cell(40, 10, "Qtd Baixada", 1); pdf.cell(30, 10, "Unid.", 1); pdf.ln()
    pdf.set_font("Arial", '', 12)
    
    for item in lista_itens:
        try: mat = str(item['ingrediente']).encode('latin-1', 'replace').decode('latin-1')
        except: mat = str(item['ingrediente'])
        pdf.cell(80, 10, mat, 1)
        pdf.cell(40, 10, f"{item['qtd']:.2f}", 1)
        pdf.cell(30, 10, item['unidade'], 1)
        pdf.ln()
        
    pdf.ln(10)
    pdf.cell(0, 10, f"Custo Total da Ordem: R$ {custo_total:.2f}", ln=True)
    return pdf.output(dest='S').encode('latin-1')

# --- INICIALIZAÇÃO ---
init_db()
popular_dados_iniciais()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🏭 Fabrica 4.0")
    if st.button("🔴 RESETAR BANCO"):
        if os.path.exists("fabrica.db"):
            os.remove("fabrica.db")
            st.rerun()

# --- INTERFACE PRINCIPAL ---
st.title("🏭 Fabrica 4.0 - Controle de Produção")
aba_prod, aba_est, aba_gest, aba_cad = st.tabs(["🚀 Execução (Novo)", "📦 Estoque", "📈 Gestão", "⚙️ Cadastros"])

# --- ABA 1: PRODUÇÃO (REMODELADA - PEDIDO DO GERENTE) ---
with aba_prod:
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("1. Configuração")
        operador = st.text_input("Operador", "João Silva")
        lista_prods = get_lista_produtos()
        produto = st.selectbox("Selecione a Receita", lista_prods) if lista_prods else None
        
        # A Mágica acontece aqui: Multiplicador de Lotes
        qtd_lotes = st.number_input("Quantos Lotes?", min_value=0.1, value=1.0, step=0.5, help="O sistema vai multiplicar a receita por este número.")

    with c2:
        if produto:
            st.subheader("2. Requisição de Materiais")
            df_rec = get_receita_produto(produto)
            
            if not df_rec.empty:
                # Cálculo Automático
                df_rec['Qtd Necessária'] = df_rec['qtd_teorica'] * qtd_lotes
                df_rec['Custo Previsto'] = df_rec['Qtd Necessária'] * df_rec['custo']
                
                # Verificação de Saldo (Alerta se faltar material)
                df_rec['Saldo Disponível'] = df_rec['estoque']
                df_rec['Status'] = df_rec.apply(lambda x: "✅ OK" if x['Saldo Disponível'] >= x['Qtd Necessária'] else "❌ FALTA", axis=1)
                
                # Exibe tabela limpa para o operador conferir
                st.dataframe(
                    df_rec[['ingrediente', 'Qtd Necessária', 'unidade', 'Status', 'Saldo Disponível']],
                    use_container_width=True,
                    hide_index=True
                )
                
                custo_total_ordem = df_rec['Custo Previsto'].sum()
                st.metric("Custo Total da Ordem", f"R$ {custo_total_ordem:.2f}")
                
                # Preparar dados para baixa
                lista_baixa = []
                pode_baixar = True
                for index, row in df_rec.iterrows():
                    if row['Status'] == "❌ FALTA":
                        pode_baixar = False
                    lista_baixa.append({
                        'ingrediente': row['ingrediente'],
                        'qtd': row['Qtd Necessária'],
                        'unidade': row['unidade']
                    })

                st.divider()
                
                if pode_baixar:
                    # BOTÃO ÚNICO COMO PEDIDO
                    if st.button("🚀 REQUISITAR E BAIXAR ESTOQUE", type="primary", use_container_width=True):
                        # 1. Baixa no Banco
                        ok, msg = baixar_estoque_automatico(lista_baixa)
                        if ok:
                            # 2. Salva Histórico
                            data_log = salvar_historico_lote(operador, produto, qtd_lotes, custo_total_ordem)
                            st.success(f"Sucesso! {msg}")
                            
                            # 3. Gera PDF
                            pdf_data = gerar_pdf_requisicao(data_log, operador, produto, qtd_lotes, lista_baixa, custo_total_ordem)
                            st.download_button("📄 Baixar Ordem de Produção", data=pdf_data, file_name="OP_Gerada.pdf", mime="application/pdf")
                            
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error(f"Erro no banco: {msg}")
                else:
                    st.error("🚨 Impossível requisitar: Saldo insuficiente de materiais. Verifique a tabela acima.")
            else:
                st.warning("Receita não cadastrada.")

# --- ABA 2: ESTOQUE (COM BARRAS E CORES) ---
with aba_est:
    st.subheader("Monitoramento de Tanques")
    df_e = get_materiais_db()
    if not df_e.empty:
        cols = st.columns(3)
        for i, row in df_e.iterrows():
            nome = row['nome']
            atual = row['estoque']
            minimo = row['estoque_minimo']
            unid = row['unidade']
            
            # Cor
            if atual < minimo: cor = "#ff4b4b" # Vermelho
            elif atual < minimo * 1.5: cor = "#ffa421" # Amarelo
            else: cor = "#21c354" # Verde
            
            perc = min((atual / (minimo*3 + 1)) * 100, 100) if minimo > 0 else 50
            
            html_card = f"""
            <div style="background-color:#262730; padding:15px; border-radius:10px; border:1px solid #444; margin-bottom:10px">
                <div style="display:flex; justify-content:space-between; color:white; font-weight:bold">
                    <span>{nome}</span>
                    <span style="color:{cor}">{atual:.1f} {unid}</span>
                </div>
                <div style="background:#444; height:10px; border-radius:5px; margin-top:5px; width:100%">
                    <div style="background:{cor}; width:{perc}%; height:10px; border-radius:5px"></div>
                </div>
                <small style="color:#888">Mínimo: {minimo:.0f}</small>
            </div>
            """
            cols[i%3].markdown(html_card, unsafe_allow_html=True)
            
        st.dataframe(df_e, use_container_width=True)
    else: st.info("Sem materiais.")

# --- ABA 3: GESTÃO (BI) ---
with aba_gest:
    conn = sqlite3.connect('fabrica.db')
    try: df_h = pd.read_sql("SELECT * FROM historico", conn)
    except: df_h = pd.DataFrame()
    conn.close()
    
    if not df_h.empty:
        k1, k2 = st.columns(2)
        k1.metric("Lotes Produzidos", len(df_h))
        k2.metric("Custo Total Acumulado", f"R$ {df_h['custo_total'].sum():.2f}")
        
        st.subheader("Histórico de Ordens")
        st.dataframe(df_h.sort_values(by='id', ascending=False), use_container_width=True)
    else: st.info("Sem produção registrada.")

# --- ABA 4: CADASTROS SIMPLES ---
with aba_cad:
    t1, t2 = st.tabs(["Materiais", "Receitas"])
    with t1:
        with st.form("mat"):
            n = st.text_input("Nome"); c = st.number_input("Custo"); e = st.number_input("Estoque"); u = st.text_input("Unidade"); em = st.number_input("Mínimo")
            if st.form_submit_button("Salvar Material"): cadastrar_material(n,c,e,u,em)
            
    with t2:
        prod = st.text_input("Nome do Produto (Para criar ou editar)")
        df_m = get_materiais_db()
        if not df_m.empty:
            ing = st.selectbox("Ingrediente", df_m['nome'].tolist())
            qtd = st.number_input("Qtd na Receita", step=0.1)
            if st.form_submit_button("Adicionar Ingrediente"): adicionar_ingrediente(prod, ing, qtd)
