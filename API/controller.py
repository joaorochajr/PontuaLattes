import ast
import re
from datetime import date
from html import unescape

from database import (
	registrar_barema,
	registrar_barema_aeri,
	registrar_barema_extensao_discente,
	registrar_barema_extensao_docente,
	registrar_consulta,
)
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


def _e_variavel_de_anos(nome_variavel):
	# As series de rotulos ("barraAnos...") nao sao producoes; se entrarem na
	# busca por padroes, os proprios anos acabam somados como pontuacao.
	return nome_variavel.lower().startswith("barraanos")


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
		if _e_variavel_de_anos(nome_variavel):
			continue
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


def _detalhar_item(quantidade, peso, teto_pontos=None):
	pontos = quantidade * peso
	if teto_pontos is not None:
		pontos = min(pontos, teto_pontos)

	detalhe = {
		"quantidade": quantidade,
		"peso": peso,
		"pontos": _normalizar_pontuacao(pontos),
	}
	if teto_pontos is not None:
		detalhe["teto_pontos"] = teto_pontos
	return detalhe


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
		[("artes",), ("music",), ("cultur",), ("artist",)],
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


def calcularBaremaAERI(resultado=None):
	dados_lattes = getConteudo(resultado) if resultado is not None else conteudo_lattes

	if not dados_lattes:
		return {"success": False, "message": "Nenhum conteúdo do Lattes foi carregado."}

	if not dados_lattes.get("success"):
		return {
			"success": False,
			"message": "Não foi possível calcular o barema AERI sem uma coleta válida.",
			"detalhe": dados_lattes.get("message"),
		}

	index_html = dados_lattes.get("index_html") or ""
	variaveis_js = _extrair_variaveis_js(index_html)

	# ------------------------------------------------------------------
	# 1. Participações / Organizações em/de Reuniões / Eventos (max 10)
	# ------------------------------------------------------------------
	qtd_apresentacoes = _somar_variaveis_por_ano(
		variaveis_js, "barraAnosProducoesTecnicas",
		["valoesApresentacoesDeTrabalhos"],
		ano_minimo=0,
	)

	participacoes_itens = {
		"Comunicação oral / Apresentação de pôster": _detalhar_item(qtd_apresentacoes, 1.0),
	}
	participacoes_bruto = _normalizar_pontuacao(
		sum(item["pontos"] for item in participacoes_itens.values())
	)
	participacoes_limitado = min(participacoes_bruto, 10.0)

	# ------------------------------------------------------------------
	# 2. Indicadores de Produção Científica, Tecnológica e Artística (max 10)
	# ------------------------------------------------------------------
	qtd_artigos_periodicos = _somar_variaveis_por_ano(
		variaveis_js, "barraAnosProducoesBibliograficas",
		["valoresArtigosPublicadosPeriodicos"],
		ano_minimo=0,
	)
	qtd_textos_jornais = _somar_variaveis_por_ano(
		variaveis_js, "barraAnosProducoesBibliograficas",
		["valoresArtigosResumidosPublicadosPeriodicos"],
		ano_minimo=0,
	)
	qtd_resumos_anais = _somar_variaveis_por_ano(
		variaveis_js, "barraAnosProducoesBibliograficas",
		["valoresTrabalhosResumidosPublicadosEventos"],
		ano_minimo=0,
	)
	qtd_trabalhos_anais = _somar_variaveis_por_ano(
		variaveis_js, "barraAnosProducoesBibliograficas",
		["valoresTrabalhosPublicadosEventos"],
		ano_minimo=0,
	)
	qtd_producao_artistica = _somar_series_por_ano(
		variaveis_js, "barraAnosProducoesCulturais",
		[("cultur",), ("artist",)],
		ano_minimo=0,
	)

	producao_itens = {
		"Artigo completo em periódico": _detalhar_item(qtd_artigos_periodicos, 5.0),
		"Texto em jornal/revista": _detalhar_item(qtd_textos_jornais, 1.0),
		"Resumo publicado em anais": _detalhar_item(qtd_resumos_anais, 0.5),
		"Trabalho completo em anais": _detalhar_item(qtd_trabalhos_anais, 5.0),
		"Exposição / Apresentação artística": _detalhar_item(qtd_producao_artistica, 5.0),
	}
	producao_bruto = _normalizar_pontuacao(
		sum(item["pontos"] for item in producao_itens.values())
	)
	producao_limitada = min(producao_bruto, 10.0)

	# ------------------------------------------------------------------
	# 3. Representação / Liderança Estudantil (max 10) — não extraível
	# ------------------------------------------------------------------
	representacao_itens = {}
	representacao_bruto = 0.0
	representacao_limitada = 0.0

	# ------------------------------------------------------------------
	# 4. Participação em Programa Acadêmico / Estágios (max 10) — não extraível
	# ------------------------------------------------------------------
	programas_itens = {}
	programas_bruto = 0.0
	programas_limitada = 0.0

	# ------------------------------------------------------------------
	# Totais
	# ------------------------------------------------------------------
	total_bruto = _normalizar_pontuacao(
		participacoes_bruto + producao_bruto + representacao_bruto + programas_bruto
	)
	total_limitado = _normalizar_pontuacao(
		participacoes_limitado + producao_limitada + representacao_limitada + programas_limitada
	)

	observacoes = [
		"Seção 'Representação/Liderança Estudantil' não pode ser extraída automaticamente do Lattes — preencha manualmente.",
		"Seção 'Participação em Programa Acadêmico/Estágios' não pode ser extraída automaticamente do Lattes — preencha manualmente.",
		"Itens como premiações, cursos de idioma, participação em eventos da AERI e outros não são identificados automaticamente.",
	]

	return {
		"success": True,
		"message": "Barema AERI calculado com sucesso.",
		"participacoes_eventos": {
			"itens": participacoes_itens,
			"subtotal_bruto": participacoes_bruto,
			"subtotal_limitado": participacoes_limitado,
		},
		"producao_cientifica": {
			"itens": producao_itens,
			"subtotal_bruto": producao_bruto,
			"subtotal_limitado": producao_limitada,
		},
		"representacao_lideranca": {
			"itens": representacao_itens,
			"subtotal_bruto": representacao_bruto,
			"subtotal_limitado": representacao_limitada,
		},
		"participacao_programas": {
			"itens": programas_itens,
			"subtotal_bruto": programas_bruto,
			"subtotal_limitado": programas_limitada,
		},
		"total_bruto": total_bruto,
		"total_limitado": total_limitado,
		"observacoes": observacoes,
	}


