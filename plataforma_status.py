import datetime
import gspread
import streamlit as st
import json

# --- CONFIGURAÇÃO DA GOOGLE SHEET ---
LINK_PLANILHA = "https://docs.google.com/spreadsheets/d/1cYhrFo_JVrTqtaxHXqiKc_gOl-En0FEYfpVs-58e9S0"
NOME_DA_ABA = "controle"

# Configuração da página web do Streamlit
st.set_page_config(page_title="Portal de Status - Logística", page_icon="📦", layout="centered")

st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; }
        .stAlert { border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def conectar_google_sheets():
    # Usa o decodificador nativo simplificado do gspread para ler a string do Secrets
    info_json = st.secrets["gspread_credentials"]["json_string"]
    dic_chaves = json.loads(info_json, strict=False)
    
    # Faz a autenticação direta via Conta de Serviço usando o gspread moderno
    cliente = gspread.service_account_from_dict(dic_chaves)
    planilha = cliente.open_by_url(LINK_PLANILHA)
    return planilha.worksheet(NOME_DA_ABA)

def calcular_fluxo_status(linha):
    def pegar_valor(idx):
        return str(linha[idx]).strip() if len(linha) > idx else ""

    responsavel = pegar_valor(0)
    operacao = pegar_valor(1)
    incoterm = pegar_valor(2)
    cliente = pegar_valor(3)
    nf = pegar_valor(4)
    transportador = pegar_valor(5)
    coleta = pegar_valor(6)
    data_solic = pegar_valor(7)
    data_col = pegar_valor(8)
    observacoes = pegar_valor(9)

    transportador_valido = transportador and transportador != "-"

    fases = {
        "Fase 1: Aguardando Separação": "🔴 Pendente",
        "Fase 2: Faturado (N.F. Gerada)": "🔴 Pendente",
        "Fase 3: Coleta Solicitada": "🔴 Pendente",
        "Fase 4: Coleta Efetivada": "🔴 Pendente"
    }
    
    status_atual = "⚪ Aguardando Processamento"
    detalhe_operacional = "Pedido registrado, aguardando início da separação."

    if cliente:
        fases["Fase 1: Aguardando Separação"] = "🟢 Concluído"
        status_atual = "🟠 Em Separação / Embalagem"
        detalhe_operacional = f"Pedido em separação técnica. Responsável pela ação: {responsavel if responsavel else 'Não informado'}."

    if nf and nf != "None" and nf != "":
        fases["Fase 2: Faturado (N.F. Gerada)"] = "🟢 Concluído"
        status_atual = "🟡 Faturado"
        detalhe_operacional = f"Nota Fiscal {nf} emitida. Aguardando agendamento ou contato do transportador."

    if coleta and coleta != "None" and coleta != "":
        fases["Fase 3: Coleta Solicitada"] = "🟢 Concluído"
        status_atual = "🔵 Coleta Solicitada"
        detalhe_operacional = f"Solicitação realizada sob o registro/contato: '{coleta}'."

    if data_col and data_col != "None" and data_col != "":
        fases["Fase 4: Coleta Efetivada"] = "🟢 Concluído"
        status_atual = "🟢 Coleta Efetivada"
        detalhe_operacional = f"Material coletado e retirado da expedição física em: {data_col}."

    return {
        "status_atual": status_atual,
        "detalhe": detalhe_operacional,
        "fases": fases,
        "detalhes_card": {
            "Cliente": cliente,
            "N.F.": nf,
            "Incoterm": incoterm if incoterm else "Não informado",
            "Operação": operacao if operacao else "Não informada",
            "Transportador": transportador if transportador_valido else "Aguardando definição",
            "Coleta/Rastreio": coleta if coleta else "Não solicitado",
            "Data Contato": data_solic if data_solic else "Não realizado",
            "Observações": observacoes if observacoes else "Nenhuma observação registrada para esta nota."
        }
    }

st.title("📦 Portal de Status de Pedidos")
st.write("Insira o número da Nota Fiscal para verificar o fluxo do processo em tempo real.")

try:
    aba_planilha = conectar_google_sheets()
    todos_dados = aba_planilha.get_all_values()
    linhas_pedidos = todos_dados[1:]
    st.success("Conexão estabelecida com a base de dados Logística 2026!")
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

pesquisa = st.text_input("Digite o número exato da Nota Fiscal:", placeholder="Ex: 47219...").strip()

if pesquisa:
    pedido_encontrado = None
    for linha in linhas_pedidos:
        nf_numero = str(linha).strip() if len(linha) > 4 else ""
        if pesquisa == nf_numero:
            pedido_encontrado = linha
            break
            
    if pedido_encontrado:
        info = calcular_fluxo_status(pedido_encontrado)
        cards = info["detalhes_card"]
        
        st.markdown(f"## 📋 Cliente: {cards['Cliente']}")
        st.markdown(f"### Status Atual: {info['status_atual']}")
        st.info(info["detalhe"])
        
        st.markdown("### ⏳ Linha do Tempo do Processo:")
        for fase, situacao in info["fases"].items():
            if "🟢" in situacao:
                st.markdown(f"**{fase}** | {situacao}")
            else:
                st.markdown(f"<span style='color: gray;'>**{fase}** | {situacao}</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 🔍 Detalhes do Pedido:")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Nota Fiscal", value=cards["N.F."])
            st.metric(label="Modalidade de Frete", value=cards["Incoterm"])
        with col2:
            st.metric(label="Transportador / Contato", value=cards["Transportador"])
            st.metric(label="Natureza da Operação", value=cards["Operação"])
        with col3:
            st.metric(label="Nº Coleta / Registro", value=cards["Coleta/Rastreio"])
            st.metric(label="Data do Contato", value=cards["Data Contato"])
            
        st.markdown("#### 💬 Mensagem / Observações Gerais (Coluna J):")
        st.warning(cards["Observações"])
    else:
        st.warning(f"Nenhuma Nota Fiscal localizada com o número: '{pesquisa}'")

st.markdown("<br><br><p style='text-align: right; color: gray; font-style: italic; font-size: 12px;'>Desenvolvido por Diego Elvis | Versão R.1.0 de 06.07</p>", unsafe_allow_html=True)
