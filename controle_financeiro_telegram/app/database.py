import os
from datetime import datetime
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras


DATABASE_URL = os.getenv("DATABASE_URL")


def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL não configurada no Render.")

    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS transacoes (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    tipo TEXT NOT NULL CHECK(tipo IN ('receita','despesa')),
                    valor NUMERIC(12,2) NOT NULL,
                    categoria TEXT NOT NULL,
                    descricao TEXT,
                    data TIMESTAMP NOT NULL
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS metas (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    categoria TEXT NOT NULL,
                    limite NUMERIC(12,2) NOT NULL,
                    mes TEXT NOT NULL,
                    UNIQUE(user_id, categoria, mes)
                )
                """
            )

        conn.commit()


def adicionar_transacao(user_id: int, tipo: str, valor: float, categoria: str, descricao: str = ""):
    data = datetime.now()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO transacoes (user_id, tipo, valor, categoria, descricao, data)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (user_id, tipo, valor, categoria, descricao, data),
            )
        conn.commit()


def saldo(user_id: int) -> float:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN tipo='receita' THEN valor ELSE 0 END),0) AS receitas,
                    COALESCE(SUM(CASE WHEN tipo='despesa' THEN valor ELSE 0 END),0) AS despesas
                FROM transacoes
                WHERE user_id=%s
                """,
                (user_id,),
            )
            row = cur.fetchone()

    return float(row["receitas"] - row["despesas"])


def resumo_mes(user_id: int, mes: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT tipo, COALESCE(SUM(valor),0) AS total
                FROM transacoes
                WHERE user_id=%s AND TO_CHAR(data, 'YYYY-MM')=%s
                GROUP BY tipo
                """,
                (user_id, mes),
            )
            totais = cur.fetchall()

            cur.execute(
                """
                SELECT categoria, COALESCE(SUM(valor),0) AS total
                FROM transacoes
                WHERE user_id=%s
                  AND tipo='despesa'
                  AND TO_CHAR(data, 'YYYY-MM')=%s
                GROUP BY categoria
                ORDER BY total DESC
                """,
                (user_id, mes),
            )
            categorias = cur.fetchall()

    receitas = sum(float(r["total"]) for r in totais if r["tipo"] == "receita")
    despesas = sum(float(r["total"]) for r in totais if r["tipo"] == "despesa")

    return receitas, despesas, categorias


def listar_transacoes(user_id: int, limite: int = 10):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT *
                FROM transacoes
                WHERE user_id=%s
                ORDER BY data DESC
                LIMIT %s
                """,
                (user_id, limite),
            )
            return cur.fetchall()


def definir_meta(user_id: int, categoria: str, limite: float, mes: str):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO metas (user_id, categoria, limite, mes)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, categoria, mes)
                DO UPDATE SET limite=EXCLUDED.limite
                """,
                (user_id, categoria, limite, mes),
            )
        conn.commit()


def gasto_categoria_mes(user_id: int, categoria: str, mes: str) -> float:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(valor),0) AS total
                FROM transacoes
                WHERE user_id=%s
                  AND tipo='despesa'
                  AND categoria=%s
                  AND TO_CHAR(data, 'YYYY-MM')=%s
                """,
                (user_id, categoria, mes),
            )
            row = cur.fetchone()

    return float(row["total"])


def zerar_dados_usuario(user_id: int):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM transacoes WHERE user_id=%s",
                (user_id,),
            )
            cur.execute(
                "DELETE FROM metas WHERE user_id=%s",
                (user_id,),
            )
        conn.commit()


def despesas_por_categoria_mes(user_id: int, mes: str):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT categoria, COALESCE(SUM(valor),0) AS total
                FROM transacoes
                WHERE user_id=%s
                  AND tipo='despesa'
                  AND TO_CHAR(data, 'YYYY-MM')=%s
                GROUP BY categoria
                ORDER BY total DESC
                """,
                (user_id, mes),
            )
            return cur.fetchall()


def listar_ultimos_lancamentos(user_id: int, limite: int = 10):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, tipo, valor, categoria, descricao, data
                FROM transacoes
                WHERE user_id=%s
                ORDER BY id DESC
                LIMIT %s
                """,
                (user_id, limite),
            )
            return cur.fetchall()


def excluir_lancamento(user_id: int, transacao_id: int) -> bool:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM transacoes
                WHERE user_id=%s AND id=%s
                """,
                (user_id, transacao_id),
            )
            apagou = cur.rowcount > 0

        conn.commit()

    return apagou

def editar_lancamento(user_id: int, transacao_id: int, valor: float, descricao: str = None):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if descricao:
                cur.execute(
                    """
                    UPDATE transacoes
                    SET valor=%s, descricao=%s
                    WHERE user_id=%s AND id=%s
                    """,
                    (valor, descricao, user_id, transacao_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE transacoes
                    SET valor=%s
                    WHERE user_id=%s AND id=%s
                    """,
                    (valor, user_id, transacao_id),
                )

            atualizado = cur.rowcount > 0

        conn.commit()

    return atualizado

def dashboard_mes(user_id: int, mes: str):
    receitas, despesas, categorias = resumo_mes(user_id, mes)

    saldo_atual = receitas - despesas

    if receitas > 0:
        percentual_gasto = (despesas / receitas) * 100
        percentual_economia = (saldo_atual / receitas) * 100
    else:
        percentual_gasto = 0
        percentual_economia = 0

    return {
        "receitas": receitas,
        "despesas": despesas,
        "saldo": saldo_atual,
        "gastos": percentual_gasto,
        "economia": percentual_economia,
        "categorias": categorias[:5]
    }