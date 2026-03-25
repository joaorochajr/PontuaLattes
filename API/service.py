import re

import requests


DEFAULT_HEADERS = {
	"User-Agent": (
		"Mozilla/5.0 (X11; Linux x86_64) "
		"AppleWebKit/537.36 (KHTML, like Gecko) "
		"Chrome/123.0.0.0 Safari/537.36"
	),
	"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
	"Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
	"Connection": "close",
}


def _normalizar_url(Url):
	Url = str(Url or "").strip()
	if not Url:
		return Url

	if not re.match(r"^https?://", Url, re.IGNORECASE):
		return f"https://{Url}"

	return Url


# Encontra o index único atribuido pela plataforma LATTES
def getLattesCode(Url):
	html = None
	Url = _normalizar_url(Url)

	for _ in range(5):
		try:
			response = requests.get(Url, headers=DEFAULT_HEADERS, timeout=15)
			response.raise_for_status()
			html = response.text
			break
		except requests.RequestException as e:
			return str(e)

	Txt = '<input type="hidden" name="id" value="'
	Str = html.find(Txt) + len(Txt) if html is not None else len(Txt) - 1
	End = html.find('"', Str) if html is not None else -1
	return html[Str:End] if html and Str >= len(Txt) and End != -1 else ""


# Encontra o HTML da página do preview
def getLattesPViewHtml(code):
	html = None
	Url = f"http://buscatextual.cnpq.br/buscatextual/preview.do?metodo=apresentar&id={code}"

	for _ in range(5):
		try:
			response = requests.get(Url, headers=DEFAULT_HEADERS, timeout=15)
			response.raise_for_status()
			response.encoding = "ISO-8859-1"
			html = response.text
			break
		except requests.RequestException:
			continue

	return html


# Encontra o HTML da página dos indices de produção
def getLattesIndexHtml(code):
	html = None
	Url = f"http://buscatextual.cnpq.br/buscatextual/graficos.do?metodo=apresentar&codRHCript={code}"

	for _ in range(1):
		try:
			response = requests.get(Url, headers=DEFAULT_HEADERS, timeout=15)
			response.raise_for_status()
			html = response.text
			break
		except requests.RequestException:
			continue

	return html