# ---------------------------------------------------------------------------
# Barema PIBEX (Extensao) - Anexo II do Edital PIBEX 01/2026 - PROEX/UEFS
#
# A - Docente/Orientador  (total maximo 40): titulacao 4, atuacao na extensao 8,
#     indicadores de producao 18, formacao de recursos humanos 10.
# B - Discente/Candidato  (total maximo 20): atuacao na extensao 6,
#     indicadores de producao 5, participacao/organizacao de eventos 9.
#
# O edital nao define recorte temporal para estes baremas, portanto o curriculo
# e considerado por inteiro (ano_minimo = 0).
# ---------------------------------------------------------------------------

_ANOS_BIBLIOGRAFICAS = "barraAnosProducoesBibliograficas"
_ANOS_TECNICAS = "barraAnosProducoesTecnicas"
_ANOS_PATENTES = "barraAnosPatentes"
_ANOS_CULTURAIS = "barraAnosProducoesCulturais"
_ANOS_ORIENTACOES = "barraAnosOrientacoes"


def _resolver_variaveis(variaveis_js, nomes_exatos=(), padroes=()):
	# Resolve os nomes das series anuais do grafico do Lattes. Os nomes exatos
	# sao tentados primeiro; os padroes de tokens funcionam apenas como reserva,
	# o que evita somar a mesma serie mais de uma vez.
	mapa = {nome.lower(): nome for nome in variaveis_js}
	encontrados = []

	for nome in nomes_exatos:
		real = mapa.get(nome.lower())
		if real and real not in encontrados:
			encontrados.append(real)

	if encontrados:
		return encontrados

	for nome_lower, nome in mapa.items():
		if _e_variavel_de_anos(nome):
			continue
		if any(all(token in nome_lower for token in padrao) for padrao in padroes):
			if nome not in encontrados:
				encontrados.append(nome)

	return encontrados


