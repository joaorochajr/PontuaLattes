const form = document.getElementById('lattes-form');
const statusBox = document.getElementById('status');
const resultsSection = document.getElementById('results');
const submitButton = document.getElementById('submit-button');
const summaryList = document.getElementById('summary-list');
const publicationList = document.getElementById('publication-list');
const publicationsTitle = document.getElementById('publications-title');
const baremaSummary = document.getElementById('barema-summary');
const baremaSections = document.getElementById('barema-sections');
const baremaObservations = document.getElementById('barema-observations');

const statBaremaTotal = document.getElementById('stat-barema-total');
const statTotal = document.getElementById('stat-total');
const token = localStorage.getItem('auth_token');

let lastResultado = null;
let editaisCarregados = { ic: {}, aeri: {}, extensao: {} };

const NOMES_EDITAL = { ic: 'IC', aeri: 'AERI', extensao: 'PIBEX' };

// Edital escolhido no formulário: 'ic' | 'aeri' | 'extensao'.
function getEditalSelecionado() {
	return document.querySelector('input[name="edital"]:checked')?.value || 'ic';
}

// Perfil do PIBEX: 'docente' | 'discente'.
function getPerfilExtensao() {
	return document.querySelector('input[name="perfil-extensao"]:checked')?.value || 'docente';
}

// Tipo enviado à API: 'ic' | 'aeri' | 'extensao_docente' | 'extensao_discente'.
function getTipoConsulta() {
	const edital = getEditalSelecionado();
	return edital === 'extensao' ? `extensao_${getPerfilExtensao()}` : edital;
}

// Apenas o barema de IC considera os últimos 5 anos; AERI e PIBEX usam o currículo completo.
function tipoUsaUltimosCincoAnos(tipo) {
	return tipo === 'ic';
}

function atualizarSubEscolhaExtensao() {
	const bloco = document.getElementById('extensao-perfil');
	if (bloco) {
		bloco.hidden = getEditalSelecionado() !== 'extensao';
	}
}

async function inicializarEditais() {
	try {
		const response = await fetch('/api/editais');
		const dados = await response.json();
		if (dados.success) {
			editaisCarregados = {
				ic: dados.ic || {},
				aeri: dados.aeri || {},
				extensao: dados.extensao || {},
			};
		}
	} catch (_) {}
	atualizarLinkEdital();
}

function atualizarLinkEdital() {
	const edital = getEditalSelecionado();
	const info = editaisCarregados[edital] || {};
	const link = document.getElementById('edital-link');
	if (!link) return;
	if (info.url) {
		const ano = info.ano ? ` UEFS ${info.ano}` : '';
		link.href = info.url;
		link.textContent = `Ver edital ${NOMES_EDITAL[edital] || edital.toUpperCase()}${ano}`;
		link.style.display = '';
	} else {
		link.style.display = 'none';
	}
}

document.addEventListener('DOMContentLoaded', () => {
	inicializarEditais();
	atualizarSubEscolhaExtensao();
});

function setStatus(type, message) {
	statusBox.className = `status visible ${type}`;
	statusBox.textContent = message;
}

function resetResults() {
	estadoBaremaEditavel = null;
	sugestoesPdf = null;
	mostrarPainelPdf(false);
	setPdfStatus('', '');
	setSalvarStatus('', '');
	renderAvisosPdf([]);
	resultsSection.classList.remove('visible');
	summaryList.innerHTML = '';
	publicationList.innerHTML = '';
	baremaSummary.innerHTML = '';
	baremaSections.innerHTML = '';
	baremaObservations.innerHTML = '';
	statBaremaTotal.textContent = '0';
	statTotal.textContent = '0';
}

function extractResearcherName(resultado, previewHtml) {
	if (resultado?.nome) {
		return resultado.nome;
	}

	const match = (previewHtml || '').match(/var\s+nome\s*=\s*'([^']+)'/i);
	return match ? match[1] : 'Não identificado';
}

function getMinimumBaremaYear() {
	return new Date().getFullYear() - 5;
}

function getCurrentBaremaYear() {
	return new Date().getFullYear();
}

