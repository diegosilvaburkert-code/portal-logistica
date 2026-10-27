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
              + _donut(pct_col, "NFs de retorno já coletadas", "#ff9ac8", "#f06aa8"))

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

# ================= 4. CONSERTO / REPARO (consulta por NF + timeline) =================
if pagina == "conserto":
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
                st.markdown(html_detalhes_conserto(r, info), unsafe_allow_html=True)

st.markdown("Desenvolvido por Diego Elvis | Versão R.2.0 de 10.26", unsafe_allow_html=True)
