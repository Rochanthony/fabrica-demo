import streamlit as st
import pandas as pd
from datetime import datetime
import time
import os
import sqlite3
import pytz
from fpdf import FPDF

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="SaaS TeCHemical v7.2 (Alertas)", layout="wide")

# --- 0. SISTEMA DE LOGIN (MVP) ---
def check_password():
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
                secrets_pass = st.secrets["passwords"]
                if user in secrets_pass and pwd == secrets_pass[user]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("Acesso negado.")
            except:
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
    c.execute('''CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT, operador TEXT,
            produto TEXT, custo_planejado REAL, custo_real REAL, diferenca REAL, status TEXT)''')
    
    # ATUALIZADO: Adicionada coluna estoque_minimo
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
            # Dados padrão AGORA COM ESTOQUE MÍNIMO (5º item)
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

# --- FUNÇÕES DE LEITURA/ESCRITA ---
def get_materiais_db():
    conn = sqlite3.connect('fabrica.db')
    try:
        df = pd.read_sql("SELECT * FROM materiais", conn)
        df['custo'] = pd.to_numeric(df['custo'], errors='coerce').fillna(0.0)
        df['estoque'] = pd.to_numeric(df['estoque'], errors='coerce').fillna(0.0)
        df['estoque_minimo'] = pd.to_numeric(df['estoque_minimo'], errors='coerce').fillna(0.0)
        if 'unidade' not in df.columns: df['unidade'] = 'kg'
    except:
        df = pd.DataFrame(columns=['nome', 'custo', 'estoque', 'unidade', 'estoque_minimo'])
    finally:
        conn.close()
    return df