function escapeHtml(value) {
	return String(value ?? '')
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;');
}

function getIndicadoresPublicacaoUrl(code) {
	const valor = String(code ?? '').trim();
	if (!valor) {
		return '-';
	}

	return `http://buscatextual.cnpq.br/buscatextual/graficos.do?metodo=apresentar&codRHCript=${encodeURIComponent(valor)}`;
}

function renderExternalLink(url) {
	if (!url || url === '-') {
		return '-';
	}

	const safeUrl = escapeHtml(url);
	return `<a class="soft-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">Link</a>`;
}

function getFilteredPublicationSeries(publicacoes, anoMinimo = getMinimumBaremaYear()) {
	const series = publicacoes?.series || [];

	return series
		.map((item) => {
			const entries = Object.entries(item.por_ano || {})
				.filter(([ano]) => Number.isInteger(Number(ano)) && Number(ano) >= anoMinimo)
				.sort((a, b) => Number(a[0]) - Number(b[0]));

			const porAno = Object.fromEntries(entries);
			const total = entries.reduce((acc, [, valor]) => acc + Number(valor || 0), 0);

			return {
				...item,
				por_ano: porAno,
				total,
			};
		})
		.filter((item) => item.total > 0);
}

function renderSummary(resultado, previewHtml, anoMinimo = getMinimumBaremaYear()) {
	const publicacoes = resultado.publicacoes || {};
	const pesquisador = extractResearcherName(resultado, previewHtml);
	const anoAtual = getCurrentBaremaYear();

	const anosLimpos = (publicacoes.anos || [])
		.map(a => String(a).trim())
		.filter(a => a !== '' && !isNaN(Number(a)));

	const anosConsiderados = anosLimpos.filter(ano => Number(ano) >= anoMinimo);
	const rotuloPeriodo = anoMinimo > 0
		? `Período considerado (${anoMinimo} a ${anoAtual})`
		: 'Período considerado (currículo completo)';

	const itens = [
		['Nome', escapeHtml(pesquisador)],
		['Indicadores de publicação', renderExternalLink(getIndicadoresPublicacaoUrl(resultado.code))],
		[rotuloPeriodo, escapeHtml(anosConsiderados.join(', ') || 'Nenhum')],
	];

	summaryList.innerHTML = itens
		.map(([titulo, valor]) => `<li><strong>${titulo}:</strong> ${valor}</li>`)
		.join('');
}

function renderPublications(series, anoMinimo = getMinimumBaremaYear()) {
	const anoAtual = getCurrentBaremaYear();
	publicationsTitle.textContent = anoMinimo > 0
		? `Publicações de ${anoMinimo} a ${anoAtual}`
		: 'Publicações do currículo completo';

	if (!series.length) {
		publicationList.innerHTML = anoMinimo > 0
			? `<div class="publication-item">Nenhuma publicação encontrada entre ${anoMinimo} e ${anoAtual}.</div>`
			: '<div class="publication-item">Nenhuma publicação encontrada no currículo.</div>';
		return;
	}

	publicationList.innerHTML = series
		.map((item) => {
			const porAno = Object.entries(item.por_ano || {})
				.map(([ano, valor]) => `${ano}: ${valor}`)
				.join(' • ');

			return `
				<div class="publication-item">
					<strong>${item.nome}</strong>
					<div>Total: ${item.total}</div>
					<div>${porAno || 'Sem detalhamento anual.'}</div>
				</div>
			`;
		})
		.join('');
}

function formatNumber(value) {
	return Number(value || 0).toLocaleString('pt-BR', {
		minimumFractionDigits: Number.isInteger(Number(value || 0)) ? 0 : 1,
		maximumFractionDigits: 2,
	});
}

