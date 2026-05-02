"""
Firebase — operações de ESCRITA para o bot Fernanda
-----------------------------------------------------
Adicione ao bot existente. Requer:
    pip install firebase-admin

Variáveis de ambiente necessárias no Railway:
    FIREBASE_URL=https://SEU_PROJETO-default-rtdb.firebaseio.com
    FIREBASE_CREDENTIALS=<conteúdo JSON da service account em base64 ou path>
"""

import os
import json
import time
import firebase_admin
from firebase_admin import credentials, db

# ── Inicialização ───────────────────────────────────────────────
def init_firebase():
    """Inicializa o Firebase Admin SDK (chame uma vez no início do bot)."""
    if firebase_admin._apps:
        return  # já inicializado

    # Opção A: arquivo JSON local (desenvolvimento)
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        # Opção B: JSON em variável de ambiente (Railway/produção)
        cred_json = os.getenv("FIREBASE_CREDENTIALS")
        if not cred_json:
            raise ValueError("FIREBASE_CREDENTIALS não configurado.")
        cred = credentials.Certificate(json.loads(cred_json))

    firebase_admin.initialize_app(cred, {
        "databaseURL": os.getenv("FIREBASE_URL")
    })


# ── CONVIDADOS ──────────────────────────────────────────────────

def adicionar_convidado(nome: str, grupo: str, status: str = "invited",
                         note: str = "", kids: list = None):
    """
    Adiciona um novo convidado ao Firebase.

    Exemplo pelo Telegram:
        /adicionar_convidado Nome Completo | FJH | invited | observação
    """
    ref = db.reference("convidados")
    novo_id = int(time.time() * 1000)  # timestamp como ID único

    novo = {
        "id": novo_id,
        "name": nome,
        "group": grupo,
        "status": status,
        "note": note,
        "kids": kids or [],
    }
    ref.child(str(novo_id)).set(novo)
    return novo


def atualizar_status_convidado(nome: str, novo_status: str):
    """
    Atualiza o status de um convidado pelo nome.
    Status válidos: invited, confirmed, declined, excluded
    """
    ref = db.reference("convidados")
    todos = ref.get() or {}

    for key, guest in todos.items():
        if guest.get("name", "").lower() == nome.lower():
            ref.child(key).update({"status": novo_status})
            return True, guest["name"]

    return False, None


def remover_convidado(nome: str):
    """Remove um convidado pelo nome."""
    ref = db.reference("convidados")
    todos = ref.get() or {}

    for key, guest in todos.items():
        if guest.get("name", "").lower() == nome.lower():
            ref.child(key).delete()
            return True, guest["name"]

    return False, None


# ── FORNECEDORES ────────────────────────────────────────────────

def adicionar_fornecedor(nome: str, categoria: str, valor: float,
                          contato: str = "", status: str = "contratado"):
    """Adiciona um novo fornecedor."""
    ref = db.reference("fornecedores")
    novo_id = int(time.time() * 1000)

    novo = {
        "id": novo_id,
        "nome": nome,
        "categoria": categoria,
        "valor": valor,
        "contato": contato,
        "status": status,
    }
    ref.child(str(novo_id)).set(novo)
    return novo


def atualizar_fornecedor(nome: str, campo: str, valor):
    """Atualiza um campo específico de um fornecedor."""
    ref = db.reference("fornecedores")
    todos = ref.get() or {}

    for key, f in todos.items():
        if f.get("nome", "").lower() == nome.lower():
            ref.child(key).update({campo: valor})
            return True, f["nome"]

    return False, None


# ── GASTOS / EXTRATO ────────────────────────────────────────────

def registrar_gasto(categoria: str, descricao: str, valor: float,
                     data: str = None, pago: bool = True):
    """Registra um novo gasto/pagamento."""
    from datetime import date
    ref = db.reference("gastos")
    novo_id = int(time.time() * 1000)

    novo = {
        "id": novo_id,
        "categoria": categoria,
        "descricao": descricao,
        "valor": valor,
        "data": data or date.today().strftime("%d/%m/%Y"),
        "pago": pago,
    }
    ref.child(str(novo_id)).set(novo)
    return novo


# -- RESUMO FINANCEIRO --------------------------------------------------

