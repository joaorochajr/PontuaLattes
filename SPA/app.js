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

	const anosLimpos = (publicacoes.anos || [])
		.map(a => String(a).trim())
		.filter(a => a !== '' && !isNaN(Number(a)));

	const itens = [
		['Nome', pesquisador],
		['URL consultada', resultado.url || '-'],
		['Código Lattes', resultado.code || '-'],
		['Anos encontrados', anosLimpos.join(', ') || 'Nenhum'],
		[
			`Anos desde ${anoMinimo}`,
			anosLimpos
				.filter(ano => Number(ano) >= anoMinimo)
				.join(', ') || 'Nenhum',
		],
	];

	summaryList.innerHTML = itens
		.map(([titulo, valor]) => `<li><strong>${titulo}:</strong> ${valor}</li>`)
		.join('');
}

function renderPublications(series) {
	const anoMinimo = getMinimumBaremaYear();
	publicationsTitle.textContent = `Publicações desde ${anoMinimo}`;

	if (!series.length) {
		publicationList.innerHTML = `<div class="publication-item">Nenhuma publicação encontrada a partir de ${anoMinimo}.</div>`;
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

function renderBaremaSection(title, section) {
	const itens = Object.entries(section.itens || {});

	return `
		<div class="barema-card">
			<div class="barema-card-header">
				<h3>${title}</h3>
				<div class="barema-card-total">
					<span>Bruto: ${formatNumber(section.subtotal_bruto)}</span>
					<span>Limitado: ${formatNumber(section.subtotal_limitado)}</span>
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
		renderBaremaSection('I - Titulação', buildTitulationSection(barema.titulacao || {})),
		renderBaremaSection('II - Produção', barema.producao || {}),
		renderBaremaSection('III - Formação de recursos humanos', barema.formacao_recursos_humanos || {}),
		renderBaremaSection('IV - Participação em eventos/comitê', barema.participacao_eventos_comite || {}),
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

form.addEventListener('submit', async (event) => {
	event.preventDefault();
	resetResults();

	const url = document.getElementById('lattes-url').value.trim();
	if (!url) {
		setStatus('error', 'Informe a URL do currículo Lattes.');
		return;
	}

	submitButton.disabled = true;
	submitButton.textContent = 'Consultando...';
	setStatus('info', 'Consultando a API e coletando os dados do currículo...');

	try {
		const response = await fetch('/api/lattes', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
			},
			body: JSON.stringify({ url }),
		});

		const resultado = await response.json();

		if (!response.ok || !resultado.success) {
			throw new Error(resultado.message || 'Não foi possível concluir a coleta.');
		}

		const previewHtml = resultado.preview_html || '';
		const publicacoes = resultado.publicacoes || {};
		const seriesPeriodo = getFilteredPublicationSeries(publicacoes);
		const barema = resultado.barema || null;

		statBaremaTotal.textContent = String(barema?.total_limitado || 0);
		statTotal.textContent = String(publicacoes.total_geral || 0);

		renderSummary(resultado, previewHtml);
		renderPublications(seriesPeriodo);
		renderBarema(barema);
		resultsSection.classList.add('visible');
		setStatus('success', 'Coleta realizada com sucesso.');
	} catch (error) {
		setStatus('error', error.message || 'Erro inesperado ao chamar a API.');
	} finally {
		submitButton.disabled = false;
		submitButton.textContent = 'Consultar';
	}
});
