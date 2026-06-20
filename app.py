import streamlit as st
import pandas as pd
from datetime import date
from streamlit_gsheets import GSheetsConnection

# Configuração da página
st.set_page_config(page_title="Gestão de Divergência", layout="wide")

# 1. Conexão com Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

PLANILHA_ABA_DADOS = "Página1"
# Pela sua imagem, o nome da aba criada ficou "Fornecedor"
PLANILHA_ABA_CONFIG = "Fornecedor" 

# 2. Função para ler os dados e as configurações
@st.cache_data(ttl=5)
def carregar_dados():
    colunas_padrao = ["Data", "NF", "Cód", "Fornecedor", "Produtos", "Comprador", "Loja", "R$ Diferença", "Protocolo"]
    
    # --- LER DADOS PRINCIPAIS ---
    try:
        df_dados = conn.read(worksheet=PLANILHA_ABA_DADOS, usecols=list(range(len(colunas_padrao))))
        if df_dados.empty or len(df_dados.columns) < len(colunas_padrao):
            df_dados = pd.DataFrame(columns=colunas_padrao)
        df_dados = df_dados.dropna(how='all')
        
        # Converte para formato de data para o Streamlit entender o calendário
        df_dados['Data'] = pd.to_datetime(df_dados['Data'], errors='coerce', dayfirst=True).dt.date
    except Exception:
        df_dados = pd.DataFrame(columns=colunas_padrao)

    # --- LER CONFIGURAÇÕES (Aba Fornecedor) ---
    try:
        # Lendo as colunas A (Cod), B (Fornecedor) até E (Comprador) -> índices 0 a 4
        df_config = conn.read(worksheet=PLANILHA_ABA_CONFIG, usecols=[0, 1, 2, 3, 4])
        df_config.columns = ['Cod', 'Fornecedor', 'C', 'D', 'Comprador']
        
        # Limpar casas decimais dos códigos (ex: o Sheets pode ler "19" como "19.0")
        df_config['Cod'] = df_config['Cod'].astype(str).str.replace(r'\.0$', '', regex=True)
        
        # Criar Dicionário de Código -> Fornecedor
        dict_fornecedores = dict(zip(df_config['Cod'].dropna(), df_config['Fornecedor'].dropna()))
        
        # Criar Lista de Compradores (Coluna E) removendo duplicatas e vazios
        lista_compradores = df_config['Comprador'].dropna().unique().tolist()
        lista_compradores = [c for c in lista_compradores if str(c).strip() != '']
    except Exception:
        dict_fornecedores = {}
        lista_compradores = []

    return df_dados, dict_fornecedores, lista_compradores

df_divergencia, dict_fornecedores, lista_compradores = carregar_dados()

st.title("📊 Base de Divergências")
st.write("Edite os dados abaixo. **Data padrão**, **Fornecedor (pelo Cód)** e **Comprador** serão formatados automaticamente ao salvar.")

# Se a data estiver vazia, preenche com hoje visualmente
df_divergencia['Data'] = df_divergencia['Data'].fillna(date.today())

# 3. Interface de Edição (st.data_editor)
df_editado = st.data_editor(
    df_divergencia,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "Cód": st.column_config.TextColumn("Cód"),
        "Fornecedor": st.column_config.TextColumn("Fornecedor", disabled=True, help="Será preenchido automaticamente ao salvar o Código."),
        "Comprador": st.column_config.SelectboxColumn("Comprador", options=lista_compradores),
        "R$ Diferença": st.column_config.NumberColumn("R$ Diferença", format="R$ %.2f")
    },
    key="editor_dados"
)

# 4. Tratamento Automático antes de Salvar no Sheets
# Limpar possíveis "19.0" digitados na tabela principal
df_editado['Cód'] = df_editado['Cód'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

# Função para preencher o Fornecedor com base no dicionário
def preencher_fornecedor(row):
    cod = row['Cód']
    if cod in dict_fornecedores and dict_fornecedores[cod]:
        return dict_fornecedores[cod]
    return row['Fornecedor'] # Se não achar, mantém o que estava

# Aplica a regra do Fornecedor
df_editado['Fornecedor'] = df_editado.apply(preencher_fornecedor, axis=1)

# Garante que as linhas novas sem data fiquem com a data de hoje no banco
df_editado['Data'] = df_editado['Data'].fillna(date.today())
# Formata a data para texto no padrão PT-BR para ficar bonito no Google Sheets
df_editado['Data'] = pd.to_datetime(df_editado['Data'], errors='coerce').dt.strftime('%d/%m/%Y')

# 5. Botão de Salvar
if st.button("💾 Salvar Alterações", type="primary"):
    with st.spinner("Sincronizando com o Google Sheets..."):
        try:
            # Envia para a nuvem
            conn.update(worksheet=PLANILHA_ABA_DADOS, data=df_editado)
            st.success("Dados salvos com sucesso!")
            
            # Limpa o cache e reinicia a tela para mostrar os Fornecedores preenchidos
            st.cache_data.clear()
            st.rerun()
            
        except Exception as e:
            st.error(f"Erro ao salvar na planilha: {e}")
