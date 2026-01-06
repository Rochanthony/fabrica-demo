import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS Fabrica 5.1", layout="wide")

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
    st.info("Sistema v5.1 - Ajustes Finais")

st.title("🏭 Fabrica 4.0 - ERP Industrial")
aba_operacao, aba_estoque, aba_gestao, aba_cadastros = st.tabs(["🔨 Produção", "📦 Estoque", "📈 Gestão", "⚙️ Cadastros"])

# --- ABA 1: PRODUÇÃO (SEM FORMULÁRIO PARA TER CÁLCULO AO VIVO) ---
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
                
                # Loop interativo (Sem st.form)
                for index, row in df_receita.iterrows():
                    ingrediente = row['ingrediente']
                    qtd_meta = row['qtd_teorica']
                    custo_unit = row['custo']
                    
                    custo_planejado += (qtd_meta * custo_unit)
                    
                    c1, c2 = st.columns([2, 1])
                    c1.markdown(f"**{ingrediente}** (Meta: {qtd_meta}kg)")
                    
                    # Key única para cada input para não perder o valor ao digitar
                    val = c2.number_input(f"Real ({ingrediente})", value=float(qtd_meta), step=0.1, key=f"input_{ingrediente}_{produto_selecionado}")
                    
                    custo_real += (val * custo_unit)
                    consumo_real[ingrediente] = val
                
                st.divider()
                
                # --- PAINEL DE CUSTOS (VOLTOU!) ---
                dif = custo_planejado - custo_real
                col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
                col_kpi1.metric("Custo Meta", f"R$ {custo_planejado:.2f}")
                col_kpi2.metric("Custo Real", f"R$ {custo_real:.2f}", delta=f"{dif:.2f}")
                
                if dif >= 0:
                    col_kpi3.success(f"✅ ECONOMIA: R$ {dif:.2f}")
                else:
                    col_kpi3.error(f"🚨 PREJUÍZO: R$ {abs(dif):.2f}")
                
                # Botão de Ação
                if st.button("💾 FINALIZAR ORDEM E GERAR PDF", type="primary"):
                    data_salva = salvar_historico(operador, produto_selecionado, custo_planejado, custo_real, dif)
                    ok, msg = baixar_estoque(consumo_real)
                    
                    if ok:
                        st.toast("Sucesso! Lote registrado.", icon="✅") # Sem balões, apenas toast discreto
                        
                        # Gera PDF
                        pdf_bytes = gerar_pdf_lote(data_salva, operador, produto_selecionado, consumo_real, custo_planejado, custo_real, dif)
                        
                        st.markdown("### 📄 Relatório Pronto:")
                        st.download_button(
                            label="Baixar PDF Assinado",
                            data=pdf_bytes,
                            file_name=f"Relatorio_{produto_selecionado}.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error(msg)
            else:
                st.warning("Produto sem receita cadastrada.")
        else:
            st.info("Cadastre produtos primeiro.")

# --- ABA 2: ESTOQUE (COM GRÁFICO DE BARRAS) ---
with aba_estoque:
    st.header("Monitoramento de Tanques")
    df_estoque = get_materiais_db()
    
    if not df_estoque.empty:
        # Gráfico Visual no Topo
        st.subheader("Visão Gráfica")
        st.bar_chart(df_estoque.set_index("nome")["estoque"], color="#29b5e8")
        
        # Tabela Detalhada com Barra de Progresso
        st.subheader("Detalhamento")
        
        # Define o máximo para a barra de progresso ficar bonita (baseado no maior estoque atual)
        max_stock = df_estoque['estoque'].max() if df_estoque['estoque'].max() > 0 else 1000
        
        st.dataframe(
            df_estoque[['nome', 'custo', 'estoque']],
            use_container_width=True,
            column_config={
                "estoque": st.column_config.ProgressColumn(
                    "Nível (Visual)", 
                    format="%.1f kg", 
                    min_value=0, 
                    max_value=max_stock,
                ),
                "custo": st.column_config.NumberColumn("Custo Unit.", format="R$ %.2f"),
                "nome": "Material"
            },
            hide_index=True
        )
    else: 
        st.info("Estoque vazio.")

# --- ABA 3: GESTÃO (COM GRÁFICO META X REAL) ---
with aba_gestao:
    st.header("Dashboard Gerencial")
    conn = sqlite3.connect('fabrica.db')
    try: df_hist = pd.read_sql_query("SELECT * FROM historico", conn)
    except: df_hist = pd.DataFrame()
    conn.close()
    
    if not df_hist.empty:
        k1, k2 = st.columns(2)
        k1.metric("Total Lotes", len(df_hist))
        k2.metric("Saldo Geral", f"R$ {df_hist['diferenca'].sum():.2f}")
        st.divider()
        
        g1, g2 = st.columns(2)
        
        with g1:
            st.subheader("Desempenho Financeiro")
            st.line_chart(df_hist['diferenca']) # Linha do tempo do lucro/prejuízo
            
        with g2:
            st.subheader("Meta vs Realizado (Por Produto)")
            # Prepara dados para o gráfico comparativo
            df_chart = df_hist.groupby('produto')[['custo_planejado', 'custo_real']].sum()
            st.bar_chart(df_chart, stack=False) # stack=False coloca as barras lado a lado
            
        st.markdown("### Histórico Detalhado")
        st.dataframe(df_hist.sort_values(by='id', ascending=False), use_container_width=True)
    else:
        st.info("ℹ️ Nenhum dado de produção encontrado. Produza o primeiro lote para ver os gráficos.")

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
