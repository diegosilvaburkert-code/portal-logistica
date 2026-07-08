import datetime
import gspread
import streamlit as st
import json

# --- CONFIGURAÇÃO DA GOOGLE SHEET ---
LINK_PLANILHA = "https://docs.google.com/spreadsheets/d/1cYhrFo_JVrTqtaxHXqiKc_gOl-En0FEYfpVs-58e9S0"
NOME_DA_ABA = "controle"

# Configuração da página web do Streamlit
st.set_page_config(page_title="Portal de Status - Logística", page_icon="📦", layout="centered")

# Estilização CSS avançada para o Stepper e centralização de cartões customizados
st.markdown("""
    <style>
        .stApp { background-color: #f8f9fa; }
        .stAlert { border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
        
        /* Estrutura do Painel Horizontal de Etapas */
        .stepper-wrapper {
            display: flex;
            justify-content: space-between;
            margin-top: 30px;
            margin-bottom: 30px;
            position: relative;
        }
        .stepper-wrapper::before {
            content: "";
            position: absolute;
            top: 25px;
            left: 0;
            width: 100%;
            height: 4px;
            background-color: #e0e0e0;
            z-index: 1;
        }
        .stepper-item {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
            z-index: 2;
        }
        .stepper-item .step-counter {
            position: relative;
            width: 50px;
            height: 50px;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #e0e0e0;
            border-radius: 50%;
            font-weight: bold;
            color: #ffffff;
            font-size: 18px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .stepper-item .step-name {
            margin-top: 10px;
            font-size: 13px;
            font-weight: 600;
            color: #888888;
            text-align: center;
        }
        .stepper-item.completed .step-counter {
            background-color: #2ec866;
            color: white;
        }
        .stepper-item.completed .step-name {
            color: #2ec866;
            font-weight: bold;
        }
        .stepper-line-active {
            position: absolute;
            top: 25px;
            left: 0;
            height: 4px;
            background-color: #2ec866;
            z-index: 1;
            transition: width 0.5s ease;
        }

        /* Estilização para o bloco centralizado de Transportadora */
        .transportador-box {
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            margin-top: 15px;
            margin-bottom: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        }
        .transportador-title {
            font-size: 14px;
            color: #555555;
            margin-bottom: 5px;
            font-weight: 500;
        }
        .transportador-value {
            font-size: 20px;
            color: #1e3d59;
            font-weight: bold;
            word-wrap: break-word;
        }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def conectar_google_sheets():
    info_json = st.secrets["gspread_credentials"]["json_string"]
    dic_chaves = json.loads(info_json, strict=False)
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

    etapa_atingida = 0 
    status_atual = "⚪ Aguardando Processamento"
    detalhe_operacional = "Pedido registrado, aguardando início da separação."

    if cliente:
        etapa_atingida = 1
        status_atual = "🟠 Em Separação / Embalagem"
        detalhe_operacional = f"Pedido em separação técnica. Responsável pela ação: {responsavel if responsavel else 'Não informado'}."

    if nf and nf != "None" and nf != "":
        etapa_atingida = 2
        status_atual = "🟡 Faturado"
        detalhe_operacional = f"Nota Fiscal {nf} emitida. Aguardando agendamento ou contato do transportador."

    if coleta and coleta != "None" and coleta != "":
        etapa_atingida = 3
        status_atual = "🔵 Coleta Solicitada"
        detalhe_operacional = f"Solicitação realizada sob o registro/contato: '{coleta}'."

    if data_col and data_col != "None" and data_col != "":
        etapa_atingida = 4
        status_atual = "🟢 Coleta Efetivada"
        detalhe_operacional = f"Material coletado e retirado da expedição física em: {data_col}."

    return {
        "etapa_atingida": etapa_atingida,
        "status_atual": status_atual,
        "detalhe": detalhe_operacional,
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
    linhas_pedidos = [l for l in todos_dados[1:] if any(l)]
    st.success("Conexão estabelecida com a base de dados Logística 2026!")
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

pesquisa = st.text_input("Digite o número exato da Nota Fiscal:", placeholder="Ex: 47219...").strip()

if pesquisa:
    pedido_encontrado = None
    for linha in lines_pedidos:
        if len(linha) > 4:
            nf_numero = str(linha[4]).strip()
            if pesquisa == nf_numero:
                pedido_encontrado = linha
                break
            
    if pedido_encontrado:
        info = calcular_fluxo_status(pedido_encontrado)
        cards = info["detalhes_card"]
        num_etapa = info["etapa_atingida"]
        
        st.markdown(f"## 📋 Cliente: {cards['Cliente']}")
        st.markdown(f"### Status Atual: {info['status_atual']}")
        st.info(info["detalhe"])
        
        # --- PAINEL HORIZONTAL DE PROGRESSO ---
        st.markdown("### ⏳ Fluxo do Processo:")
        largura_linha_verde = "0%"
        if num_etapa == 2: largura_linha_verde = "33%"
        elif num_etapa == 3: largura_linha_verde = "66%"
        elif num_etapa == 4: largura_linha_verde = "100%"
        
        html_stepper = f"""
        <div style="position: relative;">
            <div class="stepper-line-active" style="width: {largura_linha_verde};"></div>
            <div class="stepper-wrapper">
                <div class="stepper-item {'completed' if num_etapa >= 1 else ''}">
                    <div class="step-counter">✓</div>
                    <div class="step-name">Em Separação</div>
                </div>
                <div class="stepper-item {'completed' if num_etapa >= 2 else ''}">
                    <div class="step-counter">✓</div>
                    <div class="step-name">Faturado</div>
                </div>
                <div class="stepper-item {'completed' if num_etapa >= 3 else ''}">
                    <div class="step-counter">✓</div>
                    <div class="step-name">Coleta Solicitada</div>
                </div>
                <div class="stepper-item {'completed' if num_etapa >= 4 else ''}">
                    <div class="step-counter">✓</div>
                    <div class="step-name">Coleta Efetivada</div>
                </div>
            </div>
        </div>
        """
        st.markdown(html_stepper, unsafe_allow_html=True)
        
        st.markdown("---")
        st.markdown("### 🔍 Detalhes do Pedido:")
        
        # --- LINHA 1: Informações principais compactas ---
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Nota Fiscal", value=cards["N.F."])
        with col2:
            st.metric(label="Nº Coleta / Registro", value=cards["Coleta/Rastreio"])
        with col3:
            st.metric(label="Modalidade de Frete", value=cards["Incoterm"])
            
        # --- LINHA 2: Bloco exclusivo, amplo e centralizado para a transportadora completa ---
        html_transportador = f"""
        <div class="transportador-box">
            <div class="transportador-title">Transportador / Contato Completo</div>
            <div class="transportador-value">{cards['Transportador']}</div>
        </div>
        """
        st.markdown(html_transportador, unsafe_allow_html=True)
        
        # --- LINHA 3: Dados complementares finais ---
        col_inf1, col_inf2 = st.columns(2)
        with col_inf1:
            st.metric(label="Natureza da Operação", value=cards["Operação"])
        with col_inf2:
            st.metric(label="Data do Contato", value=cards["Data Contato"])
            
        st.markdown("#### 💬 Mensagem / Observações Gerais (Coluna J):")
        st.warning(cards["Observações"])
    else:
        st.warning(f"Nenhuma Nota Fiscal localizada com o número: '{pesquisa}'")

