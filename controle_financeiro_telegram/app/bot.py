import os
import re
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
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
    listar_ultimos_lancamentos,
    excluir_lancamento,
    editar_lancamento,
    dashboard_mes,
    adicionar_cartao,
    listar_cartoes,
    excluir_cartao_db,
    adicionar_parcelamento,
    listar_parcelas_futuras,
    adicionar_emprestimo,
    listar_compromissos_futuros,
    
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
        "Alimentação": [
            "mercado", "supermercado", "atacadão", "assai", "extra", "carrefour",
            "restaurante", "lanche", "ifood", "padaria", "almoço", "jantar",
            "pizza", "hamburguer", "comida", "açougue", "hortifruti"
        ],
        "Combustível": [
            "gasolina", "etanol", "diesel", "posto", "combustível", "abasteci",
            "abastecimento"
        ],
        "Transporte": [
            "uber", "99", "ônibus", "metro", "metrô", "estacionamento",
            "pedágio", "pedagio", "taxi", "táxi"
        ],
        "Moradia": [
            "aluguel", "condomínio", "condominio", "energia", "luz", "água",
            "agua", "internet", "gás", "gas", "iptu"
        ],
        "Saúde": [
            "farmácia", "farmacia", "remédio", "remedio", "médico", "medico",
            "consulta", "exame", "dentista", "hospital", "plano de saúde"
        ],
        "Educação": [
            "escola", "faculdade", "curso", "livro", "material escolar",
            "mensalidade", "aula"
        ],
        "Lazer": [
            "cinema", "show", "bar", "viagem", "passeio", "hotel",
            "netflix", "spotify", "amazon prime", "disney", "streaming"
        ],
        "Cartão de Crédito": [
            "cartão", "cartao", "fatura", "nubank", "inter", "c6", "itaucard"
        ],
        "Salário": [
            "salário", "salario", "pagamento", "ordenado"
        ],
        "Recebimentos": [
            "pix", "transferência", "transferencia", "recebi", "entrada",
            "depósito", "deposito"
        ],
        "Investimentos": [
            "investimento", "aplicação", "aplicacao", "tesouro", "cdb",
            "ações", "acoes", "fii", "renda fixa"
        ],
        "Manutenção": [
            "manutenção", "manutencao", "oficina", "mecânico", "mecanico",
            "peça", "peca", "conserto", "reparo"
        ],
        "Vestuário": [
            "roupa", "calçado", "calcado", "sapato", "camisa", "bermuda",
            "tenis", "tênis"
        ],
        "Outros": []
    }

    for categoria, palavras in regras.items():
        if any(palavra in d for palavra in palavras):
            return categoria

    return "Outros"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teclado = [
    ["➕ Receita", "➖ Despesa"],
    ["💰 Saldo", "📊 Relatório"],
    ["📈 Dashboard", "📈 Gráfico"],
    ["📋 Extrato", "📁 Exportar Excel"],
    ["💳 Cartões", "📆 Parcelas"],
    ["🏦 Banco/Empréstimo", "📆 Compromissos"]
    ["🎯 Meta", "✏️ Corrigir Lançamento"],
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
        
    elif texto == "📈 Gráfico":
        await grafico(update, context)
    
    elif texto == "✏️ Corrigir Lançamento":
        await ultimos(update, context)    
        
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
        
    elif texto == "✏️ Corrigir Lançamento":
        await update.message.reply_text(
            "Para corrigir um lançamento:\n\n"
            "1. Veja os últimos lançamentos:\n"
            "/ultimos\n\n"
            "2. Edite pelo ID:\n"
            "/editar ID VALOR\n\n"
            "Exemplo:\n"
            "/editar 25 150 Gasolina"
        )
        
    elif texto == "💳 Cartões":
        await cartoes(update, context)
    
    elif texto == "📆 Parcelas":
        await parcelas(update, context)
        
    elif texto == "📈 Dashboard":
        await dashboard(update, context)
        
    elif texto == "🏦 Banco/Empréstimo":
        await update.message.reply_text(
            "Comandos disponíveis:\n\n"
            "/emprestimo Banco 50000 48\n"
            "/financiamento Ranger 60000 48"
    )

    elif texto == "📆 Compromissos":
        await compromissos(update, context)

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

async def erro_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"ERRO NO BOT: {context.error}")
    
