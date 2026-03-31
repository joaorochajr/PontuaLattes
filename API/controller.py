import ast
import re
from datetime import date
from html import unescape

from database import registrar_barema, registrar_consulta
from service import getLattesCode, getLattesIndexHtml, getLattesPViewHtml


# Armazena o conteúdo retornado
conteudo_lattes = None


def _is_request_error(value):
	return isinstance(value, str) and (
		"http" in value.lower()
		or "erro" in value.lower()
		or "failed" in value.lower()
		or "timed out" in value.lower()
	)


def _normalizar_pontuacao(valor):
	return round(valor, 2)


def _obter_ano_minimo_barema():
	return date.today().year - 5


def _expandir_anos_ate_ano_vigente(anos):
	anos_validos = [int(ano) for ano in anos if str(ano).isdigit()]
	if not anos_validos:
		return anos

	ano_atual = date.today().year
	ultimo_ano = max(anos_validos)

	if ultimo_ano >= ano_atual:
		return anos

	anos_expandidos = list(anos)
	for ano in range(ultimo_ano + 1, ano_atual + 1):
		anos_expandidos.append(str(ano))

	return anos_expandidos


def _extrair_variaveis_js(html):
	variaveis = {}

	if not html:
		return variaveis

	for nome, conteudo in re.findall(r"var\s+([A-Za-z0-9_]+)\s*=\s*(\[.*?\]);", html, re.DOTALL):
		array_text = re.sub(r"\bnull\b", "None", conteudo)

		try:
			variaveis[nome] = ast.literal_eval(array_text)
		except (ValueError, SyntaxError):
			continue

	return variaveis


def _normalizar_serie(valores, tamanho):
	if valores in (None, [], [None], [[None]]):
		return [0] * tamanho

	if isinstance(valores, list) and len(valores) == 1 and isinstance(valores[0], list):
		valores = valores[0]

	serie = []
	for valor in valores:
		if valor is None:
			serie.append(0)
			continue

		try:
			serie.append(int(valor))
		except (TypeError, ValueError):
			serie.append(0)

	if len(serie) < tamanho:
		serie.extend([0] * (tamanho - len(serie)))

	return serie[:tamanho]


def _normalizar_anos(anos):
	if not anos:
		return []

	anchors = [
		(indice, int(ano))
		for indice, ano in enumerate(anos)
		if str(ano).isdigit()
	]

	if not anchors:
		return [str(ano).strip() for ano in anos]

	if len(anchors) == 1:
		base = anchors[0][1] - anchors[0][0]
		anos_normalizados = [str(base + indice) for indice in range(len(anos))]
		return _expandir_anos_ate_ano_vigente(anos_normalizados)

	sequencia_continua = all(
		indice_atual - indice_anterior == ano_atual - ano_anterior
		for (indice_anterior, ano_anterior), (indice_atual, ano_atual) in zip(anchors, anchors[1:])
	)

	if sequencia_continua:
		base = anchors[0][1] - anchors[0][0]
		anos_normalizados = [str(base + indice) for indice in range(len(anos))]
		return _expandir_anos_ate_ano_vigente(anos_normalizados)

	anos_normalizados = [str(ano).strip() for ano in anos]
	return _expandir_anos_ate_ano_vigente(anos_normalizados)


def _indices_validos_anos(anos, ano_minimo):
	anos = _normalizar_anos(anos)
	return [
		indice
		for indice, ano in enumerate(anos)
		if str(ano).isdigit() and int(ano) >= ano_minimo
	]


def extract_publications(index_html):
	if not index_html:
		return {"anos": [], "series": [], "anos_ultimos_5_anos": [], "series_ultimos_5_anos": [], "total_geral": 0}

	variaveis_js = _extrair_variaveis_js(index_html)
	years = _normalizar_anos(variaveis_js.get("barraAnosProducoesBibliograficas") or [])
	ano_minimo_periodo = _obter_ano_minimo_barema()
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
		values = _normalizar_serie(variaveis_js.get(variable_name), len(years))
		total = sum(values)

		if total == 0:
			continue

		series.append({
			"nome": label,
			"valores": values,
			"por_ano": dict(zip(years, values)),
			"total": total,
		})

	years_last_five_years = [
		year
		for year in years
		if str(year).isdigit() and int(year) >= ano_minimo_periodo
	]
	start_index = len(years) - len(years_last_five_years)

	series_last_five_years = []
	for item in series:
		values_last_five_years = item["valores"][start_index:] if years_last_five_years else []
		total_last_five_years = sum(values_last_five_years)

		if total_last_five_years == 0:
			continue

		series_last_five_years.append({
			"nome": item["nome"],
			"valores": values_last_five_years,
			"por_ano": dict(zip(years_last_five_years, values_last_five_years)),
			"total": total_last_five_years,
		})

	return {
		"anos": years,
		"series": series,
		"anos_ultimos_5_anos": years_last_five_years,
		"series_ultimos_5_anos": series_last_five_years,
		"total_geral": sum(item["total"] for item in series),
	}


