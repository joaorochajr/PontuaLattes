const token = localStorage.getItem("auth_token");
if (!token) {
    window.location.href = "./login.html?redirect=dashboard.html";
}

// Variáveis de gráficos

// Paginação
let paginaAtual = 1;
const itensPorPagina = 10;

// Aba ativa (ic | aeri)
let tabAtiva = "ic";

// Inicializa dashboard
document.addEventListener("DOMContentLoaded", () => {
    carregarDashboard();
    carregarEditais();

    document.querySelectorAll(".btn-salvar-edital").forEach((btn) => {
        btn.addEventListener("click", () => salvarEdital(btn.dataset.tipo));
    });

    document.querySelectorAll(".tab-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
            tabAtiva = btn.dataset.tab;
            document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");

            const titulo = document.getElementById("historico-title");
            if (titulo) {
                titulo.textContent = `Histórico de Consultas — Edital ${tabAtiva.toUpperCase()}`;
            }

            paginaAtual = 1;
            carregarDashboard(1);
        });
    });
});

async function fetchConsultas(pagina = 1) {
    try {
        const response = await fetch(`/api/consultas?page=${pagina}&per_page=${itensPorPagina}&tipo=${tabAtiva}`, {
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

function escapeHtml(valor) {
    return String(valor ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function formatarLattesUrl(consulta) {
    const candidatos = [consulta?.url_consultada, consulta?.url_informada, consulta?.code]
        .map(valor => String(valor ?? "").trim())
        .filter(Boolean);

    for (const valor of candidatos) {
        if (/^https?:\/\//i.test(valor)) {
            return valor;
        }

        if (/^lattes\.cnpq\.br\/\d+$/i.test(valor)) {
            return `http://${valor}`;
        }

        if (/^\d+$/.test(valor)) {
            return `http://lattes.cnpq.br/${valor}`;
        }
    }

    return "-";
}

function formatarIndicadoresUrl(code) {
    const valor = String(code ?? "").trim();

    if (!valor) {
        return "-";
    }

    return `http://buscatextual.cnpq.br/buscatextual/graficos.do?metodo=apresentar&codRHCript=${encodeURIComponent(valor)}`;
}

function renderizarLink(url) {
    if (!url || url === "-") {
        return "-";
    }

    const urlEscapada = escapeHtml(url);
    return `<a class="soft-link" href="${urlEscapada}" target="_blank" rel="noopener noreferrer">${urlEscapada}</a>`;
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



/* 
   Função da tabela do histórico
 */
function gerarTabelaHistoricoConsultas(consultas, totalPaginas) {
    const tabela = document.getElementById("tabela-consultas");
    tabela.innerHTML = consultas.map(c => `
        <tr>
            <td>${escapeHtml(c.id)}</td>
            <td>${escapeHtml(c.nome || "-")}</td>
            <td>${escapeHtml(c.total_limitado || "-")}</td>
            <td>${renderizarLink(formatarLattesUrl(c))}</td>
            <td>${formatarIndicadoresUrl(c.code) === "-"
                ? "-"
                : `<a class="soft-link" href="${escapeHtml(formatarIndicadoresUrl(c.code))}" target="_blank" rel="noopener noreferrer">Link</a>`}</td>
            <td>${c.success === 1 ? "✅" : "❌"}</td>
            <td>${escapeHtml(c.created_at || "-")}</td>
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
   Renderização de controles e paginação
 */
function renderizarControles(totalPaginas) {
    const container = document.getElementById("paginacao");
    container.innerHTML = "";

    const maxBotoes = 5; // máximo de botões numéricos visíveis
    let start = Math.max(paginaAtual - Math.floor(maxBotoes / 2), 1);
    let end = start + maxBotoes - 1;

    if (end > totalPaginas) {
        end = totalPaginas;
        start = Math.max(end - maxBotoes + 1, 1);
    }

    // Botão anterior
    const btnPrev = document.createElement("button");
    btnPrev.textContent = "‹";
    btnPrev.disabled = paginaAtual === 1;
    btnPrev.addEventListener("click", () => mudarPagina(paginaAtual - 1));
    container.appendChild(btnPrev);

    // Botões numéricos
    if (start > 1) {
        const btn1 = document.createElement("button");
        btn1.textContent = "1";
        btn1.addEventListener("click", () => mudarPagina(1));
        container.appendChild(btn1);

        if (start > 2) {
            const dots = document.createElement("span");
            dots.textContent = "…";
            dots.style.margin = "0 5px";
            container.appendChild(dots);
        }
    }

    for (let i = start; i <= end; i++) {
        const btn = document.createElement("button");
        btn.textContent = i;
        btn.className = i === paginaAtual ? "current" : "";
        btn.addEventListener("click", () => mudarPagina(i));
        container.appendChild(btn);
    }

    if (end < totalPaginas) {
        if (end < totalPaginas - 1) {
            const dots = document.createElement("span");
            dots.textContent = "…";
            dots.style.margin = "0 5px";
            container.appendChild(dots);
        }

        const btnLast = document.createElement("button");
        btnLast.textContent = totalPaginas;
        btnLast.addEventListener("click", () => mudarPagina(totalPaginas));
        container.appendChild(btnLast);
    }

    // Botão próximo
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
   Carregar e salvar editais
 */
async function carregarEditais() {
    try {
        const response = await fetch("/api/editais");
        const dados = await response.json();
        if (!dados.success) return;

        ["ic", "aeri"].forEach((tipo) => {
            const edital = dados[tipo] || {};
            const anoEl = document.getElementById(`edital-${tipo}-ano`);
            const urlEl = document.getElementById(`edital-${tipo}-url`);
            if (anoEl) anoEl.value = edital.ano || "";
            if (urlEl) urlEl.value = edital.url || "";
        });
    } catch (err) {
        console.error("Erro ao carregar editais:", err);
    }
}

async function salvarEdital(tipo) {
    const ano = document.getElementById(`edital-${tipo}-ano`)?.value.trim() || "";
    const url = document.getElementById(`edital-${tipo}-url`)?.value.trim() || "";
    const statusEl = document.getElementById(`edital-${tipo}-status`);

    try {
        const response = await fetch("/api/editais", {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`,
            },
            body: JSON.stringify({ tipo, ano, url }),
        });
        const dados = await response.json();
        if (statusEl) {
            statusEl.textContent = dados.success ? "✅ Salvo!" : `❌ ${dados.message}`;
            setTimeout(() => { statusEl.textContent = ""; }, 3000);
        }
    } catch (err) {
        if (statusEl) {
            statusEl.textContent = "❌ Erro de conexão.";
            setTimeout(() => { statusEl.textContent = ""; }, 3000);
        }
    }
}

/* 
   Função para carregar a todas as componentes da dashboard
 */
async function carregarDashboard(pagina = 1) {
    
    const dadosConsultas = await fetchConsultas(pagina);
    const resumo = await fetchResumo();

    if (!dadosConsultas || !resumo) return;

    gerarTabelaHistoricoConsultas(dadosConsultas.consultas, dadosConsultas.total_pages);
    resumoConsulta(resumo);
}