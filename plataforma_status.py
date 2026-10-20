import datetime
import json
import re

import altair as alt
import gspread
import pandas as pd
import streamlit as st

# --- CONFIGURAÇÃO DA GOOGLE SHEET ---
LINK_PLANILHA = "https://google.com/spreadsheets/d/1cYhrFo_JVrTqtaxHXqiKc_gOl-En0FEYfpVs-58e9S0/edit?gid=0#gid=0"
NOME_DA_ABA = "controle"
ABA_PENDENTES = "Pendentes (FUP)"
ABA_CONSERTO = "Retorno Conserto"  # nome exato da aba de reparos na planilha
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
    return pd.to_datetime(s, dayfirst=True, errors="coerce")


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


def df_conserto(valores):
    """Lê a aba de reparos. Localiza o cabeçalho pela coluna 'Número da Nota do Cliente'."""
    ini = 2
    for i, l in enumerate(valores[:8]):
        if any("nota do" in c.lower() for c in l):
            ini = i + 1
            break
    cols = ["Recebimento", "Nota cliente", "Cliente", "Pendência", "Entrada por",
            "Data entrada", "Entregue serviço", "NF venda garantia", "Resp. saída",
            "NF retorno", "Emissão NF saída", "Contabilização"]
    linhas = [(l + [""] * 12)[:12] for l in valores[ini:]]
    df = pd.DataFrame(linhas, columns=cols)
    df = df.apply(lambda c: c.astype(str).str.strip())
    df = df[(df["Cliente"] != "") | (df["Nota cliente"] != "")].copy()
    df["_ordem"] = para_data(df["Recebimento"])
    p = df["Pendência"].str.lower()
    sem_pend = (p == "") | p.str.match(r"^(finalizado|n[aã]o h[aá] pend)")
    df["_pend"] = ~sem_pend
    return df


def status_conserto(r):
    """Regras: bloqueio > NF retorno > entrada realizada > aguardando entrada."""
    base = bool(r["Nota cliente"] and r["Cliente"])
    bloqueado = base and bool(r["_pend"])
    retorno = bool(r["NF retorno"])
    entrada = bool(r["Entrada por"] and r["Data entrada"])
    if not base:
        return {"etapa": 0, "status": "⚪ Dados incompletos", "bloqueado": False,
                "detalhe": "Faltam o número da nota ou o cliente no registro.",
                "passos": ["pendente"] * 4}
    if bloqueado:
        return {"etapa": 1, "status": "🔴 Bloqueado — aguardando resolução da divergência",
                "bloqueado": True,
                "detalhe": f"Pendência registrada: {r['Pendência']}. O material só segue após a divergência ser resolvida.",
                "passos": ["ok", "bloqueado", "pendente", "pendente"]}
    if retorno:
        return {"etapa": 4, "status": "🔵 Aguardando coleta", "bloqueado": False,
                "detalhe": f"NF de retorno {r['NF retorno']} emitida"
                           + (f" em {r['Emissão NF saída']}." if r["Emissão NF saída"] else "."),
                "passos": ["ok", "ok", "ok", "ok"]}
    if entrada:
        return {"etapa": 3, "status": "🟠 Entregue para conserto", "bloqueado": False,
                "detalhe": f"Entrada realizada por {r['Entrada por']} em {r['Data entrada']}. Material em conserto.",
                "passos": ["ok", "ok", "ok", "pendente"]}
    return {"etapa": 2, "status": "⚪ Aguardando Entrada", "bloqueado": False,
            "detalhe": "Nota e cliente registrados, sem pendências. Aguardando a entrada do material.",
            "passos": ["ok", "ok", "pendente", "pendente"]}


def html_timeline(passos, etapa):
    nomes = ["Aguardando Entrada", "Pendência / Bloqueio", "Entregue p/ Conserto", "Aguardando Coleta"]
    bloqueado = "bloqueado" in passos
    if bloqueado:
        etapa = 2  # a barra vai até o X vermelho (fase 2)
    # a barra vai até o CENTRO do círculo da etapa (cada etapa ocupa 25% da trilha)
    largura = {0: "0%", 1: "12.5%", 2: "37.5%", 3: "62.5%", 4: "100%"}[etapa]
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

