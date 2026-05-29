from pathlib import Path
from datetime import datetime
import pandas as pd
from .database import get_conn

BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)


def exportar_excel(user_id: int) -> Path:
    arquivo = EXPORT_DIR / f"controle_financeiro_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with get_conn() as conn:
        df = pd.read_sql_query(
            "SELECT tipo, valor, categoria, descricao, data FROM transacoes WHERE user_id=? ORDER BY data DESC",
            conn,
            params=(user_id,),
        )

    if df.empty:
        df = pd.DataFrame(columns=["tipo", "valor", "categoria", "descricao", "data"])

    resumo = pd.DataFrame({
        "Indicador": ["Receitas", "Despesas", "Saldo"],
        "Valor": [
            df.loc[df["tipo"] == "receita", "valor"].sum(),
            df.loc[df["tipo"] == "despesa", "valor"].sum(),
            df.loc[df["tipo"] == "receita", "valor"].sum() - df.loc[df["tipo"] == "despesa", "valor"].sum(),
        ],
    })

    por_categoria = (
        df[df["tipo"] == "despesa"]
        .groupby("categoria", as_index=False)["valor"]
        .sum()
        .sort_values("valor", ascending=False)
        if not df.empty else pd.DataFrame(columns=["categoria", "valor"])
    )

    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Transacoes")
        resumo.to_excel(writer, index=False, sheet_name="Resumo")
        por_categoria.to_excel(writer, index=False, sheet_name="Categorias")

    return arquivo