def _somar_series_por_ano(variaveis_js, nome_anos, padroes, ano_minimo=None):
	ano_minimo = _obter_ano_minimo_barema() if ano_minimo is None else ano_minimo
	anos_originais = variaveis_js.get(nome_anos) or []
	anos = _normalizar_anos(anos_originais)
	indices_validos = [
		indice
		for indice, ano in enumerate(anos)
		if str(ano).isdigit() and int(ano) >= ano_minimo
	]

	if not indices_validos:
		return 0

	variaveis_encontradas = set()
	for nome_variavel in variaveis_js:
		nome_variavel_lower = nome_variavel.lower()
		if any(all(token in nome_variavel_lower for token in padrao) for padrao in padroes):
			variaveis_encontradas.add(nome_variavel)

	total = 0
	for nome_variavel in variaveis_encontradas:
		serie = _normalizar_serie(variaveis_js.get(nome_variavel), len(anos))
		total += sum(serie[indice] for indice in indices_validos)

	return total


def _somar_variaveis_por_ano(variaveis_js, nome_anos, nomes_variaveis, ano_minimo=None):
	ano_minimo = _obter_ano_minimo_barema() if ano_minimo is None else ano_minimo
	anos_originais = variaveis_js.get(nome_anos) or []
	anos = _normalizar_anos(anos_originais)
	indices_validos = [
		indice
		for indice, ano in enumerate(anos)
		if str(ano).isdigit() and int(ano) >= ano_minimo
	]

	if not indices_validos:
		return 0

	total = 0
	for nome_variavel in nomes_variaveis:
		serie = _normalizar_serie(variaveis_js.get(nome_variavel), len(anos))
		total += sum(serie[indice] for indice in indices_validos)

	return total


def _calcular_titulacao(preview_html):
	texto = unescape(re.sub(r"<[^>]+>", " ", preview_html or ""))
	texto = re.sub(r"\s+", " ", texto).strip().lower()

	if re.search(r"\bdoutor(?:a|ado)?\b|\bph\.?d\b", texto):
		return "Doutorado", 12

	if re.search(r"\bmestrado\b|\bmestre\b|\bmestra\b", texto):
		return "Mestrado", 8

	return "Não identificado", 0


def _extrair_nome_pessoa(preview_html):
	if not preview_html:
		return None

	match = re.search(r"var\s+nome\s*=\s*'([^']+)'", preview_html, re.IGNORECASE)
	if match:
		return unescape(match.group(1)).strip()

	texto = unescape(re.sub(r"<[^>]+>", " ", preview_html))
	texto = re.sub(r"\s+", " ", texto).strip()
	return texto[:255] if texto else None


def _contar_itens_numerados_secao(html, titulo_secao):
	if not html:
		return 0

	padrao_inicio = re.compile(re.escape(titulo_secao), re.IGNORECASE)
	inicio = padrao_inicio.search(html)
	if not inicio:
		return 0

	resto = html[inicio.start():]
	proximo_titulo = re.search(r'<h[1-6][^>]*class="[^"]*title-wrapper[^"]*"[^>]*>', resto, re.IGNORECASE)
	if proximo_titulo and proximo_titulo.start() > 0:
		bloco = resto[:proximo_titulo.start()]
	else:
		bloco = resto

	marcadores = re.findall(r">\s*(\d+)\.\s*<", bloco)
	if not marcadores:
		texto_bloco = unescape(re.sub(r"<[^>]+>", " ", bloco))
		marcadores = re.findall(r"\b(\d+)\.", texto_bloco)

	if not marcadores:
		return 0

	sequencia = []
	vistos = set()
	for marcador in marcadores:
		if marcador not in vistos:
			vistos.add(marcador)
			sequencia.append(marcador)

	return len(sequencia)


