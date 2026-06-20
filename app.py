import streamlit as st
import pandas as pd
from datetime import date
from streamlit_gsheets import GSheetsConnection

# Configuração da página
st.set_page_config(page_title="Gestão de Divergência", layout="wide")

# Conexão com Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

PLANILHA_ABA_DADOS = "Página1"
PLANILHA_ABA_CONFIG = "Fornecedor" 

# Função para ler os dados e as configurações
@st.cache_data(ttl=5)
def carregar_dados():
    colunas_padrao = ["Data", "NF", "Cód", "Fornecedor", "Produtos", "Comprador", "Loja", "R$ Diferença", "Protocolo"]
    
    # --- 1. LER DADOS PRINCIPAIS ---
    try:
        df_dados = conn.read(worksheet=PLANILHA_ABA_DADOS, usecols=list(range(len(colunas_padrao))))
        if df_dados.empty or len(df_dados.columns) < len(colunas_padrao):
            df_dados = pd.DataFrame(columns=colunas_padrao)
        df_dados = df_dados.dropna(how='all')
        
        # Converte para formato de data real para o calendário funcionar em DD/MM/YYYY
        df_dados['Data'] = pd.to_datetime(df_dados['Data'], format='%d/%m/%Y', errors='coerce').dt.date
    except Exception:
        df_dados = pd.DataFrame(columns=colunas_padrao)

    # --- 2. LER CONFIGURAÇÕES (Aba Fornecedor) ---
    try:
        # Lê a aba de configurações inteira
        df_config = conn.read(worksheet=PLANILHA_ABA_CONFIG)
        
        # Dicionário de Código -> Fornecedor (Colunas A e B -> Índices 0 e 1)
        codigos = df_config.iloc[:, 0].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        fornecedores = df_config.iloc[:, 1].astype(str).str.strip()
        dict_fornecedores = dict(zip(codigos, fornecedores))
        
        # Lista de Compradores (Coluna E -> Índice 4)
        if len(df_config.columns) >= 5:
            compradores_raw = df_config.iloc[:, 4].dropna().astype(str).str.strip().tolist()
            # Remove vazios e duplicados
            lista_compradores = sorted(list(set([c for c in compradores_raw if c and c.lower() != 'nan' and c.lower() != 'none'])))
        else:
            lista_compradores = []
            
    except Exception:
        dict_fornecedores = {}
        lista_compradores = []

    return df_dados, dict_fornecedores, lista_compradores

# Carrega os dados do Sheets
df_base, dict_fornecedores, lista_compradores = carregar_dados()

# Inicializa a memória da sessão para permitir atualização em tempo real
if 'df_divergencia' not in st.session_state:
    st.session_state['df_divergencia'] = df_base

st.title("📊 Base de Divergências")
st.write("Edite os dados abaixo. Ao digitar o **Cód** e apertar `Enter`, o **Fornecedor** subirá automaticamente.")

# Garante que as linhas fiquem com a data de hoje visualmente antes de preencher
st.session_state['df_divergencia']['Data'] = st.session_state['df_divergencia']['Data'].fillna(date.today())

# --- 3. INTERFACE DE EDIÇÃO ---
df_editado = st.data_editor(
    st.session_state['df_divergencia'],
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
        "Cód": st.column_config.TextColumn("Cód"),
        "Fornecedor": st.column_config.TextColumn("Fornecedor", disabled=True),
        "Comprador": st.column_config.SelectboxColumn("Comprador", options=lista_compradores),
        "R$ Diferença": st.column_config.NumberColumn("R$ Diferença", format="R$ %.2f")
    },
    key="editor_dados"
)

# --- 4. GATILHO DE PREENCHIMENTO AUTOMÁTICO IMEDIATO ---
mudou_fornecedor = False

for i in df_editado.index:
    cod_digitado = str(df_editado.at[i, 'Cód']).replace('.0', '').strip()
    
    # Se o código existir e estiver no nosso dicionário
    if cod_digitado and cod_digitado != 'None' and cod_digitado != 'nan':
        if cod_digitado in dict_fornecedores:
            fornecedor_correto = dict_fornecedores[cod_digitado]
            
            # Se o fornecedor na tela for diferente do correto, atualizamos
            if df_editado.at[i, 'Fornecedor'] != fornecedor_correto:
                df_editado.at[i, 'Fornecedor'] = fornecedor_correto
                mudou_fornecedor = True

# Se detectou que um fornecedor novo subiu, recarrega a tela na mesma hora
if mudou_fornecedor:
    st.session_state['df_divergencia'] = df_editado
    st.rerun()
else:
    # Apenas mantém os dados salvos em memória enquanto o usuário digita
    st.session_state['df_divergencia'] = df_editado

# --- 5. BOTÃO DE SALVAR NO SHEETS ---
if st.button("💾 Salvar Alterações", type="primary"):
    with st.spinner("Sincronizando com o Google Sheets..."):
        try:
            # Prepara a planilha final convertendo a data para texto padrão PT-BR
            df_salvar = st.session_state['df_divergencia'].copy()
            df_salvar['Data'] = pd.to_datetime(df_salvar['Data'], errors='coerce').dt.strftime('%d/%m/%Y')
            
            # Envia para a nuvem
            conn.update(worksheet=PLANILHA_ABA_DADOS, data=df_salvar)
            
            st.success("Dados salvos com sucesso!")
            st.cache_data.clear() # Limpa o cache
        except Exception as e:
            st.error(f"Erro ao salvar na planilha: {e}")
