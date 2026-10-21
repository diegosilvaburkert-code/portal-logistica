import datetime
import json
import re
import unicodedata

from html import escape as esc
from itertools import count
import gspread
import pandas as pd
import streamlit as st

# --- CONFIGURAÇÃO DA GOOGLE SHEET ---
LINK_PLANILHA = "https://google.com/spreadsheets/d/1cYhrFo_JVrTqtaxHXqiKc_gOl-En0FEYfpVs-58e9S0/edit?gid=0#gid=0"
NOME_DA_ABA = "controle"
ABA_PENDENTES = "Pendentes (FUP)"
ABA_CONSERTO = "Retorno Conserto"  # nome exato da aba de reparos na planilha
CLIENTES_IGNORADOS = ["burkert"]  # clientes excluídos do Dashboard (parte do nome, sem acento/maiúscula)
PRAZO_ALERTA = 3  # dias sem coleta a partir dos quais o caso é considerado atrasado

st.set_page_config(page_title="Portal de Status - Logística", page_icon="📦", layout="wide")

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

        /* CORREÇÃO DOS METRICS: Centraliza os Títulos Pequenos e os Valores Grandes */
        [data-testid="stMetric"] {
            text-align: center !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: center !important;
            justify-content: center !important;
        }
        [data-testid="stMetricLabel"] {
            text-align: center !important;
            display: block !important;
            width: 100% !important;
            justify-content: center !important;
        }
        [data-testid="stMetricValue"] {
            white-space: normal !important;
            word-break: break-word !important;
            overflow-wrap: break-word !important;
            font-size: 1.6rem !important;
            line-height: 1.3 !important;
            text-align: center !important;
            display: block !important;
            width: 100% !important;
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

        /* Estrutura do Painel Horizontal de Etapas (Stepper - BARRA CONTÍNUA) */
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
            top: 21px;
            left: 0;
            width: 100%;
            height: 14px;
            background-color: #dbdbdb;
            border-radius: 10px;
            z-index: 1;
        }
        .stepper-item {
            position: relative;
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
            z-index: 3;
        }
        .stepper-item .step-counter {
            position: relative;
            width: 50px;
            height: 50px;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #ffffff;
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
        .stepper-item.completed .step-counter {
            background-color: #00e63d;
            border-color: #00e63d;
            color: white;
        }
        .stepper-item.completed .step-name {
            color: #1b4f93;
            font-weight: bold;
        }
        .stepper-line-active {
            position: absolute;
            top: 21px;
            left: 0;
            height: 14px;
            background: linear-gradient(90deg, #00c732, #00e63d);
            border-radius: 10px;
            z-index: 2;
            transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        }
        /* Centraliza as abas (tabs) do topo */
        div[data-baseweb="tab-list"], [data-testid="stTabs"] [role="tablist"] {
            justify-content: center !important;
        }
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def conectar_google_sheets():
    """Conecta usando as credenciais da aba Secrets do Streamlit Cloud."""
    info_json = st.secrets["gspread_credentials"]["json_string"]
    dic_chaves = json.loads(info_json, strict=False)
    if "private_key" in dic_chaves:
        dic_chaves["private_key"] = dic_chaves["private_key"].replace("\\\\n", "\n").replace("\\n", "\n")
    cliente = gspread.service_account_from_dict(dic_chaves)
    return cliente.open_by_url(LINK_PLANILHA)


@st.cache_data(ttl=300)
def ler_valores(aba):
    return conectar_google_sheets().worksheet(aba).get_all_values()


def para_data(s):
    return pd.to_datetime(s, dayfirst=True, errors="coerce", format="mixed")


def limpa_status(s):
    s = re.sub(r"^[^\w\u00C0-\u00FF]+", "", str(s)).strip()
    return s or "Sem status"


def df_pendentes(valores):
    cols = ["Frete", "Cliente", "NF", "Transporte", "Ordem de coleta",
            "Data Solicitação", "Obs", "Status"]
    linhas = [(l + [""] * 8)[:8] for l in valores[1:]]
    df = pd.DataFrame(linhas, columns=cols)
    df = df[df["NF"].str.strip() != ""].copy()
    df["NF"] = df["NF"].str.strip()
    df["Status"] = df["Status"].map(limpa_status)
    df["Data Solicitação"] = para_data(df["Data Solicitação"])
    df["Dias pendente"] = (pd.Timestamp.today().normalize() - df["Data Solicitação"]).dt.days
    df["Faixa"] = pd.cut(df["Dias pendente"], [-9999, 0, 2, 5, 10, 99999],
                         labels=["Hoje", "1-2 dias", "3-5 dias", "6-10 dias", "+10 dias"])
    df["Atrasado"] = df["Dias pendente"] > PRAZO_ALERTA
    return df


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


def df_conserto(valores):
    """Lê a aba de reparos pelos NOMES das colunas (se alguém inserir/mover colunas, continua certo)."""
    ini, cab = 2, None
    for i, l in enumerate(valores[:8]):
        if any("nota do cliente" in _norm(c) for c in l):
            ini, cab = i + 1, [_norm(c) for c in l]
            break

    def achar(termos, padrao, comeca=None):
        if cab is None:
            return padrao  # cabeçalho não localizado: usa a posição padrão
        for j, h in enumerate(cab):
            if all(t in h for t in termos) and (comeca is None or h.startswith(comeca)):
                return j
        return None

    mapa = {
        "Recebimento": achar(("recebimento", "data"), 0),
        "Nota cliente": achar(("numero", "nota"), 1),
        "Cliente": achar(("cliente",), 2, "cliente"),
        "Pendência": achar(("pendencia",), 3),
        "Entrada por": achar(("entrada", "realizada"), 4),
        "Data entrada": achar(("entrada", "data"), 5),
        "Liberado": achar(("liberado",), 7),
        "NF retorno": achar(("retorno",), 9),
        "Emissão NF saída": achar(("emissao",), 10),
    }
    linhas = valores[ini:]
    df = pd.DataFrame({k: [(l[j].strip() if j is not None and j < len(l) else "") for l in linhas]
                       for k, j in mapa.items()})
    df = df[(df["Cliente"] != "") | (df["Nota cliente"] != "")].copy()
    df["_ordem"] = para_data(df["Recebimento"])
    p = df["Pendência"].str.lower()
    sem_pend = (p == "") | p.str.match(r"^(finalizado|n[aã]o h[aá] pend)")
    df["_pend"] = ~sem_pend
    df["_lib"] = df["Liberado"].str.upper().isin(["TRUE", "VERDADEIRO", "SIM", "X", "1", "✓"])
    return df


def mapa_coletas(valores):
    """Aba 'controle': liga o nº da NF (col. N.F.) à data da coleta (DATA Col.), solicitação e transportadora."""
    m = {}
    for l in valores[1:]:
        l = list(l) + [""] * 9
        nf = str(l[4]).strip()
        if not nf:
            continue
        reg = {"transp": str(l[5]).strip(), "data_solic": str(l[7]).strip(), "data_col": str(l[8]).strip()}
        if nf not in m or (reg["data_col"] and not m[nf]["data_col"]):
            m[nf] = reg
    return m


def status_conserto(r, coletas=None):
    """Fluxo sequencial: cada fase só é considerada OK se as anteriores também estiverem OK."""
    coletas = coletas or {}
    if not (r["Nota cliente"] and r["Cliente"]):
        return {"etapa": 0, "status": "⚪ Dados incompletos", "bloqueado": False, "coleta": {},
                "detalhe": "Faltam o número da nota ou o cliente no registro.",
                "passos": ["pendente"] * 7}
    if r["_pend"]:
        return {"etapa": 2, "status": "🔴 Bloqueado — aguardando resolução da divergência",
                "bloqueado": True, "coleta": {},
                "detalhe": f"Pendência registrada: {r['Pendência']}. O material só segue após a divergência ser resolvida.",
                "passos": ["ok", "bloqueado"] + ["pendente"] * 5}

    ent = bool(r["Entrada por"] and r["Data entrada"])
    lib, nf, dt = bool(r["_lib"]), bool(r["NF retorno"]), bool(r["Emissão NF saída"])
    col = coletas.get(r["NF retorno"].strip(), {}) if nf else {}
    s3 = ent                 # Entregue para conserto
    s4 = s3 and lib          # Liberado pela Assistência (flag)
    s5 = s4 and nf           # Aguardando Emissão de Retorno -> OK quando a NF de retorno é preenchida
    s6 = s5 and dt           # Aguardando Coleta -> NF de retorno + data de emissão
    s7 = s6 and bool(col.get("data_col"))   # Coletado -> data de coleta na aba controle (pelo nº da NF)
    passos = ["ok", "ok"] + ["ok" if x else "pendente" for x in (s3, s4, s5, s6, s7)]
    etapa = 2 + sum((s3, s4, s5, s6, s7))

    if s7:
        status = "🟢 Coletado"
        detalhe = (f"Material coletado em {col['data_col']}"
                   + (f" pela transportadora {col['transp']}" if col.get("transp") and col["transp"] != "-" else "")
                   + f" (NF de retorno {r['NF retorno']}). Processo concluído.")
    elif s6:
        status = "🔵 Aguardando coleta"
        detalhe = (f"NF de retorno {r['NF retorno']} emitida em {r['Emissão NF saída']}. "
                   "Aguardando o cliente coletar o material.")
        if col.get("data_solic"):
            detalhe += f" Coleta solicitada em {col['data_solic']}."
    elif s4:
        status = "🟣 Aguardando Emissão de Retorno"
        if s5:
            detalhe = (f"NF de retorno {r['NF retorno']} informada, mas falta a data de emissão "
                       "para liberar a coleta.")
        else:
            detalhe = ("Material liberado pela assistência. Aguardando a emissão da NF de retorno de conserto "
                       "para encaminhar ao cliente realizar a coleta.")
    elif s3:
        status = "🟠 Entregue para conserto"
        detalhe = f"Entrada realizada por {r['Entrada por']} em {r['Data entrada']}. Material em conserto."
    else:
        status = "⚪ Aguardando Entrada"
        detalhe = "Nota e cliente registrados, sem pendências. Aguardando a entrada do material."

    if (lib and not s3) or (nf and not s4) or (dt and not s5) or (col.get("data_col") and not s6):
        detalhe += " ⚠️ Há campos preenchidos fora da sequência do fluxo; confira a planilha."
    return {"etapa": etapa, "status": status, "bloqueado": False, "detalhe": detalhe,
            "passos": passos, "coleta": col}


def html_timeline(passos, etapa):
    nomes = ["Aguardando Entrada", "Pendência / Bloqueio", "Entregue p/ Conserto",
             "Liberado pela Assistência", "Aguardando Emissão de Retorno", "Aguardando Coleta", "Coletado"]
    bloqueado = "bloqueado" in passos
    if bloqueado:
        etapa = 2  # a barra vai até o X vermelho (fase 2)
    # a barra vai até o CENTRO do círculo da etapa (cada etapa ocupa 1/7 da trilha)
    largura = {0: "0%", 1: "7.14%", 2: "21.43%", 3: "35.71%", 4: "50%", 5: "64.29%",
               6: "78.57%", 7: "100%"}[etapa]
    fundo = "background:linear-gradient(90deg,#e53935,#c62828);" if bloqueado else ""
    itens = ""
    for nome, p in zip(nomes, passos):
        classe = {"ok": "completed", "bloqueado": "blocked", "pendente": ""}[p]
        icone = {"ok": "✓", "bloqueado": "✕", "pendente": ""}[p]
        itens += (f'<div class="stepper-item {classe}"><div class="step-counter">{icone}</div>'
                  f'<div class="step-name">{nome}</div></div>')
    return ('<style>.stepper-item.blocked .step-counter{background:#e53935;border-color:#e53935;color:#fff}'
            '.stepper-item.blocked .step-name{color:#e53935;font-weight:bold}</style>'
            '<div style="position:relative;width:100%;box-sizing:border-box;padding:0 25px;">'
            '<div class="stepper-wrapper" style="margin:0;padding:0;">'
            f'<div class="stepper-line-active" style="width:{largura};{fundo}"></div>{itens}</div></div>')


def df_controle(valores):
    cols = ["Responsável", "Operação", "Incoterm", "Cliente", "NF",
            "Transportadora", "Coleta", "Data Solic.", "Data Col.", "Observações"]
    linhas = [(l + [""] * 10)[:10] for l in valores[1:]]
    df = pd.DataFrame(linhas, columns=cols)
    df = df[df["NF"].str.strip() != ""].copy()
    df["NF"] = df["NF"].str.strip()
    df["Data Solic."] = para_data(df["Data Solic."])
    df["Data Col."] = para_data(df["Data Col."])
    df["Lead time (dias)"] = (df["Data Col."].dt.normalize() - df["Data Solic."]).dt.days
    return df


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


st.write("")
try:
    todos_dados = ler_valores(NOME_DA_ABA)
    linhas_pedidos = [l for l in todos_dados[1:] if any(l)]
    pend = df_pendentes(ler_valores(ABA_PENDENTES))
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

topo1, topo2 = st.columns([6, 1])
topo1.success("Conexão estabelecida com a base de dados Logística 2026!")
if topo2.button("🔄 Atualizar"):
    st.cache_data.clear()
    st.rerun()

# ordem na tela: Consulta, Pendentes, Conserto/Reparo, Dashboard (aba3 = Dashboard, aba4 = Conserto)
aba1, aba2, aba4, aba3 = st.tabs(
    ["🔎 Consulta Faturamento", "⏳ Pendentes de coleta", "🔧 Conserto/Reparo", "📊 Dashboard"])

# ================= 1. CONSULTA (código original) =================
with aba1:
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        st.write("Insira o número da Nota Fiscal abaixo para verificar o fluxo do processo.")
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


        if pesquisa:
            p = pend[pend["NF"] == pesquisa]
            if not p.empty:
                r = p.iloc[0]
                st.error(f"⚠️ Esta NF consta como PENDENTE de coleta há {int(r['Dias pendente'])} dia(s) — Status: {r['Status']}")

# ================= 2. PENDENTES =================
with aba2:
    f1, f2, f3, f4 = st.columns(4)
    frete = f1.multiselect("Frete", sorted(pend["Frete"].unique()))
    status = f2.multiselect("Status", sorted(pend["Status"].unique()))
    cliente = f3.multiselect("Cliente", sorted(pend["Cliente"].unique()))
    so_atr = f4.toggle(f"Só atrasados (> {PRAZO_ALERTA} dias)")

    v = pend.copy()
    if frete: v = v[v["Frete"].isin(frete)]
    if status: v = v[v["Status"].isin(status)]
    if cliente: v = v[v["Cliente"].isin(cliente)]
    if so_atr: v = v[v["Atrasado"]]

    st.caption(f"{len(v)} caso(s) pendente(s)")
    cols = ["NF", "Cliente", "Frete", "Transporte", "Ordem de coleta",
            "Data Solicitação", "Dias pendente"]
    v = v.sort_values("Dias pendente", ascending=False)[cols]

    def cor(row):
        d = row["Dias pendente"]
        c = "#fde2e2" if d > 5 else "#fff3d6" if d > PRAZO_ALERTA else ""
        return [f"background-color:{c}"] * len(row)

    sty = (v.style.apply(cor, axis=1)
           .format({"Data Solicitação": lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "-",
                    "Dias pendente": "{:.0f}"}, escape="html", na_rep="-")
           .hide(axis="index")
           .set_properties(**{"text-align": "center"})
           .set_table_styles([{"selector": "th", "props": [("text-align", "center")]}]))
    html_tab = "\n".join(l.strip() for l in sty.to_html().splitlines() if l.strip())
    st.markdown(
        """<style>
        .tabela-pend{max-height:620px;overflow:auto;border-radius:8px;background:#fff;box-shadow:0 2px 6px rgba(0,0,0,.08)}
        .tabela-pend table{width:100%;border-collapse:collapse;font-size:14px}
        .tabela-pend th{position:sticky;top:0;background:#1b4f93;color:#fff;padding:10px 8px;z-index:1}
        .tabela-pend td{padding:8px;border-bottom:1px solid #e4e9f0;text-align:center}
        </style>""" + f'<div class="tabela-pend">{html_tab}</div>',
        unsafe_allow_html=True)
    st.download_button("⬇️ Baixar CSV", v.to_csv(index=False).encode("utf-8-sig"),
                       "pendentes.csv", "text/csv")

# ================= 3. DASHBOARD =================
_uid = count(1)
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
CSS_DASH = """<style>
.pf-grid{display:grid;gap:16px;margin-bottom:16px}
.pf-r1{grid-template-columns:repeat(4,1fr)}
.pf-r2{grid-template-columns:270px 1fr}
.pf-r3{grid-template-columns:1.2fr 1fr 1fr}
@media(max-width:1000px){.pf-r1,.pf-r2,.pf-r3{grid-template-columns:1fr}}
.pf-card{background:#fff;border-radius:10px;padding:16px 18px;box-shadow:0 3px 10px rgba(27,79,147,.10);text-align:left;overflow:hidden}
.pf-t{font-size:12px;font-weight:700;letter-spacing:.5px;color:#5c6b83;text-transform:uppercase}
.pf-s{font-size:12px;color:#8a97ab;margin-top:2px}
.pf-v{font-size:36px;font-weight:700;color:#1b4f93;line-height:1.15;margin-top:6px}
.pf-blue{background:linear-gradient(90deg,#4f83cc,#1b4f93);color:#fff;display:flex;flex-direction:column;justify-content:center}
.pf-blue .pf-t,.pf-blue .pf-s{color:#e3edfb}
.pf-duo{display:flex;justify-content:space-around;gap:10px;margin-top:8px}
.pf-duo div{text-align:center}
.pf-duo b{display:block;font-size:38px;line-height:1.1}
.pf-duo span{font-size:11px;color:#e3edfb}
.pf-don{display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center}
.pf-don+.pf-don{margin-top:18px;padding-top:16px;border-top:1px solid #e1e9f5}
.pf-big{display:flex;gap:18px;align-items:center}
.pf-big .side{min-width:150px;text-align:left}
.pf-big .side b{display:block;font-size:30px;color:#1b4f93;line-height:1.1}
.pf-big .side span{font-size:12px;color:#8a97ab;display:block;margin-bottom:14px}
.pf-li{margin-top:14px}
.pf-lr{display:flex;justify-content:space-between;gap:8px;font-size:13px;font-weight:600;color:#2c3e57}
.pf-lr span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pf-lr b{color:#1b4f93;white-space:nowrap}
.pf-tr{height:6px;border-radius:6px;background:#e1e9f5;margin-top:5px}
.pf-fi{height:6px;border-radius:6px;background:linear-gradient(90deg,#4f83cc,#1b4f93)}
</style>"""


def _nome_mes(p):
    return f"{MESES[p.month - 1]}/{p.year}"


def _fmt1(x):
    return f"{x:.1f}".replace(".", ",")


def _spark(vals, w=240, h=46):
    vals = [float(v) for v in vals]
    u = next(_uid)
    if len(vals) < 2:
        return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}"><line x1="2" y1="{h-6}" x2="{w-2}" '
                f'y2="{h-6}" stroke="#dbe5f3" stroke-width="2" stroke-linecap="round"/></svg>')
    mn, mx = min(vals), max(vals)
    rng = (mx - mn) or 1
    pts = [(2 + i * (w - 4) / (len(vals) - 1), h - 8 - (v - mn) / rng * (h - 16)) for i, v in enumerate(vals)]
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none">'
            f'<defs><linearGradient id="sp{u}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4f83cc" '
            f'stop-opacity=".25"/><stop offset="1" stop-color="#4f83cc" stop-opacity="0"/></linearGradient></defs>'
            f'<polygon points="2,{h} {d} {w-2},{h}" fill="url(#sp{u})"/>'
            f'<polyline points="{d}" fill="none" stroke="#4f83cc" stroke-width="2.2" stroke-linejoin="round" '
            f'stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')


