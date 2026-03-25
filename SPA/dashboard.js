document.addEventListener("DOMContentLoaded", () => {
    criarGraficoVazio();  
    carregarDashboard();      
});
let graficoNomes;
let graficoDia;
let graficoStatus;

async function carregarDashboard() {
    const response = await fetch("http://127.0.0.1:8000/api/consultas");
    const dados = await response.json();

    if (!dados.success) return;

    const consultas = dados.consultas;

    preencherResumo(consultas);
    criarGraficoPorDia(consultas);
    criarGraficoStatus(consultas);
    preencherTopUrls(consultas);
    preencherTabela(consultas);
    atualizarGraficoNomes();
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
    const contagem = {};

    consultas.forEach(c => {
        contagem[c.url_informada] = (contagem[c.url_informada] || 0) + 1;
    });

    const ordenado = Object.entries(contagem)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);

    document.getElementById("top-urls").innerHTML =
        ordenado.map(([url, qtd]) => `<li>${url} (${qtd})</li>`).join("");
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

function preencherTabela(consultas) {
    document.getElementById("tabela-consultas").innerHTML =
        consultas.map(c => `
            <tr>
                <td>${c.id}</td>
                <td>${c.nome || "-"}</td> 
                <td>${c.url_informada}</td>
                <td>${c.code}</td>
                <td>${c.success === 1 ? "✅" : "❌"}</td>
                <td>${c.created_at}</td>
            </tr>
        `).join("");
}