def _somar_grupo(variaveis_js, nome_anos, nomes_exatos=(), padroes=(), ano_minimo=0):
	anos = _normalizar_anos(variaveis_js.get(nome_anos) or [])
	indices = [
		indice
		for indice, ano in enumerate(anos)
		if str(ano).isdigit() and int(ano) >= ano_minimo
	]

	if not indices:
		return 0

	total = 0
	for nome in _resolver_variaveis(variaveis_js, nomes_exatos, padroes):
		serie = _normalizar_serie(variaveis_js.get(nome), len(anos))
		total += sum(serie[indice] for indice in indices)

	return total


def _calcular_titulacao_extensao(preview_html):
	# Somente a maior titulacao, nao cumulativa: doutorado 4, mestrado 3,
	# especializacao 1.
	texto = unescape(re.sub(r"<[^>]+>", " ", preview_html or ""))
	texto = re.sub(r"\s+", " ", texto).strip().lower()

	if re.search(r"\bdoutor(?:a|ado)?\b|\bph\.?d\b", texto):
		return "Doutorado", 4

	if re.search(r"\bmestrado\b|\bmestre\b|\bmestra\b", texto):
		return "Mestrado", 3

	if re.search(r"\bespecializa(?:ção|cao)\b|\bespecialista\b", texto):
		return "Especialização", 1

	return "Não identificado", 0