def _donut(pct, legenda):
    pct = max(0.0, min(100.0, pct))
    r = 42
    circ = 2 * 3.14159265 * r
    u = next(_uid)
    return (f'<div class="pf-don"><svg viewBox="0 0 110 110" width="120" height="120">'
            f'<defs><linearGradient id="dn{u}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4f83cc"/>'
            f'<stop offset="1" stop-color="#1b4f93"/></linearGradient></defs>'
            f'<circle cx="55" cy="55" r="{r}" fill="none" stroke="#dbe5f3" stroke-width="9"/>'
            f'<circle cx="55" cy="55" r="{r}" fill="none" stroke="url(#dn{u})" stroke-width="9" stroke-linecap="round" '
            f'stroke-dasharray="{circ * pct / 100:.1f} {circ:.1f}" transform="rotate(-90 55 55)"/>'
            f'<text x="55" y="62" text-anchor="middle" font-size="22" font-weight="700" fill="#1b4f93">{pct:.0f}%</text>'
            f'</svg><div class="pf-s">{legenda}</div></div>')


def _linha(rot, vals, w=640, h=230):
    n = len(vals)
    pl, pr, pt, pb = 20, 20, 26, 34
    mx = max(max(vals), 1)
    X = lambda i: pl + (w - pl - pr) * (i / (n - 1) if n > 1 else 0.5)
    Y = lambda v: pt + (h - pt - pb) * (1 - v / mx)
    grade = "".join(f'<line x1="{pl}" y1="{pt + (h - pt - pb) * k / 3:.1f}" x2="{w - pr}" '
                    f'y2="{pt + (h - pt - pb) * k / 3:.1f}" stroke="#e1e9f5"/>' for k in range(4))
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    bolas = "".join(
        f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="5" fill="#fff" stroke="#4f83cc" stroke-width="3"/>'
        f'<text x="{X(i):.1f}" y="{Y(v) - 11:.1f}" text-anchor="middle" font-size="11" font-weight="600" '
        f'fill="#1b4f93">{v}</text>' for i, v in enumerate(vals))
    eixo = "".join(f'<text x="{X(i):.1f}" y="{h - 10}" text-anchor="middle" font-size="11" fill="#8a97ab">{r}</text>'
                   for i, r in enumerate(rot))
    return (f'<svg viewBox="0 0 {w} {h}" width="100%">{grade}<polyline points="{pts}" fill="none" stroke="#4f83cc" '
            f'stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>{bolas}{eixo}</svg>')


