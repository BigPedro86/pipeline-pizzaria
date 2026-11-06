"""Painel de vendas da pizzaria (Streamlit), lendo só a camada gold.

Uso: streamlit run painel/app.py
"""

import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

# permite "from src..." quando rodado com streamlit run
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.leitura_gold import formatar_moeda, formatar_numero, gold_disponivel, ler_gold  # noqa: E402

COR = "#2a78d6"  # uma série por gráfico -> uma cor só, sem legenda
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def barras(df: pd.DataFrame, x: str, y: str, titulo_x: str, titulo_y: str,
           horizontal: bool = False, ordem: list | str | None = None) -> alt.Chart:
    """Gráfico de barras de uma série, com tooltip e pontas arredondadas."""
    eixo_cat = alt.X if not horizontal else alt.Y
    eixo_val = alt.Y if not horizontal else alt.X
    canto = {"cornerRadiusTopLeft": 4, "cornerRadiusTopRight": 4} if not horizontal \
        else {"cornerRadiusTopRight": 4, "cornerRadiusBottomRight": 4}
    return (
        alt.Chart(df)
        .mark_bar(color=COR, **canto)
        .encode(
            eixo_cat(f"{x}:N", title=titulo_x, sort=ordem),
            eixo_val(f"{y}:Q", title=titulo_y),
            tooltip=[alt.Tooltip(f"{x}:N", title=titulo_x),
                     alt.Tooltip(f"{y}:Q", title=titulo_y, format=",.2f")],
        )
    )


def secao_resumo() -> None:
    """Cartões com os números do ano."""
    r = ler_gold("resumo_geral").iloc[0]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Faturamento 2015", formatar_moeda(r.faturamento))
    c2.metric("Pedidos", formatar_numero(r.pedidos))
    c3.metric("Ticket médio", formatar_moeda(r.ticket_medio))
    c4.metric("Pizzas por pedido", formatar_numero(r.pizzas_por_pedido, 2))


def secao_mensal() -> None:
    """Linha do faturamento mês a mês."""
    df = ler_gold("vendas_mensais")
    df["mes_nome"] = [MESES[m.month - 1] for m in pd.to_datetime(df.mes)]
    st.subheader("Faturamento mensal")
    linha = (
        alt.Chart(df)
        .mark_line(color=COR, strokeWidth=2, point=alt.OverlayMarkDef(color=COR, size=64))
        .encode(
            alt.X("mes_nome:N", title="Mês", sort=MESES),
            alt.Y("faturamento:Q", title="Faturamento ($)", scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip("mes_nome:N", title="Mês"),
                     alt.Tooltip("faturamento:Q", title="Faturamento ($)", format=",.2f"),
                     alt.Tooltip("pedidos:Q", title="Pedidos", format=","),
                     alt.Tooltip("ticket_medio:Q", title="Ticket médio ($)", format=",.2f")],
        )
    )
    st.altair_chart(linha, width="stretch")
    with st.expander("Ver tabela"):
        st.dataframe(df.drop(columns="mes_nome"), hide_index=True)


def secao_categoria_tamanho() -> None:
    """Barras de faturamento por categoria e por tamanho, lado a lado."""
    cat, tam = ler_gold("vendas_por_categoria"), ler_gold("vendas_por_tamanho")
    esq, dir_ = st.columns(2)
    with esq:
        st.subheader("Por categoria")
        st.altair_chart(barras(cat, "categoria", "faturamento", "Categoria", "Faturamento ($)",
                               horizontal=True, ordem="-x"), width="stretch")
        with st.expander("Ver tabela"):
            st.dataframe(cat, hide_index=True)
    with dir_:
        st.subheader("Por tamanho")
        st.altair_chart(barras(tam, "tamanho", "faturamento", "Tamanho", "Faturamento ($)",
                               ordem=list(tam.tamanho)), width="stretch")
        with st.expander("Ver tabela"):
            st.dataframe(tam, hide_index=True)


def secao_ranking() -> None:
    """Top 5 e bottom 5 de pizzas pela métrica escolhida."""
    df = ler_gold("ranking_pizzas")
    st.subheader("Ranking de pizzas")
    metrica = st.radio("Ordenar por", ["faturamento", "pizzas_vendidas"], horizontal=True,
                       format_func=lambda m: "Faturamento ($)" if m == "faturamento" else "Unidades vendidas")
    titulo = "Faturamento ($)" if metrica == "faturamento" else "Unidades"
    ordenado = df.sort_values(metrica, ascending=False)
    esq, dir_ = st.columns(2)
    with esq:
        st.markdown("**5 que mais vendem**")
        st.altair_chart(barras(ordenado.head(5), "nome_pizza", metrica, "Pizza", titulo,
                               horizontal=True, ordem="-x"), width="stretch")
    with dir_:
        st.markdown("**5 que menos vendem**")
        st.altair_chart(barras(ordenado.tail(5), "nome_pizza", metrica, "Pizza", titulo,
                               horizontal=True, ordem="x"), width="stretch")
    with st.expander("Ver as 32 pizzas"):
        st.dataframe(ordenado, hide_index=True)


def secao_picos() -> None:
    """Pedidos por hora do dia e média por dia da semana."""
    hora, dia = ler_gold("pedidos_por_hora"), ler_gold("pedidos_por_dia_semana")
    hora["hora_txt"] = hora.hora.map(lambda h: f"{h}h")
    esq, dir_ = st.columns(2)
    with esq:
        st.subheader("Pedidos por hora")
        st.altair_chart(barras(hora, "hora_txt", "pedidos", "Hora", "Pedidos no ano",
                               ordem=list(hora.hora_txt)), width="stretch")
        with st.expander("Ver tabela"):
            st.dataframe(hora.drop(columns="hora_txt"), hide_index=True)
    with dir_:
        st.subheader("Média de pedidos por dia da semana")
        st.altair_chart(barras(dia, "dia_semana", "media_pedidos_por_dia", "Dia",
                               "Pedidos por dia (média)", ordem=list(dia.dia_semana)),
                        width="stretch")
        with st.expander("Ver tabela"):
            st.dataframe(dia, hide_index=True)


def main() -> None:
    """Monta a página."""
    st.set_page_config(page_title="Pizzaria – Vendas 2015", page_icon="🍕", layout="wide")
    st.title("Vendas da pizzaria – 2015")
    st.caption("Fonte: camada gold do pipeline (Pizza Place Sales, Kaggle, CC0). Valores em dólar.")
    if not gold_disponivel():
        st.error("A camada gold ainda não foi gerada. Rode antes: `python -m src.pipeline`")
        st.stop()
    secao_resumo()
    secao_mensal()
    secao_categoria_tamanho()
    secao_ranking()
    secao_picos()


main()
