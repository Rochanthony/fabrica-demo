import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS TeCHemical v7.0", layout="wide")

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
            # Tenta usar st.secrets se configurado, senão usa o padrão "admin/1234"
            try:
                secrets_pass = st.secrets["passwords"]
                if user in secrets_pass and pwd == secrets_pass[user]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("Acesso negado.")
            except:
                # Fallback para teste local se não tiver secrets configurado
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
    
    # Tabela Materiais (AGORA COM UNIDADE)
    c.execute('''CREATE TABLE IF NOT EXISTS materiais (
            nome TEXT PRIMARY KEY, custo REAL, estoque REAL, unidade TEXT)''')
            
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
            # Dados padrão para teste (COM UNIDADES)
            materiais = [
                ('Resina', 15.0, 1000.0, 'kg'), 
                ('Solvente', 8.5, 800.0, 'L'), 
                ('Pigmento', 25.0, 200.0, 'kg'), 
                ('Aditivo', 45.0, 100.0, 'L'),
                ('Embalagem 18L', 12.0, 500.0, 'un')
            ]
            c.executemany("INSERT INTO materiais VALUES (?, ?, ?, ?)", materiais)
            
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
        # Garante que a coluna unidade existe, senão preenche com 'kg'
        if 'unidade' not in df.columns:
            df['unidade'] = 'kg'
    except:
        df = pd.DataFrame(columns=['nome', 'custo', 'estoque', 'unidade'])
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

# --- FUNÇÕES DE CADASTRO ATUALIZADAS ---
def cadastrar_material(nome, custo, estoque, unidade):
    conn = sqlite3.connect('fabrica.db')
    try:
        # Inserindo com 4 valores agora
        conn.execute("INSERT INTO materiais VALUES (?, ?, ?, ?)", (str(nome), float(custo), float(estoque), str(unidade)))
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

# --- PDF GENERATOR (Com Unidades) ---
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
            os.remove("fabrica.db")
            st.warning("Banco deletado. Atualize a página.")
            time.sleep(1)
            st.rerun()
        except:
            st.error("Erro ao deletar. Tente reiniciar o app.")

    st.markdown("---")
    st.markdown("<div style='text-align: center; color: #888;'><small>Desenvolvido por</small><br><b style='font-size: 1.2em; color: #4CAF50;'>🧪 TeCHemical</b></div>", unsafe_allow_html=True)

st.title("🏭 Fabrica 4.0 - ERP Industrial")
aba_operacao, aba_estoque, aba_gestao, aba_cadastros = st.tabs(["🔨 Produção", "📦 Estoque", "📈 Gestão", "⚙️ Cadastros"])

# --- ABA 1: PRODUÇÃO ---
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
                unidades_dict = {} # Para o PDF
                custo_planejado = 0.0
                custo_real = 0.0
                
                for index, row in df_receita.iterrows():
                    ingrediente = row['ingrediente']
                    qtd_meta = float(row['qtd_teorica'])
                    custo_unit = float(row['custo'])
                    unidade_mat = str(row['unidade']) # Nova coluna
                    unidades_dict[ingrediente] = unidade_mat
                    
                    custo_planejado += (qtd_meta * custo_unit)
                    
                    c1, c2 = st.columns([2, 1])
                    c1.markdown(f"**{ingrediente}** (Meta: {qtd_meta} {unidade_mat})")
                    val = c2.number_input(f"Real ({unidade_mat})", value=qtd_meta, step=0.1, key=f"in_{ingrediente}_{produto_selecionado}")
                    
                    custo_real += (val * custo_unit)
                    consumo_real[ingrediente] = val
                
                st.divider()
                dif = custo_planejado - custo_real
                col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
                col_kpi1.metric("Custo Meta", f"R$ {custo_planejado:.2f}")
                col_kpi2.metric("Custo Real", f"R$ {custo_real:.2f}", delta=f"{dif:.2f}")
                if dif >= 0: col_kpi3.success(f"✅ ECONOMIA: R$ {dif:.2f}")
                else: col_kpi3.error(f"🚨 PREJUÍZO: R$ {abs(dif):.2f}")
                
                if st.button("💾 FINALIZAR ORDEM E GERAR PDF", type="primary"):
                    data_salva = salvar_historico(operador, produto_selecionado, custo_planejado, custo_real, dif)
                    ok, msg = baixar_estoque(consumo_real)
                    if ok:
                        st.toast("Sucesso! Lote registrado.", icon="✅")
                        try:
                            pdf_bytes = gerar_pdf_lote(data_salva, operador, produto_selecionado, consumo_real, unidades_dict, custo_planejado, custo_real, dif)
                            st.markdown("### 📄 Relatório Pronto:")
                            st.download_button("Baixar PDF Assinado", data=pdf_bytes, file_name=f"Relatorio_{produto_selecionado}.pdf", mime="application/pdf")
                        except Exception as e_pdf:
                            st.error(f"Erro no PDF: {e_pdf}")
                    else: st.error(msg)
            else: st.warning("Produto sem receita cadastrada.")
        else: st.info("Cadastre produtos na aba Cadastros primeiro.")

