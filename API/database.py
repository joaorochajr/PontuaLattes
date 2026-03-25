import json
import sqlite3
from pathlib import Path
import hashlib
import secrets


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "DB" / "database.db"

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	username TEXT UNIQUE NOT NULL,
	password_hash TEXT NOT NULL,
	salt TEXT NOT NULL
)
"""
CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
	token TEXT PRIMARY KEY,
	user_id INTEGER NOT NULL,
	created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
)
"""

CREATE_CONSULTAS_TABLE = """
CREATE TABLE IF NOT EXISTS consultas (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	url_informada TEXT NOT NULL,
	url_consultada TEXT,
	code TEXT,
	success INTEGER NOT NULL DEFAULT 0,
	message TEXT,
	created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


CREATE_BAREMA_TABLE = """
CREATE TABLE IF NOT EXISTS barema (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	consulta_id INTEGER NOT NULL,
	code TEXT NOT NULL UNIQUE,
	nome TEXT,
	titulacao_bruto REAL DEFAULT 0,
	titulacao_limitado REAL DEFAULT 0,
	producao_bruto REAL DEFAULT 0,
	producao_limitado REAL DEFAULT 0,
	formacao_bruto REAL DEFAULT 0,
	formacao_limitado REAL DEFAULT 0,
	eventos_bruto REAL DEFAULT 0,
	eventos_limitado REAL DEFAULT 0,
	total_bruto REAL DEFAULT 0,
	total_limitado REAL DEFAULT 0,
	barema_json TEXT,
	updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
	FOREIGN KEY (consulta_id) REFERENCES consultas(id) ON DELETE CASCADE
)
"""


CREATE_CONSULTAS_CODE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_consultas_code ON consultas(code)
"""


CREATE_CONSULTAS_CREATED_AT_INDEX = """
CREATE INDEX IF NOT EXISTS idx_consultas_created_at ON consultas(created_at)
"""


CREATE_BAREMA_CONSULTA_INDEX = """
CREATE INDEX IF NOT EXISTS idx_barema_consulta_id ON barema(consulta_id)
"""


def _get_connection():
	DB_PATH.parent.mkdir(parents=True, exist_ok=True)
	connection = sqlite3.connect(DB_PATH)
	connection.row_factory = sqlite3.Row
	return connection


def _ensure_column(connection, table_name, column_name, definition):
	columns = {
		row["name"]
		for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
	}

	if column_name not in columns:
		connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def init_database():
	with _get_connection() as connection:
		connection.execute("PRAGMA foreign_keys = ON")
		connection.execute(CREATE_CONSULTAS_TABLE)
		connection.execute(CREATE_BAREMA_TABLE)
		_ensure_column(connection, "barema", "nome", "TEXT")
		connection.execute(CREATE_CONSULTAS_CODE_INDEX)
		connection.execute(CREATE_CONSULTAS_CREATED_AT_INDEX)
		connection.execute(CREATE_BAREMA_CONSULTA_INDEX)
		connection.execute(CREATE_USERS_TABLE)
		connection.execute(CREATE_SESSIONS_TABLE)
		connection.commit()


def registrar_consulta(url_informada, resultado):
	init_database()

	with _get_connection() as connection:
		connection.execute("PRAGMA foreign_keys = ON")
		cursor = connection.execute(
			"""
			INSERT INTO consultas (url_informada, url_consultada, code, success, message)
			VALUES (?, ?, ?, ?, ?)
			""",
			(
				str(url_informada or "").strip(),
				resultado.get("url"),
				resultado.get("code"),
				1 if resultado.get("success") else 0,
				resultado.get("message"),
			),
		)
		connection.commit()
		return cursor.lastrowid

def get_all_consultas(start_date=None, end_date=None, success=None):
  
    init_database()
    query = """
        SELECT id, url_informada, url_consultada, code, success, message, created_at
        FROM consultas
        WHERE 1=1
    """
    params = []

    if start_date:
        query += " AND date(created_at) >= date(?)"
        params.append(start_date)

    if end_date:
        query += " AND date(created_at) <= date(?)"
        params.append(end_date)

    if success is not None:
        query += " AND success = ?"
        params.append(int(success))

    query += " ORDER BY created_at DESC"

    with _get_connection() as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.execute(query, params)
        rows = cursor.fetchall()

    # transforma em lista de dicionários
    return [dict(row) for row in rows]



def registrar_barema(consulta_id, code, nome, barema_resultado):
	if not consulta_id or not code or not barema_resultado or not barema_resultado.get("success"):
		return

	init_database()
	payload_json = json.dumps(barema_resultado, ensure_ascii=False)

	with _get_connection() as connection:
		connection.execute("PRAGMA foreign_keys = ON")
		connection.execute(
			"""
			INSERT INTO barema (
				consulta_id,
				code,
				nome,
				titulacao_bruto,
				titulacao_limitado,
				producao_bruto,
				producao_limitado,
				formacao_bruto,
				formacao_limitado,
				eventos_bruto,
				eventos_limitado,
				total_bruto,
				total_limitado,
				barema_json,
				updated_at
			)
			VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
			ON CONFLICT(code) DO UPDATE SET
				consulta_id = excluded.consulta_id,
				nome = excluded.nome,
				titulacao_bruto = excluded.titulacao_bruto,
				titulacao_limitado = excluded.titulacao_limitado,
				producao_bruto = excluded.producao_bruto,
				producao_limitado = excluded.producao_limitado,
				formacao_bruto = excluded.formacao_bruto,
				formacao_limitado = excluded.formacao_limitado,
				eventos_bruto = excluded.eventos_bruto,
				eventos_limitado = excluded.eventos_limitado,
				total_bruto = excluded.total_bruto,
				total_limitado = excluded.total_limitado,
				barema_json = excluded.barema_json,
				updated_at = CURRENT_TIMESTAMP
			""",
			(
				consulta_id,
				code,
				nome,
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
			),
		)
		connection.commit()
def hash_password(password, salt=None):
	if salt is None:
		salt = secrets.token_hex(16)
	
	pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
	return pwd_hash.hex(), salt

def create_user(username, password):
	init_database()
	pwd_hash, salt = hash_password(password)
	try:
		with _get_connection() as connection:
			connection.execute(
				"INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
				(username, pwd_hash, salt)
			)
			connection.commit()
			return True
	except sqlite3.IntegrityError:
		return False # Usuário já existe

def verify_login(username, password):
	with _get_connection() as connection:
		cursor = connection.execute("SELECT id, password_hash, salt FROM users WHERE username = ?", (username,))
		user = cursor.fetchone()
		if not user:
			return None
		
		pwd_hash, _ = hash_password(password, user["salt"])
		if pwd_hash == user["password_hash"]:
			token = secrets.token_hex(32)
			connection.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user["id"]))
			connection.commit()
			return token
		return None
def delete_session(token):
	with _get_connection() as connection:
		connection.execute("DELETE FROM sessions WHERE token = ?", (token,))
		connection.commit()

def get_user_id_by_token(token):
	with _get_connection() as connection:
		cursor = connection.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
		session = cursor.fetchone()
		return session["user_id"] if session else None
def get_historico_geral():
	with _get_connection() as connection:
		cursor = connection.execute(
			"""
			SELECT c.id, c.code, c.url_informada, c.created_at, c.success, b.nome, b.total_limitado 
			FROM consultas c 
			LEFT JOIN barema b ON c.code = b.code 
			ORDER BY c.created_at DESC
			"""
		)
		return [dict(row) for row in cursor.fetchall()]