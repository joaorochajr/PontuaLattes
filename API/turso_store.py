# pyright: reportMissingImports=false

import hashlib
import json
import os
import re
import secrets
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

try:  # o libsql-client so e necessario no modo Turso
	import libsql_client
except ImportError:  # pragma: no cover
	libsql_client = None


TURSO_URL = os.getenv("TURSO_URL", "").strip()
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN", "").strip()

# Sem TURSO_URL o sistema roda em modo local, gravando em um arquivo SQLite.
# O Turso e SQLite distribuido, entao o mesmo SQL vale para os dois modos.
CAMINHO_BANCO_LOCAL = os.getenv(
	"LOCAL_DB_PATH",
	str(Path(__file__).resolve().parent.parent / "pontualattes.db"),
)


def usando_banco_local():
	return not TURSO_URL
DEFAULT_DASHBOARD_USERNAME = os.getenv("DEFAULT_DASHBOARD_USERNAME", "admin")
DEFAULT_DASHBOARD_PASSWORD = os.getenv("DEFAULT_DASHBOARD_PASSWORD", "")

TIPOS_VALIDOS = ("ic", "aeri", "extensao_docente", "extensao_discente")
TIPOS_EDITAL = ("ic", "aeri", "extensao")

# Cada modalidade de barema tem a sua propria tabela de pontuacoes.
_BAREMA_TABELAS = {
	"ic": "barema",
	"aeri": "barema_aeri",
	"extensao_docente": "barema_extensao_docente",
	"extensao_discente": "barema_extensao_discente",
}

_client = None
_client_init_lock = threading.Lock()
_INITIALIZED = False
_INIT_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

def _get_client():
	global _client
	with _client_init_lock:
		if _client is None:
			if usando_banco_local():
				from local_store import criar_cliente_local

				_client = criar_cliente_local(CAMINHO_BANCO_LOCAL)
				return _client

			if not TURSO_AUTH_TOKEN:
				raise RuntimeError(
					"Defina a variável TURSO_AUTH_TOKEN com o token de autenticação do Turso."
				)
			if libsql_client is None:
				raise RuntimeError(
					"O pacote libsql-client não está instalado."
					" Rode: pip install -r API/requirements.txt"
				)
			_client = libsql_client.create_client_sync(url=TURSO_URL, auth_token=TURSO_AUTH_TOKEN)
	return _client


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _q(sql, args=()):
	return _get_client().execute(sql, list(args) if args else None)


def _batch(statements):
	return _get_client().batch(statements)


def _rows(result_set):
	cols = result_set.columns
	return [dict(zip(cols, row)) for row in result_set.rows]


def _now_str():
	return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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


def normalizar_tipo(tipo):
	tipo = str(tipo or "").strip()
	return tipo if tipo in TIPOS_VALIDOS else "ic"


def normalizar_tipo_edital(tipo):
	tipo = str(tipo or "").strip()
	return tipo if tipo in TIPOS_EDITAL else None


def _tabela_barema(tipo):
	return _BAREMA_TABELAS.get(normalizar_tipo(tipo), "barema")


def _extract_public_lattes_code(value):
	value = str(value or "").strip()
	if not value:
		return None

	if re.fullmatch(r"\d+", value):
		return value

	parsed = value if re.match(r"^https?://", value, re.IGNORECASE) else f"http://{value}"
	parsed_url = urlparse(parsed)
	host = (parsed_url.netloc or "").lower()
	path = (parsed_url.path or "").strip("/")

	if host.endswith("lattes.cnpq.br") and re.fullmatch(r"\d+", path):
		return path

	return None


# ---------------------------------------------------------------------------
# Schema & initialisation
# ---------------------------------------------------------------------------