def get_receita_produto(nome_produto):
    conn = sqlite3.connect('fabrica.db')
    query = """SELECT r.ingrediente, r.qtd_teorica, m.custo, m.unidade, m.estoque 
               FROM receitas r
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
        
        status = "PREJUÍZO" if diferenca < 0 else "OK"
        c.execute("INSERT INTO historico (data, operador, produto, custo_planejado, custo_real, diferenca, status) VALUES (?,?,?,?,?,?,?)",
                  (data_hora, operador, produto, custo_planejado, custo_real, diferenca, status))
        conn.commit()
        conn.close()
        return data_hora
    except Exception as e: return None

# --- FUNÇÕES DE CADASTRO (ATUALIZADAS) ---
def cadastrar_material(nome, custo, estoque, unidade, estoque_min):
    conn = sqlite3.connect('fabrica.db')
    try:
        # Inserindo agora 5 valores
        conn.execute("INSERT INTO materiais VALUES (?, ?, ?, ?, ?)", 
                     (str(nome), float(custo), float(estoque), str(unidade), float(estoque_min)))
        conn.commit(); conn.close(); return True, "Sucesso"
    except Exception as e: conn.close(); return False, str(e)

def atualizar_material_db(nome, novo_custo, novo_estoque, novo_minimo):
    conn = sqlite3.connect('fabrica.db')
    try:
        # Atualiza também o estoque_minimo
        conn.execute("UPDATE materiais SET custo = ?, estoque = ?, estoque_minimo = ? WHERE nome = ?", 
                     (float(novo_custo), float(novo_estoque), float(novo_minimo), nome))
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

# --- PDF GENERATOR ---
def gerar_pdf_lote(data, operador, produto, itens_realizados, unidades_dict, custo_plan, custo_real, qtd_lotes):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"ORDEM DE REQUISICAO - {produto}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Data: {data}", ln=True)
    pdf.cell(0, 10, f"Operador: {operador}", ln=True)
    pdf.cell(0, 10, f"Lotes Produzidos: {qtd_lotes}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(70, 10, "Material Baixado", 1); pdf.cell(30, 10, "Qtd", 1); pdf.cell(30, 10, "Unid.", 1); pdf.ln()
    pdf.set_font("Arial", '', 12)
    for mat, qtd in itens_realizados.items():
        uni = unidades_dict.get(mat, '-')
        try: mat_txt = str(mat).encode('latin-1', 'replace').decode('latin-1')
        except: mat_txt = str(mat)
        pdf.cell(70, 10, mat_txt, 1); pdf.cell(30, 10, f"{float(qtd):.2f}", 1); pdf.cell(30, 10, str(uni), 1); pdf.ln()
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Custo Total da Ordem: R$ {custo_real:.2f}", ln=True)
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
    if st.button("🔴 RESETAR BANCO", help="Obrigatório clicar aqui após atualizar o código"):
        try:
            os.remove("fabrica.db")
            st.warning("Banco deletado. Atualize a página.")
            time.sleep(1)
            st.rerun()
        except:
            st.error("Erro ao deletar.")

    st.markdown("---")
    st.markdown("<div style='text-align: center; color: #888;'><small>Desenvolvido por</small><br><b style='font-size: 1.2em; color: #4CAF50;'>🧪 TeCHemical</b></div>", unsafe_allow_html=True)

st.title("🏭 Fabrica 4.0 - ERP Industrial")
aba_operacao, aba_estoque, aba_gestao, aba_cadastros = st.tabs(["🔨 Produção (Requisição)", "📦 Estoque", "📈 Gestão", "⚙️ Cadastros"])

st.markdown("---")
    st.subheader("Segurança")
    
    # Lê o arquivo do banco em bytes para permitir o download
    try:
        with open("fabrica.db", "rb") as fp:
            btn = st.download_button(
                label="📥 Baixar Backup dos Dados",
                data=fp,
                file_name=f"backup_fabrica_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                mime="application/x-sqlite3",
                help="Clique aqui ao final do dia para salvar seus dados!"
            )
    except FileNotFoundError:
        st.warning("Banco de dados ainda não criado para backup.")

# --- ABA 1: PRODUÇÃO (MANTIDA IGUAL) ---
# --- LOCAL: ABA 1 (PRODUÇÃO) ---
# Substitua tudo de "with aba_operacao:" até antes de "with aba_estoque:" por isso:

with aba_operacao:
    col_config, col_simulacao = st.columns([1, 2])
    lista_produtos = get_lista_produtos()
    
    with col_config:
        st.subheader("1. Setup")
        operador = st.text_input("Operador", value="João Silva")
        produto_selecionado = st.selectbox("Selecione a Receita", lista_produtos) if lista_produtos else None
        qtd_lotes = st.number_input("Quantos Lotes?", value=1.0, min_value=0.1, step=0.5)

    with col_simulacao:
        if produto_selecionado:
            st.subheader(f"2. Prévia da Requisição: {produto_selecionado}")
            df_receita = get_receita_produto(produto_selecionado)
            
            if not df_receita.empty:
                df_receita['Qtd Necessária'] = df_receita['qtd_teorica'] * qtd_lotes
                df_receita['Disponível'] = df_receita['estoque']
                
                df_receita['Status'] = df_receita.apply(
                    lambda row: "✅ OK" if row['Disponível'] >= row['Qtd Necessária'] else "❌ FALTA", axis=1
                )
                
                st.dataframe(
                    df_receita[['ingrediente', 'Qtd Necessária', 'unidade', 'Disponível', 'Status']],
                    use_container_width=True,
                    hide_index=True
                )
                
                custo_total_previsto = (df_receita['Qtd Necessária'] * df_receita['custo']).sum()
                st.metric("Custo Total da Ordem", f"R$ {custo_total_previsto:.2f}")

                if "❌ FALTA" in df_receita['Status'].values:
                    st.error("🚨 ESTOQUE INSUFICIENTE. Não é possível requisitar.")
                else:
                    st.markdown("---")
                    # Lógica de Requisitar
                    if st.button("🚀 REQUISITAR E BAIXAR ESTOQUE", type="primary", use_container_width=True):
                        consumo_final = {}
                        unidades_dict = {}
                        for index, row in df_receita.iterrows():
                            consumo_final[row['ingrediente']] = row['Qtd Necessária']
                            unidades_dict[row['ingrediente']] = row['unidade']
                        
                        ok, msg = baixar_estoque(consumo_final)
                        
                        if ok:
                            data_salva = salvar_historico(operador, produto_selecionado, custo_total_previsto, custo_total_previsto, 0)
                            st.toast("Sucesso! Estoque baixado.", icon="✅")
                            
                            # GERAÇÃO DO PDF
                            try:
                                pdf_bytes = gerar_pdf_lote(data_salva, operador, produto_selecionado, consumo_final, unidades_dict, custo_total_previsto, custo_total_previsto, qtd_lotes)
                                st.success("Ordem Processada com Sucesso!")
                                
                                # --- A CORREÇÃO ESTÁ AQUI (key único para não dar erro) ---
                                st.download_button(
                                    label="📄 Baixar PDF da Requisição",
                                    data=pdf_bytes,
                                    file_name=f"Req_{produto_selecionado}.pdf",
                                    mime="application/pdf",
                                    key=f"btn_pdf_{int(time.time())}" 
                                )
                                # ----------------------------------------------------------
                                
                                time.sleep(3)
                                st.rerun()
                                
                            except Exception as e_pdf:
                                st.error(f"Erro ao gerar botão: {e_pdf}")
                                
                        else:
                            st.error(f"Erro no Banco de Dados: {msg}")

            else: st.warning("Este produto não tem receita cadastrada.")
        else: st.info("Selecione um produto para iniciar.")

# --- ABA 2: ESTOQUE (ATUALIZADA COM ALERTA REAL) ---
with aba_estoque:
    st.header("Monitoramento de Tanques")
    df_estoque = get_materiais_db()
    
    if not df_estoque.empty:
        st.subheader("Níveis em Tempo Real")
        CAPACIDADE_MAXIMA = 2000.0 # Visual apenas
        
        cols = st.columns(3)
        for i, row in df_estoque.iterrows():
            col_atual = cols[i % 3]
            nome = str(row['nome'])
            estoque_atual = float(row['estoque'])
            unidade = str(row['unidade'])
            
            # AQUI ESTÁ A LÓGICA DO ALERTA BASEADA NO BANCO
            estoque_minimo = float(row['estoque_minimo']) # Pega do cadastro
            
            porcentagem = (estoque_atual / CAPACIDADE_MAXIMA) * 100
            if porcentagem > 100: porcentagem = 100
            
            # Comparação dinâmica
            if estoque_atual < estoque_minimo:
                cor_barra = "#ff4b4b" # Vermelho
                texto_status = f"🚨 CRÍTICO (Mín: {estoque_minimo})"
            elif estoque_atual < (estoque_minimo * 1.5):
                cor_barra = "#ffa421" # Laranja
                texto_status = f"⚠️ BAIXO (Mín: {estoque_minimo})"
            else:
                cor_barra = "#21c354" # Verde
                texto_status = "✅ OK"
            
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
                    <div style="font-size: 0.8em; color: #aaa; margin-top: 5px;">{texto_status}</div>
                </div>
                """, unsafe_allow_html=True)
        st.divider()
        st.dataframe(df_estoque, use_container_width=True, hide_index=True)
    else: st.info("Estoque vazio.")