def _barras(rot, vals, w=360, h=210):
    n = len(vals)
    mx = max(max(vals), 1)
    slot = w / n
    bw = min(34, slot * 0.55)
    top, bot = 26, h - 34
    u = next(_uid)
    corpo = ""
    for i, (r, v) in enumerate(zip(rot, vals)):
        x = slot * i + (slot - bw) / 2
        fh = (bot - top) * v / mx
        corpo += (f'<rect x="{x:.1f}" y="{top}" width="{bw:.1f}" height="{bot - top}" rx="{bw / 2:.1f}" fill="#e7edf6"/>'
                  + (f'<rect x="{x:.1f}" y="{bot - fh:.1f}" width="{bw:.1f}" height="{fh:.1f}" rx="{bw / 2:.1f}" '
                     f'fill="url(#br{u})"/>' if v > 0 else "")
                  + f'<text x="{x + bw / 2:.1f}" y="{top - 8}" text-anchor="middle" font-size="12" font-weight="700" '
                    f'fill="#1b4f93">{v}</text>'
                  + f'<text x="{x + bw / 2:.1f}" y="{h - 12}" text-anchor="middle" font-size="11" fill="#8a97ab">{r}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" width="100%"><defs><linearGradient id="br{u}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#4f83cc"/><stop offset="1" stop-color="#1b4f93"/></linearGradient></defs>'
            f'{corpo}</svg>')


