import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from database import get_all_consultas
from pathlib import Path



from controller import buscaLattes
from database import init_database


BASE_DIR = Path(__file__).resolve().parent
SPA_DIR = BASE_DIR.parent / "SPA"
INDEX_FILE = SPA_DIR / "index.html"
HOST = "127.0.0.1"
PORT = 8000


class ICCollectHandler(BaseHTTPRequestHandler):
    
    def _resolve_static_path(self, request_path):
        relative_path = request_path.lstrip("/") or "index.html"

       
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
        if self.path == "/health":
            self._send_json({"status": "ok"})
            return
        
        if self.path.startswith("/api/consultas"):
            qs = parse_qs(urlparse(self.path).query)

            start_date = qs.get("start_date", [None])[0]
            end_date = qs.get("end_date", [None])[0]
            success = qs.get("success", [None])[0]
            success = int(success) if success is not None else None

            consultas = get_all_consultas(start_date, end_date, success)
            self._send_json({"success": True, "consultas": consultas})
            return


        file_path = self._resolve_static_path(self.path)
        if file_path:
            self._send_file(file_path)
            return

        if self.path in ("/", "/index.html") and not INDEX_FILE.exists():
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
            username = payload.get("username", "").strip()
            password = payload.get("password", "")
            
            if not username or not password:
                self._send_json({"success": False, "message": "Preencha todos os campos."}, HTTPStatus.BAD_REQUEST)
                return
                
            from database import create_user
            if create_user(username, password):
                self._send_json({"success": True, "message": "Usuário registado com sucesso!"})
            else:
                self._send_json({"success": False, "message": "O utilizador já existe."}, HTTPStatus.CONFLICT)
            return

   
        elif self.path == "/api/login":
            username = payload.get("username", "").strip()
            password = payload.get("password", "")
            
            from database import verify_login
            token = verify_login(username, password)
            if token:
                self._send_json({"success": True, "token": token, "message": "Login efetuado com sucesso."})
            else:
                self._send_json({"success": False, "message": "Utilizador ou palavra-passe inválidos."}, HTTPStatus.UNAUTHORIZED)
            return

       
        elif self.path == "/api/logout":
            auth_header = self.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                from database import delete_session
                delete_session(token)
            self._send_json({"success": True, "message": "Sessão terminada."})
            return

        elif self.path == "/api/lattes":
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                self._send_json({"success": False, "message": "Não autorizado. Faça login primeiro."}, HTTPStatus.UNAUTHORIZED)
                return
            
            token = auth_header.split(" ")[1]
            from database import get_user_id_by_token
            if not get_user_id_by_token(token):
                self._send_json({"success": False, "message": "Sessão inválida ou expirada."}, HTTPStatus.UNAUTHORIZED)
                return

           
            url_lattes = str(payload.get("url") or "").strip()
            if not url_lattes:
                self._send_json({"success": False, "message": "Informe a URL completa ou o código.", "code": None}, HTTPStatus.BAD_REQUEST)
                return

            from controller import buscaLattes
            resultado = buscaLattes(url_lattes)
            status = HTTPStatus.OK if resultado.get("success") else HTTPStatus.BAD_GATEWAY
            self._send_json(resultado, status)
            return

        self._send_json({"success": False, "message": "Rota não encontrada."}, HTTPStatus.NOT_FOUND)
def run():
    init_database()
    server = ThreadingHTTPServer((HOST, PORT), ICCollectHandler)
    print(f"Servidor disponível em http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
