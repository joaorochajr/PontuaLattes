document.addEventListener("DOMContentLoaded", () => {
    criarGraficoVazio();  
    carregarDashboard();      
});
let graficoTopUrls;
let graficoDia;
let graficoStatus;
let paginaAtual = 1;
const itensPorPagina = 10;
let todasConsultas = [];

async function carregarDashboard() {
    const response = await fetch("http://127.0.0.1:8000/api/consultas");
    const dados = await response.json();

    if (!dados.success) return;

    todasConsultas = dados.consultas;

    preencherResumo(todasConsultas);
    criarGraficoPorDia(todasConsultas);
    criarGraficoStatus(todasConsultas);
    preencherTopUrls(todasConsultas);
    atualizarGraficoNomes();

    renderizarTabela(); 
}

function preencherResumo(consultas) {
    const total = consultas.length;
    const sucessos = consultas.filter(c => c.success === 1).length;
    const falhas = total - sucessos;
    const taxa = total ? ((sucessos / total) * 100).toFixed(1) : 0;

    document.getElementById("total-consultas").textContent = total;
    document.getElementById("total-sucessos").textContent = sucessos;
    document.getElementById("total-falhas").textContent = falhas;
    document.getElementById("taxa-sucesso").textContent = taxa + "%";
}

function renderizarTabela() {
    const inicio = (paginaAtual - 1) * itensPorPagina;
    const fim = inicio + itensPorPagina;

    const pagina = todasConsultas.slice(inicio, fim);

    document.getElementById("tabela-consultas").innerHTML =
        pagina.map(c => `
            <tr>
                <td>${c.id}</td>
                <td>${c.nome || "-"}</td> 
                <td>${c.url_informada}</td>
                <td>${c.code}</td>
                <td>${c.success === 1 ? "✅" : "❌"}</td>
                <td>${c.created_at}</td>
            </tr>
        `).join("");

    renderizarControles();
}

function criarGraficoPorDia(consultas) {
    const agrupado = {};

    consultas.forEach(c => {
        const dia = c.created_at.split(" ")[0];
        agrupado[dia] = (agrupado[dia] || 0) + 1;
    });

    const labels = Object.keys(agrupado);
    const valores = Object.values(agrupado);

    if (!graficoDia) {
        graficoDia = new Chart(document.getElementById("grafico-acessos"), {
            type: "line",
            data: {
                labels: labels,
                datasets: [{
                    label: "Acessos",
                    data: valores
                }]
            }
        });
    } else {
        graficoDia.data.labels = labels;
        graficoDia.data.datasets[0].data = valores;
        graficoDia.update();
    }
}

function criarGraficoStatus(consultas) {
    const sucessos = consultas.filter(c => c.success === 1).length;
    const falhas = consultas.length - sucessos;

    if (!graficoStatus) {
        graficoStatus = new Chart(document.getElementById("grafico-status"), {
            type: "doughnut",
            data: {
                labels: ["Sucesso", "Erro"],
                datasets: [{
                    data: [sucessos, falhas]
                }]
            }
        });
    } else {
        graficoStatus.data.datasets[0].data = [sucessos, falhas];
        graficoStatus.update();
    }
}

function preencherTopUrls(consultas) {

    const apenasSucessos = consultas.filter(c => c.success === 1);

    const contagem = {};

    apenasSucessos.forEach(c => {
        const chave = c.nome || c.url_informada;
        contagem[chave] = (contagem[chave] || 0) + 1;
    });

    const top5 = Object.entries(contagem)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

    const labels = top5.map(item => item[0]);
    const valores = top5.map(item => item[1]);

    if (!graficoTopUrls) {
        graficoTopUrls = new Chart(document.getElementById("grafico-top-urls"), {
            type: "bar",
            data: {
                labels: labels,
                datasets: [{
                    label: "Consultas com Sucesso",
                    data: valores
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false
            }
        });
    } else {
        graficoTopUrls.data.labels = labels;
        graficoTopUrls.data.datasets[0].data = valores;
        graficoTopUrls.update();
    }
}
function criarGraficoVazio() {
    graficoNomes = new Chart(document.getElementById("grafico-nomes"), {
        type: "bar",
        data: {
            labels: [],
            datasets: [{
                label: "Total de Consultas",
                data: [],
                barThickness: 18
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

async function atualizarGraficoNomes() {
    const response = await fetch("/api/grafico-nomes");
    const data = await response.json();

    if (!data.success) return;

    const top5 = data.dados
        .sort((a, b) => b.total - a.total)
        .slice(0, 5);

    graficoNomes.data.labels = top5.map(i => i.nome);
    graficoNomes.data.datasets[0].data = top5.map(i => i.total);

    graficoNomes.update();
}

function renderizarControles() {
    const totalPaginas = Math.ceil(todasConsultas.length / itensPorPagina);
    const container = document.getElementById("paginacao");

    if (totalPaginas <= 1) {
        container.innerHTML = "";
        return;
    }

    let html = `<div class="pagination">`;

    // Botão anterior
    html += `
        <button 
            class="page-btn ${paginaAtual === 1 ? "disabled" : ""}" 
            onclick="mudarPagina(${paginaAtual - 1})"
            ${paginaAtual === 1 ? "disabled" : ""}
        >
            ‹
        </button>
    `;

    // Números das páginas
    for (let i = 1; i <= totalPaginas; i++) {
        html += `
            <button 
                class="page-btn ${i === paginaAtual ? "active" : ""}"
                onclick="mudarPagina(${i})"
            >
                ${i}
            </button>
        `;
    }

    // Botão próxima
    html += `
        <button 
            class="page-btn ${paginaAtual === totalPaginas ? "disabled" : ""}" 
            onclick="mudarPagina(${paginaAtual + 1})"
            ${paginaAtual === totalPaginas ? "disabled" : ""}
        >
            ›
        </button>
    `;

    html += `</div>`;

    container.innerHTML = html;
}

function mudarPagina(novaPagina) {
    paginaAtual = novaPagina;
    renderizarTabela();
}