function renderBaremaSection(title, section, maximumAllowedLabel, chaveSecao) {
	const itens = Object.entries(section.itens || {});
	const editavel = Boolean(section.editavel);

	const celulaQuantidade = (label, item) => editavel
		? `<input
				type="number"
				class="qtd-editavel"
				min="0"
				step="1"
				value="${Number(item.quantidade) || 0}"
				data-secao="${escapeHtml(chaveSecao)}"
				data-rotulo="${escapeHtml(label)}"
				data-peso="${Number(item.peso) || 0}"
				data-teto="${item.teto_pontos ?? ''}"
				aria-label="Quantidade de ${escapeHtml(label)}"
			>`
		: formatNumber(item.quantidade);

	const cabecalhoTotal = editavel
		? `<span>Informe as quantidades abaixo</span>
			<span>Subtotal: <strong class="subtotal-secao" data-secao="${escapeHtml(chaveSecao)}">${formatNumber(section.subtotal_limitado)}</strong> / máximo ${maximumAllowedLabel}</span>`
		: `<span>Pontuação encontrada: ${formatNumber(section.subtotal_bruto)}</span>
			<span>Máximo permitido: ${maximumAllowedLabel}</span>`;

	return `
		<div class="barema-card${editavel ? ' barema-card-editavel' : ''}">
			<div class="barema-card-header">
				<h3>${title}${editavel ? ' <span class="barema-tag-manual">preenchimento manual</span>' : ''}</h3>
				<div class="barema-card-total">
					${cabecalhoTotal}
				</div>
			</div>
			${itens.length ? `
				<div class="barema-table-wrapper">
					<table class="barema-table">
						<thead>
							<tr>
								<th>Critério</th>
								<th>Qtd.</th>
								<th>Peso</th>
								<th>Pontos</th>
							</tr>
						</thead>
						<tbody>
							${itens.map(([label, item]) => `
								<tr>
									<td>${label}${item.teto_pontos != null ? ` <span class="barema-teto-item">máx ${formatNumber(item.teto_pontos)} pts</span>` : ''}</td>
									<td>${celulaQuantidade(label, item)}</td>
									<td>${formatNumber(item.peso)}</td>
									<td class="pontos-celula">${formatNumber(item.pontos)}</td>
								</tr>
							`).join('')}
						</tbody>
					</table>
				</div>
			` : '<p class="barema-empty">Sem itens detalhados.</p>'}
		</div>
	`;
}

function getMaximumAllowedLabel(title, titulacao) {
	if (title === 'I - Titulação') {
		const nivelMaximo = titulacao?.nivel_maximo || 'Não identificado';

		if (nivelMaximo === 'Doutorado') {
			return '12';
		}

		if (nivelMaximo === 'Mestrado') {
			return '8';
		}

		return '12 (Doutorado) ou 8 (Mestrado)';
	}

	if (title === 'II - Produção') {
		return '30';
	}

	if (title === 'III - Formação de recursos humanos') {
		return '12';
	}

	if (title === 'IV - Participação em eventos/comitê') {
		return '6';
	}

	return '-';
}

function buildTitulationSection(titulacao) {
	const nivelMaximo = titulacao?.nivel_maximo || 'Não identificado';
	const isDoutorado = nivelMaximo === 'Doutorado';
	const isMestrado = nivelMaximo === 'Mestrado';

	return {
		itens: {
			Doutorado: {
				quantidade: isDoutorado ? 1 : 0,
				peso: 12,
				pontos: isDoutorado ? 12 : 0,
			},
			Mestrado: {
				quantidade: isMestrado ? 1 : 0,
				peso: 8,
				pontos: isMestrado ? 8 : 0,
			},
		},
		subtotal_bruto: titulacao?.subtotal_bruto || 0,
		subtotal_limitado: titulacao?.subtotal_limitado || 0,
	};
}