def _coletar_quantidades_extensao(variaveis_js, preview_html, index_html):
	quantidades = {}

	quantidades["artigos_periodicos"] = _somar_grupo(
		variaveis_js, _ANOS_BIBLIOGRAFICAS, ("valoresArtigosPublicadosPeriodicos",)
	)
	quantidades["trabalhos_anais"] = _somar_grupo(
		variaveis_js, _ANOS_BIBLIOGRAFICAS, ("valoresTrabalhosPublicadosEventos",)
	)
	quantidades["resumos_anais"] = _somar_grupo(
		variaveis_js, _ANOS_BIBLIOGRAFICAS, ("valoresTrabalhosResumidosPublicadosEventos",)
	)
	quantidades["livros"] = _somar_grupo(
		variaveis_js, _ANOS_BIBLIOGRAFICAS, ("valoresLivros",)
	)
	quantidades["capitulos"] = _somar_grupo(
		variaveis_js, _ANOS_BIBLIOGRAFICAS, ("valoresCapitulos",)
	)

	quantidades["apresentacao_trabalho"] = _somar_grupo(
		variaveis_js,
		_ANOS_TECNICAS,
		("valoesApresentacoesDeTrabalhos", "valoresApresentacoesDeTrabalhos"),
		(("apresenta", "trabalho"),),
	)
	quantidades["programa_computador"] = _somar_grupo(
		variaveis_js,
		_ANOS_TECNICAS,
		(
			"valoesProgramasComputadorSemRegistro",
			"valoesProgramasComputador",
			"valoesProgramaComputador",
		),
		(("programa", "computador"),),
	)
	quantidades["produtos"] = _somar_grupo(
		variaveis_js,
		_ANOS_TECNICAS,
		("valoesProdutos", "valoresProdutos"),
		(("produto",),),
	)
	quantidades["processos"] = _somar_grupo(
		variaveis_js,
		_ANOS_TECNICAS,
		("valoesProcessoOuTecnica", "valoesProcessosOuTecnicas", "valoesProcessos"),
		(("processo",),),
	)
	quantidades["trabalhos_tecnicos"] = _somar_grupo(
		variaveis_js,
		_ANOS_TECNICAS,
		("valoesTrabalhosTecnicos", "valoresTrabalhosTecnicos"),
		(("trabalhostecnicos",),),
	)

	quantidades["patentes"] = _somar_grupo(
		variaveis_js,
		_ANOS_PATENTES,
		("valoesPatentes", "valoresPatentes"),
		(("patente",),),
	)
	if not quantidades["patentes"]:
		quantidades["patentes"] = _contar_patentes(preview_html, index_html)

	quantidades["cultivar"] = _somar_grupo(
		variaveis_js,
		_ANOS_PATENTES,
		("valoesCultivarProtegida", "valoresCultivarProtegida"),
		(("cultivar",),),
	)

	quantidades["artes_cenicas"] = _somar_grupo(
		variaveis_js,
		_ANOS_CULTURAIS,
		("valoesArtesCenicas", "valoresArtesCenicas"),
		(("cenic",),),
	)
	quantidades["artes_visuais"] = _somar_grupo(
		variaveis_js,
		_ANOS_CULTURAIS,
		("valoesArtesVisuais", "valoresArtesVisuais"),
		(("visuai",), ("visual",)),
	)
	quantidades["musica"] = _somar_grupo(
		variaveis_js,
		_ANOS_CULTURAIS,
		("valoesMusica", "valoresMusica"),
		(("music",),),
	)

	# Sobra das producoes culturais que nao caiu em nenhuma das tres linhas
	# acima (por exemplo, "outras producoes artisticas").
	total_culturais = _somar_grupo(
		variaveis_js,
		_ANOS_CULTURAIS,
		(),
		(("artes",), ("music",), ("cultur",), ("artist",)),
	)
	quantidades["outras_culturais"] = max(
		0,
		total_culturais
		- quantidades["artes_cenicas"]
		- quantidades["artes_visuais"]
		- quantidades["musica"],
	)

	quantidades["orientacao_doutorado"] = _somar_grupo(
		variaveis_js, _ANOS_ORIENTACOES, ("valoresDoutorado",)
	)
	quantidades["orientacao_mestrado"] = _somar_grupo(
		variaveis_js, _ANOS_ORIENTACOES, ("valoresMestrado",)
	)
	quantidades["supervisao_pos_doutorado"] = _somar_grupo(
		variaveis_js,
		_ANOS_ORIENTACOES,
		("valoresPosDoutorado", "valoresSupervisaoPosDoutorado"),
		(("pos", "doutorado"),),
	)
	quantidades["orientacao_demais"] = _somar_grupo(
		variaveis_js,
		_ANOS_ORIENTACOES,
		("valoresOutrasOrientacoes",),
		(("outras", "orienta"),),
	)

	return quantidades


def _montar_secao(itens_config, quantidades, teto, editavel=False):
	# itens_config: sequencia de (rotulo, chave_ou_None, peso, teto_do_item).
	# Chave None significa criterio que os graficos publicos do Lattes nao
	# expoem: entra zerado e a secao e marcada como editavel, para o avaliador
	# digitar a quantidade na tela.
	itens = {}
	for rotulo, chave, peso, teto_item in itens_config:
		quantidade = quantidades.get(chave, 0) if chave else 0
		itens[rotulo] = _detalhar_item(quantidade, peso, teto_item)

	bruto = _normalizar_pontuacao(sum(item["pontos"] for item in itens.values()))

	secao = {
		"itens": itens,
		"subtotal_bruto": bruto,
		"subtotal_limitado": _normalizar_pontuacao(min(bruto, teto)),
		"teto": teto,
	}
	if editavel:
		secao["editavel"] = True
	return secao


_EXTENSAO_ATUACAO_DOCENTE = (
	("Coordenação de Programa/Projeto de Extensão (até dois anos)", None, 1.5, None),
	("Coordenação de Programa/Projeto de Extensão (acima de dois anos)", None, 3, None),
	("Integrante da equipe de Programa/Projeto (até dois anos)", None, 0.5, None),
	("Integrante da equipe de Programa/Projeto (acima de dois anos)", None, 1, None),
)