_DDL = [
	"""
	CREATE TABLE IF NOT EXISTS consultas (
		id             INTEGER PRIMARY KEY AUTOINCREMENT,
		url_informada  TEXT,
		url_consultada TEXT,
		code           TEXT,
		success        INTEGER,
		message        TEXT,
		created_at     TEXT
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS barema (
		id                 INTEGER PRIMARY KEY AUTOINCREMENT,
		consulta_id        INTEGER,
		code               TEXT UNIQUE,
		nome               TEXT,
		titulacao_bruto    REAL,
		titulacao_limitado REAL,
		producao_bruto     REAL,
		producao_limitado  REAL,
		formacao_bruto     REAL,
		formacao_limitado  REAL,
		eventos_bruto      REAL,
		eventos_limitado   REAL,
		total_bruto        REAL,
		total_limitado     REAL,
		barema_json        TEXT,
		updated_at         TEXT
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS users (
		id            INTEGER PRIMARY KEY AUTOINCREMENT,
		username      TEXT UNIQUE,
		password_hash TEXT,
		salt          TEXT
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS sessions (
		token      TEXT PRIMARY KEY,
		user_id    INTEGER,
		created_at TEXT
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS barema_aeri (
		id                       INTEGER PRIMARY KEY AUTOINCREMENT,
		consulta_id              INTEGER,
		code                     TEXT UNIQUE,
		nome                     TEXT,
		participacoes_bruto      REAL,
		participacoes_limitado   REAL,
		producao_bruto           REAL,
		producao_limitado        REAL,
		representacao_bruto      REAL,
		representacao_limitado   REAL,
		programas_bruto          REAL,
		programas_limitado       REAL,
		total_bruto              REAL,
		total_limitado           REAL,
		barema_json              TEXT,
		updated_at               TEXT
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS barema_extensao_docente (
		id                 INTEGER PRIMARY KEY AUTOINCREMENT,
		consulta_id        INTEGER,
		code               TEXT UNIQUE,
		nome               TEXT,
		titulacao_bruto    REAL,
		titulacao_limitado REAL,
		atuacao_bruto      REAL,
		atuacao_limitado   REAL,
		producao_bruto     REAL,
		producao_limitado  REAL,
		formacao_bruto     REAL,
		formacao_limitado  REAL,
		total_bruto        REAL,
		total_limitado     REAL,
		barema_json        TEXT,
		updated_at         TEXT
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS barema_extensao_discente (
		id                INTEGER PRIMARY KEY AUTOINCREMENT,
		consulta_id       INTEGER,
		code              TEXT UNIQUE,
		nome              TEXT,
		atuacao_bruto     REAL,
		atuacao_limitado  REAL,
		producao_bruto    REAL,
		producao_limitado REAL,
		eventos_bruto     REAL,
		eventos_limitado  REAL,
		total_bruto       REAL,
		total_limitado    REAL,
		barema_json       TEXT,
		updated_at        TEXT
	)
	""",
	"""
	CREATE TABLE IF NOT EXISTS editais (
		tipo       TEXT PRIMARY KEY,
		ano        TEXT,
		url        TEXT,
		updated_at TEXT
	)
	""",
]


def _ensure_default_user():
	result = _q("SELECT id FROM users WHERE username = ?", (DEFAULT_DASHBOARD_USERNAME,))
	pwd_hash, salt = hash_password(DEFAULT_DASHBOARD_PASSWORD)
	if _rows(result):
		_q(
			"UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
			(pwd_hash, salt, DEFAULT_DASHBOARD_USERNAME),
		)
	else:
		_q(
			"INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
			(DEFAULT_DASHBOARD_USERNAME, pwd_hash, salt),
		)


def init_database():
	global _INITIALIZED
	with _INIT_LOCK:
		if _INITIALIZED:
			return
		_batch(_DDL)
		_migrate()
		_ensure_default_user()
		_INITIALIZED = True


def _migrate():
	"""Migrações idempotentes."""
	try:
		_q("ALTER TABLE consultas ADD COLUMN tipo TEXT NOT NULL DEFAULT 'ic'")
	except Exception:
		pass  # coluna já existe

	# Marca quem teve a nota ajustada manualmente (PDF do currículo ou digitação),
	# para o histórico distinguir nota automática de nota informada.
	for tabela in ("barema_extensao_docente", "barema_extensao_discente"):
		try:
			_q(f"ALTER TABLE {tabela} ADD COLUMN ajuste_manual INTEGER NOT NULL DEFAULT 0")
		except Exception:
			pass  # coluna já existe


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_editais():
	init_database()
	result = _q("SELECT tipo, ano, url, updated_at FROM editais")
	rows = {}
	for row in result.rows:
		d = dict(zip(result.columns, row))
		rows[d["tipo"]] = d
	return {
		tipo: rows.get(tipo, {"tipo": tipo, "ano": "", "url": ""})
		for tipo in TIPOS_EDITAL
	}


