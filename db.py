"""Consulta de indicadores de vendas no MySQL."""
import ssl

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


COLUNAS = (
    "consultor", "unidade", "loja", "marca", "gerente", "mes", "mes_label",
    "passagens", "refil_diant", "refil_tras", "aproveitamento",
    "total_diant", "total_tras", "total_geral",
)
CONSULTA = "SELECT " + ", ".join(COLUNAS) + " FROM vw_base_tidy"


@st.cache_resource
def get_engine():
    cfg = st.secrets["mysql"]
    url = URL.create(
        "mysql+pymysql", username=cfg["user"], password=cfg["password"],
        host=cfg["host"], port=int(cfg["port"]), database=cfg["database"],
        query={"charset": "utf8mb4"},
    )
    contexto = ssl.create_default_context()
    if cfg.get("ssl_ca_pem"):
        contexto.load_verify_locations(cadata=cfg["ssl_ca_pem"])
    elif cfg.get("ssl_ca"):
        contexto.load_verify_locations(cafile=cfg["ssl_ca"])
    return create_engine(
        url, pool_pre_ping=True, pool_recycle=300,
        connect_args={"ssl": contexto, "connect_timeout": 10, "read_timeout": 30},
    )


@st.cache_data(ttl=60)
def ler_base_tidy():
    with get_engine().connect() as conn:
        conn.execute(text("START TRANSACTION READ ONLY"))
        df = pd.read_sql(text(CONSULTA), conn)
    df = df.loc[:, list(COLUNAS)].copy()
    df["mes"] = pd.to_datetime(df["mes"])
    for coluna in COLUNAS[7:]:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
    return df