# --- ABA 3: GESTÃO (MANTIDA) ---
with aba_gestao:
    st.header("Dashboard Gerencial")
    conn = sqlite3.connect('fabrica.db')
    try: df_hist = pd.read_sql_query("SELECT * FROM historico", conn)
    except: df_hist = pd.DataFrame()
    conn.close()
    
    if not df_hist.empty:
        k1, k2 = st.columns(2)
        k1.metric("Total de Ordens", len(df_hist))
        k2.metric("Volume Financeiro", f"R$ {df_hist['custo_real'].sum():.2f}")
        st.divider()
        st.dataframe(df_hist.sort_values(by='id', ascending=False), use_container_width=True)
    else: st.info("ℹ️ Nenhum dado de produção encontrado.")

# --- ABA 4: CADASTROS (ATUALIZADA) ---
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
                col_u1, col_u2 = st.columns(2)
                e = col_u1.number_input("Estoque Inicial", min_value=0.0)
                u = col_u2.selectbox("Unidade", ["kg", "L", "un", "m", "cx", "ton"])
                
                # NOVO CAMPO
                emin = st.number_input("Estoque Mínimo (Alerta)", min_value=0.0, help="Abaixo disso, fica vermelho")

                if st.form_submit_button("Cadastrar"):
                    if n:
                        ok, m = cadastrar_material(n, c, e, u, emin)
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
                    unidade_atual = dados_atuais.get('unidade', 'kg')
                    st.info(f"Unidade: **{unidade_atual}**")
                    with st.form("edit_mat_form"):
                        new_c = st.number_input("Novo Custo (R$)", value=float(dados_atuais['custo']), step=0.1)
                        new_e = st.number_input(f"Ajuste Estoque ({unidade_atual})", value=float(dados_atuais['estoque']), step=1.0)
                        
                        # CAMPO DE EDIÇÃO DO MÍNIMO
                        new_min = st.number_input("Novo Mínimo (Alerta)", value=float(dados_atuais['estoque_minimo']), step=10.0)
                        
                        if st.form_submit_button("Atualizar"):
                            ok, msg = atualizar_material_db(mat_to_edit, new_c, new_e, new_min)
                            if ok: st.success("Atualizado!"); time.sleep(1); st.rerun()
                            else: st.error(msg)
            else: st.info("Sem materiais.")

    with col_rec:
        st.subheader("2. Produtos & Receitas")
        prod_names = get_lista_produtos()
        modo = st.radio("Ação:", ["Editar Existente", "Criar Novo"], horizontal=True)
        if modo == "Criar Novo": produto_ativo = st.text_input("Nome do Novo Produto")
        else: produto_ativo = st.selectbox("Selecione Produto", prod_names) if prod_names else None

        if produto_ativo:
            df_receita_atual = get_receita_produto(produto_ativo)
            if not df_receita_atual.empty: st.dataframe(df_receita_atual[['ingrediente','qtd_teorica','unidade']], use_container_width=True, hide_index=True)
            else: st.info("Receita vazia.")
            st.divider()
            with st.form("add_ing_form"):
                c1, c2 = st.columns(2)
                df_mats_aux = get_materiais_db()
                if not df_mats_aux.empty:
                    df_mats_aux['display'] = df_mats_aux['nome'] + " (" + df_mats_aux['unidade'] + ")"
                    mapa_mats = dict(zip(df_mats_aux['display'], df_mats_aux['nome']))
                    ing_display = c1.selectbox("Ingrediente", df_mats_aux['display'].tolist())
                    ing_nome_real = mapa_mats[ing_display]
                    qtd_sel = c2.number_input("Qtd na Receita", min_value=0.001, step=0.1)
                    if st.form_submit_button("Salvar Ingrediente"):
                        if ing_display and qtd_sel > 0:
                            ok, m = adicionar_ingrediente(produto_ativo, ing_nome_real, qtd_sel)
                            if ok: st.success("Salvo!"); time.sleep(1); st.rerun()
                            else: st.error(m)
                else: st.warning("Cadastre materiais antes.")