_EXTENSAO_PRODUCAO_DOCENTE = (
	("Artigos completos publicados em periódicos", "artigos_periodicos", 2, None),
	("Trabalhos publicados em anais de evento", "trabalhos_anais", 1, None),
	("Resumos publicados em anais de eventos", "resumos_anais", 0.5, None),
	("Livros organizados ou publicados", "livros", 2, None),
	("Capítulos de livro", "capitulos", 1.5, None),
	("Apresentação de trabalho", "apresentacao_trabalho", 1, None),
	("Programa de computador sem registro", "programa_computador", 0.5, None),
	("Produtos", "produtos", 1, None),
	("Processos ou técnica", "processos", 1, None),
	("Trabalhos técnicos", "trabalhos_tecnicos", 1, None),
	("Patente", "patentes", 1, None),
	("Cultivar protegida", "cultivar", 0.5, None),
	("Artes cênicas", "artes_cenicas", 1, None),
	("Artes visuais", "artes_visuais", 1, None),
	("Música", "musica", 1, None),
	("Outras produções culturais", "outras_culturais", 1, None),
)

_EXTENSAO_FORMACAO_DOCENTE = (
	("Doutorado (orientador)", "orientacao_doutorado", 2, None),
	("Mestrado (orientador)", "orientacao_mestrado", 1, None),
	("Supervisão de pós-doutorado", "supervisao_pos_doutorado", 1, None),
	(
		"Iniciação científica, especialização, TCC e demais orientações concluídas",
		"orientacao_demais",
		1,
		None,
	),
)

_EXTENSAO_ATUACAO_DISCENTE = (
	("Bolsista (acima de 12 meses)", None, 3, None),
	("Bolsista (até 12 meses)", None, 2, None),
	("Voluntário (acima de 12 meses)", None, 1, None),
	("Voluntário (até 12 meses)", None, 0.5, None),
)

_EXTENSAO_PRODUCAO_DISCENTE = (
	("Artigos completos publicados em periódicos", "artigos_periodicos", 2, None),
	("Trabalhos publicados em anais de evento", "trabalhos_anais", 1.5, None),
	("Resumos publicados em anais de eventos", "resumos_anais", 1.5, None),
	("Livros organizados ou publicados", "livros", 2, None),
	("Capítulos de livro", "capitulos", 2, None),
	("Apresentação de trabalho", "apresentacao_trabalho", 1, None),
	("Programa de computador", "programa_computador", 0.5, None),
	("Produtos", "produtos", 0.5, None),
	("Processos ou técnica", "processos", 0.5, None),
	("Trabalhos técnicos", "trabalhos_tecnicos", 0.5, None),
	("Patente", "patentes", 0.5, None),
	("Cultivar protegida", "cultivar", 0.5, None),
	("Artes cênicas", "artes_cenicas", 0.5, None),
	("Artes visuais", "artes_visuais", 0.5, None),
	("Música", "musica", 0.5, None),
	("Outras produções culturais", "outras_culturais", 0.5, None),
)

# No Anexo II-B a coluna e "PONTUACAO MAXIMA": cada linha tem teto proprio.
_EXTENSAO_EVENTOS_DISCENTE = (
	("Participação em eventos", None, 0.5, 5),
	("Coordenação de eventos técnico-científicos", None, 1, 2),
	("Ministrante de oficina/minicurso", None, 1, 2),
)

_OBSERVACAO_PERIODO_EXTENSAO = (
	"O Edital PIBEX não define recorte temporal para o barema: foi considerado o currículo completo."
)


# ---------------------------------------------------------------------------
# Preenchimento a partir do PDF do curriculo
#
# As secoes de atuacao na extensao e de eventos nao existem na pagina publica
# de indicadores do CNPq. Quando o avaliador envia o PDF do curriculo, o
# lattes_pdf le esses dados e aqui eles sao traduzidos para as linhas exatas
# do barema, para a tela preencher os campos editaveis.
# ---------------------------------------------------------------------------