aba1, aba2, aba3, aba4 = st.tabs(
    ["🔎 Consulta por NF", "⏳ Pendentes de coleta", "📊 Dashboard", "🔧 Conserto/Reparo"])

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
            "Data Solicitação", "Dias pendente", "Status", "Obs"]
    v = v.sort_values("Dias pendente", ascending=False)[cols]

    def cor(row):
        d = row["Dias pendente"]
        c = "#fde2e2" if d > 5 else "#fff3d6" if d > PRAZO_ALERTA else ""
        return [f"background-color:{c}"] * len(row)

    st.dataframe(v.style.apply(cor, axis=1)
                 .format({"Data Solicitação": lambda d: d.strftime("%d/%m/%Y") if pd.notna(d) else "-",
                          "Dias pendente": "{:.0f}"}, na_rep="-"),
                 use_container_width=True, hide_index=True)
    st.download_button("⬇️ Baixar CSV", v.to_csv(index=False).encode("utf-8-sig"),
                       "pendentes.csv", "text/csv")

# ================= 3. DASHBOARD =================
with aba3:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total pendente", len(pend))
    k2.metric(f"Atrasados (> {PRAZO_ALERTA}d)", int(pend["Atrasado"].sum()))
    k3.metric("Média de dias pendente", f"{pend['Dias pendente'].mean():.1f}" if len(pend) else "-")
    k4.metric("Mais antigo (dias)", int(pend["Dias pendente"].max()) if len(pend) else 0)

    def barra(df, x, y, titulo, horiz=False):
        if horiz:
            enc = dict(x=alt.X(f"{x}:Q", title=None), y=alt.Y(f"{y}:N", sort="-x", title=None))
        else:
            enc = dict(x=alt.X(f"{x}:N", sort=None, title=None), y=alt.Y(f"{y}:Q", title=None))
        return alt.Chart(df, title=titulo).mark_bar().encode(**enc, tooltip=list(df.columns))

    c1, c2 = st.columns(2)
    with c1:
        d = pend["Status"].value_counts().rename_axis("Status").reset_index(name="Qtd")
        st.altair_chart(barra(d, "Qtd", "Status", "Pendentes por status", True), use_container_width=True)
    with c2:
        ordem = ["Hoje", "1-2 dias", "3-5 dias", "6-10 dias", "+10 dias"]
        d = pend["Faixa"].value_counts().reindex(ordem).fillna(0).rename_axis("Faixa").reset_index(name="Qtd")
        d["Faixa"] = d["Faixa"].astype(str)
        st.altair_chart(barra(d, "Faixa", "Qtd", "Idade dos pendentes (prazo)"), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        d = pend["Cliente"].value_counts().head(10).rename_axis("Cliente").reset_index(name="Qtd")
        st.altair_chart(barra(d, "Qtd", "Cliente", "Top 10 clientes com pendência", True), use_container_width=True)
    with c4:
        d = pend.dropna(subset=["Data Solicitação"]).groupby("Data Solicitação").size().reset_index(name="Qtd")
        st.altair_chart(alt.Chart(d, title="Solicitações pendentes por data").mark_line(point=True)
                        .encode(x="Data Solicitação:T", y="Qtd:Q", tooltip=["Data Solicitação", "Qtd"]),
                        use_container_width=True)

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
                st.warning(f"Nenhum registro de conserto encontrado para: '{q}'")
            else:
                if len(achou) > 1:
                    opcoes = {f"{r['Nota cliente']} — {r['Cliente']}": i for i, r in achou.iterrows()}
                    escolha = st.selectbox("Mais de um registro encontrado, escolha:", list(opcoes))
                    r = achou.loc[opcoes[escolha]]
                else:
                    r = achou.iloc[0]

                info = status_conserto(r)
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
                d6, d7 = st.columns(2)
                d6.metric("NF de Retorno", r["NF retorno"] or "-")
                d7.metric("Emissão da NF de Saída", r["Emissão NF saída"] or "-")

st.markdown("Desenvolvido por Diego Elvis | Versão R.2.0 de 10.26", unsafe_allow_html=True)
