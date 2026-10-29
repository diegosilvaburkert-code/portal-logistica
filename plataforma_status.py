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
    </style>
""", unsafe_allow_html=True)


@st.cache_resource
def conectar_google_sheets():
    info_json = st.secrets["gspread_credentials"]["json_string"]
    dic_chaves = json.loads(info_json, strict=False)
    if "private_key" in dic_chaves:
        dic_chaves["private_key"] = dic_chaves["private_key"].replace("\\\\n", "\n").replace("\\n", "\n")
    cliente = gspread.service_account_from_dict(dic_chaves)
    return cliente


@st.cache_data(ttl=300)
def ler_valores(aba):
    client = conectar_google_sheets()
    return client.open_by_url(LINK_PLANILHA).worksheet(aba).get_all_values()


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
.tl-item.ok:last-child .tl-t{color:#1e8e5a}
</style>"""

COR_TRECHO_CS = {"ok": "#2fae6e", "bloqueado": "#e53935"}


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


def html_timeline_pedido(num_etapa):
    nomes = ["Em Separação", "Faturado", "Coleta Solicitada", "Coleta Efetivada"]
    n = len(nomes)
    
    idx_atual = num_etapa - 1 if 1 <= num_etapa <= n else -1

    passos = []
    for i in range(1, n + 1):
        if i < num_etapa:
            passos.append("ok")
        elif i == num_etapa:
            passos.append("pendente")
        else:
            passos.append("pendente")

    segs = ""
    for k, p in enumerate(passos, start=1):
        cor = COR_TRECHO_CS["ok"] if k < num_etapa else ""
        if not cor:
            continue
        ini = 0 if k == 1 else (k - 1.5) / n * 100
        larg = (0.5 if k == 1 else 1) / n * 100 + 0.15
        raio = "10px 0 0 10px" if k == 1 else "0"
        segs += f'<div class="tl-seg" style="left:{ini:.3f}%;width:{larg:.3f}%;background:{cor};border-radius:{raio}"></div>'

    itens = ""
    for i, (nome, p) in enumerate(zip(nomes, passos), start=1):
        is_ok = i < num_etapa
        is_cur = (i == num_etapa)
        
        cls = "ok" if is_ok else ("cur" if is_cur else "")
        ic = "✓" if is_ok else ""
        tag = "Em andamento" if is_cur else ("Concluído" if is_ok else "")
        
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

    fluxo = (f'<div class="cs-card"><div class="cs-k">Fluxo do processo</div>'
             f'{html_timeline(info["passos"], info["etapa"])}</div>')

    def linha(rot, valor, pill=""):
        v = str(valor).strip()
        if not v:
            return f'<div class="cs-row"><span>{rot}</span><b class="vz">—</b></div>'
        if v in ("Ainda não coletada", "Não informada"):
            return f'<div class="cs-row"><span>{rot}</span><b class="vz">{esc(v)}</b></div>'
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
    h = CSS_CS + hero + fluxo + f'<div class="cs-grid3">{sec}</div>'
    return "\n".join(l.strip() for l in h.splitlines() if l.strip())