async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        mes = datetime.now().strftime("%Y-%m")

        dados = despesas_por_categoria_mes(user_id, mes)

        if not dados:
            await update.message.reply_text(
                "Ainda não existem despesas neste mês para gerar gráfico."
            )
            return

        categorias = [item["categoria"] for item in dados]
        valores = [float(item["total"]) for item in dados]

        texto_categorias = ",".join(categorias)
        texto_valores = ",".join([str(v) for v in valores])

        url = (
            "https://quickchart.io/chart?"
            "c={type:'bar',data:{labels:["
            + ",".join([f"'{c}'" for c in categorias])
            + "],datasets:[{label:'Despesas',data:["
            + ",".join([str(v) for v in valores])
            + "]}]}}"
        )

        await update.message.reply_photo(
            photo=url,
            caption=f"📊 Despesas por categoria - {mes}"
        )

    except Exception as e:
        await update.message.reply_text(
            f"Erro ao gerar gráfico:\n{type(e).__name__}: {e}"
        )
        
async def ultimos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    itens = listar_ultimos_lancamentos(user_id, 10)

    if not itens:
        await update.message.reply_text("Nenhum lançamento encontrado.")
        return

    texto = "📋 Últimos lançamentos:\n\n"

    for item in itens:
        sinal = "+" if item["tipo"] == "receita" else "-"
        texto += (
            f"ID {item['id']} | {sinal} {moeda(item['valor'])} | "
            f"{item['categoria']} | {item['descricao']}\n"
        )

    texto += "\nPara excluir, use:\n/excluir ID"

    await update.message.reply_text(texto)


async def excluir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 1:
        await update.message.reply_text("Use assim:\n/excluir 15")
        return

    try:
        transacao_id = int(context.args[0])
        ok = excluir_lancamento(user_id, transacao_id)

        if ok:
            await update.message.reply_text(
                f"🗑️ Lançamento ID {transacao_id} excluído com sucesso."
            )
        else:
            await update.message.reply_text(
                "Não encontrei esse lançamento para excluir."
            )

    except ValueError:
        await update.message.reply_text("ID inválido. Exemplo:\n/excluir 15")
        
async def editar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 2:
        await update.message.reply_text(
            "Use assim:\n"
            "/editar ID VALOR\n\n"
            "Exemplo:\n"
            "/editar 25 150\n"
            "/editar 25 150 Gasolina"
        )
        return

    try:
        transacao_id = int(context.args[0])
        valor = parse_valor(context.args[1])
        descricao = " ".join(context.args[2:]) if len(context.args) > 2 else None

        ok = editar_lancamento(user_id, transacao_id, valor, descricao)

        if ok:
            await update.message.reply_text(
                f"✏️ Lançamento ID {transacao_id} atualizado com sucesso.\n"
                f"Novo valor: {moeda(valor)}"
            )
        else:
            await update.message.reply_text(
                "Não encontrei esse lançamento para editar."
            )

    except ValueError:
        await update.message.reply_text(
            "Valor ou ID inválido.\n"
            "Exemplo correto:\n"
            "/editar 25 150"
        )
        
async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    mes = datetime.now().strftime("%Y-%m")

    dados = dashboard_mes(user_id, mes)

    texto = (
        "📊 Dashboard Financeiro\n\n"
        f"💰 Receitas: {moeda(dados['receitas'])}\n"
        f"💸 Despesas: {moeda(dados['despesas'])}\n"
        f"🟢 Saldo: {moeda(dados['saldo'])}\n\n"
        f"📉 Taxa de gastos: {dados['gastos']:.1f}%\n"
        f"💵 Taxa de economia: {dados['economia']:.1f}%\n\n"
    )

    if dados["categorias"]:
        texto += "🏆 Top Gastos\n\n"

        medalhas = ["🥇", "🥈", "🥉", "🏅", "🏅"]

        for i, cat in enumerate(dados["categorias"]):
            texto += (
                f"{medalhas[i]} "
                f"{cat['categoria']}: "
                f"{moeda(cat['total'])}\n"
            )

    await update.message.reply_text(texto)
    
