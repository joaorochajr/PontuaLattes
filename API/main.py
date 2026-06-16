import json
import mimetypes
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs


from controller import buscaLattes
from database import (
    init_database, get_consultas, count_consultas, get_top5_consultas,
    verify_login, get_user_id_by_token, delete_session, get_consultas_por_dia,
    get_editais, salvar_edital,
    dump_barema, dump_barema_aeri, dump_consultas, dump_editais,
)


BASE_DIR = Path(__file__).resolve().parent
SPA_DIR = BASE_DIR.parent / "SPA"
INDEX_FILE = SPA_DIR / "index.html"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))


def _sheets_configured():
    return bool(
        os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "").strip()
        and os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    )


def _try_sync_sheets():
    """Sincroniza todo o banco Turso com a planilha Google Sheets.
    Erros são suprimidos para não afetar a resposta da API."""
    if not _sheets_configured():
        return
    try:
        from google_sheets_store import sync_all
        sync_all(
            dump_barema(),
            dump_barema_aeri(),
            dump_consultas(),
            dump_editais(),
        )
    except Exception as exc:
        print(f"[sheets] Falha na sincronização: {exc}", flush=True)


class ICCollectHandler(BaseHTTPRequestHandler):
    def _get_authenticated_user_id(self):
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ", 1)[1]
        return get_user_id_by_token(token)
    
    def _resolve_static_path(self, request_path):
        relative_path = urlparse(request_path).path.lstrip("/") or "index.html"

       
        file_path = (SPA_DIR / relative_path).resolve()

        try:
            file_path.relative_to(SPA_DIR.resolve())
        except ValueError:
            return None

       
        if file_path.exists() and file_path.is_file():
            return file_path

       
        html_path = (SPA_DIR / f"{relative_path}.html").resolve()

        try:
            html_path.relative_to(SPA_DIR.resolve())
        except ValueError:
            return None

        if html_path.exists() and html_path.is_file():
            return html_path

        return None

    def _send_json(self, payload, status=HTTPStatus.OK):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, content, status=HTTPStatus.OK):
        body = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path, status=HTTPStatus.OK):
        body = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(file_path.name)
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):

        parsed_url = urlparse(self.path)
        path = parsed_url.path
        qs = parse_qs(parsed_url.query)
    
        if path == "/api/editais":
            editais = get_editais()
            self._send_json({"success": True, "ic": editais["ic"], "aeri": editais["aeri"]})
            return

        if path == "/health":
            self._send_json({"status": "ok"})
            return
        
        if path == "/api/consultas/top5":

            # Verifica autenticação
            if not self._get_authenticated_user_id():
                self._send_json(
                    {"success": False, "message": "Não autorizado."},
                    HTTPStatus.UNAUTHORIZED
                )
                return

            tipo = qs.get("tipo", ["ic"])[0]
            if tipo not in ("ic", "aeri"):
                tipo = "ic"
            dados = get_top5_consultas(tipo)

            # Retorna o JSON
            self._send_json({
                "success": True,
                "dados": dados
            })

            return
        
        if path == "/api/consultas/dia":

            # Verifica autenticação
            if not self._get_authenticated_user_id():
                self._send_json(
                    {"success": False, "message": "Não autorizado."},
                    HTTPStatus.UNAUTHORIZED
                )
                return

            # Chama a função do banco
            dados = get_consultas_por_dia()

            self._send_json({
                "success": True,
                "dados": dados
            })
            return

        if path == "/api/consultas":

            if not self._get_authenticated_user_id():
                self._send_json(
                    {"success": False, "message": "Não autorizado."},
                    HTTPStatus.UNAUTHORIZED
                )
                return

            page = int(qs.get("page", ["1"])[0])
            per_page = int(qs.get("per_page", ["10"])[0])

            success = qs.get("success", [None])[0]
            success = int(success) if success is not None else None

            tipo = qs.get("tipo", ["ic"])[0]
            if tipo not in ("ic", "aeri"):
                tipo = "ic"

            consultas = get_consultas(success, page, per_page, tipo)
            total = count_consultas(success, tipo)

            total_pages = (total + per_page - 1) // per_page

            self._send_json({
                "success": True,
                "consultas": consultas,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages
            })

            return
            
        
        if path == "/api/consultas/resumo":

            if not self._get_authenticated_user_id():
                self._send_json(
                    {"success": False, "message": "Não autorizado."},
                    HTTPStatus.UNAUTHORIZED
                )
                return

            # Total geral
            total = count_consultas()
            # Total de sucessos
            sucessos = count_consultas(1)
            # Total de falhas
            falhas = count_consultas(0)

            self._send_json({
                "success": True,
                "total": total,
                "sucessos": sucessos,
                "falhas": falhas
            })

            return
    
        file_path = self._resolve_static_path(self.path)
        if file_path:
            self._send_file(file_path)
            return

        if path in ("/", "/index.html") and not INDEX_FILE.exists():
            self._send_html("<h1>Arquivo index.html não encontrado.</h1>", HTTPStatus.NOT_FOUND)
            return

        self._send_json({"success": False, "message": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)

    def do_POST(self):
        
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"

        try:
            payload = json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            self._send_json({"success": False, "message": "Corpo da requisição inválido."}, HTTPStatus.BAD_REQUEST)
            return

        
        if self.path == "/api/register":
            self._send_json({"success": False, "message": "Cadastro desabilitado. Use o usuário padrão do sistema."}, HTTPStatus.FORBIDDEN)
            return

   
        elif self.path == "/api/login":
            username = payload.get("username", "").strip()
            password = payload.get("password", "")
            
            token = verify_login(username, password)
            if token:
                self._send_json({"success": True, "token": token, "message": "Login efetuado com sucesso."})
            else:
                self._send_json({"success": False, "message": "Usuário ou senha inválidos!"}, HTTPStatus.UNAUTHORIZED)
            return

       
        elif self.path == "/api/logout":
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                delete_session(token)
            self._send_json({"success": True, "message": "Sessão terminada."})
            return

        elif self.path == "/api/lattes":
            url_lattes = str(payload.get("url") or "").strip()
            if not url_lattes:
                self._send_json({"success": False, "message": "Informe a URL completa ou o código.", "code": None}, HTTPStatus.BAD_REQUEST)
                return

            tipo_lattes = payload.get("tipo", "ic")
            if tipo_lattes not in ("ic", "aeri"):
                tipo_lattes = "ic"

            try:
                resultado = buscaLattes(url_lattes, tipo_lattes)
                status = HTTPStatus.OK if resultado.get("success") else HTTPStatus.BAD_GATEWAY
                self._send_json(resultado, status)
                if resultado.get("success"):
                    _try_sync_sheets()
            except Exception as exc:
                self._send_json(
                    {
                        "success": False,
                        "message": f"Erro interno ao processar a consulta: {exc}",
                    },
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        elif self.path == "/api/sync-sheets":
            if not self._get_authenticated_user_id():
                self._send_json(
                    {"success": False, "message": "Não autorizado."},
                    HTTPStatus.UNAUTHORIZED,
                )
                return
            if not _sheets_configured():
                self._send_json(
                    {"success": False, "message": "Variáveis do Google Sheets não configuradas."},
                    HTTPStatus.BAD_REQUEST,
                )
                return
            try:
                _try_sync_sheets()
                self._send_json({"success": True, "message": "Planilha sincronizada com sucesso."})
            except Exception as exc:
                self._send_json(
                    {"success": False, "message": f"Erro na sincronização: {exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            return

        self._send_json({"success": False, "message": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)

    def do_PUT(self):
        if not self._get_authenticated_user_id():
            self._send_json({"success": False, "message": "Não autorizado."}, HTTPStatus.UNAUTHORIZED)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            payload = json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            self._send_json({"success": False, "message": "Corpo da requisição inválido."}, HTTPStatus.BAD_REQUEST)
            return

        if self.path == "/api/editais":
            tipo = str(payload.get("tipo", "")).strip()
            ano  = str(payload.get("ano", "")).strip()
            url  = str(payload.get("url", "")).strip()
            if tipo not in ("ic", "aeri"):
                self._send_json({"success": False, "message": "tipo deve ser 'ic' ou 'aeri'."}, HTTPStatus.BAD_REQUEST)
                return
            salvar_edital(tipo, ano, url)
            self._send_json({"success": True, "message": "Edital salvo com sucesso."})
            return

        self._send_json({"success": False, "message": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)

def run():
    init_database()
    host = os.getenv("HOST", HOST)
    port = int(os.getenv("PORT", str(PORT)))
    server = ThreadingHTTPServer((host, port), ICCollectHandler)
    print(f"Servidor disponível em http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
