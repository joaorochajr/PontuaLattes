# pyright: reportMissingImports=false

import json
import os
import hashlib
import re
import secrets
from datetime import datetime
from pathlib import Path
from threading import RLock
from urllib.parse import urlparse

import gspread
from google.oauth2.service_account import Credentials


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DASHBOARD_USERNAME = os.getenv("DEFAULT_DASHBOARD_USERNAME", "admin")
DEFAULT_DASHBOARD_PASSWORD = os.getenv("DEFAULT_DASHBOARD_PASSWORD", "pontualattes")
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

SCOPES = [
	"https://www.googleapis.com/auth/spreadsheets",
	"https://www.googleapis.com/auth/drive",
]

WORKSHEET_HEADERS = {
	"consultas": [
		"id",
		"url_informada",
		"url_consultada",
		"code",
		"success",
		"message",
		"created_at",
	],
	"barema": [
		"id",
		"consulta_id",
		"code",
		"nome",
		"titulacao_bruto",
		"titulacao_limitado",
		"producao_bruto",
		"producao_limitado",
		"formacao_bruto",
		"formacao_limitado",
		"eventos_bruto",
		"eventos_limitado",
		"total_bruto",
		"total_limitado",
		"barema_json",
		"updated_at",
	],
	"users": [
		"id",
		"username",
		"password_hash",
		"salt",
	],
	"sessions": [
		"token",
		"user_id",
		"created_at",
	],
}

_LOCK = RLock()
_CLIENT = None
_SPREADSHEET = None
_WORKSHEETS = {}
_INITIALIZED = False


def _now_str():
	return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _column_letter(column_number):
	letters = ""
	while column_number > 0:
		column_number, remainder = divmod(column_number - 1, 26)
		letters = chr(65 + remainder) + letters
	return letters


def _as_int(value, default=0):
	try:
		return int(str(value).strip())
	except (TypeError, ValueError, AttributeError):
		return default


def _as_float(value, default=None):
	if value in (None, ""):
		return default

	try:
		return float(str(value).strip().replace(",", "."))
	except (TypeError, ValueError, AttributeError):
		return default


def _require_google_settings():
	if not GOOGLE_SHEETS_SPREADSHEET_ID:
		raise RuntimeError(
			"Defina a variável GOOGLE_SHEETS_SPREADSHEET_ID com o ID da planilha que será usada como banco de dados."
		)

	if not GOOGLE_SERVICE_ACCOUNT_JSON and not GOOGLE_SERVICE_ACCOUNT_FILE:
		raise RuntimeError(
			"Defina GOOGLE_SERVICE_ACCOUNT_JSON ou GOOGLE_SERVICE_ACCOUNT_FILE para autenticar no Google Sheets."
		)


def _load_service_account_info():
	if GOOGLE_SERVICE_ACCOUNT_JSON:
		return json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)

	service_account_path = Path(GOOGLE_SERVICE_ACCOUNT_FILE).expanduser()
	if not service_account_path.is_absolute():
		service_account_path = (BASE_DIR.parent / service_account_path).resolve()

	if not service_account_path.exists():
		raise RuntimeError(
			f"Arquivo da conta de serviço não encontrado em {service_account_path}."
		)

	return json.loads(service_account_path.read_text(encoding="utf-8"))