def _contar_patentes(preview_html, index_html):
	quantidade_preview = _contar_itens_numerados_secao(preview_html, "Patentes e registros")
	if quantidade_preview:
		return quantidade_preview

	quantidade_index = _contar_itens_numerados_secao(index_html, "Patentes e registros")
	if quantidade_index:
		return quantidade_index

	return 0


def _detalhar_item(quantidade, peso):
	pontos = quantidade * peso
	return {
		"quantidade": quantidade,
		"peso": peso,
		"pontos": _normalizar_pontuacao(pontos),
	}


def _obter_total_publicacoes_periodo(publicacoes, ano_minimo):
	series = publicacoes.get("series", []) if publicacoes else []
	totais = {}

	for item in series:
		por_ano = item.get("por_ano") or {}
		totais[item.get("nome")] = sum(
			int(valor)
			for ano, valor in por_ano.items()
			if str(ano).isdigit() and int(ano) >= ano_minimo
		)

	return totais


# Guarda o conteúdo da busca
def getConteudo(resultado):
	global conteudo_lattes
	conteudo_lattes = resultado
	return conteudo_lattes


def calcularBarema(resultado=None):
	dados_lattes = getConteudo(resultado) if resultado is not None else conteudo_lattes

	if not dados_lattes:
		return {
			"success": False,
			"message": "Nenhum conteúdo do Lattes foi carregado.",
		}

	if not dados_lattes.get("success"):
		return {
			"success": False,
			"message": "Não foi possível calcular o barema sem uma coleta válida.",
			"detalhe": dados_lattes.get("message"),
		}

	preview_html = dados_lattes.get("preview_html") or ""
	index_html = dados_lattes.get("index_html") or ""
	publicacoes = dados_lattes.get("publicacoes") or {}
	variaveis_js = _extrair_variaveis_js(index_html)
	ano_minimo = _obter_ano_minimo_barema()
	publicacoes_periodo = _obter_total_publicacoes_periodo(publicacoes, ano_minimo)

	nivel_titulacao, pontos_titulacao = _calcular_titulacao(preview_html)

	quantidade_patentes = _somar_variaveis_por_ano(
		variaveis_js,
		"barraAnosPatentes",
		["valoesPatentes", "valoesOutrasPatentesRegistros", "valoesCultivarProtegida"],
	)
	if quantidade_patentes == 0:
		quantidade_patentes = _contar_patentes(preview_html, index_html)
	quantidade_producao_artistica = _somar_series_por_ano(
		variaveis_js,
		"barraAnosProducoesCulturais",
		[("cultur",), ("artist",)],
	)
	quantidade_trabalho_tecnico = _somar_variaveis_por_ano(
		variaveis_js,
		"barraAnosProducoesTecnicas",
		["valoesTrabalhosTecnicos"],
	)
	quantidade_apresentacao_trabalho = _somar_variaveis_por_ano(
		variaveis_js,
		"barraAnosProducoesTecnicas",
		["valoesApresentacoesDeTrabalhos"],
	)
	quantidade_orientacao_doutorado = _somar_variaveis_por_ano(
		variaveis_js,
		"barraAnosOrientacoes",
		["valoresDoutorado"],
	)
	quantidade_orientacao_mestrado = _somar_variaveis_por_ano(
		variaveis_js,
		"barraAnosOrientacoes",
		["valoresMestrado"],
	)
	quantidade_orientacao_demais = _somar_variaveis_por_ano(
		variaveis_js,
		"barraAnosOrientacoes",
		["valoresOutrasOrientacoes"],
	)

	producao_itens = {
		"Artigo completo publicado em periódico": _detalhar_item(
			publicacoes_periodo.get("Artigos completos publicados em periódicos", 0),
			3,
		),
		"Livro": _detalhar_item(publicacoes_periodo.get("Livros", 0), 3),
		"Capítulo de livro": _detalhar_item(publicacoes_periodo.get("Capítulos de livros", 0), 2),
		"Resumo publicado em periódico": _detalhar_item(
			publicacoes_periodo.get("Resumos publicados em periódicos", 0),
			1.5,
		),
		"Resumo e trabalho publicado em Anais de evento": _detalhar_item(
			publicacoes_periodo.get("Trabalhos publicados em anais de evento", 0)
			+ publicacoes_periodo.get("Resumos publicados em anais de eventos", 0),
			1,
		),
		"Outras produções bibliográficas": _detalhar_item(
			publicacoes_periodo.get("Outras produções bibliográficas", 0),
			1,
		),
		"Patente": _detalhar_item(quantidade_patentes, 3),
		"Produção artística/cultural": _detalhar_item(quantidade_producao_artistica, 3),
		"Trabalho Técnico": _detalhar_item(quantidade_trabalho_tecnico, 1),
	}
	producao_bruta = _normalizar_pontuacao(sum(item["pontos"] for item in producao_itens.values()))
	producao_limitada = min(producao_bruta, 30)
	titulacao_limitada = min(pontos_titulacao, 12)

	formacao_itens = {
		"Doutorado (orientador)": _detalhar_item(quantidade_orientacao_doutorado, 1.5),
		"Mestrado (orientador)": _detalhar_item(quantidade_orientacao_mestrado, 1),
		"IC, IT, TCC, Especialização, PIBID, PIBEX, PET, Monitoria": _detalhar_item(
			quantidade_orientacao_demais,
			0.5,
		),
	}
	formacao_bruta = _normalizar_pontuacao(sum(item["pontos"] for item in formacao_itens.values()))
	formacao_limitada = min(formacao_bruta, 12)

	eventos_itens = {
		"Apresentação de trabalho": _detalhar_item(quantidade_apresentacao_trabalho, 0.5),
	}
	eventos_bruto = _normalizar_pontuacao(sum(item["pontos"] for item in eventos_itens.values()))
	eventos_limitado = min(eventos_bruto, 6)

	total_bruto = _normalizar_pontuacao(pontos_titulacao + producao_bruta + formacao_bruta + eventos_bruto)
	total_limitado = _normalizar_pontuacao(
		titulacao_limitada + producao_limitada + formacao_limitada + eventos_limitado
	)

	observacoes = []
	if pontos_titulacao == 0:
		observacoes.append("Titulação não identificada automaticamente.")
	if quantidade_patentes == 0:
		observacoes.append(f"Nenhuma patente identificada nos índices carregados a partir de {ano_minimo}.")
	if quantidade_orientacao_doutorado == 0 and quantidade_orientacao_mestrado == 0 and quantidade_orientacao_demais == 0:
		observacoes.append(f"Nenhuma orientação concluída foi encontrada nos índices carregados a partir de {ano_minimo}.")

	return {
		"success": True,
		"message": "Barema calculado com sucesso.",
		"titulacao": {
			"nivel_maximo": nivel_titulacao,
			"subtotal_bruto": _normalizar_pontuacao(pontos_titulacao),
			"subtotal_limitado": titulacao_limitada,
		},
		"producao": {
			"itens": producao_itens,
			"subtotal_bruto": producao_bruta,
			"subtotal_limitado": producao_limitada,
		},
		"formacao_recursos_humanos": {
			"itens": formacao_itens,
			"subtotal_bruto": formacao_bruta,
			"subtotal_limitado": formacao_limitada,
		},
		"participacao_eventos_comite": {
			"itens": eventos_itens,
			"subtotal_bruto": eventos_bruto,
			"subtotal_limitado": eventos_limitado,
		},
		"total_bruto": total_bruto,
		"total_limitado": total_limitado,
		"observacoes": observacoes,
	}