def html_detalhes_pedido_layout(cards, data_col_pedido, info, r_pend):
    chips = f'<span class="cs-chip">Nota Fiscal <b>{esc(cards["N.F."])}</b></span>'
    if cards["Número de Pedido"] != "—":
        chips += f'<span class="cs-chip">Pedido <b>{esc(cards["Número de Pedido"])}</b></span>'
    if cards["Incoterm"] != "Não informado":
        chips += f'<span class="cs-chip">Frete <b>{esc(cards["Incoterm"])}</b></span>'

    det = info["detalhe"]
    aviso_pend = ""
    if r_pend is not None:
        aviso_pend = f'<div class="cs-aviso">⚠️ Esta NF consta como PENDENTE de coleta há {int(r_pend["Dias pendente"])} dia(s) — Status: {esc(r_pend["Status"])}</div>'

    hero = (f'<div class="cs-hero"><div class="cs-card cs-id"><div class="cs-k">Cliente</div>'
            f'<div class="cs-nome">{esc(cards["Cliente"])}</div><div class="cs-chips">{chips}</div></div>'
            f'<div class="cs-card cs-note"><div class="cs-k">Situação Atual</div>'
            f'<div class="cs-nt">{esc(info["status_atual"])}</div>'
            f'<div style="font-size:14px;color:#5c6b73;margin-top:6px">{esc(det)}</div>{aviso_pend}</div></div>')

    fluxo = (f'<div class="cs-card"><div class="cs-k">Fluxo do Processo</div>'
             f'{html_timeline_pedido(info["etapa_atingida"])}</div>')

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
               linha("Nº Coleta / Registro", cards["Coleta/Rastreio"]),
               linha("Data do Contato", cards["Data Contato"]),
               linha("Data da Coleta", data_col_pedido or "Ainda não coletada")])
           + secao("Observações Gerais", [
               linha("Observações", cards["Observações"])]))

    h = CSS_CS + hero + fluxo + f'<div class="cs-grid3">{sec}</div>'
    return "\n".join(l.strip() for l in h.splitlines() if l.strip())


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
    num_pedido = pegar_valor(10)

    transportador_valido = transportador and transportador != "-"

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
            "N.F.": nf if nf else "—",
            "Número de Pedido": num_pedido if num_pedido else "—",
            "Incoterm": incoterm if incoterm else "Não informado",
            "Operação": operacao if operacao else "Não informada",
            "Transportador": transportador if transportador_valido else "Aguardando definição",
            "Coleta/Rastreio": coleta if coleta else "Não solicitado",
            "Data Contato": data_solic if data_solic else "Não realizado",
            "Observações": observacoes if observacoes else "Nenhuma observação registrada para esta nota."
        }
    }


# ================= TABELA INTERATIVA ESTILO EXCEL (COM BARRA LATERAL) =================
_CSS_TAB_PEND = """
body{margin:0;background:transparent;font-family:"Source Sans Pro",Arial,sans-serif;color:#1f3a57}
.table-container{background:#fff;border-radius:18px;box-shadow:0 4px 20px rgba(59,113,159,.08);overflow:hidden;border:1px solid #e2e8f0;margin-top:10px}
.table-header-bar{display:flex;justify-content:space-between;align-items:center;padding:12px 18px;background:#f8fafc;border-bottom:1px solid #e2e8f0}
.filter-toggle-btn{background:#3b719f;color:#fff;border:none;border-radius:8px;padding:6px 14px;cursor:pointer;font-size:12.5px;font-weight:600;display:flex;align-items:center;gap:6px;transition:all .2s}
.filter-toggle-btn:hover{background:#2c5a82}
.record-count{font-size:13px;color:#64748b;font-weight:600}
.tb-wrapper{max-height:580px;overflow:auto}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{position:sticky;top:0;background:#3b719f;color:#fff;padding:12px 10px;z-index:2;cursor:pointer;user-select:none;white-space:nowrap;text-align:center;font-weight:700}
th:hover{background:#2c5a82}
th i{font-style:normal;margin-left:4px;font-size:11px;opacity:0.8}
.filter-row{display:none;background:#f1f5f9;border-bottom:2px solid #cbd5e1}
.filter-row.active{display:table-row}
.filter-row td{padding:8px 6px;text-align:center}
.filter-row input,.filter-row select{width:100%;box-sizing:border-box;padding:5px 8px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px;background:#fff;color:#1e293b}
td{padding:10px 12px;border-bottom:1px solid #e2e8f0;text-align:center;color:#334155;background:#ffffff}
tr:nth-child(even) td{background:#fafcfd}
tr:hover td{background:#f1f5f9}

.status-pill{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11.5px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .4px;
    white-space: nowrap;
    background: #eef3f8;
    color: #3b719f;
    border: 1px solid #cbd5e1;
}
.status-pill.vendedor{
    background: #f8fafc;
    color: #475569;
    border-color: #cbd5e1;
}
.status-pill.aguardando{
    background: #e0f2fe;
    color: #0369a1;
    border-color: #bae6fd;
}
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

function marcar(){ths.forEach((h,i)=>h.querySelector('i').textContent=i===col?(dir>0?'▲':'▼'):'');}

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

function ordenar(i){
    dir=(col===i)?-dir:1;col=i;const num=ths[i].dataset.t!=='t';
    rows.sort((a,b)=>{
        let x=a.cells[i].dataset.v,y=b.cells[i].dataset.v;
        if(num){
            x=parseFloat(x);y=parseFloat(y);
            const nx=isNaN(x),ny=isNaN(y);
            if(nx&&ny)return 0;if(nx)return 1;if(ny)return -1;
            return (x-y)*dir;
        }
        return x.localeCompare(y,'pt-BR')*dir;
    });
    rows.forEach(r=>tb.appendChild(r));marcar();
}

ths.forEach((h,i)=>h.addEventListener('click',()=>ordenar(i)));
fls.forEach(el=>{el.addEventListener('input',filtrar);el.addEventListener('change',filtrar);});
document.getElementById('lp').addEventListener('click',()=>{fls.forEach(el=>el.value='');filtrar();});
col=__DIAS__;dir=-1;marcar();filtrar();
"""