def _rotulo(config, indice):
	return config[indice][0]


def sugerir_preenchimento_extensao(dados_pdf):
	dados_pdf = dados_pdf or {}

	def quantidade(chave):
		try:
			return max(0, int(dados_pdf.get(chave) or 0))
		except (TypeError, ValueError):
			return 0

	atuacao_docente = {
		_rotulo(_EXTENSAO_ATUACAO_DOCENTE, 0): quantidade("coordenacao_ate_2_anos"),
		_rotulo(_EXTENSAO_ATUACAO_DOCENTE, 1): quantidade("coordenacao_acima_2_anos"),
		_rotulo(_EXTENSAO_ATUACAO_DOCENTE, 2): quantidade("integrante_ate_2_anos"),
		_rotulo(_EXTENSAO_ATUACAO_DOCENTE, 3): quantidade("integrante_acima_2_anos"),
	}

	eventos_discente = {
		_rotulo(_EXTENSAO_EVENTOS_DISCENTE, 0): quantidade("participacao_eventos"),
		# O Lattes agrupa tudo em "Organizacao de eventos"; o edital separa
		# coordenacao de ministrante de oficina. A sugestao vai na coordenacao
		# e o avaliador confere.
		_rotulo(_EXTENSAO_EVENTOS_DISCENTE, 1): quantidade("organizacao_eventos"),
	}

	avisos = []
	if quantidade("papel_indefinido"):
		avisos.append(
			f"{quantidade('papel_indefinido')} projeto(s) de extensão sem papel identificado "
			"no PDF — confira manualmente."
		)
	if quantidade("organizacao_eventos"):
		avisos.append(
			"A organização de eventos foi lançada em 'Coordenação de eventos técnico-científicos'. "
			"Se algum for oficina ou minicurso ministrado, mova para a linha correspondente."
		)
	avisos.append(
		"O Lattes não distingue bolsista de voluntário em projeto de extensão: "
		"a seção 'Atuação na extensão' do barema discente continua manual."
	)

	return {
		"extensao_docente": {"atuacao_extensao": atuacao_docente},
		"extensao_discente": {"participacao_eventos": eventos_discente},
		"avisos": avisos,
	}


# ---------------------------------------------------------------------------
# Recalculo com as quantidades informadas pelo avaliador
#
# O que o navegador manda sao QUANTIDADES, nunca pontos: os pesos e os tetos
# sao aplicados aqui, no servidor, a partir das mesmas constantes usadas no
# calculo original. Assim o historico nao pode receber um total forjado.
# ---------------------------------------------------------------------------

_SECOES_EDITAVEIS = {
	"extensao_docente": {
		"atuacao_extensao": (_EXTENSAO_ATUACAO_DOCENTE, 8),
	},
	"extensao_discente": {
		"atuacao_extensao": (_EXTENSAO_ATUACAO_DISCENTE, 6),
		"participacao_eventos": (_EXTENSAO_EVENTOS_DISCENTE, 9),
	},
}

_SECOES_POR_TIPO = {
	"extensao_docente": (
		"titulacao", "atuacao_extensao", "producao", "formacao_recursos_humanos",
	),
	"extensao_discente": (
		"atuacao_extensao", "producao", "participacao_eventos",
	),
}


def _montar_secao_por_rotulo(itens_config, quantidades_por_rotulo, teto):
	itens = {}
	for rotulo, _chave, peso, teto_item in itens_config:
		try:
			quantidade = int(float(quantidades_por_rotulo.get(rotulo, 0) or 0))
		except (TypeError, ValueError):
			quantidade = 0
		itens[rotulo] = _detalhar_item(max(0, quantidade), peso, teto_item)

	bruto = _normalizar_pontuacao(sum(item["pontos"] for item in itens.values()))

	return {
		"itens": itens,
		"subtotal_bruto": bruto,
		"subtotal_limitado": _normalizar_pontuacao(min(bruto, teto)),
		"teto": teto,
		"editavel": True,
	}