def salvar_edital(tipo, ano, url):
	init_database()
	now = datetime.utcnow().isoformat()
	_q(
		"INSERT INTO editais (tipo, ano, url, updated_at) VALUES (?, ?, ?, ?) "
		"ON CONFLICT(tipo) DO UPDATE SET ano=excluded.ano, url=excluded.url, updated_at=excluded.updated_at",
		(tipo, str(ano), str(url), now),
	)


def formatar_url_lattes(url_ou_numero):
	if not url_ou_numero:
		return ""
	url_ou_numero = str(url_ou_numero).strip()
	if url_ou_numero.startswith("http://lattes.cnpq.br/"):
		return url_ou_numero
	return f"http://lattes.cnpq.br/{url_ou_numero}"


def registrar_consulta(url_informada, resultado, tipo="ic"):
	init_database()
	url_informada = str(url_informada or "").strip()
	url_consultada = resultado.get("url") or ""
	code = resultado.get("code") or ""
	success = 1 if resultado.get("success") else 0
	message = resultado.get("message") or ""
	tipo = normalizar_tipo(tipo)
	now = _now_str()

	# Dedup: find an existing row that shares any known Lattes code AND same tipo
	candidates = list({
		c
		for c in [
			_extract_public_lattes_code(url_informada),
			_extract_public_lattes_code(url_consultada),
			_extract_public_lattes_code(code),
		]
		if c
	})

	existing_id = None
	if candidates:
		placeholders = ",".join("?" * len(candidates))
		result = _q(
			f"SELECT id FROM consultas WHERE code IN ({placeholders}) AND tipo = ? ORDER BY id DESC LIMIT 1",
			(*candidates, tipo),
		)
		rows = _rows(result)
		if rows:
			existing_id = rows[0]["id"]

	if existing_id is not None:
		_q(
			"UPDATE consultas SET url_informada=?, url_consultada=?, code=?, success=?, message=?, created_at=? WHERE id=?",
			(url_informada, url_consultada, code, success, message, now, existing_id),
		)
		return existing_id

	result = _q(
		"INSERT INTO consultas (url_informada, url_consultada, code, success, message, created_at, tipo) VALUES (?, ?, ?, ?, ?, ?, ?)",
		(url_informada, url_consultada, code, success, message, now, tipo),
	)
	return result.last_insert_rowid


def get_consultas(success=None, page=1, per_page=10, tipo="ic"):
	init_database()
	tipo = normalizar_tipo(tipo)
	offset = max(page - 1, 0) * per_page
	barema_table = _tabela_barema(tipo)
	# Só as tabelas de extensão têm a marca de ajuste manual; IC e AERI
	# seguem intocadas e devolvem zero fixo.
	coluna_ajuste = (
		"b.ajuste_manual" if tipo in ("extensao_docente", "extensao_discente")
		else "0 AS ajuste_manual"
	)

	if success is not None:
		sql = f"""
			SELECT c.id, c.url_informada, c.url_consultada, c.code, c.success, c.message, c.created_at,
			       b.nome, b.total_limitado, {coluna_ajuste}
			FROM consultas c
			LEFT JOIN {barema_table} b ON b.code = c.code AND c.code != ''
			WHERE c.success = ? AND c.tipo = ?
			ORDER BY c.created_at DESC
			LIMIT ? OFFSET ?
		"""
		result = _q(sql, (int(success), tipo, per_page, offset))
	else:
		sql = f"""
			SELECT c.id, c.url_informada, c.url_consultada, c.code, c.success, c.message, c.created_at,
			       b.nome, b.total_limitado, {coluna_ajuste}
			FROM consultas c
			LEFT JOIN {barema_table} b ON b.code = c.code AND c.code != ''
			WHERE c.tipo = ?
			ORDER BY c.created_at DESC
			LIMIT ? OFFSET ?
		"""
		result = _q(sql, (tipo, per_page, offset))

	return [
		{
			"id": row["id"],
			"url_informada": row["url_informada"] or None,
			"url_consultada": row["url_consultada"] or None,
			"code": row["code"] or None,
			"success": _as_int(row["success"]),
			"message": row["message"] or None,
			"created_at": row["created_at"] or None,
			"nome": row["nome"] or None,
			"total_limitado": _as_float(row["total_limitado"], None),
			"ajuste_manual": _as_int(row.get("ajuste_manual"), 0),
		}
		for row in _rows(result)
	]