async def cartao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 2:
        await update.message.reply_text(
            "Use assim:\n"
            "/cartao NOME DIA_VENCIMENTO\n\n"
            "Exemplo:\n"
            "/cartao Nubank 10"
        )
        return

    try:
        nome = context.args[0]
        vencimento = int(context.args[1])

        if vencimento < 1 or vencimento > 31:
            await update.message.reply_text("O vencimento deve ser entre 1 e 31.")
            return

        adicionar_cartao(user_id, nome, vencimento)

        await update.message.reply_text(
            f"💳 Cartão cadastrado com sucesso!\n\n"
            f"Nome: {nome}\n"
            f"Vencimento: dia {vencimento}"
        )

    except ValueError:
        await update.message.reply_text(
            "Dia de vencimento inválido.\n"
            "Exemplo correto:\n/cartao Nubank 10"
        )


async def cartoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    itens = listar_cartoes(user_id)

    if not itens:
        await update.message.reply_text("Nenhum cartão cadastrado.")
        return

    texto = "💳 Cartões cadastrados:\n\n"

    for item in itens:
        texto += (
            f"ID {item['id']} | {item['nome']} | "
            f"Vencimento dia {item['vencimento']}\n"
        )

    texto += "\nPara excluir:\n/excluir_cartao ID"

    await update.message.reply_text(texto)

async def excluir_cartao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 1:
        await update.message.reply_text("Use assim:\n/excluir_cartao 1")
        return

    try:
        cartao_id = int(context.args[0])
        ok = excluir_cartao_db(user_id, cartao_id)

        if ok:
            await update.message.reply_text(
                f"🗑️ Cartão ID {cartao_id} excluído com sucesso."
            )
        else:
            await update.message.reply_text(
                "Não encontrei esse cartão para excluir."
            )

    except ValueError:
        await update.message.reply_text("ID inválido.\nExemplo:\n/excluir_cartao 1")
        
async def parcelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 4:
        await update.message.reply_text(
            "Use assim:\n"
            "/parcelar DESCRIÇÃO VALOR PARCELAS CARTÃO\n\n"
            "Exemplo:\n"
            "/parcelar TV 2400 12 Nubank\n"
            "/parcelar Geladeira 1800 10 Inter"
        )
        return

    try:
        cartao_nome = context.args[-1]
        quantidade = int(context.args[-2])
        valor_total = parse_valor(context.args[-3])
        descricao = " ".join(context.args[:-3])

        if quantidade <= 0:
            await update.message.reply_text("A quantidade de parcelas deve ser maior que zero.")
            return

        resultado = adicionar_parcelamento(
            user_id,
            descricao,
            valor_total,
            quantidade,
            cartao_nome,
        )

        if not resultado:
            await update.message.reply_text(
                "Cartão não encontrado.\n\n"
                "Cadastre primeiro com:\n"
                "/cartao Nubank 10"
            )
            return

        await update.message.reply_text(
            f"💳 Compra parcelada cadastrada!\n\n"
            f"Descrição: {resultado['descricao']}\n"
            f"Cartão: {resultado['cartao']}\n"
            f"Valor total: {moeda(resultado['valor_total'])}\n"
            f"Parcelas: {resultado['quantidade']}x de {moeda(resultado['valor_parcela'])}\n"
            f"ID: {resultado['id']}"
        )

    except ValueError:
        await update.message.reply_text(
            "Dados inválidos.\n\n"
            "Exemplo correto:\n"
            "/parcelar TV 2400 12 Nubank"
        )


async def parcelas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    itens = listar_parcelas_futuras(user_id, 20)

    if not itens:
        await update.message.reply_text("Nenhuma parcela futura encontrada.")
        return

    texto = "📆 Parcelas futuras:\n\n"

    for item in itens:
        texto += (
            f"{item['vencimento']} | "
            f"{item['descricao']} "
            f"{item['numero_parcela']}/{item['quantidade_parcelas']} | "
            f"{moeda(item['valor'])} | "
            f"{item['status']}\n"
        )

    await update.message.reply_text(texto)
    
