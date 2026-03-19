import requests
import re
import time
import ast
from urllib.parse import urlparse


def _is_request_error(value):
    return isinstance(value, str) and (
        "http" in value.lower()
        or "erro" in value.lower()
        or "failed" in value.lower()
        or "timed out" in value.lower()
    )


def normalize_lattes_url(url):
    parsed = urlparse(url.strip())

    if not parsed.scheme:
        return f"http://{url.strip()}"

    if parsed.scheme == "https" and parsed.netloc.lower() == "lattes.cnpq.br":
        return parsed._replace(scheme="http").geturl()

    return url.strip()

# Busca o código do Lattes
def get_lattes_code(url):
    url = normalize_lattes_url(url)
    html = ""
    for i in range(5):
        try:
            # Faz a requisição
            resposta = requests.get(url, timeout=10)
            resposta.raise_for_status()  # Verifica erros HTTP
            html = resposta.text
            break
        except requests.RequestException as e:
            if i == 4:  # Retorna o erro na última tentativa
                return str(e)
            time.sleep(1)  # Aguarda para tentar de novo

    # Busca o valor do ID
    padrao = r'<input type="hidden" name="id" value="([^"]+)"'
    match = re.search(padrao, html)
    
    if match:
        return match.group(1)  # Retorna o código
    return None

# Busca o HTML de preview
def get_lattes_pview_html(code):
    url = f"http://buscatextual.cnpq.br/buscatextual/preview.do?metodo=apresentar&id={code}"
    for _ in range(5):
        try:
            resposta = requests.get(url, timeout=10)
            resposta.encoding = 'ISO-8859-1'  # Define o charset
            return resposta.text
        except requests.RequestException:
            time.sleep(1)
    return None

# Busca o HTML dos índices
def get_lattes_index_html(code):
    url = f"http://buscatextual.cnpq.br/buscatextual/graficos.do?metodo=apresentar&codRHCript={code}"
    for _ in range(5):
        try:
            resposta = requests.get(url, timeout=10)
            return resposta.text
        except requests.RequestException:
            time.sleep(1)
    return None


def _extract_js_array(html, variable_name):
    match = re.search(rf"var\s+{variable_name}\s*=\s*(\[.*?\]);", html, re.DOTALL)

    if not match:
        return None

    array_text = re.sub(r"\bnull\b", "None", match.group(1))

    try:
        return ast.literal_eval(array_text)
    except (ValueError, SyntaxError):
        return None


def _normalize_series_values(values, size):
    if values in (None, [None], [[None]], []):
        return [0] * size

    if isinstance(values, list) and len(values) == 1 and isinstance(values[0], list):
        values = values[0]

    normalized = []
    for value in values:
        if value is None:
            normalized.append(0)
        else:
            normalized.append(int(value))

    if len(normalized) < size:
        normalized.extend([0] * (size - len(normalized)))

    return normalized[:size]


def extract_publications(index_html):
    if not index_html:
        return {"anos": [], "series": [], "series_desde_2021": [], "total_geral": 0}

    years = _extract_js_array(index_html, "barraAnosProducoesBibliograficas") or []
    labels = {
        "valoresArtigosPublicadosPeriodicos": "Artigos completos publicados em periódicos",
        "valoresArtigosResumidosPublicadosPeriodicos": "Resumos publicados em periódicos",
        "valoresTrabalhosPublicadosEventos": "Trabalhos publicados em anais de evento",
        "valoresTrabalhosResumidosPublicadosEventos": "Resumos publicados em anais de eventos",
        "valoresLivros": "Livros",
        "valoresCapitulos": "Capítulos de livros",
        "valoresOutrasProducoesBibliograficas": "Outras produções bibliográficas",
    }

    series = []
    for variable_name, label in labels.items():
        values = _normalize_series_values(_extract_js_array(index_html, variable_name), len(years))
        total = sum(values)

        if total == 0:
            continue

        series.append({
            "nome": label,
            "valores": values,
            "por_ano": dict(zip(years, values)),
            "total": total,
        })

    years_since_2021 = [year for year in years if str(year).isdigit() and int(year) >= 2021]
    start_index = len(years) - len(years_since_2021)

    series_since_2021 = []
    for item in series:
        values_since_2021 = item["valores"][start_index:] if years_since_2021 else []
        total_since_2021 = sum(values_since_2021)

        if total_since_2021 == 0:
            continue

        series_since_2021.append({
            "nome": item["nome"],
            "valores": values_since_2021,
            "por_ano": dict(zip(years_since_2021, values_since_2021)),
            "total": total_since_2021,
        })

    return {
        "anos": years,
        "series": series,
        "anos_desde_2021": years_since_2021,
        "series_desde_2021": series_since_2021,
        "total_geral": sum(item["total"] for item in series),
    }


def collect_lattes_data(url):
    normalized_url = normalize_lattes_url(url)
    code = get_lattes_code(normalized_url)

    if not code or _is_request_error(code):
        return {
            "success": False,
            "url": normalized_url,
            "code": code,
            "preview_html": None,
            "index_html": None,
            "message": "Não foi possível encontrar o código interno do currículo.",
        }

    preview_html = get_lattes_pview_html(code)
    index_html = get_lattes_index_html(code)
    publications = extract_publications(index_html)

    return {
        "success": True,
        "url": normalized_url,
        "code": code,
        "preview_html": preview_html,
        "index_html": index_html,
        "publicacoes": publications,
        "message": "Coleta realizada com sucesso.",
    }

# Teste do script
if __name__ == "__main__":
    # URL de teste
    link_lattes = "http://lattes.cnpq.br/1431810842888468" 

    print(f"Buscando dados para: {link_lattes}")
    resultado = collect_lattes_data(link_lattes)

    if resultado["success"]:
        print(f"Código interno encontrado: {resultado['code']}")
        print(
            f"HTML do preview coletado: {len(resultado['preview_html']) if resultado['preview_html'] else 0} caracteres."
        )
        print(
            f"HTML dos índices coletado: {len(resultado['index_html']) if resultado['index_html'] else 0} caracteres."
        )
    else:
        print(resultado["message"], resultado["code"])