def _lista(itens, fmt):
    if not itens:
        return '<div class="pf-s" style="margin-top:14px">Sem dados para exibir.</div>'
    mx = max(v for _, v in itens) or 1
    return "".join(
        f'<div class="pf-li"><div class="pf-lr"><span>{esc(str(n))}</span><b>{fmt(v)}</b></div>'
        f'<div class="pf-tr"><div class="pf-fi" style="width:{max(v / mx * 100, 4):.0f}%"></div></div></div>'
        for n, v in itens)


def sem_ignorados(df, col="Cliente"):
    """Remove do dataframe os clientes listados em CLIENTES_IGNORADOS."""
    if df is None or df.empty:
        return df
    nomes = df[col].map(_norm)
    return df[~nomes.apply(lambda n: any(i in n for i in CLIENTES_IGNORADOS))]


def dados_conserto(rep, coletas, hoje):
    """Uma linha por NF de retorno emitida: dias entre a emissão (liberação p/ coleta) e a coleta (ou hoje)."""
    if rep is None or rep.empty:
        return pd.DataFrame(columns=["Cliente", "dias", "coletado", "coleta"])
    r2 = rep[(rep["NF retorno"] != "") & (rep["Emissão NF saída"] != "")].copy()
    r2["emissao"] = para_data(r2["Emissão NF saída"])
    r2["coleta"] = para_data(r2["NF retorno"].map(lambda n: coletas.get(n.strip(), {}).get("data_col", "")))
    r2 = r2.dropna(subset=["emissao"])
    r2["coletado"] = r2["coleta"].notna()
    r2["dias"] = (r2["coleta"].fillna(hoje).dt.normalize() - r2["emissao"].dt.normalize()).dt.days
    return r2[(r2["dias"] >= 0) & (r2["dias"] <= 365)]


