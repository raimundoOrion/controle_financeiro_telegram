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
    
def criar_tabela_cartoes():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS cartoes (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    nome TEXT NOT NULL,
                    vencimento INTEGER NOT NULL,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        conn.commit()


def adicionar_cartao(user_id: int, nome: str, vencimento: int):
    criar_tabela_cartoes()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cartoes (user_id, nome, vencimento)
                VALUES (%s, %s, %s)
                """,
                (user_id, nome, vencimento),
            )
        conn.commit()


def listar_cartoes(user_id: int):
    criar_tabela_cartoes()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, nome, vencimento
                FROM cartoes
                WHERE user_id=%s
                ORDER BY nome
                """,
                (user_id,),
            )
            return cur.fetchall()


def excluir_cartao_db(user_id: int, cartao_id: int) -> bool:
    criar_tabela_cartoes()

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM cartoes
                WHERE user_id=%s AND id=%s
                """,
                (user_id, cartao_id),
            )
            apagou = cur.rowcount > 0
        conn.commit()

    return apagou

def criar_tabela_parcelamentos():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS parcelamentos (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    descricao TEXT NOT NULL,
                    valor_total NUMERIC(12,2) NOT NULL,
                    quantidade_parcelas INTEGER NOT NULL,
                    valor_parcela NUMERIC(12,2) NOT NULL,
                    cartao_id INTEGER,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS parcelas (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    parcelamento_id INTEGER NOT NULL,
                    numero_parcela INTEGER NOT NULL,
                    valor NUMERIC(12,2) NOT NULL,
                    vencimento DATE NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pendente'
                )
                """
            )
        conn.commit()


def buscar_cartao_por_nome(user_id: int, nome: str):
    criar_tabela_cartoes()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, nome, vencimento
                FROM cartoes
                WHERE user_id=%s AND LOWER(nome)=LOWER(%s)
                LIMIT 1
                """,
                (user_id, nome),
            )
            return cur.fetchone()


def adicionar_parcelamento(user_id: int, descricao: str, valor_total: float, quantidade: int, cartao_nome: str):
    criar_tabela_parcelamentos()

    cartao = buscar_cartao_por_nome(user_id, cartao_nome)

    if not cartao:
        return None

    valor_parcela = round(valor_total / quantidade, 2)

    from datetime import date
    import calendar

    hoje = date.today()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO parcelamentos
                (user_id, descricao, valor_total, quantidade_parcelas, valor_parcela, cartao_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, descricao, valor_total, quantidade, valor_parcela, cartao["id"]),
            )

            parcelamento_id = cur.fetchone()["id"]

            for i in range(1, quantidade + 1):
                mes = hoje.month + i - 1
                ano = hoje.year + (mes - 1) // 12
                mes = ((mes - 1) % 12) + 1

                ultimo_dia = calendar.monthrange(ano, mes)[1]
                dia_vencimento = min(cartao["vencimento"], ultimo_dia)

                vencimento = date(ano, mes, dia_vencimento)

                cur.execute(
                    """
                    INSERT INTO parcelas
                    (user_id, parcelamento_id, numero_parcela, valor, vencimento)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, parcelamento_id, i, valor_parcela, vencimento),
                )

        conn.commit()

    return {
        "id": parcelamento_id,
        "descricao": descricao,
        "valor_total": valor_total,
        "quantidade": quantidade,
        "valor_parcela": valor_parcela,
        "cartao": cartao["nome"],
    }


def listar_parcelas_futuras(user_id: int, limite: int = 20):
    criar_tabela_parcelamentos()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    p.id,
                    p.numero_parcela,
                    p.valor,
                    p.vencimento,
                    p.status,
                    pa.descricao,
                    pa.quantidade_parcelas
                FROM parcelas p
                JOIN parcelamentos pa ON pa.id = p.parcelamento_id
                WHERE p.user_id=%s
                ORDER BY p.vencimento ASC
                LIMIT %s
                """,
                (user_id, limite),
            )
            return cur.fetchall()
        
def criar_tabela_emprestimos():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS emprestimos (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    tipo TEXT NOT NULL,
                    descricao TEXT NOT NULL,
                    valor_total NUMERIC(12,2) NOT NULL,
                    quantidade_parcelas INTEGER NOT NULL,
                    valor_parcela NUMERIC(12,2) NOT NULL,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS parcelas_emprestimos (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    emprestimo_id INTEGER NOT NULL,
                    numero_parcela INTEGER NOT NULL,
                    valor NUMERIC(12,2) NOT NULL,
                    vencimento DATE NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pendente'
                )
                """
            )
        conn.commit()


def adicionar_emprestimo(user_id: int, tipo: str, descricao: str, valor_total: float, quantidade: int):
    criar_tabela_emprestimos()

    valor_parcela = round(valor_total / quantidade, 2)

    from datetime import date
    import calendar

    hoje = date.today()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO emprestimos
                (user_id, tipo, descricao, valor_total, quantidade_parcelas, valor_parcela)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, tipo, descricao, valor_total, quantidade, valor_parcela),
            )

            emprestimo_id = cur.fetchone()["id"]

            for i in range(1, quantidade + 1):
                mes = hoje.month + i - 1
                ano = hoje.year + (mes - 1) // 12
                mes = ((mes - 1) % 12) + 1

                ultimo_dia = calendar.monthrange(ano, mes)[1]
                dia_vencimento = min(hoje.day, ultimo_dia)

                vencimento = date(ano, mes, dia_vencimento)

                cur.execute(
                    """
                    INSERT INTO parcelas_emprestimos
                    (user_id, emprestimo_id, numero_parcela, valor, vencimento)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user_id, emprestimo_id, i, valor_parcela, vencimento),
                )

        conn.commit()

    return {
        "id": emprestimo_id,
        "tipo": tipo,
        "descricao": descricao,
        "valor_total": valor_total,
        "quantidade": quantidade,
        "valor_parcela": valor_parcela,
    }

def listar_compromissos_futuros(user_id: int, limite: int = 30):
    criar_tabela_parcelamentos()
    criar_tabela_emprestimos()

    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    'Cartão' AS origem,
                    p.vencimento,
                    pa.descricao,
                    p.numero_parcela,
                    pa.quantidade_parcelas,
                    p.valor,
                    p.status
                FROM parcelas p
                JOIN parcelamentos pa ON pa.id = p.parcelamento_id
                WHERE p.user_id=%s

                UNION ALL

                SELECT
                    e.tipo AS origem,
                    pe.vencimento,
                    e.descricao,
                    pe.numero_parcela,
                    e.quantidade_parcelas,
                    pe.valor,
                    pe.status
                FROM parcelas_emprestimos pe
                JOIN emprestimos e ON e.id = pe.emprestimo_id
                WHERE pe.user_id=%s

                ORDER BY vencimento ASC
                LIMIT %s
                """,
                (user_id, user_id, limite),
            )
            return cur.fetchall()