def html_tabela_pendentes(df):
    cols = [
        ("NF", "NF", "t"),
        ("Cliente", "Cliente", "t"),
        ("Frete", "Frete", "t"),
        ("Transporte", "Transporte", "t"),
        ("Ordem de coleta", "Ordem de coleta", "t"),
        ("Data Solicitação", "Data Solicitação", "d"),
        ("Dias pendente", "Dias pendente", "n"),
        ("Status", "Status", "t")
    ]
    regs = df.to_dict("records")

    def texto(r, k):
        v = r[k]
        if v is None or (isinstance(v, float) and pd.isna(v)) or v == "":
            return "-"
        if k == "Data Solicitação" and pd.notna(v):
            return pd.to_datetime(v).strftime("%d/%m/%Y")
        if k == "Dias pendente":
            return f"{int(v)}"
        return str(v)

    def chave(r, k, tipo):
        if tipo == "n":
            return "" if pd.isna(r[k]) else str(int(r[k]))
        if tipo == "d":
            d = para_data(r[k])
            return "" if pd.isna(d) else str(d.toordinal())
        return _norm(texto(r, k))

    th = "".join(f'<th data-col data-t="{t}">{n}<i></i></th>' for n, _, t in cols)
    
    fl = ""
    for n, k, t in cols:
        vals = sorted({texto(r, k) for r in regs}, key=_norm)
        if t == "t" and len(vals) <= 25:
            ops = '<option value="">Todos</option>' + "".join(f'<option value="{esc(v.lower())}">{esc(v)}</option>' for v in vals)
            fl += f'<td><select data-f>{ops}</select></td>'
        else:
            fl += '<td><input data-f type="text" placeholder="Filtrar..."></td>'
            
    linhas = ""
    for r in regs:
        d = r["Dias pendente"]
        borda_esquerda = "#e53935" if (pd.notna(d) and d > 5) else ("#f5b301" if (pd.notna(d) and d > PRAZO_ALERTA) else "#cbd5e1")
        
        tds = ""
        for _, k, t in cols:
            val_txt = texto(r, k)
            val_chave = chave(r, k, t)
            
            if k == "Status":
                st_lower = val_txt.lower()
                extra_cls = "vendedor" if "vendedor" in st_lower else "aguardando"
                conteudo = f'<span class="status-pill {extra_cls}">{esc(val_txt)}</span>'
                tds += f'<td data-v="{esc(val_chave)}">{conteudo}</td>'
            else:
                tds += f'<td data-v="{esc(val_chave)}">{esc(val_txt)}</td>'
                
        linhas += f'<tr style="border-left: 5px solid {borda_esquerda};">{tds}</tr>'
        
    js = _JS_TAB_PEND.replace("__DIAS__", str([c[1] for c in cols].index("Dias pendente")))
    
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{_CSS_TAB_PEND}</style></head><body>'
            f'<div class="table-container">'
            f'<div class="table-header-bar"><button id="toggleFilters" class="filter-toggle-btn">🔍 Filtrar Tabela</button>'
            f'<span class="record-count" id="cnt"></span><button id="lp" style="background:#e2e8f0;border:none;padding:5px 10px;border-radius:6px;cursor:pointer;font-size:12px;color:#334155;font-weight:600">Limpar Filtros</button></div>'
            f'<div class="tb-wrapper"><table id="t"><thead>'
            f'<tr>{th}</tr>'
            f'<tr class="filter-row" id="filterRow">{fl}</tr>'
            f'</thead><tbody>{linhas}</tbody></table></div></div>'
            f'<script>{js}</script></body></html>')


ABAS_RESTRITAS = {"pendentes", "dashboard"}


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