def dados_faturadas(valores, hoje):
    """Notas faturadas = linhas da aba controle (exceto canceladas), pelo mês da coluna DATA Solic."""
    ctrl = df_controle(valores)
    fat = ctrl[(ctrl["NF"] != "") & (~ctrl["Operação"].str.lower().str.contains("cancel"))].copy()
    fat = fat[(fat["Data Solic."] >= pd.Timestamp("2024-01-01")) & (fat["Data Solic."] <= hoje + pd.Timedelta(days=31))]
    fat["mes"] = fat["Data Solic."].dt.to_period("M")
    return fat


def montar_dashboard(pend, r2, fat, sel, hoje):
    total = len(pend)
    atras = int(pend["Atrasado"].sum())
    conc = r2[r2["coletado"]]

    # --- KPI 1: média de dias liberação -> coleta
    media = conc["dias"].mean() if len(conc) else None
    serie = conc.groupby(conc["coleta"].dt.to_period("M"))["dias"].mean().tail(8).tolist()
    k1 = (f'<div class="pf-card"><div class="pf-t">Liberação → Coleta</div>'
          f'<div class="pf-v">{_fmt1(media) + " dias" if media is not None else "—"}</div>'
          f'<div class="pf-s">Média de dias entre a emissão da NF de retorno e a coleta</div>{_spark(serie)}</div>')

    # --- KPI 3: notas faturadas no mês
    if sel is not None:
        mes = fat[fat["mes"] == sel]
        ult = hoje.day if sel == hoje.to_period("M") else sel.days_in_month
        diario = mes.groupby(mes["Data Solic."].dt.day).size().reindex(range(1, ult + 1), fill_value=0).tolist()
        qtd = len(mes)
        rot_mes = _nome_mes(sel)
    else:
        diario, qtd, rot_mes = [], 0, "—"
    k2 = (f'<div class="pf-card"><div class="pf-t">Notas faturadas no mês</div><div class="pf-v">{qtd}</div>'
          f'<div class="pf-s">{rot_mes} · por dia</div>{_spark(diario)}</div>')

    # --- KPI 4: maior reincidência de cliente
    fc = fat[~fat["Cliente"].isin(["", "-"])]
    rank = fc.groupby("Cliente").size().sort_values(ascending=False).head(5)
    if len(rank):
        top_n, top_q = rank.index[0], int(rank.iloc[0])
    else:
        top_n, top_q = "—", 0
    k3 = (f'<div class="pf-card"><div class="pf-t">Maior reincidência</div><div class="pf-v">{top_q}x</div>'
          f'<div class="pf-s" style="font-weight:600;color:#2c3e57">{esc(top_n)}</div>'
          f'<div class="pf-s">Vezes faturadas para o mesmo cliente</div></div>')

    k4 = (f'<div class="pf-card pf-blue"><div class="pf-t">Pendentes de coleta</div>'
          f'<div class="pf-duo"><div><b>{total}</b><span>Total</span></div>'
          f'<div><b>{atras}</b><span>Atrasados (&gt; {PRAZO_ALERTA} dias)</span></div></div></div>')

    # --- donuts
    pct_atr = atras / total * 100 if total else 0
    pct_col = len(conc) / len(r2) * 100 if len(r2) else 0
    donuts = (_donut(pct_atr, "Pendentes de coleta em atraso")
              + _donut(pct_col, "NFs de retorno já coletadas"))

    # --- evolução mensal de notas faturadas
    if sel is not None:
        per = pd.period_range(end=sel, periods=12, freq="M")
        cont = fat.groupby("mes").size().reindex(per, fill_value=0)
        linha = _linha([f"{MESES[p.month - 1]}/{str(p.year)[2:]}" for p in per], cont.tolist())
        media_m = cont.mean()
    else:
        linha, media_m = "", 0
    grande = (f'<div class="pf-card"><div class="pf-t">Notas faturadas · últimos 12 meses</div>'
              f'<div class="pf-big"><div style="flex:1;min-width:0">{linha}</div><div class="side">'
              f'<span>Mês selecionado</span><b>{qtd}</b>'
              f'<span style="margin-top:14px">Média mensal</span><b>{_fmt1(media_m)}</b></div></div></div>')

    # --- idade dos pendentes
    ordem = ["Hoje", "1-2 dias", "3-5 dias", "6-10 dias", "+10 dias"]
    fx = pend["Faixa"].astype(str).value_counts().reindex(ordem, fill_value=0)
    barras = (f'<div class="pf-card"><div class="pf-t">Idade dos pendentes</div>'
              f'<div class="pf-s">Casos pendentes por faixa de prazo</div>{_barras(ordem, fx.tolist())}</div>')

    # --- clientes mais afetados por prazos longos
    afet = (r2.groupby("Cliente")["dias"].mean().sort_values(ascending=False).head(5))
    afet_l = [(c, v) for c, v in afet.items() if c]
    l1 = (f'<div class="pf-card"><div class="pf-t">Clientes mais afetados por prazos longos</div>'
          f'<div class="pf-s">Média de dias da liberação até a coleta (inclui casos ainda aguardando, contados até hoje)</div>'
          f'{_lista(afet_l, lambda v: f"{v:.0f} dias")}</div>')

    # --- reincidência
    l2 = (f'<div class="pf-card"><div class="pf-t">Maior reincidência de clientes</div>'
          f'<div class="pf-s">Quantidade de vezes faturadas por cliente (histórico completo)</div>'
          f'{_lista([(c, int(v)) for c, v in rank.items()], lambda v: f"{v}x")}</div>')

    html_all = (CSS_DASH + f'<div class="pf-grid pf-r1">{k1}{k2}{k3}{k4}</div>'
                f'<div class="pf-grid pf-r2"><div class="pf-card">{donuts}</div>{grande}</div>'
                f'<div class="pf-grid pf-r3">{barras}{l1}{l2}</div>')
    return "\n".join(l.strip() for l in html_all.splitlines() if l.strip())