def aplicar_quantidades_manuais(barema, tipo, quantidades):
	"""Refaz as secoes editaveis do barema com as quantidades informadas e
	recalcula os totais. Devolve None se o tipo nao tiver secoes editaveis ou
	se o barema recebido nao for valido."""
	editaveis = _SECOES_EDITAVEIS.get(tipo)
	secoes = _SECOES_POR_TIPO.get(tipo)

	if not editaveis or not secoes or not barema or not barema.get("success"):
		return None

	atualizado = dict(barema)
	quantidades = quantidades or {}

	for chave, (config, teto) in editaveis.items():
		informado = quantidades.get(chave) or {}
		if not isinstance(informado, dict):
			informado = {}
		atualizado[chave] = _montar_secao_por_rotulo(config, informado, teto)

	atualizado["total_bruto"] = _normalizar_pontuacao(
		sum((atualizado.get(chave) or {}).get("subtotal_bruto", 0) for chave in secoes)
	)
	atualizado["total_limitado"] = _normalizar_pontuacao(
		sum((atualizado.get(chave) or {}).get("subtotal_limitado", 0) for chave in secoes)
	)
	atualizado["ajuste_manual"] = True

	return atualizado


def _preparar_dados_extensao(resultado, rotulo):
	dados_lattes = getConteudo(resultado) if resultado is not None else conteudo_lattes

	if not dados_lattes:
		return None, {
			"success": False,
			"message": "Nenhum conteúdo do Lattes foi carregado.",
		}

	if not dados_lattes.get("success"):
		return None, {
			"success": False,
			"message": f"Não foi possível calcular o barema {rotulo} sem uma coleta válida.",
			"detalhe": dados_lattes.get("message"),
		}

	return dados_lattes, None


def calcularBaremaExtensaoDocente(resultado=None):
	dados_lattes, erro = _preparar_dados_extensao(resultado, "PIBEX docente")
	if erro:
		return erro

	preview_html = dados_lattes.get("preview_html") or ""
	index_html = dados_lattes.get("index_html") or ""
	variaveis_js = _extrair_variaveis_js(index_html)
	quantidades = _coletar_quantidades_extensao(variaveis_js, preview_html, index_html)

	nivel_titulacao, pontos_titulacao = _calcular_titulacao_extensao(preview_html)
	titulacao = {
		"nivel_maximo": nivel_titulacao,
		"itens": {
			"Especialização": _detalhar_item(1 if nivel_titulacao == "Especialização" else 0, 1),
			"Mestrado": _detalhar_item(1 if nivel_titulacao == "Mestrado" else 0, 3),
			"Doutorado": _detalhar_item(1 if nivel_titulacao == "Doutorado" else 0, 4),
		},
		"subtotal_bruto": _normalizar_pontuacao(pontos_titulacao),
		"subtotal_limitado": _normalizar_pontuacao(min(pontos_titulacao, 4)),
		"teto": 4,
	}

	atuacao = _montar_secao(_EXTENSAO_ATUACAO_DOCENTE, quantidades, 8, editavel=True)
	producao = _montar_secao(_EXTENSAO_PRODUCAO_DOCENTE, quantidades, 18)
	formacao = _montar_secao(_EXTENSAO_FORMACAO_DOCENTE, quantidades, 10)

	total_bruto = _normalizar_pontuacao(
		titulacao["subtotal_bruto"]
		+ atuacao["subtotal_bruto"]
		+ producao["subtotal_bruto"]
		+ formacao["subtotal_bruto"]
	)
	total_limitado = _normalizar_pontuacao(
		titulacao["subtotal_limitado"]
		+ atuacao["subtotal_limitado"]
		+ producao["subtotal_limitado"]
		+ formacao["subtotal_limitado"]
	)

	observacoes = [
		"Seção 'II - Atuação na extensão' (máximo 8 pontos) não existe nos gráficos públicos do Lattes — informe as quantidades nos campos da tabela.",
		_OBSERVACAO_PERIODO_EXTENSAO,
	]
	if pontos_titulacao == 0:
		observacoes.insert(0, "Titulação não identificada automaticamente.")

	return {
		"success": True,
		"message": "Barema PIBEX docente calculado com sucesso.",
		"titulacao": titulacao,
		"atuacao_extensao": atuacao,
		"producao": producao,
		"formacao_recursos_humanos": formacao,
		"total_bruto": total_bruto,
		"total_limitado": total_limitado,
		"observacoes": observacoes,
	}