def count_consultas(success=None, tipo=None):
	init_database()
	if tipo is not None:
		tipo = normalizar_tipo(tipo)
	if tipo is not None and success is not None:
		result = _q("SELECT COUNT(*) AS n FROM consultas WHERE success = ? AND tipo = ?", (int(success), tipo))
	elif tipo is not None:
		result = _q("SELECT COUNT(*) AS n FROM consultas WHERE tipo = ?", (tipo,))
	elif success is not None:
		result = _q("SELECT COUNT(*) AS n FROM consultas WHERE success = ?", (int(success),))
	else:
		result = _q("SELECT COUNT(*) AS n FROM consultas")
	rows = _rows(result)
	return _as_int(rows[0]["n"]) if rows else 0


def get_top5_consultas(tipo="ic"):
	init_database()
	tipo = normalizar_tipo(tipo)
	barema_table = _tabela_barema(tipo)
	sql = f"""
		SELECT b.code, b.nome, COUNT(*) AS total
		FROM consultas c
		JOIN {barema_table} b ON b.code = c.code AND c.code != ''
		WHERE c.tipo = ?
		GROUP BY b.code, b.nome
		ORDER BY total DESC, b.nome ASC
		LIMIT 5
	"""
	result = _q(sql, (tipo,))
	return [
		{"nome": row["nome"] or "Sem nome", "code": row["code"], "total": _as_int(row["total"])}
		for row in _rows(result)
	]


def get_consultas_por_dia():
	init_database()
	sql = """
		SELECT SUBSTR(created_at, 1, 10) AS dia, COUNT(*) AS total
		FROM consultas
		WHERE created_at IS NOT NULL AND created_at != ''
		GROUP BY dia
		ORDER BY dia ASC
	"""
	result = _q(sql)
	return [
		{"dia": row["dia"], "total": _as_int(row["total"])}
		for row in _rows(result)
	]


def registrar_barema(consulta_id, code, nome, barema_resultado):
	if not consulta_id or not code or not barema_resultado or not barema_resultado.get("success"):
		return

	init_database()
	payload_json = json.dumps(barema_resultado, ensure_ascii=False)
	now = _now_str()

	_q(
		"""
		INSERT INTO barema (
			consulta_id, code, nome,
			titulacao_bruto, titulacao_limitado,
			producao_bruto, producao_limitado,
			formacao_bruto, formacao_limitado,
			eventos_bruto, eventos_limitado,
			total_bruto, total_limitado,
			barema_json, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(code) DO UPDATE SET
			consulta_id        = excluded.consulta_id,
			nome               = excluded.nome,
			titulacao_bruto    = excluded.titulacao_bruto,
			titulacao_limitado = excluded.titulacao_limitado,
			producao_bruto     = excluded.producao_bruto,
			producao_limitado  = excluded.producao_limitado,
			formacao_bruto     = excluded.formacao_bruto,
			formacao_limitado  = excluded.formacao_limitado,
			eventos_bruto      = excluded.eventos_bruto,
			eventos_limitado   = excluded.eventos_limitado,
			total_bruto        = excluded.total_bruto,
			total_limitado     = excluded.total_limitado,
			barema_json        = excluded.barema_json,
			updated_at         = excluded.updated_at
		""",
		(
			consulta_id,
			code,
			nome or "",
			barema_resultado.get("titulacao", {}).get("subtotal_bruto", 0),
			barema_resultado.get("titulacao", {}).get("subtotal_limitado", 0),
			barema_resultado.get("producao", {}).get("subtotal_bruto", 0),
			barema_resultado.get("producao", {}).get("subtotal_limitado", 0),
			barema_resultado.get("formacao_recursos_humanos", {}).get("subtotal_bruto", 0),
			barema_resultado.get("formacao_recursos_humanos", {}).get("subtotal_limitado", 0),
			barema_resultado.get("participacao_eventos_comite", {}).get("subtotal_bruto", 0),
			barema_resultado.get("participacao_eventos_comite", {}).get("subtotal_limitado", 0),
			barema_resultado.get("total_bruto", 0),
			barema_resultado.get("total_limitado", 0),
			payload_json,
			now,
		),
	)