function renderBarema(barema) {
	if (!barema || !barema.success) {
		baremaSummary.innerHTML = '<div class="publication-item">Barema não disponível.</div>';
		baremaSections.innerHTML = '';
		baremaObservations.innerHTML = '';
		statBaremaTotal.textContent = '0';
		return;
	}

	statBaremaTotal.textContent = formatNumber(barema.total_limitado);

	baremaSummary.innerHTML = `
		<div class="barema-highlight-grid">
			<div class="barema-highlight-item">
				<span class="barema-highlight-label">Titulação</span>
				<strong>${formatNumber(barema.titulacao?.subtotal_limitado)}</strong>
			</div>
			<div class="barema-highlight-item">
				<span class="barema-highlight-label">Produção</span>
				<strong>${formatNumber(barema.producao?.subtotal_limitado)}</strong>
			</div>
			<div class="barema-highlight-item">
				<span class="barema-highlight-label">Formação RH</span>
				<strong>${formatNumber(barema.formacao_recursos_humanos?.subtotal_limitado)}</strong>
			</div>
			<div class="barema-highlight-item">
				<span class="barema-highlight-label">Eventos/comitê</span>
				<strong>${formatNumber(barema.participacao_eventos_comite?.subtotal_limitado)}</strong>
			</div>
			<div class="barema-highlight-item barema-highlight-total">
				<span class="barema-highlight-label">Total final</span>
				<strong>${formatNumber(barema.total_limitado)}</strong>
			</div>
		</div>
	`;

	baremaSections.innerHTML = [
		renderBaremaSection(
			'I - Titulação',
			buildTitulationSection(barema.titulacao || {}),
			getMaximumAllowedLabel('I - Titulação', barema.titulacao || {}),
		),
		renderBaremaSection(
			'II - Produção',
			barema.producao || {},
			getMaximumAllowedLabel('II - Produção', barema.titulacao || {}),
		),
		renderBaremaSection(
			'III - Formação de recursos humanos',
			barema.formacao_recursos_humanos || {},
			getMaximumAllowedLabel('III - Formação de recursos humanos', barema.titulacao || {}),
		),
		renderBaremaSection(
			'IV - Participação em eventos/comitê',
			barema.participacao_eventos_comite || {},
			getMaximumAllowedLabel('IV - Participação em eventos/comitê', barema.titulacao || {}),
		),
	].join('');

	const observacoes = barema.observacoes || [];
	baremaObservations.innerHTML = observacoes.length
		? `
			<h3>Observações</h3>
			<ul class="details-list">
				${observacoes.map((item) => `<li>${item}</li>`).join('')}
			</ul>
		`
		: '';
}

function renderBaremaAERI(barema) {
	const baremaCardTitle = document.getElementById('barema-card-title');

	if (!barema || !barema.success) {
		baremaSummary.innerHTML = '<div class="publication-item">Barema AERI não disponível.</div>';
		baremaSections.innerHTML = '';
		baremaObservations.innerHTML = '';
		statBaremaTotal.textContent = '0';
		return;
	}

	if (baremaCardTitle) baremaCardTitle.textContent = 'Barema discente (Edital AERI)';
	statBaremaTotal.textContent = formatNumber(barema.total_limitado);

	baremaSummary.innerHTML = `
		<div class="barema-highlight-grid">
			<div class="barema-highlight-item">
				<span class="barema-highlight-label">Participações/Eventos</span>
				<strong>${formatNumber(barema.participacoes_eventos?.subtotal_limitado)}</strong>
			</div>
			<div class="barema-highlight-item">
				<span class="barema-highlight-label">Produção Científica</span>
				<strong>${formatNumber(barema.producao_cientifica?.subtotal_limitado)}</strong>
			</div>
			<div class="barema-highlight-item">
				<span class="barema-highlight-label">Representação/Liderança</span>
				<strong>${formatNumber(barema.representacao_lideranca?.subtotal_limitado)}</strong>
			</div>
			<div class="barema-highlight-item">
				<span class="barema-highlight-label">Programas/Estágios</span>
				<strong>${formatNumber(barema.participacao_programas?.subtotal_limitado)}</strong>
			</div>
			<div class="barema-highlight-item barema-highlight-total">
				<span class="barema-highlight-label">Total final</span>
				<strong>${formatNumber(barema.total_limitado)}</strong>
			</div>
		</div>
	`;

	baremaSections.innerHTML = [
		renderBaremaSection('I - Participações / Eventos', barema.participacoes_eventos || {}, '10'),
		renderBaremaSection('II - Produção Científica', barema.producao_cientifica || {}, '10'),
		renderBaremaSection('III - Representação / Liderança Estudantil', barema.representacao_lideranca || {}, '10'),
		renderBaremaSection('IV - Participação em Programas / Estágios', barema.participacao_programas || {}, '10'),
	].join('');

	const observacoesAERI = barema.observacoes || [];
	baremaObservations.innerHTML = observacoesAERI.length
		? `
			<h3>Observações</h3>
			<ul class="details-list">
				${observacoesAERI.map((item) => `<li>${item}</li>`).join('')}
			</ul>
		`
		: '';
}

