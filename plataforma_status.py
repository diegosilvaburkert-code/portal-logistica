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

# --- CONFIGURAÇÃO DA GOOGLE SHEET ---
LINK_PLANILHA = "https://google.com/spreadsheets/d/1cYhrFo_JVrTqtaxHXqiKc_gOl-En0FEYfpVs-58e9S0/edit?gid=0#gid=0"
NOME_DA_ABA = "controle"
ABA_PENDENTES = "Pendentes (FUP)"
ABA_CONSERTO = "Retorno Conserto"  # nome exato da aba de reparos na planilha
CLIENTES_IGNORADOS = ["burkert"]  # clientes excluídos do Dashboard (parte do nome, sem acento/maiúscula)
PRAZO_ALERTA = 3  # dias sem coleta a partir dos quais o caso é considerado atrasado

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
            --azul: #7c93fb;
            --azul-esc: #4f67e8;
            --rosa: #f06aa8;
        }}
        .stApp {{
            background: linear-gradient(135deg, #f0f3ff 0%, #e3e9fd 100%);
        }}
        header[data-testid="stHeader"] {{
            background: transparent !important;
        }}
        .block-container {{
            padding-top: 1.6rem;
            max-width: 1500px;
        }}
        .header-banner {{
            background: linear-gradient(110deg, #8aa0ff, #4f67e8);
            border-radius: 22px;
            padding: 28px;
            box-shadow: 0 14px 32px rgba(79, 103, 232, .30);
            margin-bottom: 25px;
        }}
        .header-banner h1 {{
            color: white !important;
            font-size: 24px !important;
            margin: 0 !important;
            letter-spacing: 1px;
            font-weight: 700;
            text-align: center !important;
        }}
        .header-banner p {{
            margin: 5px 0 0 0 !important;
            font-size: 14px;
            opacity: 0.9;
            text-align: center !important;
        }}

        /* CENTRALIZAÇÃO GLOBAL DE TEXTOS E ELEMENTOS */
        .stApp h2, .stApp h