def registrar_barema_aeri(consulta_id, code, nome, barema_resultado):
	if not consulta_id or not code or not barema_resultado or not barema_resultado.get("success"):
		return

	init_database()
	payload_json = json.dumps(barema_resultado, ensure_ascii=False)
	now = _now_str()

	_q(
		"""
		INSERT INTO barema_aeri (
			consulta_id, code, nome,
			participacoes_bruto, participacoes_limitado,
			producao_bruto, producao_limitado,
			representacao_bruto, representacao_limitado,
			programas_bruto, programas_limitado,
			total_bruto, total_limitado,
			barema_json, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(code) DO UPDATE SET
			consulta_id            = excluded.consulta_id,
			nome                   = excluded.nome,
			participacoes_bruto    = excluded.participacoes_bruto,
			participacoes_limitado = excluded.participacoes_limitado,
			producao_bruto         = excluded.producao_bruto,
			producao_limitado      = excluded.producao_limitado,
			representacao_bruto    = excluded.representacao_bruto,
			representacao_limitado = excluded.representacao_limitado,
			programas_bruto        = excluded.programas_bruto,
			programas_limitado     = excluded.programas_limitado,
			total_bruto            = excluded.total_bruto,
			total_limitado         = excluded.total_limitado,
			barema_json            = excluded.barema_json,
			updated_at             = excluded.updated_at
		""",
		(
			consulta_id,
			code,
			nome or "",
			barema_resultado.get("participacoes_eventos", {}).get("subtotal_bruto", 0),
			barema_resultado.get("participacoes_eventos", {}).get("subtotal_limitado", 0),
			barema_resultado.get("producao_cientifica", {}).get("subtotal_bruto", 0),
			barema_resultado.get("producao_cientifica", {}).get("subtotal_limitado", 0),
			barema_resultado.get("representacao_lideranca", {}).get("subtotal_bruto", 0),
			barema_resultado.get("representacao_lideranca", {}).get("subtotal_limitado", 0),
			barema_resultado.get("participacao_programas", {}).get("subtotal_bruto", 0),
			barema_resultado.get("participacao_programas", {}).get("subtotal_limitado", 0),
			barema_resultado.get("total_bruto", 0),
			barema_resultado.get("total_limitado", 0),
			payload_json,
			now,
		),
	)


def registrar_barema_extensao_docente(consulta_id, code, nome, barema_resultado):
	if not consulta_id or not code or not barema_resultado or not barema_resultado.get("success"):
		return

	init_database()
	payload_json = json.dumps(barema_resultado, ensure_ascii=False)
	now = _now_str()

	_q(
		"""
		INSERT INTO barema_extensao_docente (
			consulta_id, code, nome,
			titulacao_bruto, titulacao_limitado,
			atuacao_bruto, atuacao_limitado,
			producao_bruto, producao_limitado,
			formacao_bruto, formacao_limitado,
			total_bruto, total_limitado,
			barema_json, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(code) DO UPDATE SET
			consulta_id        = excluded.consulta_id,
			nome               = excluded.nome,
			titulacao_bruto    = excluded.titulacao_bruto,
			titulacao_limitado = excluded.titulacao_limitado,
			atuacao_bruto      = excluded.atuacao_bruto,
			atuacao_limitado   = excluded.atuacao_limitado,
			producao_bruto     = excluded.producao_bruto,
			producao_limitado  = excluded.producao_limitado,
			formacao_bruto     = excluded.formacao_bruto,
			formacao_limitado  = excluded.formacao_limitado,
			total_bruto        = excluded.total_bruto,
			total_limitado     = excluded.total_limitado,
			barema_json        = excluded.barema_json,
			updated_at         = excluded.updated_at
		""",
		(
			consulta_id,
			code,
			nome or "",
			barema_resultado.get("titulacao", {}).get("subtotal_bruto", 0),
			barema_resultado.get("titulacao", {}).get("subtotal_limitado", 0),
			barema_resultado.get("atuacao_extensao", {}).get("subtotal_bruto", 0),
			barema_resultado.get("atuacao_extensao", {}).get("subtotal_limitado", 0),
			barema_resultado.get("producao", {}).get("subtotal_bruto", 0),
			barema_resultado.get("producao", {}).get("subtotal_limitado", 0),
			barema_resultado.get("formacao_recursos_humanos", {}).get("subtotal_bruto", 0),
			barema_resultado.get("formacao_recursos_humanos", {}).get("subtotal_limitado", 0),
			barema_resultado.get("total_bruto", 0),
			barema_resultado.get("total_limitado", 0),
			payload_json,
			now,
		),
	)