const salvarPanel = document.getElementById('salvar-panel');
const salvarBotao = document.getElementById('salvar-barema');
const salvarStatus = document.getElementById('salvar-status');

function setSalvarStatus(tipo, mensagem) {
	if (!salvarStatus) return;
	salvarStatus.className = `salvar-status ${tipo}`;
	salvarStatus.textContent = mensagem;
}

// Lê as quantidades digitadas, agrupadas por seção. Só quantidades são
// enviadas — os pesos e tetos são aplicados no servidor.
function coletarQuantidadesManuais() {
	const porSecao = {};
	baremaSections.querySelectorAll('.qtd-editavel').forEach((campo) => {
		const secao = campo.dataset.secao;
		const rotulo = campo.dataset.rotulo;
		if (!secao || !rotulo) return;
		if (!porSecao[secao]) porSecao[secao] = {};
		porSecao[secao][rotulo] = Math.max(0, Math.floor(Number(campo.value) || 0));
	});
	return porSecao;
}

async function salvarNoHistorico() {
	if (!lastResultado || !salvarBotao) return;

	const tipo = getTipoConsulta();
	if (!tipo.startsWith('extensao_')) return;

	salvarBotao.disabled = true;
	setSalvarStatus('', 'Gravando...');

	try {
		const resposta = await fetch('/api/barema-manual', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				code: lastResultado.code,
				tipo,
				quantidades: coletarQuantidadesManuais(),
			}),
		});

		const dados = await resposta.json();
		if (!resposta.ok || !dados.success) {
			throw new Error(dados.message || 'Não foi possível gravar.');
		}

		setSalvarStatus('sucesso', `Histórico atualizado: ${formatNumber(dados.total_limitado)} pontos.`);
	} catch (erro) {
		setSalvarStatus('erro', erro.message || 'Falha ao gravar no histórico.');
	} finally {
		salvarBotao.disabled = false;
	}
}

if (salvarBotao) {
	salvarBotao.addEventListener('click', salvarNoHistorico);
}

const pdfPanel = document.getElementById('pdf-panel');
const pdfInput = document.getElementById('pdf-input');
const pdfStatus = document.getElementById('pdf-status');

// Guarda as sugestões vindas do PDF para reaplicar ao trocar docente/discente.
let sugestoesPdf = null;

function setPdfStatus(tipo, mensagem) {
	if (!pdfStatus) return;
	pdfStatus.className = `pdf-status ${tipo}`;
	pdfStatus.textContent = mensagem;
}

function mostrarPainelPdf(visivel) {
	if (pdfPanel) pdfPanel.hidden = !visivel;
	if (salvarPanel) salvarPanel.hidden = !visivel;
}

function lerArquivoComoBase64(arquivo) {
	return new Promise((resolve, reject) => {
		const leitor = new FileReader();
		leitor.onerror = () => reject(new Error('Não foi possível ler o arquivo.'));
		leitor.onload = () => {
			const resultado = String(leitor.result || '');
			resolve(resultado.slice(resultado.indexOf(',') + 1));
		};
		leitor.readAsDataURL(arquivo);
	});
}

// Escreve as quantidades sugeridas nos campos editáveis do barema em exibição.
function aplicarSugestoesPdf() {
	if (!sugestoesPdf) return 0;

	const tipo = getTipoConsulta();
	const porSecao = sugestoesPdf[tipo];
	if (!porSecao) return 0;

	let preenchidos = 0;
	Object.entries(porSecao).forEach(([chaveSecao, itens]) => {
		Object.entries(itens).forEach(([rotulo, quantidade]) => {
			const campo = baremaSections.querySelector(
				`.qtd-editavel[data-secao="${chaveSecao}"][data-rotulo="${CSS.escape(rotulo)}"]`,
			);
			if (campo) {
				campo.value = String(Math.max(0, Number(quantidade) || 0));
				preenchidos += 1;
			}
		});
	});

	if (preenchidos) recalcularBaremaEditavel();
	return preenchidos;
}

