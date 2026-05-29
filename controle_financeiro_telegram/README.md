# Controle Financeiro no Telegram

Projeto inicial de bot para controle financeiro pessoal via Telegram.

## Funcionalidades

- Cadastro de receitas
- Cadastro de despesas
- Categorização automática simples
- Consulta de saldo
- Extrato das últimas transações
- Relatório mensal
- Meta por categoria
- Exportação para Excel
- Banco de dados SQLite

## Comandos do Bot

```text
/start
/receita 1500 Salário
/despesa 120 Mercado
/saldo
/extrato
/relatorio
/meta Alimentação 800
/exportar
```

## Como criar o Bot no Telegram

1. Abra o Telegram.
2. Pesquise por `BotFather`.
3. Envie o comando:

```text
/newbot
```

4. Defina o nome do bot.
5. Defina o usuário do bot, terminando com `bot`, por exemplo:

```text
meu_controle_financeiro_bot
```

6. Copie o token gerado.

## Como instalar no computador

Entre na pasta do projeto e execute:

```bash
python -m venv venv
```

Ative o ambiente virtual:

### Windows

```bash
venv\Scripts\activate
```

### Linux/Mac

```bash
source venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Crie o arquivo `.env` com base no `.env.example`:

```env
TELEGRAM_BOT_TOKEN=COLE_AQUI_O_TOKEN_DO_SEU_BOT
```

Execute o bot:

```bash
python main.py
```

## Estrutura do Projeto

```text
controle_financeiro_telegram/
├── app/
│   ├── bot.py
│   ├── database.py
│   └── reports.py
├── data/
│   └── financeiro.db
├── exports/
├── .env.example
├── main.py
├── requirements.txt
└── README.md
```

## Próximas melhorias sugeridas

- Cadastro de cartão de crédito
- Controle por conta bancária
- Parcelamento de despesas
- Dashboard web
- Relatório em PDF
- Backup automático
- Integração com Google Sheets
- Multiusuário com grupos ou família