def calcularBaremaExtensaoDiscente(resultado=None):
	dados_lattes, erro = _preparar_dados_extensao(resultado, "PIBEX discente")
	if erro:
		return erro

	preview_html = dados_lattes.get("preview_html") or ""
	index_html = dados_lattes.get("index_html") or ""
	variaveis_js = _extrair_variaveis_js(index_html)
	quantidades = _coletar_quantidades_extensao(variaveis_js, preview_html, index_html)

	atuacao = _montar_secao(_EXTENSAO_ATUACAO_DISCENTE, quantidades, 6, editavel=True)
	producao = _montar_secao(_EXTENSAO_PRODUCAO_DISCENTE, quantidades, 5)
	eventos = _montar_secao(_EXTENSAO_EVENTOS_DISCENTE, quantidades, 9, editavel=True)

	total_bruto = _normalizar_pontuacao(
		atuacao["subtotal_bruto"] + producao["subtotal_bruto"] + eventos["subtotal_bruto"]
	)
	total_limitado = _normalizar_pontuacao(
		atuacao["subtotal_limitado"] + producao["subtotal_limitado"] + eventos["subtotal_limitado"]
	)

	observacoes = [
		"Seções 'I - Atuação na extensão' (máximo 6) e 'III - Participação/organização de eventos' (máximo 9) não existem nos gráficos públicos do Lattes — informe as quantidades nos campos da tabela.",
		_OBSERVACAO_PERIODO_EXTENSAO,
	]

	return {
		"success": True,
		"message": "Barema PIBEX discente calculado com sucesso.",
		"atuacao_extensao": atuacao,
		"producao": producao,
		"participacao_eventos": eventos,
		"total_bruto": total_bruto,
		"total_limitado": total_limitado,
		"observacoes": observacoes,
	}


def _registrar_barema_por_tipo(tipo, consulta_id, conteudo):
	code = conteudo.get("code")
	nome = conteudo.get("nome")

	if tipo == "aeri":
		registrar_barema_aeri(consulta_id, code, nome, conteudo.get("barema_aeri"))
	elif tipo == "extensao_docente":
		registrar_barema_extensao_docente(
			consulta_id, code, nome, conteudo.get("barema_extensao_docente")
		)
	elif tipo == "extensao_discente":
		registrar_barema_extensao_discente(
			consulta_id, code, nome, conteudo.get("barema_extensao_discente")
		)
	else:
		registrar_barema(consulta_id, code, nome, conteudo.get("barema"))


# Busca os dados no service
def buscaLattes(url, tipo="ic"):
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
		conteudo["barema_aeri"] = calcularBaremaAERI()
		conteudo["barema_extensao_docente"] = calcularBaremaExtensaoDocente()
		conteudo["barema_extensao_discente"] = calcularBaremaExtensaoDiscente()
		registrar_consulta(url, conteudo, tipo)
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
	conteudo["barema_aeri"] = calcularBaremaAERI()
	conteudo["barema_extensao_docente"] = calcularBaremaExtensaoDocente()
	conteudo["barema_extensao_discente"] = calcularBaremaExtensaoDiscente()
	consulta_id = registrar_consulta(url, conteudo, tipo)
	_registrar_barema_por_tipo(tipo, consulta_id, conteudo)
	return conteudo