def resumo_financeiro():
    meta   = db.reference("config/meta").get() or 0
    gastos = db.reference("gastos").get() or {}

    ja_pago = sum(
        g.get("valor", 0) for g in gastos.values()
        if g.get("status") == "pago"
    )
    a_pagar = max(0.0, meta - ja_pago)

    def fmt(v):
        return "R$ {:,.2f}".format(v).replace(",", "X").replace(".", ",").replace("X", ".")

    linhas = [
        "*RESUMO FINANCEIRO:*\n",
        "| Status | Valor |",
        "|--------|-------|",
        "| PAGO | {} |".format(fmt(ja_pago)),
        "| A PAGAR | {} |".format(fmt(a_pagar)),
        "| TOTAL | {} |".format(fmt(meta)),
    ]

    if a_pagar <= 0:
        resumo = u"Resumindo: Voces ja pagaram tudo que foi comprometido. Nada esta pendente! v"
    else:
        resumo = "Resumindo: Faltam {} para quitar o total comprometido ({} pagos de {}).".format(
            fmt(a_pagar), fmt(ja_pago), fmt(meta)
        )

    return {
        "meta": meta, "ja_pago": ja_pago, "a_pagar": a_pagar,
        "texto": "\n".join(linhas) + "\n\n" + resumo,
    }


def handle_resumo_financeiro(bot, message):
    try:
        dados = resumo_financeiro()
        bot.reply_to(message, dados["texto"], parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, "Erro ao calcular resumo: {}".format(e))
# ── HANDLERS PARA O BOT (integração com pyTelegramBotAPI) ───────

def handle_adicionar_convidado(bot, message):
    """
    Handler para o comando /add_convidado no bot Fernanda.
    Formato: /add_convidado Nome | Grupo | status | observação
    Exemplo: /add_convidado Ana Paula | FJG | invited | prima da Júlia
    """
    try:
        partes = message.text.replace("/add_convidado", "").strip().split("|")
        nome   = partes[0].strip()
        grupo  = partes[1].strip() if len(partes) > 1 else "FJG"
        status = partes[2].strip() if len(partes) > 2 else "invited"
        note   = partes[3].strip() if len(partes) > 3 else ""

        novo = adicionar_convidado(nome, grupo, status, note)
        bot.reply_to(message,
            f"✅ *{nome}* adicionado!\n"
            f"Grupo: `{grupo}` | Status: `{status}`",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {e}\n\nFormato: /add_convidado Nome | Grupo | status | obs")


def handle_confirmar_convidado(bot, message):
    """
    Handler: /confirmar Nome
    Marca convidado como confirmado.
    """
    nome = message.text.replace("/confirmar", "").strip()
    if not nome:
        bot.reply_to(message, "Uso: /confirmar Nome do Convidado")
        return

    ok, nome_real = atualizar_status_convidado(nome, "confirmed")
    if ok:
        bot.reply_to(message, f"✅ *{nome_real}* marcado como confirmado! 🎉", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"❌ Convidado '{nome}' não encontrado.")


def handle_registrar_gasto(bot, message):
    """
    Handler: /gasto Categoria | Descrição | Valor
    Exemplo: /gasto Cerimônia | Parcela decoração | 500
    """
    try:
        partes = message.text.replace("/gasto", "").strip().split("|")
        categoria = partes[0].strip()
        descricao = partes[1].strip()
        valor     = float(partes[2].strip().replace(",", "."))

        gasto = registrar_gasto(categoria, descricao, valor)
        bot.reply_to(message,
            f"💸 Gasto registrado!\n"
            f"*{categoria}* — {descricao}\n"
            f"Valor: R$ {valor:,.2f}",
            parse_mode="Markdown"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Erro: {e}\n\nFormato: /gasto Categoria | Descrição | Valor")


# ── EXEMPLO DE INTEGRAÇÃO no bot.py existente ──────────────────
"""
Adicione no seu bot.py principal:

    from firebase_writes import (
        init_firebase,
        handle_adicionar_convidado,
        handle_confirmar_convidado,
        handle_registrar_gasto,
    )

    # Na inicialização:
    init_firebase()

    # Novos handlers:
    @bot.message_handler(commands=["add_convidado"])
    def cmd_add_convidado(message):
        handle_adicionar_convidado(bot, message)

    @bot.message_handler(commands=["confirmar"])
    def cmd_confirmar(message):
        handle_confirmar_convidado(bot, message)

    @bot.message_handler(commands=["gasto"])
    def cmd_gasto(message):
        handle_registrar_gasto(bot, message)
"""
