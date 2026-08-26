import datetime
import gspread
import streamlit as st
import json

# --- CONFIGURAÇÃO DA GOOGLE SHEET ---
LINK_PLANILHA = "https://google.com/spreadsheets/d/1cYhrFo_JVrTqtaxHXqiKc_gOl-En0FEYfpVs-58e9S0/edit?gid=0#gid=0"
NOME_DA_ABA = "controle"

# Configuração da página web do Streamlit
st.set_page_config(page_title="Portal de Status - Logística", page_icon="📦", layout="centered")

# Estilização CSS avançada (Identidade Visual, Centralização Completa e Ajuste de Layout)
st.markdown("""
    <style>
        /* 1. Alteração do Fundo da Página para o Azul Claro da Empresa */
        .stApp { 
            background-color: #e6effa; 
        }
        
        /* CENTRALIZAÇÃO GLOBAL DE TEXTOS E ELEMENTOS INDICADOS */
        .stApp h2, .stApp h3, .stApp h4, .stApp p, .stMarkdown p {
            text-align: center !important;
            justify-content: center !important;
        }
        
        /* Centralizar os alertas do Streamlit (st.success, st.info, st.warning) */
        .stAlert { 
            border-radius: 8px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            text-align: center !important;
        }
        .stAlert > div {
            justify-content: center !important;
            text-align: center !important;
        }
        
        /* Centralizar o bloco de input da Nota Fiscal e seu texto descritivo */
        [data-testid="stWidgetLabel"] {
            text-align: center !important;
            display: block !important;
            width: 100% !important;
        }
        [data-testid="stTextInput"] div[data-baseweb="input"] {
            max-width: 400px !important;
            margin: 0 auto !important;
        }
        [data-testid="stTextInput"] input {
            text-align: center !important;
        }

        /* 2. CORREÇÃO: Forçar quebra de linha em textos longos do st.metric */
        [data-testid="stMetricValue"] {
            white-space: normal !important;
            word-break: break-word !important;
            overflow-wrap: break-word !important;
            font-size: 1.6rem !important;
            line-height: 1.3 !important;
        }
        
        /* Banner Corporativo Superior */
        .header-banner {
            background: linear-gradient(90deg, #4f83cc, #1b4f93);
            padding: 25px;
            border-radius: 10px;
            color: white;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        }
        .header-banner h1 {
            color: white !important;
            font-size: 24px !important;
            margin: 0 !important;
            letter-spacing: 1px;
            font-weight: 700;
            text-align: center !important;
        }
        .header-banner p {
            margin: 5px 0 0 0 !important;
            font-size: 14px;
            opacity: 0.9;
            text-align: center !important;
        }

                /* Estrutura do Painel Horizontal de Etapas (Stepper) */
        .stepper-wrapper {
            display: flex;
            justify-content: space-between;
            margin-top: 30px;
            margin-bottom: 30px;
            position: relative;
        }
        /* Linha cinza de fundo contínua e arredondada (IGUAL À IMAGEM) */
        .stepper-wrapper::before {
            content: "";
            position: absolute;
            top: 21px; /* Centraliza verticalmente com o círculo */
            left: 0;
            width: 100%;
            height: 14px; /* Barra mais grossa como a do modelo */
            background-color: #dbdbdb;
            border-radius: 10px; /* Pontas totalmente arredondadas */
            z-index: 1;
        }
        .stepper-item {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
            z-index: 3; /* Fica acima das barras */
        }
        .stepper-item .step-counter {
            position: relative;
            width: 50px;
            height: 50px;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #ffffff; /* Fundo branco para os círculos não iniciados */
            border: 4px solid #cbd6e2;
            border-radius: 50%;
            font-weight: bold;
            color: #cbd6e2;
            font-size: 18px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            z-index: 4;
        }
        .stepper-item .step-name {
            margin-top: 10px;
            font-size: 13px;
            font-weight: 600;
            color: #5c6b73;
            text-align: center;
        }
        /* Círculo completo com verde brilhante */
        .stepper-item.completed .step-counter {
            background-color: #00e63d;
            border-color: #00e63d;
            color: white;
        }
        .stepper-item.completed .step-name {
            color: #1b4f93;
            font-weight: bold;
        }
        /* Linha verde ativa que vai preenchendo (IGUAL À IMAGEM) */
        .stepper-line-active {
            position: absolute;
            top: 21px; /* Alinhado perfeitamente com a cinza */
            left: 0;
            height: 14px;
            background: linear-gradient(90deg, #00c732, #00e63d); /* Gradiente verde vivo */
            border-radius: 10px; /* Pontas arredondadas ao encher */
            z-index: 2; /* Fica acima da cinza e abaixo dos círculos */
            transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); /* Animação suave de preenchimento */
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

# --- APLICAÇÃO DO BANNER CORPORATIVO ---
st.markdown("""
    <div class="header-banner">
        <h1>WELCOME TO THE PIONEERS OF FLOW</h1>
        <p>Portal Logístico de Rastreamento de Pedidos em Tempo Real</p>
    </div>
""", unsafe_allow_html=True)

st.write("Insira o número da Nota Fiscal abaixo para verificar o fluxo do processo.")

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
    for linha in list(linhas_pedidos):
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
        
        # --- PAINEL HORIZONTAL DE PROGRESSO ESTILO BARRA CONTÍNUA ---
        st.markdown("### ⏳ Fluxo do Processo:")
        
        # Define o preenchimento da barra verde contínua com compensação para as extremidades
        largura_calculada = "0%"
        if num_etapa == 1:
            largura_calculada = "25px" # Preenche apenas o início do primeiro círculo
        elif num_etapa == 2:
            largura_calculada = "calc(33.33% + 25px)"
        elif num_etapa == 3:
            largura_calculada = "calc(66.66% + 25px)"
        elif num_etapa == 4:
            largura_calculada = "100%" # Barra totalmente preenchida e arredondada no final

        html_stepper = f"""
        <div style="position: relative; width: 100%; box-sizing: border-box; padding: 0 25px;">
            <div class="stepper-line-active" style="width: {largura_calculada};"></div>
            <div class="stepper-wrapper" style="margin: 0; padding: 0;">
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
        
        # --- LINHA 1 ---
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Nota Fiscal", value=cards["N.F."])
        with col2:
            st.metric(label="Nº Coleta / Registro", value=cards["Coleta/Rastreio"])
        with col3:
            st.metric(label="Modalidade de Frete", value=cards["Incoterm"])
            
        # --- LINHA 2 (Agora auto-ajustável e sem cortes) ---
        st.metric(label="Transportador / Contato Completo", value=cards["Transportador"])
                # --- LINHA 3 ---
        col_inf1, col_inf2 = st.columns(2)
        with col_inf1:
            st.metric(label="Natureza da Operação", value=cards["Operação"])
        with col_inf2:
            st.metric(label="Data do Contato", value=cards["Data Contato"])
            
        st.markdown("#### 💬 Mensagem / Observações Gerais (Coluna J):")
        st.warning(cards["Observações"])
    else:
        st.warning(f"Nenhuma Nota Fiscal localizada com o número: '{pesquisa}'")

st.markdown("Desenvolvido por Diego Elvis | Versão R.1.1 de 08.26", unsafe_allow_html=True)