async def emprestimo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 3:
        await update.message.reply_text(
            "Use assim:\n"
            "/emprestimo DESCRIÇÃO VALOR PARCELAS\n\n"
            "Exemplo:\n"
            "/emprestimo Banco 50000 48"
        )
        return

    try:
        quantidade = int(context.args[-1])
        valor_total = parse_valor(context.args[-2])
        descricao = " ".join(context.args[:-2])

        resultado = adicionar_emprestimo(
            user_id,
            "Empréstimo",
            descricao,
            valor_total,
            quantidade,
        )

        await update.message.reply_text(
            f"🏦 Empréstimo cadastrado!\n\n"
            f"Descrição: {resultado['descricao']}\n"
            f"Valor total: {moeda(resultado['valor_total'])}\n"
            f"Parcelas: {resultado['quantidade']}x de {moeda(resultado['valor_parcela'])}\n"
            f"ID: {resultado['id']}"
        )

    except ValueError:
        await update.message.reply_text(
            "Dados inválidos.\n\n"
            "Exemplo correto:\n"
            "/emprestimo Banco 50000 48"
        )


async def financiamento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if len(context.args) < 3:
        await update.message.reply_text(
            "Use assim:\n"
            "/financiamento DESCRIÇÃO VALOR PARCELAS\n\n"
            "Exemplo:\n"
            "/financiamento Ranger 60000 48"
        )
        return

    try:
        quantidade = int(context.args[-1])
        valor_total = parse_valor(context.args[-2])
        descricao = " ".join(context.args[:-2])

        resultado = adicionar_emprestimo(
            user_id,
            "Financiamento",
            descricao,
            valor_total,
            quantidade,
        )

        await update.message.reply_text(
            f"🚗 Financiamento cadastrado!\n\n"
            f"Descrição: {resultado['descricao']}\n"
            f"Valor total: {moeda(resultado['valor_total'])}\n"
            f"Parcelas: {resultado['quantidade']}x de {moeda(resultado['valor_parcela'])}\n"
            f"ID: {resultado['id']}"
        )

    except ValueError:
        await update.message.reply_text(
            "Dados inválidos.\n\n"
            "Exemplo correto:\n"
            "/financiamento Ranger 60000 48"
        )


async def compromissos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    itens = listar_compromissos_futuros(user_id, 30)

    if not itens:
        await update.message.reply_text("Nenhum compromisso futuro encontrado.")
        return

    texto = "📆 Compromissos futuros:\n\n"

    for item in itens:
        texto += (
            f"{item['vencimento']} | "
            f"{item['origem']} | "
            f"{item['descricao']} "
            f"{item['numero_parcela']}/{item['quantidade_parcelas']} | "
            f"{moeda(item['valor'])} | "
            f"{item['status']}\n"
        )

    await update.message.reply_text(texto)           

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
    app.add_handler(CommandHandler("grafico", grafico))
    app.add_handler(CommandHandler("ultimos", ultimos))
    app.add_handler(CommandHandler("excluir", excluir))
    app.add_handler(CommandHandler("editar", editar))
    app.add_handler(CommandHandler("dashboard", dashboard))
    app.add_handler(CommandHandler("cartao", cartao))
    app.add_handler(CommandHandler("cartoes", cartoes))
    app.add_handler(CommandHandler("excluir_cartao", excluir_cartao))
    app.add_handler(CommandHandler("parcelar", parcelar))
    app.add_handler(CommandHandler("parcelas", parcelas))
    app.add_handler(CommandHandler("emprestimo", emprestimo))
    app.add_handler(CommandHandler("financiamento", financiamento))
    app.add_handler(CommandHandler("compromissos", compromissos))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menu_botoes))

    import asyncio

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    print("BOT RODANDO - POLLING ATIVO", flush=True)

    app.run_polling(
        close_loop=False,
        drop_pending_updates=True
    )


if __name__ == "__main__":
    main()
