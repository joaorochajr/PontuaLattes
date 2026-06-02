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
let editaisCarregados = { ic: {}, aeri: {} };

async function inicializarEditais() {
	try {
		const response = await fetch('/api/editais');
		const dados = await response.json();
		if (dados.success) {
			editaisCarregados = { ic: dados.ic || {}, aeri: dados.aeri || {} };
		}
	} catch (_) {}
	atualizarLinkEdital();
}

function atualizarLinkEdital() {
	const edital = document.querySelector('input[name="edital"]:checked')?.value || 'ic';
	const info = editaisCarregados[edital] || {};
	const link = document.getElementById('edital-link');
	if (!link) return;
	if (info.url) {
		const ano = info.ano ? ` UEFS ${info.ano}` : '';
		link.href = info.url;
		link.textContent = `Ver edital ${edital.toUpperCase()}${ano}`;
		link.style.display = '';
	} else {
		link.style.display = 'none';
	}
}

document.addEventListener('DOMContentLoaded', () => {
	inicializarEditais();
});

function setStatus(type, message) {
	statusBox.className = `status visible ${type}`;
	statusBox.textContent = message;
}

function resetResults() {
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

function getFilteredPublicationSeries(publicacoes) {
	const anoMinimo = getMinimumBaremaYear();
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

function renderSummary(resultado, previewHtml) {
	const publicacoes = resultado.publicacoes || {};
	const pesquisador = extractResearcherName(resultado, previewHtml);
	const anoMinimo = getMinimumBaremaYear();
	const anoAtual = getCurrentBaremaYear();

	const anosLimpos = (publicacoes.anos || [])
		.map(a => String(a).trim())
		.filter(a => a !== '' && !isNaN(Number(a)));

	const itens = [
		['Nome', escapeHtml(pesquisador)],
		['Indicadores de publicação', renderExternalLink(getIndicadoresPublicacaoUrl(resultado.code))],
		[
			`Período considerado (${anoMinimo} a ${anoAtual})`,
			escapeHtml(anosLimpos
				.filter(ano => Number(ano) >= anoMinimo)
				.join(', ') || 'Nenhum'),
		],
	];

	summaryList.innerHTML = itens
		.map(([titulo, valor]) => `<li><strong>${titulo}:</strong> ${valor}</li>`)
		.join('');
}

function renderPublications(series) {
	const anoMinimo = getMinimumBaremaYear();
	const anoAtual = getCurrentBaremaYear();
	publicationsTitle.textContent = `Publicações de ${anoMinimo} a ${anoAtual}`;

	if (!series.length) {
		publicationList.innerHTML = `<div class="publication-item">Nenhuma publicação encontrada entre ${anoMinimo} e ${anoAtual}.</div>`;
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

function renderBaremaSection(title, section, maximumAllowedLabel) {
	const itens = Object.entries(section.itens || {});

	return `
		<div class="barema-card">
			<div class="barema-card-header">
				<h3>${title}</h3>
				<div class="barema-card-total">
					<span>Pontuação encontrada: ${formatNumber(section.subtotal_bruto)}</span>
					<span>Máximo permitido: ${maximumAllowedLabel}</span>
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
									<td>${label}</td>
									<td>${formatNumber(item.quantidade)}</td>
									<td>${formatNumber(item.peso)}</td>
									<td>${formatNumber(item.pontos)}</td>
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

function renderFromResultado(resultado) {
	if (!resultado) return;

	const edital = document.querySelector('input[name="edital"]:checked')?.value || 'ic';
	const baremaCardTitle = document.getElementById('barema-card-title');
	const statLabel = document.getElementById('stat-barema-label');

	if (edital === 'aeri') {
		if (baremaCardTitle) baremaCardTitle.textContent = 'Barema discente (Edital AERI)';
		if (statLabel) statLabel.textContent = 'Pontuação máxima: 40 pontos';
		renderBaremaAERI(resultado.barema_aeri || null);
	} else {
		if (baremaCardTitle) baremaCardTitle.textContent = 'Barema docente (Edital IC)';
		if (statLabel) statLabel.textContent = 'Pontuação máxima: 60 pontos';
		renderBarema(resultado.barema || null);
	}
}

document.querySelectorAll('input[name="edital"]').forEach((radio) => {
	radio.addEventListener('change', () => {
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

	const edital = document.querySelector('input[name="edital"]:checked')?.value || 'ic';

	submitButton.disabled = true;
	submitButton.textContent = 'Consultando...';
	setStatus('info', 'Consultando a API e coletando os dados do currículo...');

	try {
		const response = await fetch('/api/lattes', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({ url, tipo: edital }),
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

		const previewHtml = resultado.preview_html || '';
		const publicacoes = resultado.publicacoes || {};
		const seriesPeriodo = getFilteredPublicationSeries(publicacoes);

		statTotal.textContent = String(publicacoes.total_geral || 0);

		renderSummary(resultado, previewHtml);
		renderPublications(seriesPeriodo);
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
