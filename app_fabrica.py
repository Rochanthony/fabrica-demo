import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS TeCHemical v9.0", layout="wide")

# --- 0. SISTEMA DE LOGIN ---
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br><h2 style='text-align: center;'>🔐 TeCHemical Login</h2>", unsafe_allow_html=True)
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

# --- 1. GERENCIAMENTO DE BANCO DE DADOS ---
def init_db():
    conn = sqlite3.connect('fabrica.db')
    c = conn.cursor()
    
    # Tabela Histórico
    c.execute('''CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, operador TEXT,
            produto TEXT, custo_planejado REAL, custo_real REAL, diferenca REAL, status TEXT)''')
    
    # Tabela Materiais (COM ESTOQUE MÍNIMO)
    c.execute('''CREATE TABLE IF NOT EXISTS materiais (
            nome TEXT PRIMARY KEY, custo REAL, estoque REAL, unidade TEXT, codigo TEXT, estoque_minimo REAL)''')
            
    # Tabela de Códigos de Produtos
    c.execute('''CREATE TABLE IF NOT EXISTS produtos_codigos (
            nome_produto TEXT PRIMARY KEY, codigo TEXT)''')

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
            # Materiais com CÓDIGO e ESTOQUE MINIMO PERSONALIZADO
            # Formato: (Nome, Custo, EstoqueAtual, Unidade, Codigo, MinimoAlerta)
            materiais = [
                ('Resina Epóxi', 15.0, 1000.0, 'kg', 'MP-101', 300.0), 
                ('Solvente X', 8.5, 800.0, 'L', 'MP-102', 200.0), 
                ('Pigmento Azul', 25.0, 200.0, 'kg', 'MP-103', 50.0), 
                ('Aditivo Secante', 45.0, 100.0, 'L', 'MP-104', 20.0),
                ('Lata 18L', 12.0, 500.0, 'un', 'EM-001', 100.0)
            ]
            c.executemany("INSERT INTO materiais VALUES (?, ?, ?, ?, ?, ?)", materiais)
            
            c.execute("INSERT INTO produtos_codigos VALUES (?, ?)", ('Tinta Piso Premium', 'PA-500'))

            receita = [
                ('Tinta Piso Premium', 'Resina Epóxi', 60.0), 
                ('Tinta Piso Premium', 'Solvente X', 30.0), 
                ('Tinta Piso Premium', 'Pigmento Azul', 10.0),
                ('Tinta Piso Premium', 'Lata 18L', 1.0)
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
        df['custo'] = pd.to_numeric(df['custo']).fillna(0.0)
        df['estoque'] = pd.to_numeric(df['estoque']).fillna(0.0)
        df['estoque_minimo'] = pd.to_numeric(df['estoque_minimo']).fillna(0.0) # Garante numero
        if 'codigo' not in df.columns: df['codigo'] = '-'
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
    query = """SELECT r.ingrediente, r.qtd_teorica, m.custo, m.unidade, m.codigo FROM receitas r
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
        try: fuso = pytz.timezone('America/Sao_Paulo')
        except: fuso = pytz.utc
        data_hora = datetime.now(fuso).strftime("%Y-%m-%d %H:%M:%S")
        status = "PREJUÍZO" if diferenca < 0 else "LUCRO"
        c.execute("INSERT INTO historico (data, operador, produto, custo_planejado, custo_real, diferenca, status) VALUES (?,?,?,?,?,?,?)",
                  (data_hora, operador, produto, custo_plan, custo_real, diferenca, status))
        conn.commit(); conn.close()
        return data_hora
    except: return None

# --- CADASTRO ---
def cadastrar_material(nome, custo, estoque, unidade, codigo, est_min):
    conn = sqlite3.connect('fabrica.db')
    try:
        # Agora salva também o estoque mínimo
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

# --- PDF ---
def gerar_pdf_lote(data, operador, produto, itens_realizados, unidades_dict, codigos_dict, custo_plan, custo_real, diferenca):
    cod_prod = get_prod_code(produto)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"RELATORIO DE PRODUCAO", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Produto: {produto} (Cod: {cod_prod})", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(0, 10, f"Data: {data}", ln=True)
    pdf.cell(0, 10, f"Operador: {operador}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(30, 10, "Cod.", 1); pdf.cell(60, 10, "Material", 1); pdf.cell(30, 10, "Qtd Real", 1); pdf.cell(20, 10, "Unid.", 1); pdf.ln()
    pdf.set_font("Arial", '', 11)
    for mat, qtd in itens_realizados.items():
        uni = unidades_dict.get(mat, '-')
        cod = codigos_dict.get(mat, '-')
        try: mat_txt = str(mat).encode('latin-1', 'replace').decode('latin-1')
        except: mat_txt = str(mat)
        pdf.cell(30, 10, str(cod), 1); pdf.cell(60, 10, mat_txt, 1); pdf.cell(30, 10, f"{float(qtd):.2f}", 1); pdf.cell(20, 10, str(uni), 1); pdf.ln()
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Realizado: R$ {custo_real:.2f}", ln=True)
    if diferenca >= 0:
        pdf.set_text_color(0, 128, 0)
        status = f"ECONOMIA: R$ {diferenca:.2f}"
    else:
        pdf.set_text_color(255, 0, 0)
        status = f"PREJUIZO: R$ {diferenca:.2f}"
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
    except: agora = datetime.now()
    st.write(f"📅 {agora.strftime('%d/%m/%Y')} | ⏰ {agora.strftime('%H:%M')}")
    st.divider()

    if st.button("🔴 RESETAR BANCO DE DADOS"):
        try:
            os.remove("fabrica.db")
            st.warning("Banco deletado. Atualize a página.")
            time.sleep(1)
            st.rerun()
        except: st.error("Erro ao deletar.")
    
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
        if produto_selecionado:
            cod_p = get_prod_code(produto_selecionado)
            st.caption(f"Código: **{cod_p}**")

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
                    codigo_mat = str(row['codigo'])
                    
                    unidades_dict[ingrediente] = unidade_mat
                    codigos_dict[ingrediente] = codigo_mat
                    custo_planejado += (qtd_meta * custo_unit)
                    
                    c1, c2 = st.columns([2, 1])
                    c1.markdown(f"**{ingrediente}** <small>({codigo_mat})</small>", unsafe_allow_html=True)
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
                        st.toast("Sucesso!", icon="✅")
                        try:
                            pdf_bytes = gerar_pdf_lote(data_salva, operador, produto_selecionado, consumo_real, unidades_dict, codigos_dict, custo_planejado, custo_real, dif)
                            st.download_button("Baixar PDF", data=pdf_bytes, file_name="Relatorio.pdf", mime="application/pdf")
                        except Exception as e: st.error(f"Erro PDF: {e}")

# --- ABA 2: ESTOQUE (INTELIGENTE) ---
with aba_estoque:
    st.header("Monitoramento de Tanques")
    df_estoque = get_materiais_db()
    
    if not df_estoque.empty:
        # VISUALIZAÇÃO COM LÓGICA DE MÍNIMO POR PRODUTO
        cols = st.columns(3)
        for i, row in df_estoque.iterrows():
            col_atual = cols[i % 3]
            nome = str(row['nome'])
            estoque_atual = float(row['estoque'])
            unidade = str(row['unidade'])
            codigo = str(row['codigo'])
            # Pega o mínimo cadastrado para este material (padrão 0 se não tiver)
            estoque_minimo = float(row.get('estoque_minimo', 0.0))
            
            # Define o máximo da barra apenas visualmente (para a barra não quebrar)
            # Se o estoque for 1000 e o minimo 500, usamos 2000 como "cheio" visual
            CAPACIDADE_VISUAL = max(estoque_atual * 1.5, estoque_minimo * 3, 100.0) 

            porcentagem = (estoque_atual / CAPACIDADE_VISUAL) * 100
            if porcentagem > 100: porcentagem = 100
            if porcentagem < 0: porcentagem = 0
            
            # --- AQUI ESTÁ A LÓGICA QUE VOCÊ PEDIU ---
            if estoque_atual < estoque_minimo:
                cor_barra = "#ff4b4b" # Vermelho (Abaixo do definido)
                texto_status = "CRÍTICO (Abaixo do Min)"
            elif estoque_atual < (estoque_minimo * 1.2):
                cor_barra = "#ffa421" # Amarelo (Até 20% acima do mínimo)
                texto_status = "ATENÇÃO (Próximo do Min)"
            else:
                cor_barra = "#21c354" # Verde
                texto_status = "OK"
            # -----------------------------------------

            with col_atual:
                st.markdown(f"""
                <div style="border: 1px solid #444; padding: 15px; border-radius: 10px; margin-bottom: 15px; background-color: #262730;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <div>
                            <span style="font-weight: bold; color: white; font-size: 1.1em;">{nome}</span>
                            <div style="font-size: 0.8em; color: #bbb;">Sku: {codigo}</div>
                        </div>
                        <div style="text-align: right;">
                            <span style="color: {cor_barra}; font-weight: bold; font-size: 1.2em;">{estoque_atual:.0f} {unidade}</span>
                            <div style="font-size: 0.7em; color: #888;">Min: {estoque_minimo:.0f}</div>
                        </div>
                    </div>
                    
                    <div style="width: 100%; background-color: #404040; border-radius: 5px; height: 12px;">
                        <div style="width: {porcentagem}%; background-color: {cor_barra}; height: 12px; border-radius: 5px; transition: width 0.5s;"></div>
                    </div>
                    
                    <div style="margin-top: 8px; font-size: 0.8em; color: {cor_barra}; font-weight: bold;">
                        {texto_status}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.divider()
        st.subheader("Tabela Detalhada")
        st.dataframe(df_estoque, use_container_width=True, hide_index=True)
    else:
        st.info("Estoque vazio.")

# --- ABA 3: GESTÃO ---
with aba_gestao:
    conn = sqlite3.connect('fabrica.db')
    try: df_hist = pd.read_sql_query("SELECT * FROM historico", conn)
    except: df_hist = pd.DataFrame()
    conn.close()
    if not df_hist.empty:
        st.metric("Saldo Geral", f"R$ {df_hist['diferenca'].sum():.2f}")
        st.dataframe(df_hist.sort_values(by='id', ascending=False), use_container_width=True)

# --- ABA 4: CADASTROS (ATUALIZADO COM ESTOQUE MINIMO) ---
with aba_cadastros:
    st.header("⚙️ Central de Cadastros")
    c1, c2 = st.columns(2)
    
    with c1:
        st.subheader("1. Materiais (MP)")
        with st.form("mat_form"):
            nome = st.text_input("Nome Material")
            codigo = st.text_input("Código (Serial/Lote)", placeholder="Ex: MP-100")
            col_a, col_b = st.columns(2)
            custo = col_a.number_input("Custo R$", min_value=0.01)
            est = col_b.number_input("Estoque Inicial", min_value=0.0)
            
            col_c, col_d = st.columns(2)
            uni = col_c.selectbox("Unid.", ["kg", "L", "un", "m"])
            # CAMPO NOVO AQUI:
            est_min = col_d.number_input("Estoque Mínimo (Alerta)", min_value=0.0, help="Abaixo disso a barra fica vermelha")
            
            if st.form_submit_button("Salvar Material"):
                if nome and codigo:
                    # Passando o est_min para a função
                    ok, m = cadastrar_material(nome, custo, est, uni, codigo, est_min)
                    if ok: st.success("Salvo!"); time.sleep(1); st.rerun()
                    else: st.error(m)
                else: st.warning("Nome e Código obrigatórios")

    with c2:
        st.subheader("2. Produtos (PA)")
        prod_names = get_lista_produtos()
        tipo = st.radio("Ação", ["Criar Novo Produto", "Editar Receita Existente"], horizontal=True)
        
        if tipo == "Criar Novo Produto":
            prod_novo = st.text_input("Nome do Produto")
            cod_novo = st.text_input("Código SKU", placeholder="Ex: PA-500")
            if prod_novo:
                save_prod_code(prod_novo, cod_novo)
            produto_ativo = prod_novo
        else:
            produto_ativo = st.selectbox("Selecione", prod_names) if prod_names else None
            if produto_ativo:
                cod_existente = get_prod_code(produto_ativo)
                st.caption(f"SKU Atual: {cod_existente}")

        if produto_ativo:
            st.divider()
            with st.form("rec_form"):
                st.markdown(f"Adicionar ingrediente em: **{produto_ativo}**")
                df_m = get_materiais_db()
                if not df_m.empty:
                    opts = [f"{r['nome']} | {r['codigo']}" for i, r in df_m.iterrows()]
                    sel = st.selectbox("Ingrediente", opts)
                    nome_ing = sel.split(" | ")[0]
                    qtd = st.number_input("Quantidade", min_value=0.1)
                    if st.form_submit_button("Adicionar"):
                        adicionar_ingrediente(produto_ativo, nome_ing, qtd)
                        st.success("Adicionado!"); time.sleep(1); st.rerun()

