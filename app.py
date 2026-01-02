import streamlit as st
import pandas as pd
import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from datetime import date

# --- CONFIGURAÇÃO INICIAL ---
st.set_page_config(page_title="Gerador de FDS", page_icon="🧪")

# --- CORREÇÃO DE ERROS DO WINDOWS (GTK) ---
# Mantido para funcionar no seu PC local. No servidor Linux, será ignorado.
caminhos_gtk = [
    r"C:\Program Files\GTK3-Runtime Win64\bin",
    r"C:\Program Files (x86)\GTK3-Runtime Win64\bin",
    os.path.join(os.getenv('LOCALAPPDATA'), 'GTK3-Runtime Win64', 'bin') if os.getenv('LOCALAPPDATA') else ""
]

gtk_encontrado = False
for caminho in caminhos_gtk:
    if os.path.isdir(caminho):
        os.environ['PATH'] = caminho + os.pathsep + os.environ['PATH']
        gtk_encontrado = True
        break

# --- FUNÇÕES ---
@st.cache_data
def load_data():
    try:
        df_prod = pd.read_excel('database.xlsx', sheet_name='Produtos')
        df_h = pd.read_excel('database.xlsx', sheet_name='FrasesH')
        df_p = pd.read_excel('database.xlsx', sheet_name='FrasesP')

        # Limpeza de dados
        df_prod = df_prod.fillna("")
        df_h = df_h.fillna("")
        df_p = df_p.fillna("")

        df_h['Codigo'] = df_h['Codigo'].astype(str).str.strip()
        df_p['Codigo'] = df_p['Codigo'].astype(str).str.strip()
        
        return df_prod, df_h, df_p
    except PermissionError:
        st.error("⚠️ O ARQUIVO EXCEL ESTÁ ABERTO! Feche-o e recarregue a página.")
        st.stop()
    except FileNotFoundError:
        return None, None, None

def render_html(template_name, context):
    env = Environment(loader=FileSystemLoader('.'))
    template = env.get_template(template_name)
    return template.render(context)

# --- INTERFACE ---
st.title("🧪 Gerador de FDS (Sem Logo)")
st.markdown("Conformidade NBR 14725:2023")

if not gtk_encontrado and os.name == 'nt':
    st.warning("⚠️ GTK3 não encontrado no Windows. Se o PDF falhar, verifique a instalação.")

st.markdown("---")

df_produtos, df_frases_h, df_frases_p = load_data()

if df_produtos is None:
    st.error("ERRO: 'database.xlsx' não encontrado.")
    st.stop()

# 1. Seleção Produto
st.subheader("1. Escolha o Produto")
if not df_produtos.empty:
    nomes_produtos = df_produtos['NomeProduto'].unique()
    produto_escolhido = st.selectbox("Selecione:", nomes_produtos)
else:
    st.warning("Excel vazio.")
    st.stop()

# 2. Seleção Frases
col1, col2 = st.columns(2)
with col1:
    st.subheader("2. Perigos (H)")
    if not df_frases_h.empty:
        lista_h_display = df_frases_h['Codigo'] + " - " + df_frases_h['Texto']
        frases_h_selecionadas = st.multiselect("Selecione:", lista_h_display)
    else:
        frases_h_selecionadas = []

with col2:
    st.subheader("3. Precaução (P)")
    if not df_frases_p.empty:
        lista_p_display = df_frases_p['Codigo'] + " - " + df_frases_p['Texto']
        frases_p_selecionadas = st.multiselect("Selecione:", lista_p_display)
    else:
        frases_p_selecionadas = []

# --- BOTÃO GERAR ---
st.markdown("---")
if st.button("📄 Gerar FDS (PDF)", type="primary"):

    with st.spinner("Processando..."):
        try:
            # Filtra dados
            info_produto = df_produtos[df_produtos['NomeProduto'] == produto_escolhido].to_dict('records')[0]
            
            codigos_h_limpos = [item.split(' - ')[0] for item in frases_h_selecionadas]
            codigos_p_limpos = [item.split(' - ')[0] for item in frases_p_selecionadas]
            
            info_h = df_frases_h[df_frases_h['Codigo'].isin(codigos_h_limpos)].to_dict('records')
            info_p = df_frases_p[df_frases_p['Codigo'].isin(codigos_p_limpos)].to_dict('records')

            # Define data atual
            data_hoje = date.today().strftime("%d/%m/%Y")

            contexto = {
                "produto": info_produto, 
                "frases_h": info_h, 
                "frases_p": info_p,
                "data_emissao": data_hoje
            }

            # Gera HTML e PDF
            html_content = render_html('template_fds.html', contexto)
            pdf_bytes = HTML(string=html_content).write_pdf()

            st.success(f"✅ FDS de '{produto_escolhido}' gerada!")
            st.download_button(
                label="⬇️ Baixar Arquivo PDF",
                data=pdf_bytes,
                file_name=f"FDS_{produto_escolhido}.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"Erro: {e}")