with aba3:
    hoje = pd.Timestamp.today().normalize()
    try:
        rep_d = df_conserto(ler_valores(ABA_CONSERTO))
    except Exception:
        rep_d = None
        st.warning(f"Não consegui ler a aba '{ABA_CONSERTO}'; os indicadores de conserto ficam vazios.")
    r2 = sem_ignorados(dados_conserto(rep_d, mapa_coletas(todos_dados), hoje))
    fat = sem_ignorados(dados_faturadas(todos_dados, hoje))
    pend_d = sem_ignorados(pend)

    meses = sorted(fat["mes"].dropna().unique(), reverse=True)
    sel = None
    if meses:
        atual = hoje.to_period("M")
        _, cs, _ = st.columns([2, 1, 2])
        sel = cs.selectbox("Mês de referência (notas faturadas)", meses,
                           index=meses.index(atual) if atual in meses else 0, format_func=_nome_mes)
    st.markdown(montar_dashboard(pend_d, r2, fat, sel, hoje), unsafe_allow_html=True)

# ================= 4. CONSERTO / REPARO (consulta por NF + timeline) =================
with aba4:
    _, mid4, _ = st.columns([1, 3, 1])
    with mid4:
        try:
            rep = df_conserto(ler_valores(ABA_CONSERTO))
        except Exception as e:
            st.error(f"Não consegui ler a aba '{ABA_CONSERTO}'. Confira o nome da aba na planilha.")
            st.caption(str(e))
            st.stop()

        st.write("Digite o número da Nota Fiscal do cliente para acompanhar o conserto/reparo.")
        q = st.text_input("Número da Nota Fiscal (conserto):", placeholder="Ex: 295889-1 ou 295889...",
                          key="nf_conserto").strip()

        if q:
            base = rep["Nota cliente"].str.split("-").str[0]
            achou = rep[(rep["Nota cliente"] == q) | (base == q) | (rep["NF retorno"] == q)]
            if achou.empty:
                st.markdown(
                    '<div style="background:#fff4e5;border:2px solid #f5a623;border-radius:12px;padding:26px 20px;'
                    'text-align:center;box-shadow:0 4px 12px rgba(245,166,35,.18);margin-top:10px">'
                    '<div style="font-size:38px;line-height:1">⚠️</div>'
                    '<div style="font-size:24px;font-weight:800;color:#b45309;margin-top:8px">'
                    'Nota Fiscal NÃO recebida em nossa Expedição</div>'
                    '<div style="font-size:16px;color:#5c6b73;margin-top:8px">'
                    'ou número incluído incorretamente</div>'
                    f'<div style="font-size:13px;color:#8a97ab;margin-top:12px">Número pesquisado: <b>{esc(q)}</b></div>'
                    '</div>', unsafe_allow_html=True)
            else:
                if len(achou) > 1:
                    opcoes = {f"{r['Nota cliente']} — {r['Cliente']}": i for i, r in achou.iterrows()}
                    escolha = st.selectbox("Mais de um registro encontrado, escolha:", list(opcoes))
                    r = achou.loc[opcoes[escolha]]
                else:
                    r = achou.iloc[0]

                info = status_conserto(r, mapa_coletas(todos_dados))
                st.markdown(f"## 📋 Cliente: {r['Cliente']}")
                st.markdown(f"### Status Atual: {info['status']}")
                (st.error if info["bloqueado"] else st.info)(info["detalhe"])

                st.markdown("### ⏳ Fluxo do Conserto:")
                st.markdown(html_timeline(info["passos"], info["etapa"]), unsafe_allow_html=True)

                st.markdown("---")
                st.markdown("### 🔍 Detalhes:")
                d1, d2, d3 = st.columns(3)
                d1.metric("Nota do Cliente", r["Nota cliente"])
                d2.metric("Data de Recebimento", r["Recebimento"] or "-")
                d3.metric("Pendência / Bloqueio", r["Pendência"] or "Sem pendência")
                d4, d5 = st.columns(2)
                d4.metric("Entrada realizada por", r["Entrada por"] or "-")
                d5.metric("Data de Entrada", r["Data entrada"] or "-")
                d6, d7, d8 = st.columns(3)
                d6.metric("Liberado pela Assistência", "Sim" if r["_lib"] else "Não")
                d7.metric("NF de Retorno", r["NF retorno"] or "-")
                d8.metric("Emissão da NF de Saída", r["Emissão NF saída"] or "-")
                d9, d10 = st.columns(2)
                d9.metric("Data da Coleta", info["coleta"].get("data_col") or "-")
                d10.metric("Transportadora", info["coleta"].get("transp") or "-")

st.markdown("Desenvolvido por Diego Elvis | Versão R.2.0 de 10.26", unsafe_allow_html=True)
