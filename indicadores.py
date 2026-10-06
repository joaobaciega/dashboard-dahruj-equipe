"""Indicadores de desempenho e agregações."""
import pandas as pd

N_MESES = 3
MESES_PT = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']

def mlabel(d):
    d = pd.Timestamp(d)
    return f"{MESES_PT[d.month][:3]}/{d.year}"


def last_n_months(df, n=N_MESES, mes_fim=None):
    """Janela dos n meses que TERMINAM em `mes_fim` (trimestre móvel). Sem
    `mes_fim`, usa o mês mais recente da base."""
    meses = sorted(df["mes"].unique())
    if mes_fim is not None and mes_fim in meses:
        idx = meses.index(mes_fim)
        keep = meses[max(0, idx - n + 1): idx + 1]
    else:
        keep = meses[-n:]
    return df[df["mes"].isin(keep)].copy(), keep


def agg_by(df, group):
    """Agrega os KPIs. O aproveitamento é SEMPRE recalculado como
    soma(refil_diant) / soma(passagens) — nunca média de percentuais. Para a
    conversão, conta apenas refis de linhas que também têm passagens informadas,
    evitando inflar a taxa com linhas incompletas. O aproveitamento traseiro
    (refil_tras / passagens) é calculado com o mesmo critério."""
    df = df.copy()
    df["_refil_conv"] = df["refil_diant"].where(df["passagens"].notna())
    df["_refil_conv_t"] = df["refil_tras"].where(df["passagens"].notna())
    g = df.groupby(group, as_index=False).agg(
        passagens=("passagens", "sum"),
        refil_diant=("refil_diant", "sum"),
        refil_tras=("refil_tras", "sum"),
        total_diant=("total_diant", "sum"),
        total_tras=("total_tras", "sum"),
        total_geral=("total_geral", "sum"),
        _refil_conv=("_refil_conv", "sum"),
        _refil_conv_t=("_refil_conv_t", "sum"),
    )
    g["aproveitamento"] = (g["_refil_conv"] / g["passagens"]).where(g["passagens"] > 0)
    g["aproveitamento_tras"] = (g["_refil_conv_t"] / g["passagens"]).where(g["passagens"] > 0)
    return g.drop(columns=["_refil_conv", "_refil_conv_t"])


def _relatorio_semana(df, mes_sel):
    """Monta o ranking por gerente/unidade de um mês + a linha de totais."""
    sem = df[df["mes"] == mes_sel].copy()
    sem["gerente"] = sem["gerente"].fillna("(sem gerente)")
    g = agg_by(sem, ["unidade", "gerente", "loja", "marca"])
    g["aprov_d"] = (g["refil_diant"] / g["passagens"]).where(g["passagens"] > 0)
    g["aprov_t"] = (g["refil_tras"] / g["passagens"]).where(g["passagens"] > 0)
    tot_fat = g["total_geral"].sum()
    g["part"] = (g["total_geral"] / tot_fat) if tot_fat else 0.0
    ov = agg_by(sem.assign(_g=1), "_g").iloc[0].to_dict()
    p = ov["passagens"]
    ov["aprov_d"] = (ov["refil_diant"] / p) if (p and p > 0) else None
    ov["aprov_t"] = (ov["refil_tras"] / p) if (p and p > 0) else None
    return g, ov



def _relatorio_consultor(df, mes_sel):
    """Monta o ranking por consultor/unidade de um mês + a linha de totais."""
    sem = df[df["mes"] == mes_sel].copy()
    g = agg_by(sem, ["consultor", "unidade"])
    g["aprov_d"] = (g["refil_diant"] / g["passagens"]).where(g["passagens"] > 0)
    g["aprov_t"] = (g["refil_tras"] / g["passagens"]).where(g["passagens"] > 0)
    tot_fat = g["total_geral"].sum()
    g["part"] = (g["total_geral"] / tot_fat) if tot_fat else 0.0
    ov = agg_by(sem.assign(_g=1), "_g").iloc[0].to_dict()
    p = ov["passagens"]
    ov["aprov_d"] = (ov["refil_diant"] / p) if (p and p > 0) else None
    ov["aprov_t"] = (ov["refil_tras"] / p) if (p and p > 0) else None
    return g, ov



