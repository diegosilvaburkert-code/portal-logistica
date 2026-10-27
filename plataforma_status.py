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
LINK_PLANILHA = "https://google.com"
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
            background-color: #eaeeff; 
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
            background: linear-gradient(90deg, #7c93fb, #4f67e8);
            padding: 25px;
            border-radius: 10px;
            color: white;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