# Busca os dados no service
def buscaLattes(url):
	code = getLattesCode(url)

	if not code or _is_request_error(code):
		resultado = {
			"success": False,
			"url": url,
			"code": code,
			"preview_html": None,
			"index_html": None,
			"publicacoes": {"anos": [], "series": [], "anos_ultimos_5_anos": [], "series_ultimos_5_anos": [], "total_geral": 0},
			"message": "Não foi possível encontrar o código interno do currículo.",
		}
		conteudo = getConteudo(resultado)
		conteudo["barema"] = calcularBarema()
		registrar_consulta(url, conteudo)
		return conteudo

	preview_html = getLattesPViewHtml(code)
	index_html = getLattesIndexHtml(code)
	nome = _extrair_nome_pessoa(preview_html)
	resultado = {
		"success": bool(index_html),
		"url": url,
		"code": code,
		"nome": nome,
		"preview_html": preview_html,
		"index_html": index_html,
		"publicacoes": extract_publications(index_html),
		"message": "Coleta realizada com sucesso." if index_html else "Não foi possível carregar os índices do currículo.",
	}

	conteudo = getConteudo(resultado)
	conteudo["barema"] = calcularBarema()
	consulta_id = registrar_consulta(url, conteudo)
	registrar_barema(consulta_id, conteudo.get("code"), conteudo.get("nome"), conteudo.get("barema"))
	return conteudo