def registrar_barema_extensao_discente(consulta_id, code, nome, barema_resultado):
	if not consulta_id or not code or not barema_resultado or not barema_resultado.get("success"):
		return

	init_database()
	payload_json = json.dumps(barema_resultado, ensure_ascii=False)
	now = _now_str()

	_q(
		"""
		INSERT INTO barema_extensao_discente (
			consulta_id, code, nome,
			atuacao_bruto, atuacao_limitado,
			producao_bruto, producao_limitado,
			eventos_bruto, eventos_limitado,
			total_bruto, total_limitado,
			barema_json, updated_at
		) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
		ON CONFLICT(code) DO UPDATE SET
			consulta_id       = excluded.consulta_id,
			nome              = excluded.nome,
			atuacao_bruto     = excluded.atuacao_bruto,
			atuacao_limitado  = excluded.atuacao_limitado,
			producao_bruto    = excluded.producao_bruto,
			producao_limitado = excluded.producao_limitado,
			eventos_bruto     = excluded.eventos_bruto,
			eventos_limitado  = excluded.eventos_limitado,
			total_bruto       = excluded.total_bruto,
			total_limitado    = excluded.total_limitado,
			barema_json       = excluded.barema_json,
			updated_at        = excluded.updated_at
		""",
		(
			consulta_id,
			code,
			nome or "",
			barema_resultado.get("atuacao_extensao", {}).get("subtotal_bruto", 0),
			barema_resultado.get("atuacao_extensao", {}).get("subtotal_limitado", 0),
			barema_resultado.get("producao", {}).get("subtotal_bruto", 0),
			barema_resultado.get("producao", {}).get("subtotal_limitado", 0),
			barema_resultado.get("participacao_eventos", {}).get("subtotal_bruto", 0),
			barema_resultado.get("participacao_eventos", {}).get("subtotal_limitado", 0),
			barema_resultado.get("total_bruto", 0),
			barema_resultado.get("total_limitado", 0),
			payload_json,
			now,
		),
	)


def obter_barema(tipo, code):
	"""Devolve o barema já gravado para um currículo, ou None."""
	init_database()
	tipo = normalizar_tipo(tipo)
	code = str(code or "").strip()
	if not code:
		return None

	result = _q(
		f"SELECT barema_json, nome FROM {_tabela_barema(tipo)} WHERE code = ?",
		(code,),
	)
	rows = _rows(result)
	if not rows or not rows[0]["barema_json"]:
		return None

	try:
		return {"barema": json.loads(rows[0]["barema_json"]), "nome": rows[0]["nome"]}
	except (TypeError, ValueError):
		return None


# Colunas de subtotal de cada modalidade de extensão, na ordem das seções.
_COLUNAS_AJUSTE = {
	"extensao_docente": (
		("titulacao", "titulacao"),
		("atuacao_extensao", "atuacao"),
		("producao", "producao"),
		("formacao_recursos_humanos", "formacao"),
	),
	"extensao_discente": (
		("atuacao_extensao", "atuacao"),
		("producao", "producao"),
		("participacao_eventos", "eventos"),
	),
}


def atualizar_barema_ajustado(tipo, code, barema):
	"""Regrava a pontuação de um currículo já consultado, marcando-a como
	ajustada manualmente. Não cria registro novo: se o currículo não foi
	consultado nessa modalidade, devolve False."""
	init_database()
	tipo = normalizar_tipo(tipo)
	colunas = _COLUNAS_AJUSTE.get(tipo)
	code = str(code or "").strip()

	if not colunas or not code or not barema or not barema.get("success"):
		return False

	campos = []
	valores = []
	for chave_secao, prefixo in colunas:
		secao = barema.get(chave_secao) or {}
		campos.append(f"{prefixo}_bruto = ?")
		valores.append(secao.get("subtotal_bruto", 0))
		campos.append(f"{prefixo}_limitado = ?")
		valores.append(secao.get("subtotal_limitado", 0))

	campos += ["total_bruto = ?", "total_limitado = ?", "barema_json = ?",
	           "ajuste_manual = 1", "updated_at = ?"]
	valores += [
		barema.get("total_bruto", 0),
		barema.get("total_limitado", 0),
		json.dumps(barema, ensure_ascii=False),
		_now_str(),
	]

	result = _q(
		f"UPDATE {_tabela_barema(tipo)} SET {', '.join(campos)} WHERE code = ?",
		(*valores, code),
	)
	return bool(getattr(result, "rows_affected", 1))


