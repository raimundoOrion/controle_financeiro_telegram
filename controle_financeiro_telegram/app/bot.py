import os
import re
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .database import (
    init_db,
    adicionar_transacao,
    saldo,
    resumo_mes,
    listar_transacoes,
    definir_meta,
    gasto_categoria_mes,
    zerar_dados_usuario,
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
    teclado = [
        ["➕ Receita", "➖ Despesa"],
        ["💰 Saldo", "📊 Relatório"],
        ["📋 Extrato", "📁 Exportar Excel"],
        ["🎯 Meta"],
        ["🗑️ Zerar Dados"]
    ]

    menu = ReplyKeyboardMarkup(
        teclado,
        resize_keyboard=True,
        one_time_keyboard=False
    )

    texto = (
        "👋 Bem-vindo ao Controle Financeiro!\n\n"
        "Escolha uma opção no menu abaixo ou use os comandos:\n\n"
        "/receita 1500 Salário\n"
        "/despesa 120 Mercado\n"
        "/saldo\n"
        "/extrato\n"
        "/relatorio\n"
        "/meta Alimentação 800\n"
        "/exportar\n"
        "/zerar"
    )

    await update.message.reply_text(texto, reply_markup=menu)


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
    
def interpretar_lancamento(texto: str):
    texto_original = texto
    texto = texto.lower().strip()

    palavras_despesa = [
        "gastei", "paguei", "comprei", "despesa", "saída", "saida",
        "pagamento", "debito", "débito"
    ]

    palavras_receita = [
        "recebi", "ganhei", "entrou", "entrada", "receita",
        "salário", "salario", "pix recebido"
    ]

    tipo = None

    if any(p in texto for p in palavras_despesa):
        tipo = "despesa"
    elif any(p in texto for p in palavras_receita):
        tipo = "receita"

    padrao_valor = r"(\d+(?:[.,]\d{1,2})?)"
    encontrado = re.search(padrao_valor, texto)

    if not encontrado or not tipo:
        return None

    valor = parse_valor(encontrado.group(1))

    descricao = texto_original
    categoria = categoria_automatica(descricao)

    return {
        "tipo": tipo,
        "valor": valor,
        "descricao": descricao,
        "categoria": categoria
    }
    
async def menu_botoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text

    if texto == "➕ Receita":
        await update.message.reply_text("Use assim:\n/receita 1500 Salário")

    elif texto == "➖ Despesa":
        await update.message.reply_text("Use assim:\n/despesa 120 Mercado")

    elif texto == "💰 Saldo":
        await saldo_cmd(update, context)

    elif texto == "📊 Relatório":
        await relatorio(update, context)

    elif texto == "📋 Extrato":
        await extrato(update, context)

    elif texto == "📁 Exportar Excel":
        await exportar(update, context)

    elif texto == "🎯 Meta":
        await update.message.reply_text("Use assim:\n/meta Alimentação 800")
        
    elif texto == "🗑️ Zerar Dados":
        await zerar(update, context)

    elif texto == "CONFIRMAR":
        user_id = update.effective_user.id
        zerar_dados_usuario(user_id)
        await update.message.reply_text(
            "🗑️ Dados zerados com sucesso.\n\n"
            "Você pode começar novamente usando:\n"
            "/receita 1000 Salário\n"
            "/despesa 100 Mercado"
        )

    else:
        lancamento = interpretar_lancamento(texto)

        if lancamento:
            user_id = update.effective_user.id
            adicionar_transacao(
                user_id,
                lancamento["tipo"],
                lancamento["valor"],
                lancamento["categoria"],
                lancamento["descricao"]
            )

            saldo_atual = saldo(user_id)

            await update.message.reply_text(
                f"✅ Lançamento registrado automaticamente\n\n"
                f"Tipo: {lancamento['tipo'].capitalize()}\n"
                f"Valor: {moeda(lancamento['valor'])}\n"
                f"Categoria: {lancamento['categoria']}\n"
                f"Descrição: {lancamento['descricao']}\n"
                f"Saldo atual: {moeda(saldo_atual)}"
            )
        else:
            await update.message.reply_text(
                "Não entendi. Você pode usar o menu ou escrever, por exemplo:\n\n"
                "Gastei 150 no mercado\n"
                "Recebi 3000 de salário"
            )

async def zerar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚠️ Atenção!\n\n"
        "Isso apagará todas as suas receitas, despesas, metas e extratos.\n\n"
        "Para confirmar, digite:\n\n"
        "CONFIRMAR"
    )

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
    app.add_handler(CommandHandler("zerar", zerar))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_botoes))
    
    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
