"""Dashboard de desempenho Dahruj."""
import datetime as dt
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import db
from relatorios import gerar_excel_ranking, gerar_excel_semanal, gerar_excel_consultor
from indicadores import agg_by, last_n_months, mlabel, MESES_PT

st.set_page_config(page_title="Dahruj — Refis para Palhetas",
                   page_icon="📊", layout="wide")

ORANGE = "#EB5E33"
BRANCO = "#F5F5F5"
ASSETS = Path(__file__).resolve().parent / "assets"
PALETTE = ["#EB5E33", "#F5A623", "#FF8A5B", "#F58220", "#FFFFFF",
           "#C0C0C0", "#B5451F", "#8A8A8A", "#FFB07C", "#E0E0E0"]
PAG_DASHBOARD = "Dashboard"
PAG_GERENTE = "Relatório Por Gerente"
PAG_CONSULTOR = "Relatório Por Consultor"

from indicadores import _relatorio_semana, _relatorio_consultor

def _injetar_css():
    """Aplica a identidade PRETO/LARANJA/BRANCO (60/30/10) sobre o tema escuro."""
    st.markdown(f"""
        <style>
        /* Títulos e cabeçalhos em laranja (acento de marca) */
        h1, h2, h3 {{ color: {ORANGE} !important; }}
        /* Cartões de KPI: fundo escuro com acento laranja à esquerda */
        div[data-testid="stMetric"] {{
            background: #1A1A1A; border-left: 5px solid {ORANGE};
            border-radius: 8px; padding: 14px 16px; }}
        div[data-testid="stMetricValue"] {{ color: {BRANCO}; }}
        /* Sidebar mais escura, com borda laranja sutil */
        section[data-testid="stSidebar"] {{
            background: #0A0A0A; border-right: 1px solid rgba(235,94,51,.35); }}
        /* Divisores em laranja translúcido */
        hr {{ border-color: rgba(235,94,51,.45) !important; }}
        /* Item de menu (radio) selecionado destacado em laranja */
        section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {{
            color: {ORANGE}; font-weight: 700; }}
        </style>
    """, unsafe_allow_html=True)


def _achar_logo():
    for ext in ("png", "jpg", "jpeg", "webp", "gif"):
        p = ASSETS / f"logo.{ext}"
        if p.exists():
            return p
    return None


def mostrar_logo():
    """Exibe a logo grande no topo da barra lateral — canto superior esquerdo,
    presente em todas as páginas. Sem arquivo, cai para o texto 'DAHRUJ'.
    """
    logo = _achar_logo()
    if logo:
        st.sidebar.image(str(logo), width="stretch")
    else:
        st.sidebar.markdown(
            f'<div style="font-family:\'Arial Black\',Arial,sans-serif;'
            f'font-weight:900;font-size:30px;letter-spacing:2px;color:{ORANGE};'
            f'border:3px solid {ORANGE};border-radius:8px;padding:2px 12px;'
            f'display:inline-block;margin-bottom:6px;">DAHRUJ</div>',
            unsafe_allow_html=True)


def fmt_money(v):
    if v is None or pd.isna(v):
        return "—"
    return ("R$ {:,.2f}".format(v)).replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_int(v):
    if v is None or pd.isna(v):
        return "—"
    return "{:,.0f}".format(v).replace(",", ".")


def fmt_pct(v):
    if v is None or pd.isna(v):
        return "—"
    return ("{:.1f}%".format(v * 100)).replace(".", ",")


def delta_str(v, kind):
    if v is None or pd.isna(v):
        return None
    sign = "+" if v >= 0 else "-"
    a = abs(v)
    if kind == "money":
        body = fmt_money(a)
    elif kind == "int":
        body = fmt_int(a)
    else:  # pp (pontos percentuais)
        body = "{:.1f}".format(a * 100).replace(".", ",") + " p.p."
    return f"{sign}{body}"