# --- LEITURA DE DADOS E AUTENTICAÇÃO ---
try:
    todos_dados = ler_valores(NOME_DA_ABA)
    linhas_pedidos = [l for l in todos_dados[1:] if any(l)]
    pend = df_pendentes(ler_valores(ABA_PENDENTES))
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

topo1, topo2, topo3 = st.columns([5, 2, 1])
erro_login = ""
if AUTH_ATIVO:
    with topo2:
        if logado:
            st.caption(f"👤 {cfg_user.get('nome', logado)}")
            if st.button("Sair"):
                st.session_state.pop("usuario", None)
                st.rerun()
        else:
            with st.popover("🔐 Entrar (colaboradores)"):
                with st.form("form_login"):
                    u_in = st.text_input("Usuário").strip().lower()
                    p_in = st.text_input("Senha", type="password")
                    entrou = st.form_submit_button("Entrar")
            if entrou:
                if st.session_state.get("tentativas", 0) >= 5:
                    erro_login = "Muitas tentativas incorretas. Aguarde e recarregue a página."
                elif u_in in usuarios and verifica_senha(p_in, usuarios[u_in]):
                    st.session_state["usuario"] = u_in
                    st.session_state["tentativas"] = 0
                    st.rerun()
                else:
                    st.session_state["tentativas"] = st.session_state.get("tentativas", 0) + 1
                    time.sleep(1.5)
                    erro_login = "Usuário ou senha inválidos."
if erro_login:
    st.error(erro_login)
if AUTH_ATIVO and not logado:
    st.info("🔒 Acesso externo: as abas **Pendentes de coleta** e **Dashboard** são exclusivas para colaboradores. "
            "Se você é da empresa, clique em **Entrar** com seu usuário e senha.")

nomes_completos_todos = {
    "consulta": "🔎 Consulta Saída",
    "pendentes": "⏳ Pendentes de coleta",
    "conserto": "🔧 Conserto/Reparo",
    "dashboard": "📊 Dashboard"
}
icones_apenas_todos = {
    "consulta": "🔎",
    "pendentes": "⏳",
    "conserto": "🔧",
    "dashboard": "📊"
}

chaves = ["consulta"]
if "pendentes" in permitidas:
    chaves.append("pendentes")
chaves.append("conserto")
if "dashboard" in permitidas:
    chaves.append("dashboard")

if "pagina" not in st.session_state:
    st.session_state["pagina"] = "consulta"

# ======================= NAVEGAÇÃO LATERAL (SIDEBAR DINÂMICA) =======================
with st.sidebar:
    if expandido:
        c_logo, c_btn = st.columns([4, 1])
        with c_logo:
            st.markdown('<div class="sb-header" style="border:none;margin:0;padding:0;"><div class="sb-logo">📦<span>PIONEERS<br>OF FLOW</span></div></div>', unsafe_allow_html=True)
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
        _ativo = st.session_state["pagina"] == _k
        if st.button(_label, key=f"nav_{_k}", use_container_width=True, type="primary" if _ativo else "secondary"):
            st.session_state["pagina"] = _k
            st.rerun()

    st.markdown('<div style="border-bottom:1px solid rgba(255,255,255,.22);margin:16px 0;"></div>', unsafe_allow_html=True)

    # 🔄 BOTÃO DE ATUALIZAÇÃO MANUAL
    if st.button("🔄", use_container_width=True, help="Limpa o cache e busca os dados mais recentes do Google Sheets"):
        st.cache_data.clear()
        st.rerun()

    texto_conexao = "🟢 Conexão Estabelecida" if expandido else "🟢"
    st.markdown(
        f'<div class="sidebar-status-container">{texto_conexao}</div>',
        unsafe_allow_html=True
    )

pagina = st.session_state["pagina"]
if pagina not in chaves:
    pagina = "consulta"

# ======================= CABEÇALHO DA PÁGINA =======================
PAGINAS = {
    "consulta": ("Onde está o pedido.", "Portal Logístico de Rastreamento de Pedidos em Tempo Real."),
    "pendentes": ("Pendentes de coleta.", "Acompanhe e gerencie a lista de coletas pendentes."),
    "conserto": ("Conserto / Reparo.", "Verifique o andamento de notas e peças em manutenção."),
    "dashboard": ("Visão Geral.", "Métricas de lead time, volume faturado e gargalos de expedição."),
}
_tit, _sub = PAGINAS.get(pagina, ("Pioneers of Flow.", ""))
st.markdown(f"""
    <div class="header-banner">
        <div class="hb-kicker">PIONEERS OF FLOW</div>
        <h1>{esc(_tit)}</h1>
        <p>{esc(_sub)}</p>
    </div>
""", unsafe_allow_html=True)


