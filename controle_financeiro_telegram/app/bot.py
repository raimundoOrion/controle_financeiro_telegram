import os
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from .database import (
    init_db,
    adicionar_transacao,
    saldo,
    resumo_mes,
    listar_transacoes,
    definir_meta,
    gasto_categoria_mes,
)
from .reports import exportar_excel

load_dotenv()


def moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_valor(texto: str) -> float:
    return float(texto.replace("R$", "").replace(".", "").replace(",", ".").strip())


def categoria_automatica(descricao: str) -> str:
    d = descricao.lower()
    regras = {
        "Alimentação": ["mercado", "restaurante", "lanche", "ifood", "padaria", "almoço", "jantar"],
        "Combustível": ["gasolina", "etanol", "diesel", "posto", "combustível"],
        "Moradia": ["aluguel", "condomínio", "energia", "água", "internet"],
        "Saúde": ["farmácia", "médico", "consulta", "exame"],
        "Transporte": ["uber", "99", "ônibus", "metrô", "estacionamento"],
        "Lazer": ["cinema", "show", "bar", "viagem", "passeio"],
    }
    for categoria, palavras in regras.items():
        if any(p in d for p in palavras):
            return categoria
    return "Outros"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = (
        "👋 Bem-vindo ao Controle Financeiro!\n\n"
        "Comandos disponíveis:\n"
        "/receita 1500 Salário\n"
        "/despesa 120 Mercado\n"
        "/saldo\n"
        "/extrato\n"
        "/relatorio\n"
        "/meta Alimentação 800\n"
        "/exportar\n\n"
        "Dica: use vírgula ou ponto para valores."
    )
    await update.message.reply_text(texto)


async def registrar(update: Update, context: ContextTypes.DEFAULT_TYPE, tipo: str):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text(f"Use assim: /{tipo} 120 Mercado")
        return

    try:
        valor = parse_valor(context.args[0])
        descricao = " ".join(context.args[1:])
        categoria = categoria_automatica(descricao)
        adicionar_transacao(user_id, tipo, valor, categoria, descricao)
        saldo_atual = saldo(user_id)
        resposta = (
            f"✅ {tipo.capitalize()} cadastrada\n\n"
            f"Valor: {moeda(valor)}\n"
            f"Categoria: {categoria}\n"
            f"Descrição: {descricao}\n"
            f"Saldo atual: {moeda(saldo_atual)}"
        )
        await update.message.reply_text(resposta)
    except ValueError:
        await update.message.reply_text("Valor inválido. Exemplo correto: /despesa 89,90 Mercado")


async def receita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await registrar(update, context, "receita")


async def despesa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await registrar(update, context, "despesa")


async def saldo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(f"💰 Saldo atual: {moeda(saldo(user_id))}")


async def extrato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    linhas = listar_transacoes(user_id, 10)
    if not linhas:
        await update.message.reply_text("Nenhuma transação cadastrada ainda.")
        return
    texto = "📋 Últimas transações:\n\n"
    for item in linhas:
        sinal = "+" if item["tipo"] == "receita" else "-"
        texto += f"{sinal} {moeda(item['valor'])} | {item['categoria']} | {item['descricao']} | {item['data']}\n"
    await update.message.reply_text(texto)


async def relatorio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mes = datetime.now().strftime("%Y-%m")
    receitas, despesas, categorias = resumo_mes(user_id, mes)
    texto = (
        f"📊 Relatório do mês {mes}\n\n"
        f"Receitas: {moeda(receitas)}\n"
        f"Despesas: {moeda(despesas)}\n"
        f"Saldo do mês: {moeda(receitas - despesas)}\n\n"
        "Despesas por categoria:\n"
    )
    if categorias:
        for c in categorias:
            texto += f"• {c['categoria']}: {moeda(c['total'])}\n"
    else:
        texto += "Sem despesas no mês."
    await update.message.reply_text(texto)


async def meta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("Use assim: /meta Alimentação 800")
        return
    categoria = context.args[0]
    try:
        limite = parse_valor(context.args[1])
        mes = datetime.now().strftime("%Y-%m")
        definir_meta(user_id, categoria, limite, mes)
        gasto = gasto_categoria_mes(user_id, categoria, mes)
        await update.message.reply_text(
            f"🎯 Meta definida para {categoria}: {moeda(limite)}\n"
            f"Gasto atual no mês: {moeda(gasto)}"
        )
    except ValueError:
        await update.message.reply_text("Valor inválido. Exemplo: /meta Alimentação 800")


async def exportar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    arquivo = exportar_excel(user_id)
    await update.message.reply_document(document=open(arquivo, "rb"), filename=arquivo.name)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Configure o TELEGRAM_BOT_TOKEN no arquivo .env")

    init_db()
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("receita", receita))
    app.add_handler(CommandHandler("despesa", despesa))
    app.add_handler(CommandHandler("saldo", saldo_cmd))
    app.add_handler(CommandHandler("extrato", extrato))
    app.add_handler(CommandHandler("relatorio", relatorio))
    app.add_handler(CommandHandler("meta", meta))
    app.add_handler(CommandHandler("exportar", exportar))
    app.run_polling()


if __name__ == "__main__":
    main()