function renderAvisosPdf(avisos) {
	const anterior = pdfPanel?.querySelector('.pdf-avisos');
	if (anterior) anterior.remove();
	if (!pdfPanel || !avisos || !avisos.length) return;

	const lista = document.createElement('ul');
	lista.className = 'pdf-avisos';
	lista.innerHTML = avisos.map((aviso) => `<li>${escapeHtml(aviso)}</li>`).join('');
	pdfPanel.appendChild(lista);
}

async function enviarPdf(arquivo) {
	if (!arquivo) return;

	if (arquivo.type && arquivo.type !== 'application/pdf' && !/\.pdf$/i.test(arquivo.name)) {
		setPdfStatus('erro', 'Selecione um arquivo PDF.');
		return;
	}

	setPdfStatus('', `Lendo ${arquivo.name}...`);

	try {
		const pdfBase64 = await lerArquivoComoBase64(arquivo);
		const resposta = await fetch('/api/lattes-pdf', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ pdf_base64: pdfBase64 }),
		});

		const dados = await resposta.json();
		if (!resposta.ok || !dados.success) {
			throw new Error(dados.message || 'Não foi possível ler o PDF.');
		}

		sugestoesPdf = dados.sugestoes || null;
		renderAvisosPdf(dados.sugestoes?.avisos);

		const preenchidos = aplicarSugestoesPdf();
		const titular = dados.nome ? ` (${dados.nome})` : '';
		setPdfStatus(
			'sucesso',
			preenchidos
				? `PDF lido${titular}: ${preenchidos} campo(s) preenchido(s). Confira e ajuste se precisar.`
				: `PDF lido${titular}, mas não havia dados para as seções deste perfil.`,
		);
	} catch (erro) {
		setPdfStatus('erro', erro.message || 'Falha ao enviar o PDF.');
	}
}

if (pdfInput) {
	pdfInput.addEventListener('change', () => {
		enviarPdf(pdfInput.files && pdfInput.files[0]);
		pdfInput.value = '';
	});
}

// Estado do barema exibido, para recalcular quando o avaliador digita
// as quantidades das seções que o Lattes não expõe.
let estadoBaremaEditavel = null;

function ligarCamposEditaveis() {
	const campos = baremaSections.querySelectorAll('.qtd-editavel');
	campos.forEach((campo) => {
		campo.addEventListener('input', recalcularBaremaEditavel);
		// Ao sair do campo, normaliza o que foi digitado (negativo, decimal,
		// texto colado) para o inteiro que realmente entrou na conta.
		campo.addEventListener('change', () => {
			const valor = Math.max(0, Math.floor(Number(campo.value) || 0));
			if (String(valor) !== campo.value) {
				campo.value = String(valor);
			}
			recalcularBaremaEditavel();
		});
	});
	if (campos.length) {
		recalcularBaremaEditavel();
	}
}