def label_mes(d):
    """Rótulo do mês (ex.: 'Junho/2026')."""
    nomes = ["", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    return f"{nomes[d.month]}/{d.year}"


def pagina_dashboard():
    st.title("📊 Análise de Vendas — Dahruj")
    try:
        df = db.ler_base_tidy()
    except Exception:
        st.error("Não foi possível conectar ao banco de dados no momento. "
                 "Verifique se o MySQL está ativo e tente novamente.")
        return

    if df.empty:
        st.info("Ainda não há lançamentos no banco. Procure o gestor responsável "
                "pelo lançamento dos dados.")
        return

    # ---- Seleção do mês de referência (menu suspenso) ----
    meses_disp = sorted(df["mes"].dropna().unique())
    lbl_to_mes = {mlabel(m): m for m in meses_disp}
    labels_mes = [mlabel(m) for m in reversed(meses_disp)]  # mais recente primeiro
    csel, _ = st.columns([2, 3])
    mes_sel_lbl = csel.selectbox(
        "📅 Mês de referência", labels_mes, index=0,
        help="Escolha o mês para ver os KPIs. Os gráficos mostram o trimestre "
             "móvel encerrado no mês selecionado.")
    mes_sel = lbl_to_mes[mes_sel_lbl]

    win, keep = last_n_months(df, mes_fim=mes_sel)
    ordem_meses = [mlabel(m) for m in sorted(keep)]
    periodo = " · ".join(ordem_meses)
    st.caption(f"Acompanhamento trimestral móvel · {periodo}")

    # ---- Filtros (sidebar) ----
    st.sidebar.header("Filtros")
    st.sidebar.caption(f"Trimestre vigente: **{periodo}**")
    marcas = sorted(win["marca"].dropna().unique())
    sel_marcas = st.sidebar.multiselect("Marca", marcas, default=[])

    base_uni = win[win["marca"].isin(sel_marcas)] if sel_marcas else win
    unidades = sorted(base_uni["unidade"].dropna().unique())
    sel_unidades = st.sidebar.multiselect("Unidade", unidades, default=[])

    base_cons = win.copy()
    if sel_marcas:
        base_cons = base_cons[base_cons["marca"].isin(sel_marcas)]
    if sel_unidades:
        base_cons = base_cons[base_cons["unidade"].isin(sel_unidades)]
    consultores = sorted(base_cons["consultor"].dropna().unique())
    sel_cons = st.sidebar.multiselect("Consultor", consultores, default=[])
    st.sidebar.divider()
    st.sidebar.caption("Sem consultor selecionado, mostra o agregado do filtro. "
                       "Selecionando consultores, cada um vira uma linha.")

    f = win.copy()
    if sel_marcas:
        f = f[f["marca"].isin(sel_marcas)]
    if sel_unidades:
        f = f[f["unidade"].isin(sel_unidades)]
    if sel_cons:
        f = f[f["consultor"].isin(sel_cons)]

    if f.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    # ---- Exportar relatório (reflete os filtros atuais) ----
    partes = []
    if sel_marcas:
        partes.append("Marcas: " + ", ".join(sel_marcas))
    if sel_unidades:
        partes.append("Unidades: " + ", ".join(sel_unidades))
    if sel_cons:
        partes.append("Consultores: " + ", ".join(sel_cons))
    filtros_txt = " · ".join(partes) if partes else "Todos"
    _, colexp = st.columns([3, 1])
    colexp.download_button(
        "📥 Exportar relatório (Excel)",
        data=gerar_excel_ranking(f, periodo, filtros_txt),
        file_name=f"Ranking_Dahruj_{dt.date.today().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    # ---- KPI cards ----
    mensal = agg_by(f, "mes").sort_values("mes")
    mensal["mes_lbl"] = mensal["mes"].apply(mlabel)
    atual = mensal.iloc[-1]
    ant = mensal.iloc[-2] if len(mensal) > 1 else None

    def d(col, kind):
        return delta_str(atual[col] - ant[col], kind) if ant is not None else None

    r1 = st.columns(3)
    r1[0].metric(f"Passagens ({mes_sel_lbl})", fmt_int(atual["passagens"]), d("passagens", "int"))
    r1[1].metric(f"Nº Refil Diant. ({mes_sel_lbl})", fmt_int(atual["refil_diant"]),
                 d("refil_diant", "int"))
    r1[2].metric(f"Aproveitamento Diant. ({mes_sel_lbl})", fmt_pct(atual["aproveitamento"]),
                 d("aproveitamento", "pp"))
    r2 = st.columns(3)
    r2[0].metric(f"Faturamento total ({mes_sel_lbl})", fmt_money(atual["total_geral"]),
                 d("total_geral", "money"))
    r2[1].metric(f"Nº Refil Tras. ({mes_sel_lbl})", fmt_int(atual["refil_tras"]),
                 d("refil_tras", "int"))
    r2[2].metric(f"Aproveitamento Tras. ({mes_sel_lbl})", fmt_pct(atual["aproveitamento_tras"]),
                 d("aproveitamento_tras", "pp"))
    st.caption("Variação comparada ao mês imediatamente anterior dentro da janela.")
    st.divider()

    # ---- Evolução ----
    st.subheader("Evolução no trimestre")
    by_cons = bool(sel_cons)
    if by_cons:
        evo = agg_by(f, ["mes", "consultor"]).sort_values("mes")
        evo["mes_lbl"] = evo["mes"].apply(mlabel)
        color = "consultor"
    else:
        evo = mensal.copy()
        evo["consultor"] = "Agregado"
        color = None

    def line_fig(dfp, ycol, titulo, fmt):
        fig = px.line(dfp, x="mes_lbl", y=ycol, color=color, markers=True,
                      color_discrete_sequence=PALETTE,
                      category_orders={"mes_lbl": ordem_meses})
        fig.update_traces(hovertemplate="%{x}<br>" + fmt + "<extra>%{fullData.name}</extra>")
        fig.update_layout(title=titulo, template="plotly_dark", height=300,
                          margin=dict(l=10, r=10, t=50, b=10),
                          xaxis_title=None, yaxis_title=None,
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color=BRANCO,
                          legend=dict(orientation="h", y=-0.2, title=None))
        # Piso do eixo Y por métrica (em vez de começar no zero): dá zoom o
        # suficiente para ver a variação, sem exagerar as quedas. O piso só vale
        # quando os dados estão acima dele — no modo por consultor, com valores
        # menores, o eixo volta a se ajustar sozinho (não corta as linhas).
        pisos = {"passagens": 1500, "refil_diant": 350,
                 "aproveitamento": 0.10, "total_geral": 80000}
        piso = pisos.get(ycol)
        ymax = dfp[ycol].max()
        if piso is not None and pd.notna(ymax) and ymax > piso:
            fig.update_yaxes(range=[piso, ymax * 1.05])
        else:
            fig.update_yaxes(rangemode="tozero")
        if ycol == "aproveitamento":
            fig.update_yaxes(tickformat=".0%")
        return fig

    r1c1, r1c2 = st.columns(2)
    r1c1.plotly_chart(line_fig(evo, "passagens", "Passagens", "%{y:,.0f}"),
                      use_container_width=True)
    r1c2.plotly_chart(line_fig(evo, "refil_diant", "Nº Refil Dianteiro", "%{y:,.0f}"),
                      use_container_width=True)
    r2c1, r2c2 = st.columns(2)
    r2c1.plotly_chart(line_fig(evo, "aproveitamento", "Aproveitamento", "%{y:.1%}"),
                      use_container_width=True)
    r2c2.plotly_chart(line_fig(evo, "total_geral", "Faturamento (R$)", "R$ %{y:,.2f}"),
                      use_container_width=True)
    st.divider()

    # ---- Por unidade (aproveitamento ou faturamento) ----
    ctit, cord = st.columns([3, 1])
    ord_uni = cord.radio("Ordenar por", ["Aproveitamento", "Faturamento"],
                         key="ord_unidade")
    por_fat = ord_uni == "Faturamento"
    ctit.subheader("Faturamento por unidade" if por_fat else "Aproveitamento por unidade")
    ctit.caption("Faturamento total por unidade, somado no trimestre." if por_fat
                 else "Taxa de conversão (refil dianteiro ÷ passagens) por unidade, "
                      "somada no trimestre.")
    apu = agg_by(f, "unidade")
    if por_fat:
        apu = apu.sort_values("total_geral")
        xcol = "total_geral"
        txt = apu["total_geral"].map(fmt_money)
        htmpl, xfmt = "%{y}<br>R$ %{x:,.2f}<extra></extra>", None
    else:
        apu = apu[apu["passagens"] > 0].sort_values("aproveitamento")
        xcol = "aproveitamento"
        txt = apu["aproveitamento"].map(fmt_pct)
        htmpl, xfmt = "%{y}<br>%{x:.1%}<extra></extra>", ".0%"
    if apu.empty:
        st.caption("Sem dados suficientes no período para montar este gráfico.")
    else:
        figu = px.bar(apu, x=xcol, y="unidade", orientation="h",
                      color_discrete_sequence=[ORANGE], text=txt)
        figu.update_traces(hovertemplate=htmpl, textposition="outside", cliponaxis=False)
        figu.update_layout(template="plotly_dark", height=max(320, 28 * len(apu)),
                           margin=dict(l=10, r=60, t=20, b=10),
                           xaxis_title=ord_uni, yaxis_title=None,
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font_color=BRANCO)
        if xfmt:
            figu.update_xaxes(tickformat=xfmt)
        st.plotly_chart(figu, use_container_width=True)
    st.divider()

    # ---- Ranking ----
    st.subheader("Ranking no trimestre")
    rk = {"Faturamento (R$)": ("total_geral", "money"),
          "Passagens": ("passagens", "int"),
          "Nº Refil Dianteiro": ("refil_diant", "int"),
          "Aproveitamento": ("aproveitamento", "pct")}
    colr1, colr2 = st.columns([2, 1])
    metrica = colr1.selectbox("Ordenar por", list(rk.keys()))
    topn = colr2.slider("Quantos exibir", 5, 65, 15)
    ycol, kind = rk[metrica]
    rank = agg_by(f, "consultor").sort_values(ycol, ascending=False).head(topn).sort_values(ycol)
    if kind == "money":
        txt = rank[ycol].map(fmt_money); htmpl = "R$ %{x:,.2f}<extra></extra>"; xfmt = None
    elif kind == "pct":
        txt = rank[ycol].map(fmt_pct); htmpl = "%{x:.1%}<extra></extra>"; xfmt = ".0%"
    else:
        txt = rank[ycol].map(fmt_int); htmpl = "%{x:,.0f}<extra></extra>"; xfmt = None
    figr = px.bar(rank, x=ycol, y="consultor", orientation="h",
                  color_discrete_sequence=[ORANGE], text=txt)
    figr.update_traces(hovertemplate=htmpl, textposition="outside", cliponaxis=False)
    figr.update_layout(template="plotly_dark", height=max(340, 26 * len(rank)),
                       margin=dict(l=10, r=40, t=20, b=10),
                       xaxis_title=metrica, yaxis_title=None,
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font_color=BRANCO)
    if xfmt:
        figr.update_xaxes(tickformat=xfmt)
    st.plotly_chart(figr, use_container_width=True)
    st.divider()

    # ---- Tabela detalhada ----
    with st.expander("Ver dados detalhados (filtro aplicado)"):
        show = f[["consultor", "unidade", "mes_label", "passagens", "refil_diant",
                  "refil_tras", "aproveitamento", "total_diant", "total_tras",
                  "total_geral"]].copy()
        show = show.rename(columns={
            "consultor": "Consultor", "unidade": "Unidade", "mes_label": "Mês",
            "passagens": "Passagens", "refil_diant": "Refil Diant.",
            "refil_tras": "Refil Tras.", "aproveitamento": "Aproveitamento",
            "total_diant": "Total Diant.", "total_tras": "Total Tras.",
            "total_geral": "Total Geral"})
        st.dataframe(show, use_container_width=True, hide_index=True,
                     column_config={
                         "Aproveitamento": st.column_config.NumberColumn(format="%.1f%%"),
                         "Total Diant.": st.column_config.NumberColumn(format="R$ %.2f"),
                         "Total Tras.": st.column_config.NumberColumn(format="R$ %.2f"),
                         "Total Geral": st.column_config.NumberColumn(format="R$ %.2f")})


def pagina_relatorio_semanal():
    st.title("📅 Relatório por Gerente")
    st.caption("Ranking das unidades no mês, no formato do relatório da diretoria.")
    try:
        df = db.ler_base_tidy()
    except Exception:
        st.error("Não foi possível conectar ao banco de dados no momento. "
                 "Verifique se o MySQL está ativo e tente novamente.")
        return
    if df.empty or df["mes"].dropna().empty:
        st.info("Ainda não há lançamentos no banco.")
        return

    meses = sorted(df["mes"].dropna().unique(), reverse=True)
    mes_por_label = {label_mes(pd.Timestamp(s).date()): s for s in meses}
    c1, c2 = st.columns([2, 1])
    label_sel = c1.selectbox("Mês", list(mes_por_label.keys()))
    ordenar = c2.radio("Ordenar por", ["Faturamento", "Aproveitamento"], horizontal=True)
    mes_sel = mes_por_label[label_sel]

    g, ov = _relatorio_semana(df, mes_sel)
    if g.empty:
        st.warning("Sem dados neste mês.")
        return
    ordcol = "total_geral" if ordenar == "Faturamento" else "aprov_d"
    g = g.sort_values(ordcol, ascending=False).reset_index(drop=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Passagens", fmt_int(ov["passagens"]))
    k2.metric("Refil Diant.", fmt_int(ov["refil_diant"]))
    k3.metric("Aproveitamento", fmt_pct(ov["aprov_d"]))
    k4.metric("Faturamento total", fmt_money(ov["total_geral"]))

    _, cexp = st.columns([3, 1])
    cexp.download_button(
        "📥 Exportar relatório (Excel)",
        data=gerar_excel_semanal(g, ov, label_sel, ordenar),
        file_name=f"Relatorio_Semanal_Dahruj_{pd.Timestamp(mes_sel).date().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    linhas = []
    for i, (_, r) in enumerate(g.iterrows(), 1):
        linhas.append({
            "Seq": str(i), "Gerente": r["gerente"], "Marca": r["marca"], "Loja": r["loja"],
            "Passagens": fmt_int(r["passagens"]), "Refil Diant.": fmt_int(r["refil_diant"]),
            "% Aprov (D)": fmt_pct(r["aprov_d"]), "Total Diant.": fmt_money(r["total_diant"]),
            "Refil Tras.": fmt_int(r["refil_tras"]), "% Aprov (T)": fmt_pct(r["aprov_t"]),
            "Total Tras.": fmt_money(r["total_tras"]), "Total Geral": fmt_money(r["total_geral"]),
            "Part %": fmt_pct(r["part"]),
        })
    linhas.append({
        "Seq": "", "Gerente": "TOTAL", "Marca": "", "Loja": "",
        "Passagens": fmt_int(ov["passagens"]), "Refil Diant.": fmt_int(ov["refil_diant"]),
        "% Aprov (D)": fmt_pct(ov["aprov_d"]), "Total Diant.": fmt_money(ov["total_diant"]),
        "Refil Tras.": fmt_int(ov["refil_tras"]), "% Aprov (T)": fmt_pct(ov["aprov_t"]),
        "Total Tras.": fmt_money(ov["total_tras"]), "Total Geral": fmt_money(ov["total_geral"]),
        "Part %": "100,0%",
    })
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
    st.caption("Part % = participação da unidade no faturamento total do mês.")

def pagina_relatorio_consultor():
    st.title("🧑‍💼 Relatório por Consultor")
    st.caption("Ranking dos consultores no mês.")
    try:
        df = db.ler_base_tidy()
    except Exception:
        st.error("Não foi possível conectar ao banco de dados no momento. "
                 "Verifique se o MySQL está ativo e tente novamente.")
        return
    if df.empty or df["mes"].dropna().empty:
        st.info("Ainda não há lançamentos no banco.")
        return

    meses = sorted(df["mes"].dropna().unique(), reverse=True)
    mes_por_label = {label_mes(pd.Timestamp(s).date()): s for s in meses}
    TODAS = "Todas as unidades"
    unidades = [TODAS] + sorted(df["unidade"].dropna().unique())
    c1, c2, c3 = st.columns([2, 2, 1])
    label_sel = c1.selectbox("Mês", list(mes_por_label.keys()))
    unidade_sel = c2.selectbox("Unidade", unidades)
    ordenar = c3.radio("Ordenar por", ["Faturamento", "Aproveitamento"], horizontal=True)
    mes_sel = mes_por_label[label_sel]

    if unidade_sel != TODAS:
        df = df[df["unidade"] == unidade_sel]
    if df[df["mes"] == mes_sel].empty:
        st.warning("Sem dados para esta unidade neste mês.")
        return
    g, ov = _relatorio_consultor(df, mes_sel)
    if g.empty:
        st.warning("Sem dados neste mês.")
        return
    ordcol = "total_geral" if ordenar == "Faturamento" else "aprov_d"
    g = g.sort_values(ordcol, ascending=False).reset_index(drop=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Passagens", fmt_int(ov["passagens"]))
    k2.metric("Refil Diant.", fmt_int(ov["refil_diant"]))
    k3.metric("Aproveitamento", fmt_pct(ov["aprov_d"]))
    k4.metric("Faturamento total", fmt_money(ov["total_geral"]))

    _, cexp = st.columns([3, 1])
    cexp.download_button(
        "📥 Exportar relatório (Excel)",
        data=gerar_excel_consultor(g, ov, label_sel, ordenar),
        file_name=f"Relatorio_Consultor_Dahruj_{pd.Timestamp(mes_sel).date().isoformat()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    linhas = []
    for i, (_, r) in enumerate(g.iterrows(), 1):
        linhas.append({
            "Seq": str(i), "Consultor": r["consultor"], "Unidade": r["unidade"],
            "Passagens": fmt_int(r["passagens"]), "Refil Diant.": fmt_int(r["refil_diant"]),
            "% Aprov (D)": fmt_pct(r["aprov_d"]), "Total Diant.": fmt_money(r["total_diant"]),
            "Refil Tras.": fmt_int(r["refil_tras"]), "% Aprov (T)": fmt_pct(r["aprov_t"]),
            "Total Tras.": fmt_money(r["total_tras"]), "Total Geral": fmt_money(r["total_geral"]),
            "Part %": fmt_pct(r["part"]),
        })
    linhas.append({
        "Seq": "", "Consultor": "TOTAL", "Unidade": "",
        "Passagens": fmt_int(ov["passagens"]), "Refil Diant.": fmt_int(ov["refil_diant"]),
        "% Aprov (D)": fmt_pct(ov["aprov_d"]), "Total Diant.": fmt_money(ov["total_diant"]),
        "Refil Tras.": fmt_int(ov["refil_tras"]), "% Aprov (T)": fmt_pct(ov["aprov_t"]),
        "Total Tras.": fmt_money(ov["total_tras"]), "Total Geral": fmt_money(ov["total_geral"]),
        "Part %": "100,0%",
    })
    st.dataframe(pd.DataFrame(linhas), use_container_width=True, hide_index=True)
    st.caption("Part % = participação do consultor no faturamento total do mês.")

_injetar_css()
mostrar_logo()
st.sidebar.title("Dahruj")
DESTINOS = {
    PAG_DASHBOARD: pagina_dashboard,
    PAG_GERENTE: pagina_relatorio_semanal,
    PAG_CONSULTOR: pagina_relatorio_consultor,
}
if st.session_state.get("menu_pagina", PAG_DASHBOARD) not in DESTINOS:
    st.session_state["menu_pagina"] = PAG_DASHBOARD
pagina = st.sidebar.radio("Menu", list(DESTINOS), key="menu_pagina")
st.sidebar.divider()

st.session_state["_ultima_renderizacao"] = time.monotonic()

@st.fragment(run_every=60)
def acompanhar_atualizacoes():
    if time.monotonic() - st.session_state["_ultima_renderizacao"] >= 60:
        db.ler_base_tidy.clear()
        st.rerun()

acompanhar_atualizacoes()
DESTINOS[pagina]()