# --- ABA 2: ESTOQUE ---
with aba_estoque:
    st.header("Monitoramento de Tanques")
    df_estoque = get_materiais_db()
    
    if not df_estoque.empty:
        st.subheader("Níveis em Tempo Real")
        CAPACIDADE_MAXIMA = 2000.0 # Apenas visual
        MINIMO_CRITICO = 300.0
        
        cols = st.columns(3)
        for i, row in df_estoque.iterrows():
            col_atual = cols[i % 3]
            nome = str(row['nome'])
            estoque_atual = float(row['estoque'])
            unidade = str(row['unidade']) # Pega a unidade
            
            # Cálculo visual simples
            porcentagem = (estoque_atual / CAPACIDADE_MAXIMA) * 100
            if porcentagem > 100: porcentagem = 100
            
            if estoque_atual < MINIMO_CRITICO:
                cor_barra = "#ff4b4b" # Vermelho
                texto_status = "CRÍTICO"
            elif estoque_atual < (CAPACIDADE_MAXIMA * 0.5):
                cor_barra = "#ffa421" # Laranja
                texto_status = "ATENÇÃO"
            else:
                cor_barra = "#21c354" # Verde
                texto_status = "OK"
            
            with col_atual:
                st.markdown(f"""
                <div style="border: 1px solid #ddd; padding: 10px; border-radius: 8px; margin-bottom: 10px; background-color: #262730;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-weight: bold; color: white;">{nome}</span>
                        <span style="color: {cor_barra}; font-weight: bold;">{estoque_atual:.1f} {unidade}</span>
                    </div>
                    <div style="width: 100%; background-color: #444; border-radius: 4px; height: 15px;">
                        <div style="width: {porcentagem}%; background-color: {cor_barra}; height: 15px; border-radius: 4px;"></div>
                    </div>
                    <div style="font-size: 0.8em; color: #aaa; margin-top: 5px;">Status: {texto_status}</div>
                </div>
                """, unsafe_allow_html=True)
        st.divider()
        st.subheader("Tabela de Detalhes")
        st.dataframe(df_estoque, use_container_width=True, hide_index=True)
    else: st.info("Estoque vazio.")

# --- ABA 3: GESTÃO ---
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
            st.line_chart(df_hist['diferenca'])
        with g2:
            st.subheader("Meta vs Realizado")
            df_chart = df_hist.groupby('produto')[['custo_planejado', 'custo_real']].sum()
            st.bar_chart(df_chart, stack=False)
        st.dataframe(df_hist.sort_values(by='id', ascending=False), use_container_width=True)
    else: st.info("ℹ️ Nenhum dado de produção encontrado.")

