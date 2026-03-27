const token = localStorage.getItem("auth_token");
if (!token) {
    window.location.href = "./login.html?redirect=dashboard.html";
}

// Variáveis de gráficos
let graficoTopUrls;
let graficoDia;
let graficoStatus;
let graficoNomes;

// Paginação
let paginaAtual = 1;
const itensPorPagina = 10;

// Inicializa dashboard
document.addEventListener("DOMContentLoaded", () => {
    carregarDashboard();
});

async function fetchConsultas(pagina = 1) {
    try {
        const response = await fetch(`/api/consultas?page=${pagina}&per_page=${itensPorPagina}`, {
            headers: { Authorization: `Bearer ${token}` }
        });

        if (response.status === 401) {
            localStorage.removeItem("auth_token");
            window.location.href = "./login.html?redirect=dashboard.html";
            return null;
        }

        const dados = await response.json();
        return dados.success ? dados : null;
    } catch (err) {
        console.error("Erro ao buscar consultas:", err);
        return null;
    }
}

async function fetchConsultasPorDia() {
    try {
        const response = await fetch(`/api/consultas/dia`, {
            headers: { Authorization: `Bearer ${token}` }
        });

        const dados = await response.json();
        return dados.success ? dados.dados : [];
    } catch (err) {
        console.error("Erro ao buscar consultas por dia:", err);
        return [];
    }
}

async function fetchResumo() {
    try {
        const response = await fetch(`/api/consultas/resumo`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        const dados = await response.json();
        return dados.success ? dados : null;
    } catch (err) {
        console.error("Erro ao buscar resumo:", err);
        return null;
    }
}

async function fetchTopUrls() {
    try {
        const response = await fetch(`/api/consultas/top5`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        const dados = await response.json();
        return dados.success ? dados.dados : [];
    } catch (err) {
        console.error("Erro ao buscar top URLs:", err);
        return [];
    }
}
/* 
   Função de requisição da API para o TOP 5 de
 */
async function fetchTopNomes() {
    try {
        const response = await fetch(`/api/consultas/top5`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        const dados = await response.json();
        return dados.success ? dados.dados : [];
    } catch (err) {
        console.error("Erro ao buscar top nomes:", err);
        return [];
    }
}

/* 
   Função da tabela do histórico
 */
function gerarTabelaHistoricoConsultas(consultas, totalPaginas) {
    const tabela = document.getElementById("tabela-consultas");
    tabela.innerHTML = consultas.map(c => `
        <tr>
            <td>${c.id}</td>
            <td>${c.nome || "-"}</td>
            <td>${c.total_limitado || "-"}</td>
            <td>${c.url_consultada}</td>
            <td>${c.code}</td>
            <td>${c.success === 1 ? "✅" : "❌"}</td>
            <td>${c.created_at}</td>
        </tr>
    `).join("");

    renderizarControles(totalPaginas);
}


/* 
   Resumo de falhas e sucessos
 */
function resumoConsulta(resumo) {
    document.getElementById("total-consultas").textContent = resumo.total || 0;
    document.getElementById("total-sucessos").textContent = resumo.sucessos || 0;
    document.getElementById("total-falhas").textContent = resumo.falhas || 0;
    document.getElementById("taxa-sucesso").textContent = ((resumo.sucessos / resumo.total) * 100).toFixed(1) + "%";
}

/* 
   Geração do gráfico do top 5 de URLS
 */
function gerarBarGraficoTopAcessos(topUrls) {
    const labels = topUrls.map(i => i.nome);
    const valores = topUrls.map(i => i.total);

    if (!graficoTopUrls) {
        graficoTopUrls = new Chart(document.getElementById("grafico-top-urls"), {
            type: "bar",
            data: { labels, datasets: [{ label: "Consultas com Sucesso", data: valores }] },
            options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false }
        });
    } else {
        graficoTopUrls.data.labels = labels;
        graficoTopUrls.data.datasets[0].data = valores;
        graficoTopUrls.update();
    }
}


/* 
   Gráfico de acesso por dias
 */

function criarGraficoPorDia(dadosPorDia) {
    const labels = dadosPorDia.map(item => item.dia);
    const valores = dadosPorDia.map(item => item.total);

    if (!graficoDia) {
        graficoDia = new Chart(document.getElementById("grafico-acessos"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Consultas por Dia",
                    data: valores,
                    fill: false,
                    borderColor: "rgb(75, 192, 192)",
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });
    } else {
        graficoDia.data.labels = labels;
        graficoDia.data.datasets[0].data = valores;
        graficoDia.update();
    }
}

/* 
   Gráfico de status de consulta
 */
function criarGraficoStatus(resumo) {
    const sucessos = resumo.sucessos || 0;
    const falhas = resumo.falhas || 0;

    if (!graficoStatus) {
        graficoStatus = new Chart(document.getElementById("grafico-status"), {
            type: "doughnut",
            data: { labels: ["Sucesso", "Erro"], datasets: [{ data: [sucessos, falhas] }] }
        });
    } else {
        graficoStatus.data.datasets[0].data = [sucessos, falhas];
        graficoStatus.update();
    }
}

async function fetchConsultasPorDia() {
    try {
        const response = await fetch(`/api/consultas/dia`, {
            headers: { Authorization: `Bearer ${token}` }
        });
        const dados = await response.json();
        return dados.success ? dados.dados : [];
    } catch (err) {
        console.error("Erro ao buscar consultas por dia:", err);
        return [];
    }
}

/* 
   Renderização de controles e paginação
 */
function renderizarControles(totalPaginas) {
    const container = document.getElementById("paginacao");
    container.innerHTML = "";

    const btnPrev = document.createElement("button");
    btnPrev.textContent = "‹";
    btnPrev.disabled = paginaAtual === 1;
    btnPrev.addEventListener("click", () => mudarPagina(paginaAtual - 1));
    container.appendChild(btnPrev);

    for (let i = 1; i <= totalPaginas; i++) {
        const btn = document.createElement("button");
        btn.textContent = i;
        btn.style.fontWeight = i === paginaAtual ? "bold" : "normal";
        btn.addEventListener("click", () => mudarPagina(i));
        container.appendChild(btn);
    }

    const btnNext = document.createElement("button");
    btnNext.textContent = "›";
    btnNext.disabled = paginaAtual === totalPaginas;
    btnNext.addEventListener("click", () => mudarPagina(paginaAtual + 1));
    container.appendChild(btnNext);
}
/* 
   Alteração de página
 */
function mudarPagina(novaPagina) {
    if (novaPagina < 1) return;
    paginaAtual = novaPagina;
    carregarDashboard(paginaAtual);
}

/* 
   Função para carregar a todas as componentes da dashboard
 */
async function carregarDashboard(pagina = 1) {
    
    const dadosConsultas = await fetchConsultas(pagina);
    const resumo = await fetchResumo();
    const topUrls = await fetchTopUrls();
    const consultasPorDia = await fetchConsultasPorDia();

    if (!dadosConsultas || !resumo) return;

    gerarTabelaHistoricoConsultas(dadosConsultas.consultas, dadosConsultas.total_pages);
    resumoConsulta(resumo);
    criarGraficoPorDia(consultasPorDia);
    criarGraficoStatus(resumo);
    gerarBarGraficoTopAcessos(topUrls);
}