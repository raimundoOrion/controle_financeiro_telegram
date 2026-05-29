import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "financeiro.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tipo TEXT NOT NULL CHECK(tipo IN ('receita','despesa')),
                valor REAL NOT NULL,
                categoria TEXT NOT NULL,
                descricao TEXT,
                data TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                categoria TEXT NOT NULL,
                limite REAL NOT NULL,
                mes TEXT NOT NULL,
                UNIQUE(user_id, categoria, mes)
            )
            """
        )


def adicionar_transacao(user_id: int, tipo: str, valor: float, categoria: str, descricao: str = ""):
    data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO transacoes (user_id, tipo, valor, categoria, descricao, data) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, tipo, valor, categoria, descricao, data),
        )


def saldo(user_id: int) -> float:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(CASE WHEN tipo='receita' THEN valor ELSE 0 END),0) AS receitas,
                COALESCE(SUM(CASE WHEN tipo='despesa' THEN valor ELSE 0 END),0) AS despesas
            FROM transacoes WHERE user_id=?
            """,
            (user_id,),
        ).fetchone()
    return float(row["receitas"] - row["despesas"])


def resumo_mes(user_id: int, mes: str):
    with get_conn() as conn:
        totais = conn.execute(
            """
            SELECT tipo, COALESCE(SUM(valor),0) AS total
            FROM transacoes
            WHERE user_id=? AND strftime('%Y-%m', data)=?
            GROUP BY tipo
            """,
            (user_id, mes),
        ).fetchall()
        categorias = conn.execute(
            """
            SELECT categoria, COALESCE(SUM(valor),0) AS total
            FROM transacoes
            WHERE user_id=? AND tipo='despesa' AND strftime('%Y-%m', data)=?
            GROUP BY categoria
            ORDER BY total DESC
            """,
            (user_id, mes),
        ).fetchall()
    receitas = sum(float(r["total"]) for r in totais if r["tipo"] == "receita")
    despesas = sum(float(r["total"]) for r in totais if r["tipo"] == "despesa")
    return receitas, despesas, categorias


def listar_transacoes(user_id: int, limite: int = 10):
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT * FROM transacoes
            WHERE user_id=?
            ORDER BY data DESC
            LIMIT ?
            """,
            (user_id, limite),
        ).fetchall()


def definir_meta(user_id: int, categoria: str, limite: float, mes: str):
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO metas (user_id, categoria, limite, mes)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, categoria, mes)
            DO UPDATE SET limite=excluded.limite
            """,
            (user_id, categoria, limite, mes),
        )


def gasto_categoria_mes(user_id: int, categoria: str, mes: str) -> float:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(valor),0) AS total
            FROM transacoes
            WHERE user_id=? AND tipo='despesa' AND categoria=? AND strftime('%Y-%m', data)=?
            """,
            (user_id, categoria, mes),
        ).fetchone()
    return float(row["total"])
