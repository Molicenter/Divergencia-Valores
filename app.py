import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection

# Configuração da página
st.set_page_config(page_title="Gestão de Divergência", layout="wide")
st.title("📊 Gestão - Divergência de Preço")

# 1. Estabelecendo a conexão com o Google Sheets
# O Streamlit vai buscar as credenciais no arquivo .streamlit/secrets.toml
conn = st.connection("gsheets", type=GSheetsConnection)

# Nome da aba da sua planilha (conforme a imagem, está como "Página1")
PLANILHA_ABA = "Página1"

# Definindo as colunas padrão caso a planilha esteja vazia
colunas_padrao = ["Data", "NF", "Cód", "Fornecedor", "Produtos", "Comprador", "Loja", "R$ Diferença", "Protocolo"]

# 2. Lendo os dados do Google Sheets
@st.cache_data(ttl=5) # Cache curto para atualizar rápido, mas não sobrecarregar a API
def carregar_dados():
    try:
        df = conn.read(worksheet=PLANILHA_ABA, usecols=list(range(len(colunas_padrao))))
        # Se a planilha estiver totalmente vazia (nova), cria o DataFrame com as colunas
        if df.empty or len(df.columns) < len(colunas_padrao):
            df = pd.DataFrame(columns=colunas_padrao)
        return df.dropna(how='all') # Remove linhas totalmente vazias
    except Exception as e:
        st.error(f"Erro ao conectar com a planilha. Verifique o secrets.toml e o compartilhamento. Detalhes: {e}")
        return pd.DataFrame(columns=colunas_padrao)

df_divergencia = carregar_dados()

# 3. Interface de Edição (Estilo Excel)
st.subheader("Base de Divergências")
st.write("Edite os dados diretamente na tabela abaixo. Após finalizar, clique em **Salvar Alterações**.")

# O st.data_editor exibe e permite editar os dados
df_editado = st.data_editor(
    df_divergencia,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Data": st.column_config.TextColumn("Data"), # Mantendo como texto simples inicialmente para facilitar a digitação da planilha
        "R$ Diferença": st.column_config.NumberColumn("R$ Diferença", format="R$ %.2f"),
        "Protocolo": st.column_config.TextColumn("Protocolo")
    },
    key="editor_dados"
)

# Botão para salvar no Google Sheets
if st.button("💾 Salvar Alterações no Google Sheets", type="primary"):
    with st.spinner("Salvando..."):
        # Atualiza a planilha no Google Drive
        conn.update(worksheet=PLANILHA_ABA, data=df_editado)
        st.success("Dados salvos com sucesso!")
        st.cache_data.clear() # Limpa o cache para recarregar os dados novos

# 4. Processamento do Dashboard Consolidado
st.divider()
st.subheader("Painel Consolidado por Comprador")

df_dash = df_editado.copy()

if not df_dash.empty and len(df_dash) > 0:
    # Tratamento de dados para o cálculo
    df_dash['R$ Diferença'] = pd.to_numeric(df_dash['R$ Diferença'], errors='coerce').fillna(0)
    # Tem ação se o protocolo estiver preenchido
    df_dash['Tem_Acao'] = df_dash['Protocolo'].astype(str).str.strip().replace('None', '').replace('nan', '') != ''
    
    # Agrupamentos
    resumo = df_dash.groupby('Comprador').agg(
        Qtde=('Comprador', 'count'),
        Total_RS=('R$ Diferença', 'sum')
    )
    
    acoes = df_dash[df_dash['Tem_Acao']].groupby('Comprador').agg(
        Acoes=('Comprador', 'count'),
        RS_Acoes=('R$ Diferença', 'sum')
    )
    
    # Consolidando
    consolidado = resumo.merge(acoes, on='Comprador', how='left').fillna(0)
    
    # Cálculos de Diferença e Percentual
    consolidado['Reg_Dif'] = consolidado['Acoes'] - consolidado['Qtde']
    consolidado['Reg_Pct'] = np.where(consolidado['Qtde'] == 0, 0, consolidado['Acoes'] / consolidado['Qtde'])
    
    consolidado['RS_Dif'] = consolidado['RS_Acoes'] - consolidado['Total_RS']
    consolidado['RS_Pct'] = np.where(consolidado['Total_RS'] == 0, 0, consolidado['RS_Acoes'] / consolidado['Total_RS'])
    
    consolidado = consolidado[['Qtde', 'Acoes', 'Reg_Dif', 'Reg_Pct', 'Total_RS', 'RS_Acoes', 'RS_Dif', 'RS_Pct']]
    
    # Linha de Totais
    total_row = pd.DataFrame({
        'Qtde': [consolidado['Qtde'].sum()],
        'Acoes': [consolidado['Acoes'].sum()],
        'Reg_Dif': [consolidado['Reg_Dif'].sum()],
        'Reg_Pct': [consolidado['Acoes'].sum() / consolidado['Qtde'].sum() if consolidado['Qtde'].sum() > 0 else 0],
        'Total_RS': [consolidado['Total_RS'].sum()],
        'RS_Acoes': [consolidado['RS_Acoes'].sum()],
        'RS_Dif': [consolidado['RS_Dif'].sum()],
        'RS_Pct': [consolidado['RS_Acoes'].sum() / consolidado['Total_RS'].sum() if consolidado['Total_RS'].sum() > 0 else 0]
    }, index=['Total Compradores'])
    
    consolidado = pd.concat([consolidado, total_row])
    
    # Exibição do Consolidado
    st.dataframe(
        consolidado,
        use_container_width=True,
        column_config={
            "Comprador": st.column_config.TextColumn("Compradores"),
            "Qtde": st.column_config.NumberColumn("Qtde", format="%d"),
            "Acoes": st.column_config.NumberColumn("Ações", format="%d"),
            "Reg_Dif": st.column_config.NumberColumn("<>", format="%d"),
            "Reg_Pct": st.column_config.ProgressColumn("% (Registros)", format="%.1f%%", min_value=0, max_value=1),
            "Total_RS": st.column_config.NumberColumn("Total", format="R$ %.2f"),
            "RS_Acoes": st.column_config.NumberColumn("R$ Ações", format="R$ %.2f"),
            "RS_Dif": st.column_config.NumberColumn("<>", format="R$ %.2f"),
            "RS_Pct": st.column_config.ProgressColumn("% (R$)", format="%.1f%%", min_value=0, max_value=1)
        }
    )
else:
    st.info("A planilha está vazia no momento. Adicione registros na tabela acima e clique em Salvar.")