def hash_password(password, salt=None):
	if salt is None:
		salt = secrets.token_hex(16)
	pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
	return pwd_hash.hex(), salt


def create_user(username, password):
	init_database()
	username = str(username or "").strip()
	if not username:
		return False
	result = _q("SELECT id FROM users WHERE username = ?", (username,))
	if _rows(result):
		return False
	pwd_hash, salt = hash_password(password)
	_q(
		"INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
		(username, pwd_hash, salt),
	)
	return True


def verify_login(username, password):
	init_database()
	result = _q(
		"SELECT id, password_hash, salt FROM users WHERE username = ?",
		(str(username or "").strip(),),
	)
	rows = _rows(result)
	if not rows:
		return None

	user = rows[0]
	pwd_hash, _ = hash_password(password, user["salt"])
	if pwd_hash != user["password_hash"]:
		return None

	token = secrets.token_hex(32)
	_q(
		"INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
		(token, user["id"], _now_str()),
	)
	return token


def delete_session(token):
	_q("DELETE FROM sessions WHERE token = ?", (token,))


def get_user_id_by_token(token):
	result = _q("SELECT user_id FROM sessions WHERE token = ?", (token,))
	rows = _rows(result)
	if not rows:
		return None
	return _as_int(rows[0]["user_id"], rows[0]["user_id"])


# ---------------------------------------------------------------------------
# Dump completo (para backup / sync externo)
# ---------------------------------------------------------------------------

def dump_barema():
	"""Retorna todos os registros da tabela barema (sem paginação)."""
	init_database()
	result = _q(
		"SELECT id, consulta_id, code, nome, "
		"titulacao_bruto, titulacao_limitado, "
		"producao_bruto, producao_limitado, "
		"formacao_bruto, formacao_limitado, "
		"eventos_bruto, eventos_limitado, "
		"total_bruto, total_limitado, updated_at "
		"FROM barema ORDER BY id ASC"
	)
	return _rows(result)


def dump_barema_aeri():
	"""Retorna todos os registros da tabela barema_aeri (sem paginação)."""
	init_database()
	result = _q(
		"SELECT id, consulta_id, code, nome, "
		"participacoes_bruto, participacoes_limitado, "
		"producao_bruto, producao_limitado, "
		"representacao_bruto, representacao_limitado, "
		"programas_bruto, programas_limitado, "
		"total_bruto, total_limitado, updated_at "
		"FROM barema_aeri ORDER BY id ASC"
	)
	return _rows(result)


def dump_barema_extensao_docente():
	"""Retorna todos os registros do barema PIBEX docente (sem paginação)."""
	init_database()
	result = _q(
		"SELECT id, consulta_id, code, nome, "
		"titulacao_bruto, titulacao_limitado, "
		"atuacao_bruto, atuacao_limitado, "
		"producao_bruto, producao_limitado, "
		"formacao_bruto, formacao_limitado, "
		"total_bruto, total_limitado, updated_at "
		"FROM barema_extensao_docente ORDER BY id ASC"
	)
	return _rows(result)


def dump_barema_extensao_discente():
	"""Retorna todos os registros do barema PIBEX discente (sem paginação)."""
	init_database()
	result = _q(
		"SELECT id, consulta_id, code, nome, "
		"atuacao_bruto, atuacao_limitado, "
		"producao_bruto, producao_limitado, "
		"eventos_bruto, eventos_limitado, "
		"total_bruto, total_limitado, updated_at "
		"FROM barema_extensao_discente ORDER BY id ASC"
	)
	return _rows(result)


def dump_consultas():
	"""Retorna todos os registros da tabela consultas (sem paginação)."""
	init_database()
	result = _q(
		"SELECT id, url_informada, url_consultada, code, "
		"success, message, created_at, tipo "
		"FROM consultas ORDER BY id ASC"
	)
	return _rows(result)


def dump_editais():
	"""Retorna todos os editais cadastrados."""
	init_database()
	result = _q("SELECT tipo, ano, url, updated_at FROM editais")
	return _rows(result)