// Recalcula pontos por item (respeitando o teto de cada linha), subtotal de
// cada seção (respeitando o teto da seção) e o total final.
function recalcularBaremaEditavel() {
	if (!estadoBaremaEditavel) return;

	const { barema, secoes } = estadoBaremaEditavel;
	let total = 0;

	secoes.forEach(([, chave, maximo]) => {
		const secao = barema[chave] || {};
		const teto = Number(secao.teto ?? maximo) || 0;
		let subtotal;

		if (secao.editavel) {
			subtotal = 0;
			baremaSections
				.querySelectorAll(`.qtd-editavel[data-secao="${chave}"]`)
				.forEach((campo) => {
					const quantidade = Math.max(0, Math.floor(Number(campo.value) || 0));
					const peso = Number(campo.dataset.peso) || 0;
					const tetoItem = campo.dataset.teto === '' ? null : Number(campo.dataset.teto);

					let pontos = quantidade * peso;
					if (tetoItem !== null && Number.isFinite(tetoItem)) {
						pontos = Math.min(pontos, tetoItem);
					}
					subtotal += pontos;

					const celula = campo.closest('tr')?.querySelector('.pontos-celula');
					if (celula) celula.textContent = formatNumber(pontos);
				});

			subtotal = Math.min(subtotal, teto);
			const rodape = baremaSections.querySelector(`.subtotal-secao[data-secao="${chave}"]`);
			if (rodape) rodape.textContent = formatNumber(subtotal);
		} else {
			subtotal = Number(secao.subtotal_limitado) || 0;
		}

		total += subtotal;

		const destaque = baremaSummary.querySelector(`.barema-highlight-item[data-secao="${chave}"] strong`);
		if (destaque) destaque.textContent = formatNumber(subtotal);
	});

	total = Math.round(total * 100) / 100;
	statBaremaTotal.textContent = formatNumber(total);
	if (salvarStatus && salvarStatus.classList.contains('sucesso')) {
		setSalvarStatus('', 'Valores alterados — grave novamente para atualizar o histórico.');
	}
	const totalFinal = baremaSummary.querySelector('.barema-highlight-total strong');
	if (totalFinal) totalFinal.textContent = formatNumber(total);
}

// Renderiza um barema qualquer a partir da lista de destaques e de seções.
// destaques: [rótulo, chave]  ·  secoes: [título, chave, máximo permitido]
function renderBaremaComSecoes(barema, destaques, secoes, mensagemIndisponivel) {
	if (!barema || !barema.success) {
		baremaSummary.innerHTML = `<div class="publication-item">${mensagemIndisponivel}</div>`;
		baremaSections.innerHTML = '';
		baremaObservations.innerHTML = '';
		statBaremaTotal.textContent = '0';
		return;
	}

	statBaremaTotal.textContent = formatNumber(barema.total_limitado);

	baremaSummary.innerHTML = `
		<div class="barema-highlight-grid">
			${destaques.map(([rotulo, chave]) => `
				<div class="barema-highlight-item" data-secao="${escapeHtml(chave)}">
					<span class="barema-highlight-label">${rotulo}</span>
					<strong>${formatNumber(barema[chave]?.subtotal_limitado)}</strong>
				</div>
			`).join('')}
			<div class="barema-highlight-item barema-highlight-total">
				<span class="barema-highlight-label">Total final</span>
				<strong>${formatNumber(barema.total_limitado)}</strong>
			</div>
		</div>
	`;

	baremaSections.innerHTML = secoes
		.map(([titulo, chave, maximo]) => renderBaremaSection(titulo, barema[chave] || {}, maximo, chave))
		.join('');

	estadoBaremaEditavel = { barema, secoes };
	ligarCamposEditaveis();
	aplicarSugestoesPdf();

	const observacoes = barema.observacoes || [];
	baremaObservations.innerHTML = observacoes.length
		? `
			<h3>Observações</h3>
			<ul class="details-list">
				${observacoes.map((item) => `<li>${item}</li>`).join('')}
			</ul>
		`
		: '';
}

// Barema A do Anexo II do Edital PIBEX — docente/orientador (máximo 40 pontos).
function renderBaremaExtensaoDocente(barema) {
	renderBaremaComSecoes(
		barema,
		[
			['Titulação', 'titulacao'],
			['Atuação na extensão', 'atuacao_extensao'],
			['Produção', 'producao'],
			['Formação RH', 'formacao_recursos_humanos'],
		],
		[
			['I - Titulação', 'titulacao', '4'],
			['II - Atuação na extensão', 'atuacao_extensao', '8'],
			['III - Indicadores de produção científica, tecnológica e artística', 'producao', '18'],
			['IV - Formação de recursos humanos', 'formacao_recursos_humanos', '10'],
		],
		'Barema PIBEX docente não disponível.',
	);
}