def _get_client():
	global _CLIENT

	with _LOCK:
		if _CLIENT is None:
			_require_google_settings()
			credentials = Credentials.from_service_account_info(
				_load_service_account_info(),
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


def _ensure_worksheet(name):
	headers = WORKSHEET_HEADERS[name]

	with _LOCK:
		worksheet = _WORKSHEETS.get(name)
		if worksheet is None:
			spreadsheet = _get_spreadsheet()
			try:
				worksheet = spreadsheet.worksheet(name)
			except gspread.WorksheetNotFound:
				worksheet = spreadsheet.add_worksheet(
					title=name,
					rows=1000,
					cols=max(20, len(headers)),
				)

			current_headers = worksheet.row_values(1)
			if current_headers != headers:
				worksheet.update(f"A1:{_column_letter(len(headers))}1", [headers])

			_WORKSHEETS[name] = worksheet

		return worksheet


def _get_records(name):
	worksheet = _ensure_worksheet(name)
	headers = WORKSHEET_HEADERS[name]
	rows = worksheet.get_all_values()

	if len(rows) <= 1:
		return []

	records = []
	for row_number, row in enumerate(rows[1:], start=2):
		if not any(str(value).strip() for value in row):
			continue

		normalized_row = row + [""] * (len(headers) - len(row))
		record = {header: normalized_row[index] for index, header in enumerate(headers)}
		record["_row_number"] = row_number
		records.append(record)

	return records


def _append_record(name, record):
	worksheet = _ensure_worksheet(name)
	headers = WORKSHEET_HEADERS[name]
	values = [str(record.get(header, "")) for header in headers]
	worksheet.append_row(values, value_input_option="USER_ENTERED")


def _update_row(name, row_number, record):
	worksheet = _ensure_worksheet(name)
	headers = WORKSHEET_HEADERS[name]
	values = [str(record.get(header, "")) for header in headers]
	worksheet.update(
		f"A{row_number}:{_column_letter(len(headers))}{row_number}",
		[values],
		value_input_option="USER_ENTERED",
	)


def _delete_rows_by_value(name, key, value):
	worksheet = _ensure_worksheet(name)
	matches = [record for record in _get_records(name) if str(record.get(key, "")).strip() == str(value).strip()]

	for record in sorted(matches, key=lambda item: item["_row_number"], reverse=True):
		worksheet.delete_rows(record["_row_number"])


def _find_record(name, key, value):
	for record in _get_records(name):
		if str(record.get(key, "")).strip() == str(value).strip():
			return record
	return None


def _next_id(name):
	records = _get_records(name)
	ids = [_as_int(record.get("id")) for record in records if str(record.get("id", "")).strip()]
	return max(ids, default=0) + 1


def _extract_public_lattes_code(value):
	value = str(value or "").strip()
	if not value:
		return None

	if re.fullmatch(r"\d+", value):
		return value

	parsed_value = value if re.match(r"^https?://", value, re.IGNORECASE) else f"http://{value}"
	parsed_url = urlparse(parsed_value)
	host = (parsed_url.netloc or "").lower()
	path = (parsed_url.path or "").strip("/")

	if host.endswith("lattes.cnpq.br") and re.fullmatch(r"\d+", path):
		return path

	return None


def _normalize_consulta_key(value):
	public_code = _extract_public_lattes_code(value)
	if public_code:
		return f"code:{public_code}"

	value = str(value or "").strip()
	if not value:
		return None

	return f"raw:{value.lower()}"


def _build_consulta_keys(url_informada, resultado):
	keys = set()
	for candidate in (url_informada, (resultado or {}).get("url"), (resultado or {}).get("code")):
		key = _normalize_consulta_key(candidate)
		if key:
			keys.add(key)

	return keys


def _find_matching_consultas(url_informada, resultado):
	target_keys = _build_consulta_keys(url_informada, resultado)
	if not target_keys:
		return []

	matches = []
	for consulta in _get_records("consultas"):
		existing_keys = {
			key
			for key in (
				_normalize_consulta_key(consulta.get("url_informada")),
				_normalize_consulta_key(consulta.get("url_consultada")),
				_normalize_consulta_key(consulta.get("code")),
			)
			if key
		}

		if target_keys & existing_keys:
			matches.append(consulta)

	return sorted(matches, key=lambda item: item.get("_row_number", 0), reverse=True)


def _ensure_default_dashboard_user():
	pwd_hash, salt = hash_password(DEFAULT_DASHBOARD_PASSWORD)
	user = _find_record("users", "username", DEFAULT_DASHBOARD_USERNAME)

	if user:
		updated_user = {
			"id": user.get("id") or _next_id("users"),
			"username": DEFAULT_DASHBOARD_USERNAME,
			"password_hash": pwd_hash,
			"salt": salt,
		}
		_update_row("users", user["_row_number"], updated_user)
		return

	_append_record(
		"users",
		{
			"id": _next_id("users"),
			"username": DEFAULT_DASHBOARD_USERNAME,
			"password_hash": pwd_hash,
			"salt": salt,
		},
	)


def init_database():
	global _INITIALIZED

	with _LOCK:
		if _INITIALIZED:
			return

		for worksheet_name in WORKSHEET_HEADERS:
			_ensure_worksheet(worksheet_name)

		_ensure_default_dashboard_user()
		_INITIALIZED = True


def formatar_url_lattes(url_ou_numero):
	if not url_ou_numero:
		return ""

	url_ou_numero = str(url_ou_numero).strip()

	if url_ou_numero.startswith("http://lattes.cnpq.br/"):
		return url_ou_numero

	return f"http://lattes.cnpq.br/{url_ou_numero}"


def registrar_consulta(url_informada, resultado):
	init_database()
	matches = _find_matching_consultas(url_informada, resultado)
	current_timestamp = _now_str()
	consulta_id = _as_int(matches[0].get("id")) if matches else _next_id("consultas")
	record = {
		"id": consulta_id,
		"url_informada": str(url_informada or "").strip(),
		"url_consultada": resultado.get("url") or "",
		"code": resultado.get("code") or "",
		"success": 1 if resultado.get("success") else 0,
		"message": resultado.get("message") or "",
		"created_at": current_timestamp,
	}

	if matches:
		_update_row("consultas", matches[0]["_row_number"], record)
		worksheet = _ensure_worksheet("consultas")
		for duplicate in matches[1:]:
			worksheet.delete_rows(duplicate["_row_number"])
		return consulta_id

	_append_record("consultas", record)
	return consulta_id


def get_consultas(success=None, page=1, per_page=10):
	consultas = _get_records("consultas")
	baremas = {
		record.get("code"): record
		for record in _get_records("barema")
		if str(record.get("code", "")).strip()
	}

	registros = []
	for consulta in consultas:
		success_value = _as_int(consulta.get("success"))
		if success is not None and success_value != int(success):
			continue

		barema = baremas.get(consulta.get("code"), {})
		registros.append(
			{
				"id": _as_int(consulta.get("id"), consulta.get("id")),
				"url_informada": consulta.get("url_informada") or None,
				"url_consultada": consulta.get("url_consultada") or None,
				"code": consulta.get("code") or None,
				"success": success_value,
				"message": consulta.get("message") or None,
				"created_at": consulta.get("created_at") or None,
				"nome": barema.get("nome") or None,
				"total_limitado": _as_float(barema.get("total_limitado"), None),
			}
		)

	registros.sort(key=lambda item: item.get("created_at") or "", reverse=True)
	offset = max(page - 1, 0) * per_page
	return registros[offset:offset + per_page]


def count_consultas(success=None):
	consultas = _get_records("consultas")
	if success is None:
		return len(consultas)

	return sum(1 for consulta in consultas if _as_int(consulta.get("success")) == int(success))


def get_top5_consultas():
	consultas = _get_records("consultas")
	baremas = {
		record.get("code"): record
		for record in _get_records("barema")
		if str(record.get("code", "")).strip()
	}
	totais = {}

	for consulta in consultas:
		code = str(consulta.get("code", "")).strip()
		if not code or code not in baremas:
			continue

		nome = baremas[code].get("nome") or "Sem nome"
		chave = (code, nome)
		totais[chave] = totais.get(chave, 0) + 1

	resultados = [
		{"nome": nome, "code": code, "total": total}
		for (code, nome), total in totais.items()
	]
	resultados.sort(key=lambda item: (-item["total"], item["nome"], item["code"]))
	return resultados[:5]


def get_consultas_por_dia():
	totais = {}
	for consulta in _get_records("consultas"):
		created_at = str(consulta.get("created_at", "")).strip()
		if not created_at:
			continue

		dia = created_at.split(" ", 1)[0]
		totais[dia] = totais.get(dia, 0) + 1

	return [
		{"dia": dia, "total": total}
		for dia, total in sorted(totais.items(), key=lambda item: item[0])
	]


def registrar_barema(consulta_id, code, nome, barema_resultado):
	if not consulta_id or not code or not barema_resultado or not barema_resultado.get("success"):
		return

	init_database()
	payload_json = json.dumps(barema_resultado, ensure_ascii=False)
	existing_record = _find_record("barema", "code", code)
	barema_id = existing_record.get("id") if existing_record else _next_id("barema")
	record = {
		"id": barema_id,
		"consulta_id": consulta_id,
		"code": code,
		"nome": nome or "",
		"titulacao_bruto": barema_resultado.get("titulacao", {}).get("subtotal_bruto", 0),
		"titulacao_limitado": barema_resultado.get("titulacao", {}).get("subtotal_limitado", 0),
		"producao_bruto": barema_resultado.get("producao", {}).get("subtotal_bruto", 0),
		"producao_limitado": barema_resultado.get("producao", {}).get("subtotal_limitado", 0),
		"formacao_bruto": barema_resultado.get("formacao_recursos_humanos", {}).get("subtotal_bruto", 0),
		"formacao_limitado": barema_resultado.get("formacao_recursos_humanos", {}).get("subtotal_limitado", 0),
		"eventos_bruto": barema_resultado.get("participacao_eventos_comite", {}).get("subtotal_bruto", 0),
		"eventos_limitado": barema_resultado.get("participacao_eventos_comite", {}).get("subtotal_limitado", 0),
		"total_bruto": barema_resultado.get("total_bruto", 0),
		"total_limitado": barema_resultado.get("total_limitado", 0),
		"barema_json": payload_json,
		"updated_at": _now_str(),
	}

	if existing_record:
		_update_row("barema", existing_record["_row_number"], record)
		return

	_append_record("barema", record)


def hash_password(password, salt=None):
	if salt is None:
		salt = secrets.token_hex(16)

	pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
	return pwd_hash.hex(), salt


def create_user(username, password):
	init_database()
	username = str(username or "").strip()
	if not username or _find_record("users", "username", username):
		return False

	pwd_hash, salt = hash_password(password)
	_append_record(
		"users",
		{
			"id": _next_id("users"),
			"username": username,
			"password_hash": pwd_hash,
			"salt": salt,
		},
	)
	return True


def verify_login(username, password):
	init_database()
	user = _find_record("users", "username", str(username or "").strip())
	if not user:
		return None

	pwd_hash, _ = hash_password(password, user.get("salt"))
	if pwd_hash != user.get("password_hash"):
		return None

	token = secrets.token_hex(32)
	_append_record(
		"sessions",
		{
			"token": token,
			"user_id": user.get("id"),
			"created_at": _now_str(),
		},
	)
	return token


def delete_session(token):
	_delete_rows_by_value("sessions", "token", token)


def get_user_id_by_token(token):
	session = _find_record("sessions", "token", token)
	if not session:
		return None

	return _as_int(session.get("user_id"), session.get("user_id"))