# ================= 1. CONSULTA =================
if pagina == "consulta":
    pedido_encontrado = None
    r_pend = None
    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        st.write("Insira o número da Nota Fiscal ou o Número de Pedido abaixo para verificar o fluxo do processo.")
        pesquisa = st.text_input("Digite o número da Nota Fiscal ou Pedido:", placeholder="Ex: 47219...", key="nf_consulta").strip()

        if pesquisa:
            for linha in list(linhas_pedidos):
                if len(linha) > 4:
                    nf_numero = str(linha[4]).strip()
                    num_pedido = str(linha[10]).strip() if len(linha) > 10 else ""
                    
                    if pesquisa == nf_numero or (num_pedido and pesquisa == num_pedido):
                        pedido_encontrado = linha
                        break
            
            if not pedido_encontrado:
                titulo_aviso = "Nota fiscal não faturada" if len(pesquisa) > 6 else "Pedido não faturado"
                st.markdown(
                    f'<div style="background:#fff4e5;border:2px solid #f5a623;border-radius:12px;padding:24px 20px;text-align:center;'
                    f'box-shadow:0 4px 12px rgba(245,166,35,.18);margin-top:10px"><div style="font-size:34px;line-height:1">⚠️</div>'
                    f'<div style="font-size:22px;font-weight:800;color:#b45309;margin-top:8px">{titulo_aviso}</div>'
                    f'<div style="font-size:15px;color:#5c6b73;margin-top:8px">Nenhum registro para: <b>{esc(pesquisa)}</b>. Confira o número digitado.</div></div>',
                    unsafe_allow_html=True
                )

            p = pend[pend["NF"] == pesquisa]
            if not p.empty:
                r_pend = p.iloc[0]

    if pedido_encontrado is not None:
        info = calcular_fluxo_status(pedido_encontrado)
        cards = info["detalhes_card"]
        data_col_pedido = str(pedido_encontrado[8]).strip() if len(pedido_encontrado) > 8 else ""
        st.markdown(html_detalhes_pedido_layout(cards, data_col_pedido, info, r_pend), unsafe_allow_html=True)

# ================= 2. PENDENTES =================
if pagina == "pendentes":
    with st.container():
        st.caption(f"Clique no título de uma coluna para ordenar · clique no botão **Filtrar Tabela** acima da tabela para exibir os campos de filtro · "
                   f"amarelo > {PRAZO_ALERTA} dias · vermelho > 5 dias desde a solicitação")
        
        v = pend.copy()
        v = v.sort_values("Dias pendente", ascending=False)
        
        components.html(html_tabela_pendentes(v), height=660, scrolling=False)
        
        st.markdown("<br>", unsafe_allow_html=True)
        cols_dl = st.columns([1, 4, 1])
        with cols_dl[1]:
            st.download_button("⬇️ Baixar Relatório em CSV", v[["NF", "Cliente", "Frete", "Transporte", "Ordem de coleta", "Data Solicitação", "Dias pendente", "Status"]].to_csv(index=False).encode("utf-8-sig"),
                               "pendentes_coleta.csv", "text/csv", use_container_width=True)