// Barema B do Anexo II do Edital PIBEX — discente/candidato (máximo 20 pontos).
function renderBaremaExtensaoDiscente(barema) {
	renderBaremaComSecoes(
		barema,
		[
			['Atuação na extensão', 'atuacao_extensao'],
			['Produção', 'producao'],
			['Eventos acadêmicos', 'participacao_eventos'],
		],
		[
			['I - Atuação na extensão', 'atuacao_extensao', '6'],
			['II - Indicadores de produção científica, tecnológica e artística', 'producao', '5'],
			['III - Participação/organização de eventos acadêmicos', 'participacao_eventos', '9'],
		],
		'Barema PIBEX discente não disponível.',
	);
}

function renderFromResultado(resultado) {
	if (!resultado) return;

	const tipo = getTipoConsulta();
	const anoMinimo = tipoUsaUltimosCincoAnos(tipo) ? getMinimumBaremaYear() : 0;
	const baremaCardTitle = document.getElementById('barema-card-title');
	const statLabel = document.getElementById('stat-barema-label');

	renderSummary(resultado, resultado.preview_html || '', anoMinimo);
	renderPublications(
		getFilteredPublicationSeries(resultado.publicacoes || {}, anoMinimo),
		anoMinimo,
	);

	// O envio do PDF só faz sentido no PIBEX, que é onde há seções manuais.
	mostrarPainelPdf(tipo.startsWith('extensao_'));

	if (tipo === 'aeri') {
		if (baremaCardTitle) baremaCardTitle.textContent = 'Barema discente (Edital AERI)';
		if (statLabel) statLabel.textContent = 'Pontuação máxima: 40 pontos';
		renderBaremaAERI(resultado.barema_aeri || null);
	} else if (tipo === 'extensao_docente') {
		if (baremaCardTitle) baremaCardTitle.textContent = 'Barema docente/orientador (Edital PIBEX)';
		if (statLabel) statLabel.textContent = 'Pontuação máxima: 40 pontos';
		renderBaremaExtensaoDocente(resultado.barema_extensao_docente || null);
	} else if (tipo === 'extensao_discente') {
		if (baremaCardTitle) baremaCardTitle.textContent = 'Barema discente/candidato (Edital PIBEX)';
		if (statLabel) statLabel.textContent = 'Pontuação máxima: 20 pontos';
		renderBaremaExtensaoDiscente(resultado.barema_extensao_discente || null);
	} else {
		if (baremaCardTitle) baremaCardTitle.textContent = 'Barema docente (Edital IC)';
		if (statLabel) statLabel.textContent = 'Pontuação máxima: 60 pontos';
		renderBarema(resultado.barema || null);
	}
}

document.querySelectorAll('input[name="edital"], input[name="perfil-extensao"]').forEach((radio) => {
	radio.addEventListener('change', () => {
		atualizarSubEscolhaExtensao();
		atualizarLinkEdital();
		if (lastResultado) renderFromResultado(lastResultado);
	});
});

form.addEventListener('submit', async (event) => {
	event.preventDefault();
	resetResults();

	const url = document.getElementById('lattes-url').value.trim();
	if (!url) {
		setStatus('error', 'Informe a URL completa ou o código do currículo Lattes.');
		return;
	}

	const tipo = getTipoConsulta();

	submitButton.disabled = true;
	submitButton.textContent = 'Consultando...';
	setStatus('info', 'Consultando a API e coletando os dados do currículo...');

	try {
		const response = await fetch('/api/lattes', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({ url, tipo }),
		});

		const responseText = await response.text();
		let resultado;

		try {
			resultado = responseText ? JSON.parse(responseText) : null;
		} catch {
			throw new Error('A API retornou uma resposta inválida.');
		}

		if (!resultado) {
			throw new Error('A API retornou uma resposta vazia.');
		}

		if (!response.ok || !resultado.success) {
			throw new Error(resultado.message || 'Não foi possível concluir a coleta.');
		}

		const publicacoes = resultado.publicacoes || {};

		statTotal.textContent = String(publicacoes.total_geral || 0);

		lastResultado = resultado;
		renderFromResultado(resultado);
		resultsSection.classList.add('visible');
		setStatus('success', 'Coleta realizada com sucesso.');
	} catch (error) {
		setStatus('error', error.message || 'Erro inesperado ao chamar a API.');
	} finally {
		submitButton.disabled = false;
		submitButton.textContent = 'Consultar';
	}
});
