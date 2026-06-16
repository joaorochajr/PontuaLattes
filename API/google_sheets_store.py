# pyright: reportMissingImports=false
"""
Módulo de persistência no Google Sheets para backup do banco Turso.

Variáveis de ambiente necessárias:
  GOOGLE_SHEETS_SPREADSHEET_ID   – ID da planilha Google (parte da URL)
  GOOGLE_SERVICE_ACCOUNT_JSON    – JSON da Service Account (string ou base64)
"""

import base64
import json
import os
from threading import RLock

import gspread
from google.oauth2.service_account import Credentials


GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Definição das abas e seus cabeçalhos
SHEETS_CONFIG = {
    "barema": [
        "id", "consulta_id", "code", "nome",
        "titulacao_bruto", "titulacao_limitado",
        "producao_bruto", "producao_limitado",
        "formacao_bruto", "formacao_limitado",
        "eventos_bruto", "eventos_limitado",
        "total_bruto", "total_limitado",
        "updated_at",
    ],
    "barema_aeri": [
        "id", "consulta_id", "code", "nome",
        "participacoes_bruto", "participacoes_limitado",
        "producao_bruto", "producao_limitado",
        "representacao_bruto", "representacao_limitado",
        "programas_bruto", "programas_limitado",
        "total_bruto", "total_limitado",
        "updated_at",
    ],
    "consultas": [
        "id", "url_informada", "url_consultada", "code",
        "success", "message", "created_at", "tipo",
    ],
    "editais": ["tipo", "ano", "url", "updated_at"],
}

_LOCK = RLock()
_CLIENT = None
_SPREADSHEET = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _column_letter(n):
    """Converte número de coluna (1-based) em letra(s) de planilha."""
    letters = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        letters = chr(65 + r) + letters
    return letters


def _parse_service_account_json(raw_value):
    value = str(raw_value or "").strip()
    if not value:
        raise RuntimeError("A variável GOOGLE_SERVICE_ACCOUNT_JSON está vazia.")

    # Remove aspas envolventes, se houver
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]

    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        decoded = base64.b64decode(value).decode("utf-8")
        data = json.loads(decoded)

    private_key = str(data.get("private_key") or "").replace("\\n", "\n")
    if private_key and not private_key.endswith("\n"):
        private_key += "\n"
    data["private_key"] = private_key
    return data


def _require_settings():
    if not GOOGLE_SHEETS_SPREADSHEET_ID:
        raise RuntimeError(
            "Defina GOOGLE_SHEETS_SPREADSHEET_ID com o ID da planilha."
        )
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError(
            "Defina GOOGLE_SERVICE_ACCOUNT_JSON com o JSON da Service Account."
        )


# ---------------------------------------------------------------------------
# Conexão
# ---------------------------------------------------------------------------

def _get_client():
    global _CLIENT
    with _LOCK:
        if _CLIENT is None:
            _require_settings()
            credentials = Credentials.from_service_account_info(
                _parse_service_account_json(GOOGLE_SERVICE_ACCOUNT_JSON),
                scopes=SCOPES,
            )
            _CLIENT = gspread.authorize(credentials)
    return _CLIENT


def _get_spreadsheet():
    global _SPREADSHEET
    with _LOCK:
        if _SPREADSHEET is None:
            _SPREADSHEET = _get_client().open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)
    return _SPREADSHEET


def _get_or_create_worksheet(name, headers):
    """Retorna a aba pelo nome, criando-a (com cabeçalhos) se não existir."""
    spreadsheet = _get_spreadsheet()
    try:
        ws = spreadsheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=name,
            rows=2000,
            cols=max(20, len(headers)),
        )

    current_headers = ws.row_values(1)
    if current_headers != headers:
        ws.update(
            f"A1:{_column_letter(len(headers))}1",
            [headers],
        )

    return ws


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def sync_table(table_name, rows):
    """
    Substitui todo o conteúdo da aba *table_name* pelos dados em *rows*.

    Parameters
    ----------
    table_name : str
        Nome da aba na planilha (chave de SHEETS_CONFIG).
    rows : list[dict]
        Registros vindos do Turso. Cada dict deve conter as chaves
        correspondentes aos cabeçalhos configurados em SHEETS_CONFIG.
    """
    headers = SHEETS_CONFIG[table_name]
    ws = _get_or_create_worksheet(table_name, headers)

    # Limpa os dados existentes (mantém cabeçalho)
    last_col = _column_letter(len(headers))
    ws.batch_clear([f"A2:{last_col}"])

    if not rows:
        return

    # Converte para lista de listas respeitando a ordem dos cabeçalhos
    matrix = [
        [str(row.get(col, "") if row.get(col) is not None else "") for col in headers]
        for row in rows
    ]

    ws.update(
        f"A2:{last_col}{1 + len(matrix)}",
        matrix,
        value_input_option="USER_ENTERED",
    )


def sync_all(barema_rows, barema_aeri_rows, consultas_rows, editais_rows):
    """Sincroniza todas as abas de uma vez."""
    sync_table("barema", barema_rows)
    sync_table("barema_aeri", barema_aeri_rows)
    sync_table("consultas", consultas_rows)
    sync_table("editais", editais_rows)