# --- ABA 4: CADASTROS (ATUALIZADO) ---
with aba_cadastros:
    st.header("⚙️ Central de Cadastros")
    col_mat, col_rec = st.columns(2)
    
    with col_mat:
        st.subheader("1. Materiais")
        tab_new_mat, tab_edit_mat = st.tabs(["➕ Novo", "✏️ Editar"])
        
        with tab_new_mat:
            with st.form("new_mat_form"):
                n = st.text_input("Nome do Material")
                c = st.number_input("Custo Unitário (R$)", min_value=0.01)
                
                # AQUI ESTÁ A NOVIDADE: SELEÇÃO DE UNIDADE
                col_u1, col_u2 = st.columns(2)
                e = col_u1.number_input("Estoque Inicial", min_value=0.0)
                u = col_u2.selectbox("Unidade", ["kg", "L", "un", "m", "cx", "ton"])
                
                if st.form_submit_button("Cadastrar"):
                    if n:
                        ok, m = cadastrar_material(n, c, e, u)
                        if ok: st.success("Cadastrado!"); time.sleep(1); st.rerun()
                        else: st.error(m)
                    else: st.warning("Nome obrigatório.")
        
        with tab_edit_mat:
            df_mats = get_materiais_db()
            if not df_mats.empty:
                lista_nomes = df_mats['nome'].astype(str).tolist()
                mat_to_edit = st.selectbox("Selecione o Material", lista_nomes)
                dados = df_mats[df_mats['nome'] == mat_to_edit]
                if not dados.empty:
                    dados_atuais = dados.iloc[0]
                    # Mostra a unidade atual
                    unidade_atual = dados_atuais.get('unidade', 'kg')
                    st.info(f"Unidade cadastrada: **{unidade_atual}** (Não editável)")
                    
                    with st.form("edit_mat_form"):
                        new_c = st.number_input("Novo Custo (R$)", value=float(dados_atuais['custo']), step=0.1)
                        new_e = st.number_input(f"Ajuste de Estoque ({unidade_atual})", value=float(dados_atuais['estoque']), step=1.0)
                        if st.form_submit_button("Atualizar"):
                            ok, msg = atualizar_material_db(mat_to_edit, new_c, new_e)
                            if ok: st.success("Atualizado!"); time.sleep(1); st.rerun()
                            else: st.error(msg)
            else: st.info("Sem materiais.")

    with col_rec:
        st.subheader("2. Produtos & Receitas")
        prod_names = get_lista_produtos()
        modo = st.radio("Ação:", ["Editar Existente", "Criar Novo"], horizontal=True)
        
        if modo == "Criar Novo":
            produto_ativo = st.text_input("Nome do Novo Produto")
        else:
            produto_ativo = st.selectbox("Selecione Produto", prod_names) if prod_names else None

        if produto_ativo:
            st.markdown(f"**Gerenciando: {produto_ativo}**")
            df_receita_atual = get_receita_produto(produto_ativo)
            if not df_receita_atual.empty:
                st.dataframe(df_receita_atual, use_container_width=True, hide_index=True)
            else: st.info("Receita vazia.")
            
            st.divider()
            with st.form("add_ing_form"):
                c1, c2 = st.columns(2)
                # Traz o nome e a unidade para ajudar na escolha
                df_mats_aux = get_materiais_db()
                if not df_mats_aux.empty:
                    # Cria lista tipo "Resina (kg)"
                    df_mats_aux['display'] = df_mats_aux['nome'] + " (" + df_mats_aux['unidade'] + ")"
                    mapa_mats = dict(zip(df_mats_aux['display'], df_mats_aux['nome']))
                    
                    ing_display = c1.selectbox("Ingrediente", df_mats_aux['display'].tolist())
                    ing_nome_real = mapa_mats[ing_display]
                    
                    qtd_sel = c2.number_input("Qtd na Receita", min_value=0.001, step=0.1, format="%.3f")
                    
                    if st.form_submit_button("Salvar Ingrediente"):
                        if ing_display and qtd_sel > 0:
                            ok, m = adicionar_ingrediente(produto_ativo, ing_nome_real, qtd_sel)
                            if ok: st.success("Salvo!"); time.sleep(1); st.rerun()
                            else: st.error(m)
                else: st.warning("Cadastre materiais antes.")
