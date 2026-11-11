import datetime
import hashlib
import hmac
import json
import re
import time
import unicodedata

from html import escape as esc
from itertools import count
import gspread
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ======================= CONFIGURAÇÃO DA GOOGLE SHEET =======================
LINK_PLANILHA = "https://google.com/spreadsheets/d/1cYhrFo_JVrTqtaxHXqiKc_gOl-En0FEYfpVs-58e9S0/edit?gid=0#gid=0"
NOME_DA_ABA = "controle"
ABA_PENDENTES = "Pendentes (FUP)"
ABA_CONSERTO = "Retorno Conserto"
ABA_DEMONSTRACAO = "Demonstração"

CLIENTES_IGNORADOS = ["burkert"]
PRAZO_ALERTA = 3

st.set_page_config(page_title="Portal de Status - Logística", page_icon="📦", layout="wide")

# ======================= ESTADO DA SIDEBAR (EXPANDIDO / RECOLHIDO) =======================
if "sidebar_expanded" not in st.session_state:
    st.session_state["sidebar_expanded"] = True

expandido = st.session_state["sidebar_expanded"]
sb_width = "270px" if expandido else "90px"

# ======================= ESTILOS CSS (PADRÃO LOGÍSTICA / PIONEERS) =======================
st.markdown(f"""
    <style>
        :root {{
            --azul: #6d8fb6;
            --azul-esc: #3b719f;
            --prata: #b8bdc6;
        }}
        .stApp {{
            background: linear-gradient(135deg, #eef3f8 0%, #dce6f1 100%);
        }}
        header[data-testid="stHeader"] {{
            background: transparent !important;
        }}
        .block-container {{
            padding-top: 1.6rem;
            max-width: 100% !important;
            padding-left: 1.2rem;
            padding-right: 1.2rem;
        }}

        .header-banner {{
            position: relative; overflow: hidden;
            background: linear-gradient(160deg, #6d8fb6 0%, #5681ac 48%, #3b719f 100%);
            border-radius: 26px;
            padding: 34px 40px 36px;
            box-shadow: 0 16px 36px rgba(44, 90, 130, .30);
            margin-bottom: 26px;
        }}
        .header-banner::before {{
            content: ""; position: absolute; right: -36px; top: -46px; width: 250px; height: 250px; border-radius: 50%;
            background: radial-gradient(circle at 34% 28%, #f6f8fb 0%, #c9ced6 38%, #8a919d 100%);
            box-shadow: inset -14px -18px 34px rgba(31, 58, 87, .35); opacity: .92;
        }}
        .header-banner::after {{
            content: ""; position: absolute; right: 200px; bottom: -42px; width: 120px; height: 120px; border-radius: 50%;
            background: radial-gradient(circle at 34% 28%, rgba(255,255,255,.75), rgba(184,189,198,.5) 55%, rgba(255,255,255,.10));
            box-shadow: inset -8px -10px 22px rgba(31, 58, 87, .25);
        }}
        .header-banner > * {{ position: relative; z-index: 1; }}
        .stApp .header-banner .hb-kicker {{
            font-size: 12px; font-weight: 800; letter-spacing: 3px; color: #dbe6f1; text-align: left !important; margin: 0 0 10px 0 !important;
        }}
        .stApp .header-banner h1 {{
            color: #ffffff !important; font-size: 44px !important; line-height: 1.02 !important; margin: 0 !important;
            letter-spacing: .5px; font-weight: 800 !important; text-transform: uppercase;
            text-align: left !important; max-width: 75%;
        }}
        .stApp .header-banner p {{
            margin: 12px 0 0 0 !important; font-size: 16px; color: #eaf1f8; opacity: .95;
            text-align: left !important; max-width: 65%;
        }}
        @media (max-width: 900px) {{
            .header-banner::before, .header-banner::after {{ display: none; }}
            .stApp .header-banner h1 {{ font-size: 28px !important; max-width: 100%; }}
            .stApp .header-banner p {{ max-width: 100%; }}
        }}

        section[data-testid="stSidebar"] {{
            width: {sb_width} !important;
            min-width: {sb_width} !important;
            max-width: {sb_width} !important;
            transform: none !important;
            visibility: visible !important;
            background: linear-gradient(185deg, #5681ac 0%, #3b719f 55%, #2c5a82 100%) !important;
            border-radius: 0 28px 28px 0;
            box-shadow: 8px 0 30px rgba(44, 90, 130, .28);
            transition: width 0.3s ease, min-width 0.3s ease, max-width 0.3s ease;
            position: relative !important;
        }}
        section[data-testid="stSidebar"] > div {{ background: transparent !important; }}

        [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        [data-testid="stSidebarResizeHandle"] {{
            display: none !important;
        }}

        [data-testid="stSidebarUserContent"] {{
            padding: 1.2rem 0.8rem 3.5rem 0.8rem !important;
        }}

        .sb-header {{
            display: flex; align-items: center;
            justify-content: {"space-between" if expandido else "center"};
            padding: 4px 6px 16px 6px;
            border-bottom: 1px solid rgba(255,255,255,.22);
            margin-bottom: 20px;
        }}
        .sb-logo {{
            display: flex; align-items: center; gap: 10px; white-space: nowrap; font-size: 24px;
        }}
        .sb-logo span {{
            font-size: 12px; font-weight: 800; letter-spacing: 1.6px; line-height: 1.2; color: #ffffff;
        }}

        section[data-testid="stSidebar"] .stButton {{ margin-bottom: 8px; }}
        section[data-testid="stSidebar"] .stButton button {{
            width: 100%;
            justify-content: center !important;
            border: none;
            border-radius: 16px;
            padding: {"0.8rem 1rem" if expandido else "0.8rem 0rem"} !important;
            background: transparent;
            box-shadow: none;
            transition: all 0.2s;
        }}
        .stApp section[data-testid="stSidebar"] .stButton button p {{
            text-align: {"left" if expandido else "center"} !important;
            font-size: {"15px" if expandido else "20px"};
            font-weight: 700;
            color: #e3ecf5;
            margin: 0;
        }}
        section[data-testid="stSidebar"] .stButton button:hover {{ background: rgba(255,255,255,.14); }}
        section[data-testid="stSidebar"] .stButton button[kind="primary"],
        section[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"] {{
            background: #ffffff;
            box-shadow: 0 10px 22px rgba(20, 50, 80, .30);
        }}
        .stApp section[data-testid="stSidebar"] .stButton button[kind="primary"] p,
        .stApp section[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"] p {{
            color: #2c5a82 !important;
        }}

        .sidebar-status-container {{
            margin-top: 28px; text-align: center;
            background: rgba(255,255,255,.14); color: #ffffff;
            padding: 7px 10px; border-radius: 12px;
            font-size: 11px; font-weight: 700; letter-spacing: .4px;
            border: 1px solid rgba(255,255,255,.30); white-space: nowrap;
        }}

        .stApp h2, .stApp h3, .stApp h4, .stApp p, .stMarkdown p {{ text-align: center !important; }}
        .stAlert {{ border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); text-align: center !important; }}
        [data-testid="stWidgetLabel"] {{ text-align: center !important; display: block !important; width: 100% !important; }}
        [data-testid="stTextInput"] div[data-baseweb="input"] {{ max-width: 560px !important; margin: 0 auto !important; }}
        [data-testid="stTextInput"] input {{ text-align: center !important; }}

        @keyframes pulse-alert {{
            0% {{ box-shadow: 0 0 0 0 rgba(229, 57, 53, 0.4); }}
            70% {{ box-shadow: 0 0 0 12px rgba(229, 57, 53, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(229, 57, 53, 0); }}
        }}
        .fup-urgent-banner {{
            background: linear-gradient(135deg, #ffebee 0%, #ffcdd2 100%);
            border: 2px solid #e53935;
            border-radius: 16px;
            padding: 16px 24px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            animation: pulse-alert 2s infinite;
        }}
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def conectar_google_sheets():
    info_json = st.secrets["gspread_credentials"]["json_string"]
    dic_chaves = json.loads(info_json, strict=False)
    if "private_key" in dic_chaves:
        dic_chaves["private_key"] = dic_chaves["private_key"].replace("\\n", "\n").replace("\n", "\n")
    cliente = gspread.service_account_from_dict(dic_chaves)
    return cliente


@st.cache_data(ttl=300)
def ler_valores(aba):
    client = conectar_google_sheets()
    return client.open_by_url(LINK_PLANILHA).worksheet(aba).get_all_values()


def para_data(s):
    return pd.to_datetime(s, dayfirst=True, errors="coerce", format="mixed")


def limpa_status(s):
    s = re.sub(r"^[^\wÀ-ÿ]+", "", str(s)).strip()
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


def df_demonstracao(val_demo, val_ctrl):
    if not val_demo or len(val_demo) < 2:
        return pd.DataFrame()
    
    ini, cab = 2, None
    for i, l in enumerate(val_demo[:8]):
        norm_l = [_norm(c) for c in l]
        if any("business partner" in c or "emitida para" in c or "nota" in c for c in norm_l):
            ini, cab = i + 1, norm_l
            break

    def achar(termos, padrao):
        if cab is None:
            return padrao
        for j, h in enumerate(cab):
            if all(t in h for t in termos):
                return j
        return padrao

    mapa = {
        "bp": achar(("business", "partner"), 0),
        "cliente": achar(("emitida", "para"), 1),
        "solicitado_por": achar(("solicitado", "por"), 2),
        "nf": achar(("nota",), 3),
        "itens": achar(("itens",), 4),
        "data_saida": achar(("data", "saida"), 5),
        "prev_retorno": achar(("previsao", "retorno"), 6),
        "emissao_tipo": achar(("emissao",), 7),
        "retorno_data": achar(("retorno",), 8),
        "nota_retorno": achar(("nota", "retorno"), 9),
        "status_prazo": achar(("status", "prazo"), 10),
        "retorno_atraso": achar(("retorno", "atraso"), 11),
        "custo": achar(("custo",), 12),
        "observacao": achar(("observac",), 13),
    }

    linhas = val_demo[ini:]
    df = pd.DataFrame({k: [(l[j].strip() if j is not None and j < len(l) else "") for l in linhas]
                       for k, j in mapa.items()})
    
    df = df[(df["cliente"] != "") | (df["nf"] != "")].copy()
    
    df["d_saida"] = para_data(df["data_saida"])
    df["d_prev"] = para_data(df["prev_retorno"])
    df["d_retorno"] = para_data(df["retorno_data"])
    
    def calcula_status_fup(r):
        st_prazo = str(r["status_prazo"]).strip().lower()
        if "finalizado" in st_prazo:
            return "🟢 Finalizado"
        elif "retorno urgente" in st_prazo or "atraso" in st_prazo or "atrasou" in st_prazo:
            return "🔴 Retorno Urgente"
        else:
            return "🔵 No Prazo"
            
    df["status_fup"] = df.apply(calcula_status_fup, axis=1)
    df["finalizado"] = df["status_fup"] == "🟢 Finalizado"
    
    def avalia_cliente(r):
        if pd.notna(r["d_retorno"]) and pd.notna(r["d_prev"]):
            dias_dif = (r["d_retorno"] - r["d_prev"]).days
            if dias_dif <= 0:
                return "🟢 Positivo (No Prazo/Adiantado)"
            else:
                return "🔴 Negativo (Devolução Atrasada)"
        elif not r["finalizado"] and pd.notna(r["d_prev"]) and pd.Timestamp.today().normalize() > r["d_prev"]:
            return "🔴 Negativo (Vencido em Aberto)"
        return "⚪ Neutro / Em Andamento"

    df["avaliacao_cliente"] = df.apply(avalia_cliente, axis=1)
    return df


def df_conserto(valores):
    ini, cab = 2, None
    for i, l in enumerate(valores[:8]):
        if any("nota do cliente" in _norm(c) for c in l):
            ini, cab = i + 1, [_norm(c) for c in l]
            break

    def achar(termos, padrao, comeca=None):
        if cab is None:
            return padrao
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
    s3 = ent
    s4 = s3 and lib
    s5 = s4 and nf
    s6 = s5 and dt
    s7 = s6 and bool(col.get("data_col"))
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


CSS_CS = """<style>
.cs-hero{display:grid;grid-template-columns:1.15fr 1fr;gap:16px;margin:4px 0 16px}
.cs-grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:16px}
@media(max-width:1000px){.cs-hero,.cs-grid3{grid-template-columns:1fr}}
.cs-card{background:#fff;border-radius:18px;padding:20px 24px;box-shadow:0 3px 12px rgba(59,113,159,.12);text-align:left;box-sizing:border-box}
.cs-id{border-left:6px solid #3b719f}
.cs-note{border-left:6px solid #6d8fb6}
.cs-note.bad{border-left-color:#e53935;background:#fff5f5}
.cs-k{font-size:11px;font-weight:800;letter-spacing:1.4px;text-transform:uppercase;color:#7b8aa0}
.cs-nome{font-size:30px;font-weight:800;color:#2c5a82;line-height:1.15;margin-top:6px;overflow-wrap:anywhere}
.cs-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.cs-chip{background:#eef3f8;border-radius:20px;padding:6px 14px;font-size:13px;color:#4a5b73}
.cs-chip b{color:#2c5a82}
.cs-nt{font-size:15.5px;line-height:1.55;color:#34495e;margin-top:8px}
.cs-aviso{margin-top:12px;padding:8px 12px;border-radius:10px;background:#fff6e0;color:#8a5a00;font-size:13px}
.cs-row{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:11px 0;border-bottom:1px dashed #dbe5f0;font-size:14px}
.cs-row:last-child{border-bottom:none;padding-bottom:2px}
.cs-row span{color:#6b7a90}
.cs-row b{color:#2c5a82;text-align:right;overflow-wrap:anywhere}
.cs-row b.vz{color:#b3bdcc;font-weight:500}
.cs-pill{display:inline-block;padding:3px 12px;border-radius:20px;font-size:12.5px;font-weight:700;background:#eef3f8;color:#4a5b73}
.cs-pill.ok{background:#e3f6ec;color:#1e8e5a}.cs-pill.bad{background:#fde2e2;color:#c62828}
.cs-sec-h{margin-bottom:6px}
.tl-wrap{position:relative;display:flex;justify-content:space-between;margin:26px 0 6px}
.tl-wrap::before{content:"";position:absolute;top:16px;left:0;width:100%;height:12px;background:#dbe5f0;border-radius:10px;z-index:1}
.tl-seg{position:absolute;top:16px;height:12px;z-index:2}
.tl-item{position:relative;display:flex;flex-direction:column;align-items:center;flex:1;z-index:3;min-width:0}
.tl-c{width:44px;height:44px;border-radius:50%;box-sizing:border-box;background:#fff;border:4px solid #cbd6e2;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:18px;color:#fff;box-shadow:0 2px 6px rgba(0,0,0,.10)}
.tl-n{margin-top:9px;font-size:12.5px;font-weight:600;color:#6b7a90;text-align:center;padding:0 4px;line-height:1.25}
.tl-t{margin-top:5px;min-height:18px;font-size:10.5px;font-weight:800;letter-spacing:.8px;text-transform:uppercase;color:#3b719f}
.tl-item.ok .tl-c{background:#2fae6e;border-color:#2fae6e}
.tl-item.ok .tl-n{color:#2c5a82;font-weight:700}
.tl-item.cur .tl-c{border-color:#3b719f;box-shadow:0 0 0 6px rgba(59,113,159,.16),0 2px 6px rgba(0,0,0,.10)}
.tl-item.cur .tl-c::after{content:"";width:14px;height:14px;border-radius:50%;background:#3b719f}
.tl-item.cur .tl-n{color:#2c5a82;font-weight:800}
.tl-item.bad .tl-c{background:#e53935;border-color:#e53935}
.tl-item.bad .tl-n{color:#e53935;font-weight:800}
.tl-item.bad .tl-t{color:#e53935}
.tl-item.cancelado .tl-c{background:#e53935;border-color:#e53935}
.tl-item.cancelado .tl-n{color:#e53935;font-weight:800}
.tl-item.cancelado .tl-t{color:#e53935}
.tl-item.ok:last-child .tl-t{color:#1e8e5a}
</style>"""

COR_TRECHO_CS = {"ok": "#2fae6e", "bloqueado": "#e53935", "cancelado": "#e53935"}


def html_timeline(passos, etapa=None):
    nomes = ["Aguardando Entrada", "Pendência / Bloqueio", "Entregue p/ Conserto",
             "Liberado pela Assistência", "Aguardando Emissão de Retorno", "Aguardando Coleta", "Coletado"]
    n = len(passos)
    bloq = "bloqueado" in passos
    atual = None if bloq else next((i for i, p in enumerate(passos) if p == "pendente"), None)
    segs = ""
    for k, p in enumerate(passos, start=1):
        cor = COR_TRECHO_CS.get(p)
        if not cor:
            continue
        ini = 0 if k == 1 else (k - 1.5) / n * 100
        larg = (0.5 if k == 1 else 1) / n * 100 + 0.15
        raio = "10px 0 0 10px" if k == 1 else "0"
        segs += f'<div class="tl-seg" style="left:{ini:.3f}%;width:{larg:.3f}%;background:{cor};border-radius:{raio}"></div>'
    if passos[-1] == "ok":
        segs += (f'<div class="tl-seg" style="left:{(n - 0.5) / n * 100:.3f}%;width:{0.5 / n * 100:.3f}%;'
                 f'background:{COR_TRECHO_CS["ok"]};border-radius:0 10px 10px 0"></div>')
    itens = ""
    for i, (nome, p) in enumerate(zip(nomes, passos)):
        cls = "ok" if p == "ok" else "bad" if p == "bloqueado" else "cur" if i == atual else ""
        ic = "✓" if p == "ok" else "✕" if p == "bloqueado" else ""
        tag = "Bloqueado" if p == "bloqueado" else "Em andamento" if i == atual else "Concluído" if (i == n - 1 and p == "ok") else ""
        itens += f'<div class="tl-item {cls}"><div class="tl-c">{ic}</div><div class="tl-n">{nome}</div><div class="tl-t">{tag}</div></div>'
    return f'<div class="tl-wrap">{segs}{itens}</div>'


def html_timeline_pedido(num_etapa, cancelado=False):
    nomes = ["Em Separação", "Faturado", "Coleta Solicitada", "Coleta Efetivada"]
    n = len(nomes)
    passos = []
    for i in range(1, n + 1):
        if cancelado:
            passos.append("cancelado")
        elif i < num_etapa:
            passos.append("ok")
        elif i == num_etapa:
            passos.append("ok" if num_etapa == n else "pendente")
        else:
            passos.append("pendente")

    segs = ""
    for k, p in enumerate(passos, start=1):
        cor = "#e53935" if cancelado else (COR_TRECHO_CS["ok"] if k < num_etapa or (num_etapa == n and k <= n) else "")
        if not cor:
            continue
        ini = 0 if k == 1 else (k - 1.5) / n * 100
        larg = (0.5 if k == 1 else 1) / n * 100 + 0.15
        raio = "10px 0 0 10px" if k == 1 else ("0 10px 10px 0" if k == n else "0")
        segs += f'<div class="tl-seg" style="left:{ini:.3f}%;width:{larg:.3f}%;background:{cor};border-radius:{raio}"></div>'

    if cancelado:
        segs = f'<div class="tl-seg" style="left:0%;width:100%;background:#e53935;border-radius:10px"></div>'
    elif num_etapa == n:
        segs += f'<div class="tl-seg" style="left:{(n - 0.5) / n * 100:.3f}%;width:{0.5 / n * 100:.3f}%;background:{COR_TRECHO_CS["ok"]};border-radius:0 10px 10px 0"></div>'

    itens = ""
    for i, (nome, p) in enumerate(zip(nomes, passos), start=1):
        if cancelado:
            cls, ic, tag = "cancelado", "✕", "Cancelado"
        else:
            is_ok, is_cur = p == "ok", (i == num_etapa and num_etapa < n)
            cls, ic, tag = ("ok" if is_ok else ("cur" if is_cur else "")), ("✓" if is_ok else ""), ("Em andamento" if is_cur else ("Concluído" if is_ok else ""))
        itens += f'<div class="tl-item {cls}"><div class="tl-c">{ic}</div><div class="tl-n">{nome}</div><div class="tl-t">{tag}</div></div>'
    return f'<div class="tl-wrap">{segs}{itens}</div>'


def _dias_atendimento(r, info):
    rec = para_data(r["Recebimento"])
    if pd.isna(rec):
        return None, "Em atendimento há"
    col = (info.get("coleta") or {}).get("data_col", "")
    fim = para_data(col) if col else pd.NaT
    if pd.notna(fim) and info["passos"][-1] == "ok":
        return max((fim.normalize() - rec.normalize()).days, 0), "Ciclo total"
    return max((pd.Timestamp.today().normalize() - rec.normalize()).days, 0), "Em atendimento há"


def html_detalhes_conserto(r, info):
    col = info.get("coleta") or {}
    dias, rot_dias = _dias_atendimento(r, info)
    chips = f'<span class="cs-chip">Nota do cliente <b>{esc(r["Nota cliente"])}</b></span>'
    if r["Recebimento"]:
        chips += f'<span class="cs-chip">Recebido em <b>{esc(r["Recebimento"])}</b></span>'
    if dias is not None:
        chips += f'<span class="cs-chip">{rot_dias} <b>{dias} dia{"s" if dias != 1 else ""}</b></span>'

    det, aviso = info["detalhe"], ""
    if " ⚠️ " in det:
        det, aviso = det.split(" ⚠️ ", 1)
    aviso_html = f'<div class="cs-aviso">{esc(aviso)}</div>' if aviso else ""
    hero = (f'<div class="cs-hero"><div class="cs-card cs-id"><div class="cs-k">Cliente</div>'
            f'<div class="cs-nome">{esc(r["Cliente"])}</div><div class="cs-chips">{chips}</div></div>'
            f'<div class="cs-card cs-note{" bad" if info["bloqueado"] else ""}"><div class="cs-k">Situação</div>'
            f'<div class="cs-nt">{esc(det)}</div>{aviso_html}</div></div>')
    fluxo = f'<div class="cs-card"><div class="cs-k">Fluxo do processo</div>{html_timeline(info["passos"], info["etapa"])}</div>'

    def linha(rot, valor, pill=""):
        v = str(valor).strip()
        if not v or v in ("Ainda não coletada", "Não informada"):
            return f'<div class="cs-row"><span>{rot}</span><b class="vz">{esc(v) if v else "—"}</b></div>'
        corpo = f'<span class="cs-pill {pill}">{esc(v)}</span>' if pill else esc(v)
        return f'<div class="cs-row"><span>{rot}</span><b>{corpo}</b></div>'

    def secao(titulo, linhas):
        return f'<div class="cs-card"><div class="cs-k cs-sec-h">{titulo}</div>{"".join(linhas)}</div>'

    transp = (col.get("transp") or "").strip()
    transp = "" if transp == "-" else transp
    pend = r["Pendência"].strip() or "Sem pendência"
    sec = (secao("Entrada do material", [
               linha("Entrada realizada por", r["Entrada por"]),
               linha("Data de entrada", r["Data entrada"]),
               linha("Pendência / Bloqueio", pend, "bad" if r["_pend"] else "ok")])
           + secao("Liberação e retorno", [
               linha("Liberado pela Assistência", "Sim" if r["_lib"] else "Não", "ok" if r["_lib"] else ""),
               linha("NF de retorno", r["NF retorno"]),
               linha("Emissão da NF de saída", r["Emissão NF saída"])])
           + secao("Coleta pela transportadora", [
               linha("Coleta solicitada em", col.get("data_solic", "")),
               linha("Data da coleta", col.get("data_col") or "Ainda não coletada"),
               linha("Transportadora", transp or "Não informada")]))
    return CSS_CS + hero + fluxo + f'<div class="cs-grid3">{sec}</div>'


def html_detalhes_pedido_layout(cards, data_col_pedido, info, r_pend):
    chips = f'<span class="cs-chip">Nota Fiscal <b>{esc(cards["N.F."])}</b></span>'
    if cards["Número de Pedido"] != "—":
        chips += f'<span class="cs-chip">Pedido <b>{esc(cards["Número de Pedido"])}</b></span>'
    if cards["Incoterm"] != "Não informado":
        chips += f'<span class="cs-chip">Frete <b>{esc(cards["Incoterm"])}</b></span>'

    det = info["detalhe"]
    aviso_pend = f'<div class="cs-aviso">⚠️ Esta NF consta como PENDENTE de coleta há {int(r_pend["Dias pendente"])} dia(s) — Status: {esc(r_pend["Status"])}</div>' if r_pend is not None else ""
    hero = (f'<div class="cs-hero"><div class="cs-card cs-id"><div class="cs-k">Cliente</div>'
            f'<div class="cs-nome">{esc(cards["Cliente"])}</div><div class="cs-chips">{chips}</div></div>'
            f'<div class="cs-card cs-note"><div class="cs-k">Situação Atual</div>'
            f'<div class="cs-nt">{esc(info["status_atual"])}</div>'
            f'<div style="font-size:14px;color:#5c6b73;margin-top:6px">{esc(det)}</div>{aviso_pend}</div></div>')
    fluxo = f'<div class="cs-card"><div class="cs-k">Fluxo do Processo</div>{html_timeline_pedido(info["etapa_atingida"], info["cancelado"])}</div>'

    def linha(rot, valor, pill=""):
        v = str(valor).strip()
        if not v or v in ("—", "Não solicitado", "Não realizado", "Não informado", "Não informada", "Aguardando definição"):
            return f'<div class="cs-row"><span>{rot}</span><b class="vz">—</b></div>'
        corpo = f'<span class="cs-pill {pill}">{esc(v)}</span>' if pill else esc(v)
        return f'<div class="cs-row"><span>{rot}</span><b>{corpo}</b></div>'

    def secao(titulo, linhas):
        return f'<div class="cs-card"><div class="cs-k cs-sec-h">{titulo}</div>{"".join(linhas)}</div>'

    sec = (secao("Informações do Pedido", [
               linha("Nota Fiscal", cards["N.F."]),
               linha("Número de Pedido", cards["Número de Pedido"]),
               linha("Natureza da Operação", cards["Operação"]),
               linha("Modalidade de Frete", cards["Incoterm"])])
           + secao("Logística & Transporte", [
               linha("Transportador", cards["Transportador"]),
               linha("Nº Coleta / Rastreio", cards["Coleta/Rastreio"]),
               linha("Data do Contato", cards["Data Contato"]),
               linha("Data da Coleta", data_col_pedido or "Ainda não coletada")])
           + secao("Observações Gerais", [
               linha("Observações", cards["Observações"])]))
    return CSS_CS + hero + fluxo + f'<div class="cs-grid3">{sec}</div>'


def df_controle(valores):
    cols = ["Responsável", "Operação", "Incoterm", "Cliente", "NF",
            "Transportadora", "Coleta", "Data Solic.", "Data Col.", "Observações", "Num Pedido"]
    linhas = [(l + [""] * 11)[:11] for l in valores[1:]]
    df = pd.DataFrame(linhas, columns=cols)
    df = df[(df["NF"].str.strip() != "") | (df["Num Pedido"].str.strip() != "")].copy()
    df["NF"] = df["NF"].str.strip()
    df["Num Pedido"] = df["Num Pedido"].str.strip()
    df["Data Solic."] = para_data(df["Data Solic."])
    df["Data Col."] = para_data(df["Data Col."])
    return df


def calcular_fluxo_status(linha):
    def pegar_valor(idx):
        return str(linha[idx]).strip() if len(linha) > idx else ""

    responsavel, operacao, incoterm, cliente, nf, transportador, coleta, data_solic, data_col, observacoes, num_pedido = [pegar_valor(i) for i in range(11)]
    cancelado = "cancelada" in operacao.lower()
    etapa_atingida, status_atual = 1, "🟠 Em Separação"
    detalhe_operacional = f"Pedido em separação técnica. Responsável pela ação: {responsavel if responsavel else 'Não informado'}."

    if cancelado:
        status_atual, detalhe_operacional = "❌ Pedido Cancelado", "Esta Nota Fiscal consta como cancelada no sistema."
    else:
        if nf:
            etapa_atingida, status_atual = 2, "🟡 Embalagem / Faturado"
            detalhe_operacional = f"Nota Fiscal {nf} emitida e cliente preenchido. Aguardando solicitação de coleta."
        if coleta and data_solic:
            etapa_atingida, status_atual = 3, "🔵 Coleta Solicitada"
            detalhe_operacional = f"Coleta solicitada em {data_solic} sob o registro/contato: '{coleta}'."
        if data_col:
            etapa_atingida, status_atual = 4, "🟢 Coleta Efetivada"
            detalhe_operacional = f"Material coletado e efetivado em: {data_col}."

    return {
        "etapa_atingida": etapa_atingida, "status_atual": status_atual, "detalhe": detalhe_operacional, "cancelado": cancelado,
        "detalhes_card": {
            "Cliente": cliente or "—", "N.F.": nf or "—", "Número de Pedido": num_pedido or "—",
            "Incoterm": incoterm or "Não informado", "Operação": operacao or "Não informada",
            "Transportador": transportador if transportador and transportador != "-" else "Aguardando definição",
            "Coleta/Rastreio": coleta or "Não solicitado",
            "Data Contato": data_solic if pd.notna(data_solic) and str(data_solic) != "" else "Não realizado",
            "Observações": observacoes or "Nenhuma observação registrada para esta nota."
        }
    }


# ================= TABELAS INTERATIVAS =================
_CSS_TAB_PEND = """
body{margin:0;background:transparent;font-family:"Source Sans Pro",Arial,sans-serif;color:#1f3a57}
.table-container{background:#fff;border-radius:18px;box-shadow:0 4px 20px rgba(59,113,159,.08);overflow:hidden;border:1px solid #e2e8f0;margin-top:10px}
.table-header-bar{display:flex;justify-content:space-between;align-items:center;padding:12px 18px;background:#f8fafc;border-bottom:1px solid #e2e8f0}
.filter-toggle-btn{background:#3b719f;color:#fff;border:none;border-radius:8px;padding:6px 14px;cursor:pointer;font-size:12.5px;font-weight:600}
.filter-toggle-btn:hover{background:#2c5a82}
.record-count{font-size:13px;color:#64748b;font-weight:600}
.tb-wrapper{max-height:580px;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{position:sticky;top:0;background:#3b719f;color:#fff;padding:12px 10px;z-index:2;cursor:pointer;text-align:center;font-weight:700}
.filter-row{display:none;background:#f1f5f9;border-bottom:2px solid #cbd5e1}
.filter-row.active{display:table-row}
.filter-row td{padding:8px 6px;text-align:center}
.filter-row input,.filter-row select{width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px;background:#fff}
td{padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:center;color:#334155;background:#ffffff}
tr:nth-child(even) td{background:#fafcfd}
tr:hover td{background:#f1f5f9}
.status-pill{display:inline-block;padding:4px 10px;border-radius:6px;font-size:11.5px;font-weight:700;text-transform:uppercase;background:#eef3f8;color:#3b719f;border:1px solid #cbd5e1}
.status-pill.urgente{background:#fee2e2;color:#991b1b;border-color:#fca5a5}
.status-pill.ok{background:#dcfce7;color:#166534;border-color:#86efac}
"""

_JS_TAB_PEND = """
const tb=document.querySelector('#t tbody');let rows=[...tb.rows];
const ths=[...document.querySelectorAll('th[data-col]')];
const fls=[...document.querySelectorAll('.filter-row [data-f]')];
const cnt=document.getElementById('cnt');
const toggleBtn=document.getElementById('toggleFilters');
const filterRow=document.getElementById('filterRow');
let col=-1,dir=1, filtersVisible=false;
toggleBtn.addEventListener('click', ()=>{
    filtersVisible = !filtersVisible;
    filterRow.classList.toggle('active', filtersVisible);
    toggleBtn.innerHTML = filtersVisible ? '🔍 Ocultar Filtros' : '🔍 Filtrar Tabela';
});
function filtrar(){
    let n=0;
    rows.forEach(r=>{
        let ok=true;
        fls.forEach((el,i)=>{
            const v=el.value.toLowerCase();
            if(!v)return;
            const txt=r.cells[i].textContent.trim().toLowerCase();
            if(el.tagName==='SELECT'?txt!==v:txt.indexOf(v)<0)ok=false;
        });
        r.style.display=ok?'':'none';
        if(ok)n++;
    });
    cnt.textContent=n+' de '+rows.length+' caso(s)';
}
fls.forEach(el=>{el.addEventListener('input',filtrar);el.addEventListener('change',filtrar);});
document.getElementById('lp').addEventListener('click',()=>{fls.forEach(el=>el.value='');filtrar();});
filtrar();
"""


def html_tabela_pendentes(df):
    cols = [("NF", "NF", "t"), ("Cliente", "Cliente", "t"), ("Frete", "Frete", "t"), ("Transporte", "Transporte", "t"),
            ("Ordem de coleta", "Ordem de coleta", "t"), ("Data Solicitação", "Data Solicitação", "d"), ("Dias pendente", "Dias pendente", "n"), ("Status", "Status", "t")]
    regs = df.to_dict("records")
    th = "".join(f'<th data-col>{n}</th>' for n, _, _ in cols)
    fl = "".join(f'<td><input data-f type="text" placeholder="Filtrar..."></td>' for _, _, _ in cols)
    linhas = ""
    for r in regs:
        d = r["Dias pendente"]
        borda = "#e53935" if (pd.notna(d) and d > 5) else ("#f5b301" if (pd.notna(d) and d > PRAZO_ALERTA) else "#cbd5e1")
        tds = "".join(f'<td>{str(r[k])}</td>' for _, k, _ in cols)
        linhas += f'<tr style="border-left: 5px solid {borda};">{tds}</tr>'
    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_CSS_TAB_PEND}</style></head><body><div class="table-container"><div class="table-header-bar"><button id="toggleFilters" class="filter-toggle-btn">🔍 Filtrar Tabela</button><span class="record-count" id="cnt"></span><button id="lp" style="background:#e2e8f0;border:none;padding:5px 10px;border-radius:6px;cursor:pointer;font-size:12px;color:#334155;">Limpar</button></div><div class="tb-wrapper"><table id="t"><thead><tr>{th}</tr><tr class="filter-row" id="filterRow">{fl}</tr></thead><tbody>{linhas}</tbody></table></div></div><script>{_JS_TAB_PEND}</script></body></html>'


def html_tabela_demonstracao(df):
    cols = [("N.F.", "nf", "t"), ("Cliente", "cliente", "t"), ("Solicitado Por", "solicitado_por", "t"), ("Data Saída", "d_saida", "d"),
            ("Prev. Retorno", "d_prev", "d"), ("Status FUP", "status_fup", "t"), ("Retorno (Data)", "d_retorno", "d"), ("NF Retorno", "nota_retorno", "t"), ("Avaliação", "avaliacao_cliente", "t"), ("Observação", "observacao", "t")]
    regs = df.to_dict("records")
    th = "".join(f'<th data-col>{n}</th>' for n, _, _ in cols)
    fl = "".join(f'<td><input data-f type="text" placeholder="Filtrar..."></td>' for _, _, _ in cols)
    linhas = ""
    for r in regs:
        st_fup = r["status_fup"]
        borda = "#e53935" if "Retorno Urgente" in st_fup else ("#2fae6e" if "Finalizado" in st_fup else "#cbd5e1")
        tds = ""
        for _, k, _ in cols:
            val = str(r[k]) if pd.notna(r[k]) else "-"
            if k == "status_fup":
                cls = "urgente" if "Retorno Urgente" in val else ("ok" if "Finalizado" in val else "")
                tds += f'<td><span class="status-pill {cls}">{esc(val)}</span></td>'
            elif k == "avaliacao_cliente":
                cls = "urgente" if "Negativo" in val else ("ok" if "Positivo" in val else "")
                tds += f'<td><span class="status-pill {cls}">{esc(val)}</span></td>'
            else:
                tds += f'<td>{esc(val)}</td>'
        linhas += f'<tr style="border-left: 5px solid {borda};">{tds}</tr>'
    return f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_CSS_TAB_PEND}</style></head><body><div class="table-container"><div class="table-header-bar"><button id="toggleFilters" class="filter-toggle-btn">🔍 Filtrar Tabela</button><span class="record-count" id="cnt"></span><button id="lp" style="background:#e2e8f0;border:none;padding:5px 10px;border-radius:6px;cursor:pointer;font-size:12px;color:#334155;">Limpar</button></div><div class="tb-wrapper"><table id="t"><thead><tr>{th}</tr><tr class="filter-row" id="filterRow">{fl}</tr></thead><tbody>{linhas}</tbody></table></div></div><script>{_JS_TAB_PEND}</script></body></html>'


ABAS_RESTRITAS = {"pendentes", "dashboard", "demonstracao"}

def verifica_senha(informada, cfg):
    h = cfg.get("senha_hash")
    if h:
        try:
            _, iteracoes, sal, esperado = str(h).split("$")
            calc = hashlib.pbkdf2_hmac("sha256", informada.encode(), sal.encode(), int(iteracoes)).hex()
            return hmac.compare_digest(calc, esperado)
        except Exception:
            return False
    senha = cfg.get("senha")
    return bool(senha) and hmac.compare_digest(str(senha).encode(), informada.encode())


def abas_do_usuario(cfg):
    abas = cfg.get("abas", "todas")
    if isinstance(abas, str):
        return set(ABAS_RESTRITAS) if abas.strip().lower() == "todas" else {abas.strip().lower()} & ABAS_RESTRITAS
    return {str(a).strip().lower() for a in abas} & ABAS_RESTRITAS


# --- DADOS E SESSÃO ---
try:
    todos_dados = ler_valores(NOME_DA_ABA)
    linhas_pedidos = [l for l in todos_dados[1:] if any(l)]
    pend = df_pendentes(ler_valores(ABA_PENDENTES))
    try:
        demo_df = df_demonstracao(ler_valores(ABA_DEMONSTRACAO), todos_dados)
    except Exception:
        demo_df = pd.DataFrame()
except Exception as e:
    st.error(f"Erro ao conectar com a planilha: {e}")
    st.stop()

AUTH_ATIVO = "usuarios" in st.secrets
usuarios = st.secrets["usuarios"] if AUTH_ATIVO else {}
logado = st.session_state.get("usuario")
if logado and logado not in usuarios:
    st.session_state.pop("usuario", None)
    logado = None
cfg_user = usuarios[logado] if logado else {}
permitidas = set(ABAS_RESTRITAS) if not AUTH_ATIVO else (abas_do_usuario(cfg_user) if logado else set())

nomes_completos_todos = {"consulta": "🔎 Consulta Saída", "pendentes": "⏳ Pendentes de coleta", "demonstracao": "🔄 Demonstrações (FUP)", "conserto": "🔧 Conserto/Reparo", "dashboard": "📊 Dashboard"}
icones_apenas_todos = {"consulta": "🔎", "pendentes": "⏳", "demonstracao": "🔄", "conserto": "🔧", "dashboard": "📊"}

chaves = ["consulta"]
if "pendentes" in permitidas: chaves.append("pendentes")
if "demonstracao" in permitidas: chaves.append("demonstracao")
chaves.append("conserto")
if "dashboard" in permitidas: chaves.append("dashboard")

if "pagina" not in st.session_state: st.session_state["pagina"] = "consulta"

# ======================= SIDEBAR =======================
with st.sidebar:
    if expandido:
        c_logo, c_btn = st.columns([4, 1])
        with c_logo: st.markdown('<div class="sb-header" style="border:none;margin:0;padding:0;"><div class="sb-logo">📦<span>PIONEERS<br>OF FLOW</span></div></div>', unsafe_allow_html=True)
        with c_btn:
            if st.button("◀", key="toggle_sb", use_container_width=True):
                st.session_state["sidebar_expanded"] = False
                st.rerun()
    else:
        st.markdown('<div style="text-align:center;font-size:24px;margin-bottom:10px;">📦</div>', unsafe_allow_html=True)
        if st.button("▶", key="toggle_sb", use_container_width=True):
            st.session_state["sidebar_expanded"] = True
            st.rerun()

    st.markdown('<div style="border-bottom:1px solid rgba(255,255,255,.22);margin-bottom:16px;"></div>', unsafe_allow_html=True)
    for _k in chaves:
        _label = nomes_completos_todos[_k] if expandido else icones_apenas_todos[_k]
        if st.button(_label, key=f"nav_{_k}", use_container_width=True, type="primary" if st.session_state["pagina"] == _k else "secondary"):
            st.session_state["pagina"] = _k
            st.rerun()

    st.markdown('<div style="border-bottom:1px solid rgba(255,255,255,.22);margin:16px 0;"></div>', unsafe_allow_html=True)
    if st.button("🔄", use_container_width=True, help="Limpar cache"):
        st.cache_data.clear()
        st.rerun()

    if AUTH_ATIVO:
        if logado:
            with st.popover(f"👤 {cfg_user.get('nome', logado)}" if expandido else "👤", use_container_width=True):
                st.write(f"Conectado como: **{cfg_user.get('nome', logado)}**")
                if st.button("🚪 Sair", key="btn_logout_sb", use_container_width=True):
                    st.session_state.pop("usuario", None)
                    st.rerun()
        else:
            with st.popover("🔐 Logar" if expandido else "🔐", use_container_width=True):
                with st.form("form_login_sb"):
                    u_in = st.text_input("Usuário").strip().lower()
                    p_in = st.text_input("Senha", type="password")
                    entrou = st.form_submit_button("Entrar", use_container_width=True)
                if entrou:
                    if u_in in usuarios and verifica_senha(p_in, usuarios[u_in]):
                        st.session_state["usuario"] = u_in
                        st.rerun()
                    else:
                        st.error("Dados inválidos.")

    st.markdown(f'<div class="sidebar-status-container">{"🟢 Conectado" if logado else "🟢 Modo Convidado"}</div>', unsafe_allow_html=True)

pagina = st.session_state["pagina"]
if pagina not in chaves: pagina = "consulta"

PAGINAS = {
    "consulta": ("Onde está o pedido.", "Portal Logístico de Rastreamento de Pedidos em Tempo Real."),
    "pendentes": ("Pendentes de coleta.", "Acompanhe e gerencie a lista de coletas pendentes."),
    "demonstracao": ("Controle de Demonstrações.", "Gestão contínua de prazos e follow-up de materiais em demonstração."),
    "conserto": ("Conserto / Reparo.", "Verifique o andamento de notas e peças em manutenção."),
    "dashboard": ("Painel de Indicadores & Seções.", "Análise executiva completa de Vendas, Consertos, Demonstrações e Lead Times."),
}
_tit, _sub = PAGINAS.get(pagina, ("Pioneers of Flow.", ""))
st.markdown(f'<div class="header-banner"><div class="hb-kicker">PIONEERS OF FLOW</div><h1>{esc(_tit)}</h1><p>{esc(_sub)}</p></div>', unsafe_allow_html=True)


# ================= 1. CONSULTA =================
if pagina == "consulta":
    pedido_encontrado, r_pend = None, None
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        pesquisa = st.text_input("Digite o número da Nota Fiscal ou Pedido:", placeholder="Ex: 47219...", key="nf_consulta").strip()
        if pesquisa:
            for linha in list(linhas_pedidos):
                if len(linha) > 4 and (pesquisa == str(linha[4]).strip() or (len(linha) > 10 and pesquisa == str(linha[10]).strip())):
                    pedido_encontrado = linha
                    break
            if not pedido_encontrado:
                st.markdown(f'<div style="background:#fff4e5;border:2px solid #f5a623;border-radius:12px;padding:24px;text-align:center;"><div style="font-size:22px;font-weight:800;color:#b45309;">Nota/Pedido não encontrado</div><div style="font-size:15px;color:#5c6b73;margin-top:8px">Nenhum registro para: <b>{esc(pesquisa)}</b></div></div>', unsafe_allow_html=True)
            p = pend[pend["NF"] == pesquisa]
            if not p.empty: r_pend = p.iloc[0]
    if pedido_encontrado is not None:
        info = calcular_fluxo_status(pedido_encontrado)
        st.markdown(html_detalhes_pedido_layout(info["detalhes_card"], str(pedido_encontrado[8]).strip() if len(pedido_encontrado) > 8 else "", info, r_pend), unsafe_allow_html=True)

# ================= 2. PENDENTES =================
elif pagina == "pendentes":
    with st.container():
        st.caption(f"Clique no título de uma coluna para ordenar · amarelo > {PRAZO_ALERTA} dias · vermelho > 5 dias")
        v = pend.copy().sort_values("Dias pendente", ascending=False)
        components.html(html_tabela_pendentes(v), height=660, scrolling=False)
        st.markdown("<br>", unsafe_allow_html=True)
        _, cd_col, _ = st.columns([1, 4, 1])
        with cd_col:
            st.download_button("⬇️ Baixar Relatório em CSV", v.to_csv(index=False).encode("utf-8-sig"), "pendentes_coleta.csv", "text/csv", use_container_width=True)

# ================= 3. DEMONSTRAÇÕES =================
elif pagina == "demonstracao":
    with st.container():
        if demo_df.empty:
            st.warning("Sem dados na aba Demonstração.")
        else:
            tot_abertos = len(demo_df[~demo_df["finalizado"]])
            tot_urgentes = len(demo_df[demo_df["status_fup"] == "🔴 Retorno Urgente"])
            tot_fin = len(demo_df[demo_df["finalizado"]])

            if tot_urgentes > 0:
                st.markdown(f'<div class="fup-urgent-banner"><div style="display:flex;align-items:center;gap:16px;"><span style="font-size:36px;">🚨</span><div><div style="font-size:16px;font-weight:800;color:#c62828;text-transform:uppercase;">Atenção Necessária — Follow-up Urgente!</div><div style="font-size:13.5px;color:#b71c1c;margin-top:2px;">Existem <b>{tot_urgentes}</b> caso(s) com Retorno Urgente pendente.</div></div></div></div>', unsafe_allow_html=True)

            st.markdown(f"""
            <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:20px;">
                <div style="background:#fff;border-radius:16px;padding:16px;box-shadow:0 4px 12px rgba(59,113,159,.1);border-top:5px solid #3b719f;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">Em Aberto (Total)</div>
                    <div style="font-size:32px;font-weight:800;color:#2c5a82;margin-top:4px;">{tot_abertos}</div>
                </div>
                <div style="background:#fff;border-radius:16px;padding:16px;box-shadow:0 4px 12px rgba(59,113,159,.1);border-top:5px solid #e53935;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">🚨 Retorno Urgente</div>
                    <div style="font-size:32px;font-weight:800;color:#e53935;margin-top:4px;">{tot_urgentes}</div>
                </div>
                <div style="background:#fff;border-radius:16px;padding:16px;box-shadow:0 4px 12px rgba(59,113,159,.1);border-top:5px solid #2fae6e;">
                    <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;">🟢 Finalizados</div>
                    <div style="font-size:32px;font-weight:800;color:#1e8e5a;margin-top:4px;">{tot_fin}</div>
                </div>
            </div>""", unsafe_allow_html=True)

            c_t1, c_t2 = st.columns([2, 1])
            with c_t1: inc_fin = st.toggle("Incluir demonstrações finalizadas", value=False)
            with c_t2: apenas_urgentes = st.toggle("🚨 Filtrar apenas Retornos Urgentes", value=False)

            df_ex = demo_df if inc_fin else demo_df[~demo_df["finalizado"]]
            if apenas_urgentes: df_ex = df_ex[df_ex["status_fup"] == "🔴 Retorno Urgente"]

            components.html(html_tabela_demonstracao(df_ex), height=660, scrolling=False)
            st.markdown("<br>", unsafe_allow_html=True)
            _, cd_col2, _ = st.columns([1, 4, 1])
            with cd_col2:
                st.download_button("⬇️ Baixar Relatório CSV", df_ex.to_csv(index=False).encode("utf-8-sig"), "demonstracoes.csv", "text/csv", use_container_width=True)

# ================= 4. CONSERTO =================
elif pagina == "conserto":
    try:
        rep = df_conserto(ler_valores(ABA_CONSERTO))
    except Exception:
        rep = pd.DataFrame()
    r_sel = None
    _, mid4, _ = st.columns([1, 2, 1])
    with mid4:
        q = st.text_input("Número da Nota Fiscal (conserto):", placeholder="Ex: 295889...", key="nf_conserto").strip()
        if q:
            base = rep["Nota cliente"].str.split("-").str[0]
            achou = rep[(rep["Nota cliente"] == q) | (base == q) | (rep["NF retorno"] == q)]
            if achou.empty:
                st.markdown(f'<div style="background:#fff4e5;border:2px solid #f5a623;border-radius:12px;padding:26px;text-align:center;"><div style="font-size:22px;font-weight:800;color:#b45309;">Nota Fiscal NÃO recebida</div><div style="font-size:14px;color:#5c6b73;margin-top:6px">Pesquisado: <b>{esc(q)}</b></div></div>', unsafe_allow_html=True)
            else:
                r_sel = achou.iloc[0]
    if r_sel is not None:
        st.markdown(html_detalhes_conserto(r_sel, status_conserto(r_sel, mapa_coletas(todos_dados))), unsafe_allow_html=True)

# ================= 5. DASHBOARD (COM SEÇÕES E FILTROS AMPLIADOS) =================
_uid = count(1)
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
CSS_DASH = """<style>
.pf-grid{display:grid;gap:16px;margin-bottom:16px}
.pf-r1{grid-template-columns:repeat(4,1fr)}
.pf-card{background:#fff;border-radius:20px;padding:18px 20px;box-shadow:0 3px 10px rgba(59,113,159,.10);text-align:left;overflow:hidden}
.pf-t{font-size:12px;font-weight:700;letter-spacing:.5px;color:#5c6b83;text-transform:uppercase}
.pf-s{font-size:12px;color:#8a97ab;margin-top:2px}
.pf-v{font-size:36px;font-weight:700;color:#3b719f;line-height:1.15;margin-top:6px}
.pf-blue{background:linear-gradient(90deg,#6d8fb6,#3b719f);color:#fff;display:flex;flex-direction:column;justify-content:center}
.pf-blue .pf-t,.pf-blue .pf-s{color:#e3edfb}
.pf-duo{display:flex;justify-content:space-around;gap:10px;margin-top:8px}
.pf-duo div{text-align:center}
.pf-duo b{display:block;font-size:38px;line-height:1.1}
.pf-duo span{font-size:11px;color:#e3edfb}
.pf-li{margin-top:14px}
.pf-lr{display:flex;justify-content:space-between;gap:8px;font-size:13px;font-weight:600;color:#1f3a57}
.pf-lr span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pf-lr b{color:#3b719f;white-space:nowrap}
.pf-tr{height:6px;border-radius:6px;background:#e1e9f5;margin-top:5px}
.pf-fi{height:6px;border-radius:6px;background:linear-gradient(90deg,#6d8fb6,#3b719f)}
</style>"""

def _fmt1(x): return f"{x:.1f}".replace(".", ",")
def _spark(vals, w=240, h=46):
    vals = [float(v) for v in vals]
    u = next(_uid)
    if len(vals) < 2: return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}"><line x1="2" y1="{h-6}" x2="{w-2}" y2="{h-6}" stroke="#dbe5f3" stroke-width="2"/></svg>'
    mn, mx = min(vals), max(vals)
    rng = (mx - mn) or 1
    pts = [(2 + i * (w - 4) / (len(vals) - 1), h - 8 - (v - mn) / rng * (h - 16)) for i, v in enumerate(vals)]
    d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return f'<svg viewBox="0 0 {w} {h}" width="100%" height="{h}" preserveAspectRatio="none"><defs><linearGradient id="sp{u}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6d8fb6" stop-opacity=".25"/><stop offset="1" stop-color="#6d8fb6" stop-opacity="0"/></linearGradient></defs><polygon points="2,{h} {d} {w-2},{h}" fill="url(#sp{u})"/><polyline points="{d}" fill="none" stroke="#6d8fb6" stroke-width="2.2" stroke-linejoin="round"/></svg>'

def _linha(rot, vals, w=640, h=230):
    n, pl, pr, pt, pb = len(vals), 20, 20, 26, 34
    mx = max(max(vals), 1)
    X = lambda i: pl + (w - pl - pr) * (i / (n - 1) if n > 1 else 0.5)
    Y = lambda v: pt + (h - pt - pb) * (1 - v / mx)
    grade = "".join(f'<line x1="{pl}" y1="{pt + (h - pt - pb) * k / 3:.1f}" x2="{w - pr}" y2="{pt + (h - pt - pb) * k / 3:.1f}" stroke="#e1e9f5"/>' for k in range(4))
    pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    bolas = "".join(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="5" fill="#fff" stroke="#6d8fb6" stroke-width="3"/><text x="{X(i):.1f}" y="{Y(v) - 11:.1f}" text-anchor="middle" font-size="11" font-weight="600" fill="#3b719f">{v}</text>' for i, v in enumerate(vals))
    eixo = "".join(f'<text x="{X(i):.1f}" y="{h - 10}" text-anchor="middle" font-size="11" fill="#8a97ab">{r}</text>' for i, r in enumerate(rot))
    return f'<svg viewBox="0 0 {w} {h}" width="100%">{grade}<polyline points="{pts}" fill="none" stroke="#6d8fb6" stroke-width="3" stroke-linejoin="round"/>{bolas}{eixo}</svg>'

def _lista(itens, fmt):
    if not itens: return '<div class="pf-s" style="margin-top:14px">Sem dados.</div>'
    mx = max(v for _, v in itens) or 1
    return "".join(f'<div class="pf-li"><div class="pf-lr"><span>{esc(str(n))}</span><b>{fmt(v)}</b></div><div class="pf-tr"><div class="pf-fi" style="width:{max(v / mx * 100, 4):.0f}%"></div></div></div>' for n, v in itens)

def sem_ignorados(df, col="Cliente"):
    if df is None or df.empty: return df
    return df[~df[col].map(_norm).apply(lambda n: any(i in n for i in CLIENTES_IGNORADOS))]

def dados_conserto_dash(rep, coletas, hoje):
    if rep is None or rep.empty: return pd.DataFrame(columns=["Cliente", "dias", "coletado"])
    r2 = rep[(rep["NF retorno"] != "") & (rep["Emissão NF saída"] != "")].copy()
    r2["emissao"] = para_data(r2["Emissão NF saída"])
    r2["coleta"] = para_data(r2["NF retorno"].map(lambda n: coletas.get(n.strip(), {}).get("data_col", "")))
    r2 = r2.dropna(subset=["emissao"])
    r2["coletado"] = r2["coleta"].notna()
    r2["dias"] = (r2["coleta"].fillna(hoje).dt.normalize() - r2["emissao"].dt.normalize()).dt.days
    return r2[(r2["dias"] >= 0) & (r2["dias"] <= 365)]


if pagina == "dashboard":
    with st.container():
        hoje = pd.Timestamp.today().normalize()
        try:
            rep_d = df_conserto(ler_valores(ABA_CONSERTO))
        except Exception:
            rep_d = None
        r2 = sem_ignorados(dados_conserto_dash(rep_d, mapa_coletas(todos_dados), hoje))
        fat_all = sem_ignorados(df_controle(todos_dados))
        fat_all["mes"] = fat_all["Data Solic."].dt.to_period("M")
        fat = fat_all[(fat_all["NF"] != "") & (~fat_all["Operação"].str.lower().str.contains("cancel"))].copy()
        pend_d = sem_ignorados(pend)

        st.markdown("### 🎛️ Seções de Análise e KPIs Executivos")
        secao_analise = st.selectbox(
            "Selecione a seção de KPIs que deseja analisar:",
            [
                "📊 Vendas & Faturamento (Filtro por Mês, Múltiplos Meses ou Ano)",
                "🔧 Conserto & Reparo",
                "🔄 Demonstrações & Avaliação de Clientes",
                "⏳ Prazos Acima do Comum & Gargalos",
                "🔍 Modo Tela Cheia (Análise Individual de KPI)"
            ],
            key="secao_dashboard_sel"
        )
        st.markdown("---")

        if "Vendas" in secao_analise:
            st.markdown("#### 📊 Análise de Vendas e Faturamento")
            tipo_filtro = st.radio("Filtro temporal de vendas:", ["Mês Específico", "Ano Inteiro / Múltiplos Meses"], horizontal=True)
            
            meses_disp = sorted(fat["mes"].dropna().unique(), reverse=True)
            if tipo_filtro == "Mês Específico":
                sel_m = st.selectbox("Selecione o Mês", meses_disp, index=0 if meses_disp else 0, format_func=lambda p: f"{MESES[p.month-1]}/{p.year}")
                fat_f = fat[fat["mes"] == sel_m]
            else:
                anos_disp = sorted(list({str(p.year) for p in meses_disp}), reverse=True)
                sel_ano = st.selectbox("Selecione o Ano", anos_disp)
                fat_f = fat[fat["mes"].astype(str).str.startswith(sel_ano)]

            conc = r2[r2["coletado"]]
            media_lib = conc["dias"].mean() if len(conc) else 0
            qtd_fat = len(fat_f)
            rank = fat_f[~fat_f["Cliente"].isin(["", "-"])].groupby("Cliente").size().sort_values(ascending=False)
            top_n, top_q = (rank.index[0], int(rank.iloc[0])) if len(rank) else ("—", 0)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="pf-card" style="border-top:5px solid #3b719f;"><div class="pf-t">Liberação → Coleta</div><div class="pf-v">{_fmt1(media_lib)} dias</div><div class="pf-s">Média do período</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown(f'<div class="pf-card" style="border-top:5px solid #3b719f;"><div class="pf-t">Notas Faturadas</div><div class="pf-v">{qtd_fat}</div><div class="pf-s">Total no filtro</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="pf-card" style="border-top:5px solid #3b719f;"><div class="pf-t">Maior Reincidência</div><div class="pf-v">{top_q}x</div><div class="pf-s" style="font-weight:700;color:#2c5a82;">{esc(top_n)}</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="pf-card pf-blue"><div class="pf-t">Pendentes de Coleta</div><div class="pf-duo"><div><b>{len(pend_d)}</b><span>Total</span></div><div><b>{int(pend_d["Atrasado"].sum())}</b><span>Atrasados</span></div></div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            per = pd.period_range(end=hoje.to_period("M"), periods=12, freq="M")
            cont = fat.groupby("mes").size().reindex(per, fill_value=0)
            st.markdown(f'<div class="pf-card"><div class="pf-t">Notas Faturadas · Últimos 12 Meses</div><div style="margin-top:14px;">{_linha([f"{MESES[p.month-1]}/{str(p.year)[2:]}" for p in per], cont.tolist())}</div></div>', unsafe_allow_html=True)

        elif "Conserto" in secao_analise:
            st.markdown("#### 🔧 Métricas de Conserto e Reparo")
            total_cons = len(rep_d) if rep_d is not None and not rep_d.empty else 0
            cons_coletados = len(r2[r2["coletado"]]) if not r2.empty else 0
            media_cons = r2["dias"].mean() if not r2.empty else 0

            c1, c2, c3 = st.columns(3)
            with c1: st.markdown(f'<div class="pf-card" style="border-top:5px solid #6d8fb6;"><div class="pf-t">Total em Conserto</div><div class="pf-v">{total_cons}</div><div class="pf-s">Registrados na assistência</div></div>', unsafe_allow_html=True)
            with c2: st.markdown(f'<div class="pf-card" style="border-top:5px solid #2fae6e;"><div class="pf-t">Consertos Concluídos</div><div class="pf-v">{cons_coletados}</div><div class="pf-s">Devolvidos com coleta efetuada</div></div>', unsafe_allow_html=True)
            with c3: st.markdown(f'<div class="pf-card" style="border-top:5px solid #3b719f;"><div class="pf-t">Tempo Médio de Reparo</div><div class="pf-v">{_fmt1(media_cons)} dias</div><div class="pf-s">Emissão NF saída → Coleta</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            afet = r2.groupby("Cliente")["dias"].mean().sort_values(ascending=False).head(5)
            st.markdown(f'<div class="pf-card"><div class="pf-t">Clientes com Maior Tempo de Ciclo em Conserto</div><div class="pf-s">Média de dias até a coleta</div>{_lista([(c, v) for c, v in afet.items() if c], lambda v: f"{v:.0f} dias")}</div>', unsafe_allow_html=True)

        elif "Demonstrações" in secao_analise:
            st.markdown("#### 🔄 Demonstrações & Avaliação de Desempenho dos Clientes")
            if demo_df.empty:
                st.warning("Sem dados de demonstração.")
            else:
                tot_d, urg_d = len(demo_df), len(demo_df[demo_df["status_fup"] == "🔴 Retorno Urgente"])
                pos_c = len(demo_df[demo_df["avaliacao_cliente"].str.contains("Positivo")])
                neg_c = len(demo_df[demo_df["avaliacao_cliente"].str.contains("Negativo")])

                c1, c2, c3, c4 = st.columns(4)
                with c1: st.markdown(f'<div class="pf-card" style="border-top:5px solid #3b719f;"><div class="pf-t">Total Demonstrações</div><div class="pf-v">{tot_d}</div><div class="pf-s">Casos registrados</div></div>', unsafe_allow_html=True)
                with c2: st.markdown(f'<div class="pf-card" style="border-top:5px solid #e53935;"><div class="pf-t">Retornos Urgentes</div><div class="pf-v">{urg_d}</div><div class="pf-s">Follow-up imediato</div></div>', unsafe_allow_html=True)
                with c3: st.markdown(f'<div class="pf-card" style="border-top:5px solid #2fae6e;"><div class="pf-t">🟢 Clientes Positivos</div><div class="pf-v">{pos_c}</div><div class="pf-s">Devolução no prazo</div></div>', unsafe_allow_html=True)
                with c4: st.markdown(f'<div class="pf-card" style="border-top:5px solid #e53935;"><div class="pf-t">🔴 Clientes Negativos</div><div class="pf-v">{neg_c}</div><div class="pf-s">Devolução em atraso</div></div>', unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)
                resumo_cli = demo_df.groupby("cliente").agg(Total_Casos=("nf", "count"), Atrasados=("status_fup", lambda x: (x == "🔴 Retorno Urgente").sum())).reset_index()
                resumo_cli["Avaliação Geral"] = resumo_cli["Atrasados"].apply(lambda x: "🟢 Excelente (Sem Atrasos)" if x == 0 else "🔴 Requer Atenção (Com Atrasos)")
                st.dataframe(resumo_cli, use_container_width=True, hide_index=True)

        elif "Prazos Acima" in secao_analise:
            st.markdown("#### ⏳ Prazos Acima do Comum & Gargalos")
            atrasados_p = pend_d[pend_d["Atrasado"]].copy()
            st.markdown(f'<div class="pf-card" style="border-left: 6px solid #e53935; margin-bottom: 16px;"><div class="pf-t">Coletas com Atraso Crítico (> {PRAZO_ALERTA} dias)</div><div class="pf-v">{len(atrasados_p)} casos</div><div class="pf-s">Aguardando coleta na expedição</div></div>', unsafe_allow_html=True)
            if not atrasados_p.empty:
                st.dataframe(atrasados_p[["NF", "Cliente", "Frete", "Transporte", "Data Solicitação", "Dias pendente", "Status"]], use_container_width=True, hide_index=True)
            else:
                st.success("Nenhum caso com prazo acima do comum no momento!")

        else:
            st.markdown("#### 🔍 Modo Tela Cheia — Análise Individual de KPI")
            kpi_esc = st.selectbox("Escolha o KPI para análise detalhada:", ["Média de Liberação até Coleta", "Volume de Notas Faturadas", "Cliente com Maior Reincidência", "Status de Pendentes de Coleta", "Taxa de Retorno Urgente (Demonstrações)"])
            st.markdown("---")
            if "Liberação" in kpi_esc:
                st.markdown(f'<div class="pf-card" style="padding: 40px; text-align: center;"><div class="pf-t">Média de Liberação → Coleta</div><div class="pf-v" style="font-size: 64px; margin: 20px 0;">{_fmt1(r2["dias"].mean() if not r2.empty else 0)} dias</div><div class="pf-s">Média de dias entre a emissão da NF de retorno e a efetivação da coleta.</div></div>', unsafe_allow_html=True)
            elif "Faturadas" in kpi_esc:
                st.markdown(f'<div class="pf-card" style="padding: 40px; text-align: center;"><div class="pf-t">Volume Total Faturado</div><div class="pf-v" style="font-size: 64px; margin: 20px 0;">{len(fat)} notas</div><div class="pf-s">Total acumulado de notas faturadas no sistema.</div></div>', unsafe_allow_html=True)
            elif "Reincidência" in kpi_esc:
                rank = fat[~fat["Cliente"].isin(["", "-"])].groupby("Cliente").size().sort_values(ascending=False)
                tn, tq = (rank.index[0], int(rank.iloc[0])) if len(rank) else ("—", 0)
                st.markdown(f'<div class="pf-card" style="padding: 40px; text-align: center;"><div class="pf-t">Maior Reincidência</div><div class="pf-v" style="font-size: 64px; margin: 20px 0;">{tq}x</div><div class="pf-s" style="font-size: 18px; font-weight:700;">Cliente: {esc(tn)}</div></div>', unsafe_allow_html=True)
            elif "Pendentes" in kpi_esc:
                st.markdown(f'<div class="pf-card pf-blue" style="padding: 40px; text-align: center;"><div class="pf-t" style="color:#e3edfb">Pendentes de Coleta</div><div class="pf-v" style="font-size: 64px; margin: 20px 0; color:#fff">{len(pend_d)} itens</div><div class="pf-s" style="color:#e3edfb">Destes, {int(pend_d["Atrasado"].sum())} encontram-es com atraso superior a {PRAZO_ALERTA} dias.</div></div>', unsafe_allow_html=True)
            else:
                urg = len(demo_df[demo_df["status_fup"] == "🔴 Retorno Urgente"]) if not demo_df.empty else 0
                st.markdown(f'<div class="pf-card" style="padding: 40px; text-align: center;"><div class="pf-t">Retornos Urgentes (Demonstração)</div><div class="pf-v" style="font-size: 64px; margin: 20px 0; color:#e53935">{urg} casos</div><div class="pf-s">Casos que exigem follow-up imediato na aba de demonstrações.</div></div>', unsafe_allow_html=True)

st.markdown("<br><hr><div style='text-align: center; color: #6b7a90; font-size: 13px;'>Pioneers of Flow · Desenvolvido por Diego Elvis</div>", unsafe_allow_html=True)