# ================= 3. DASHBOARD =================
_uid = count(1)
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
CSS_DASH = """<style>
.pf-grid{display:grid;gap:16px;margin-bottom:16px}
.pf-r1{grid-template-columns:repeat(4,1fr)}
.pf-r2{grid-template-columns:270px 1fr}
.pf-r3{grid-template-columns:1.2fr 1fr 1fr}
@media(max-width:1000px){.pf-r1,.pf-r2,.pf-r3{grid-template-columns:1fr}}
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
.pf-don{display:flex;flex-direction:column;align-items:center;gap:6px;text-align:center}
.pf-don+.pf-don{margin-top:18px;padding-top:16px;border-top:1px solid #e1e9f5}
.pf-big{display:flex;gap:18px;align-items:center}
.pf-big .side{min-width:150px;text-align:left}
.pf-big .side b{display:block;font-size:30px;color:#3b719f;line-height:1.1}
.pf-big .side span{font-size:12px;color:#8a97ab;display:block;margin-bottom:14px}
.pf-li{margin-top:14px}
.pf-lr{display:flex;justify-content:space-between;gap:8px;font-size:13px;font-weight:600;color:#1f3a57}
.pf-lr span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pf-lr b{color:#3b719f;white-space:nowrap}
.pf-tr{height:6px;border-radius:6px;background:#e1e9f5;margin-top:5px}
.pf-fi{height:6px;border-radius:6px;background:linear-gradient(90deg,#6d8fb6,#3b719f)}
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
            f'<defs><linearGradient id="sp{u}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6d8fb6" '
            f'stop-opacity=".25"/><stop offset="1" stop-color="#6d8fb6" stop-opacity="0"/></linearGradient></defs>'
            f'<polygon points="2,{h} {d} {w-2},{h}" fill="url(#sp{u})"/>'
            f'<polyline points="{d}" fill="none" stroke="#6d8fb6" stroke-width="2.2" stroke-linejoin="round" '
            f'stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')


def _donut(pct, legenda, c1="#6d8fb6", c2="#3b719f"):
    pct = max(0.0, min(100.0, pct))
    r = 42
    circ = 2 * 3.14159265 * r
    u = next(_uid)
    return (f'<div class="pf-don"><svg viewBox="0 0 110 110" width="120" height="120">'
            f'<defs><linearGradient id="dn{u}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/>'
            f'<stop offset="1" stop-color="{c2}"/></linearGradient></defs>'
            f'<circle cx="55" cy="55" r="{r}" fill="none" stroke="#dbe5f3" stroke-width="9"/>'
            f'<circle cx="55" cy="55" r="{r}" fill="none" stroke="url(#dn{u})" stroke-width="9" stroke-linecap="round" '
            f'stroke-dasharray="{circ * pct / 100:.1f} {circ:.1f}" transform="rotate(-90 55 55)"/>'
            f'<text x="55" y="62" text-anchor="middle" font-size="22" font-weight="700" fill="#3b719f">{pct:.0f}%</text>'
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
        f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="5" fill="#fff" stroke="#6d8fb6" stroke-width="3"/>'
        f'<text x="{X(i):.1f}" y="{Y(v) - 11:.1f}" text-anchor="middle" font-size="11" font-weight="600" '
        f'fill="#3b719f">{v}</text>' for i, v in enumerate(vals))
    eixo = "".join(f'<text x="{X(i):.1f}" y="{h - 10}" text-anchor="middle" font-size="11" fill="#8a97ab">{r}</text>'
                   for i, r in enumerate(rot))
    return (f'<svg viewBox="0 0 {w} {h}" width="100%">{grade}<polyline points="{pts}" fill="none" stroke="#6d8fb6" '
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
                    f'fill="#3b719f">{v}</text>'
                  + f'<text x="{x + bw / 2:.1f}" y="{h - 12}" text-anchor="middle" font-size="11" fill="#8a97ab">{r}</text>')
    return (f'<svg viewBox="0 0 {w} {h}" width="100%"><defs><linearGradient id="br{u}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#6d8fb6"/><stop offset="1" stop-color="#3b719f"/></linearGradient></defs>'
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
    if df is None or df.empty:
        return df
    nomes = df[col].map(_norm)
    return df[~nomes.apply(lambda n: any(i in n for i in CLIENTES_IGNORADOS))]


def dados_conserto(rep, coletas, hoje):
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
    ctrl = df_controle(valores)
    fat = ctrl[(ctrl["NF"] != "") & (~ctrl["Operação"].str.lower().str.contains("cancel"))].copy()
    fat = fat[(fat["Data Solic."] >= pd.Timestamp("2024-01-01")) & (fat["Data Solic."] <= hoje + pd.Timedelta(days=31))]
    fat["mes"] = fat["Data Solic."].dt.to_period("M")
    return fat


def montar_dashboard(pend, r2, fat, sel, hoje):
    total = len(pend)
    atras = int(pend["Atrasado"].sum())
    conc = r2[r2["coletado"]]

    media = conc["dias"].mean() if len(conc) else None
    serie = conc.groupby(conc["coleta"].dt.to_period("M"))["dias"].mean().tail(8).tolist()
    k1 = (f'<div class="pf-card"><div class="pf-t">Liberação → Coleta</div>'
          f'<div class="pf-v">{_fmt1(media) + " dias" if media is not None else "—"}</div>'
          f'<div class="pf-s">Média de dias entre a emissão da NF de retorno e a coleta</div>{_spark(serie)}</div>')

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

    fc = fat[~fat["Cliente"].isin(["", "-"])]
    rank = fc.groupby("Cliente").size().sort_values(ascending=False).head(5)
    if len(rank):
        top_n, top_q = rank.index[0], int(rank.iloc[0])
    else:
        top_n, top_q = "—", 0
    k3 = (f'<div class="pf-card"><div class="pf-t">Maior reincidência</div><div class="pf-v">{top_q}x</div>'
          f'<div class="pf-s" style="font-weight:600;color:#1f3a57">{esc(top_n)}</div>'
          f'<div class="pf-s">Vezes faturadas para o mesmo cliente</div></div>')

    k4 = (f'<div class="pf-card pf-blue"><div class="pf-t">Pendentes de coleta</div>'
          f'<div class="pf-duo"><div><b>{total}</b><span>Total</span></div>'
          f'<div><b>{atras}</b><span>Atrasados (&gt; {PRAZO_ALERTA} dias)</span></div></div></div>')

    pct_atr = atras / total * 100 if total else 0
    pct_col = len(conc) / len(r2) * 100 if len(r2) else 0
    donuts = (_donut(pct_atr, "Pendentes de coleta em atraso")
              + _donut(pct_col, "NFs de retorno já coletadas", "#6d8fb6", "#3b719f"))

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

    ordem = ["Hoje", "1-2 dias", "3-5 dias", "6-10 dias", "+10 dias"]
    fx = pend["Faixa"].astype(str).value_counts().reindex(ordem, fill_value=0)
    barras = (f'<div class="pf-card"><div class="pf-t">Idade dos pendentes</div>'
              f'<div class="pf-s">Casos pendentes por faixa de prazo</div>{_barras(ordem, fx.tolist())}</div>')

    afet = (r2.groupby("Cliente")["dias"].mean().sort_values(ascending=False).head(5))
    afet_l = [(c, v) for c, v in afet.items() if c]
    l1 = (f'<div class="pf-card"><div class="pf-t">Clientes mais afetados por prazos longos</div>'
          f'<div class="pf-s">Média de dias da liberação até a coleta (inclui casos ainda aguardando, contados até hoje)</div>'
          f'{_lista(afet_l, lambda v: f"{v:.0f} dias")}</div>')

    l2 = (f'<div class="pf-card"><div class="pf-t">Maior reincidência de clientes</div>'
          f'<div class="pf-s">Quantidade de vezes faturadas por cliente (histórico completo)</div>'
          f'{_lista([(c, int(v)) for c, v in rank.items()], lambda v: f"{v}x")}</div>')

    html_all = (CSS_DASH + f'<div class="pf-grid pf-r1">{k1}{k2}{k3}{k4}</div>'
                f'<div class="pf-grid pf-r2"><div class="pf-card">{donuts}</div>{grande}</div>'
                f'<div class="pf-grid pf-r3">{barras}{l1}{l2}</div>')
    return "\n".join(l.strip() for l in html_all.splitlines() if l.strip())


if pagina == "dashboard":
    with st.container():
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

# ================= 4. CONSERTO / REPARO =================
if pagina == "conserto":
    try:
        rep = df_conserto(ler_valores(ABA_CONSERTO))
    except Exception as e:
        st.error(f"Não consegui ler a aba '{ABA_CONSERTO}'. Confira o nome da aba na planilha.")
        st.caption(str(e))
        st.stop()

    r_sel = None
    _, mid4, _ = st.columns([1, 2, 1])
    with mid4:
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
                    r_sel = achou.loc[opcoes[escolha]]
                else:
                    r_sel = achou.iloc[0]

    if r_sel is not None:
        info = status_conserto(r_sel, mapa_coletas(todos_dados))
        st.markdown(html_detalhes_conserto(r_sel, info), unsafe_allow_html=True)

st.markdown("<br><hr><div style='text-align: center; color: #6b7a90; font-size: 13px;'>Pioneers of Flow · Desenvolvido por Diego Elvis</div>", unsafe_allow_html=True)
