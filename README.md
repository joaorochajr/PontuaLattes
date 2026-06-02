# PontuaLattes

Projeto de extensão desenvolvido na disciplina EXA618: Programação para Redes, da Universidade Estadual de Feira de Santana (UEFS).

Sistema que analisa o currículo Lattes e calcula automaticamente o barema para avaliação de candidatos a bolsas de **Iniciação Científica (IC)** e **Assessoria Especial de Relações Institucionais (AERI)** da UEFS.

- Repositório: https://github.com/argalvao/PontuaLattes
- Desenvolvedores: Abel Galvão, Alex Júnior e Bruno Campos

---

## Sumário

1. [Visão geral](#visão-geral)
2. [Funcionalidades](#funcionalidades)
3. [Estrutura do projeto](#estrutura-do-projeto)
4. [Como executar localmente](#como-executar-localmente)
5. [Banco de dados — Turso](#banco-de-dados--turso)
6. [Deploy no Vercel](#deploy-no-vercel)

---

## Visão geral

O sistema recebe uma URL pública do currículo Lattes (ou apenas o código), consulta os dados públicos disponíveis no CNPq/Buscatextual, extrai indicadores bibliográficos e calcula automaticamente a pontuação do barema conforme as regras do edital selecionado (IC ou AERI).

O backend é um único servidor Python (`BaseHTTPRequestHandler`) que serve a SPA e expõe os endpoints da API. O banco de dados é o [Turso](https://turso.tech) (libSQL).

---

## Funcionalidades

- Consulta pública do barema sem necessidade de login
- Suporte a editais de **IC** e **AERI** com regras de pontuação distintas
- Link dinâmico para o edital vigente configurável pelo dashboard
- Autenticação com token de sessão para acesso ao dashboard
- Histórico de consultas com paginação
- Dashboard administrativo para configurar URLs dos editais
- Interface web em SPA (HTML/CSS/JS puro, sem framework)

---

## Estrutura do projeto

```
PontuaLattes/
├── API/
│   ├── main.py           # servidor HTTP, roteamento e endpoints
│   ├── controller.py     # lógica de scraping, cálculo do barema IC e AERI
│   ├── service.py        # coleta dos dados públicos do Lattes
│   ├── database.py       # fachada do banco (reexporta funções do turso_store)
│   ├── turso_store.py    # camada de persistência — Turso/libSQL
│   └── requirements.txt  # dependências Python
├── SPA/
│   ├── index.html        # página principal — consulta do barema
│   ├── app.js            # lógica da consulta e renderização do barema
│   ├── auth.js           # autenticação e sessão
│   ├── login.html        # formulário de login
│   ├── dashboard.html    # dashboard administrativo
│   ├── dashboard.js      # lógica do dashboard
│   └── styles.css        # estilos da interface
├── api/
│   ├── index.py          # entrypoint Vercel (importa ICCollectHandler)
│   └── requirements.txt  # dependências instaladas pelo Vercel
├── vercel.json           # configuração do deploy serverless
└── README.md
```

---

## Como executar localmente

### Pré-requisitos

- Python 3.10 ou superior
- Acesso à internet (para consultar o Lattes e o Turso)

### 1. Clone o repositório

```bash
git clone https://github.com/argalvao/PontuaLattes.git
cd PontuaLattes
```

### 2. Crie e ative o ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r API/requirements.txt
```

### 4. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto:

```env
TURSO_URL=https://SEU-BANCO.turso.io
TURSO_AUTH_TOKEN=seu_token_aqui
DEFAULT_DASHBOARD_USERNAME=admin
DEFAULT_DASHBOARD_PASSWORD=sua_senha_aqui
HOST=0.0.0.0
PORT=8000
```

### 5. Inicie o servidor

```bash
cd API
env $(cat ../.env | grep -v '^#' | xargs) python3 main.py
```

Acesse em: `http://localhost:8000`

---

## Banco de dados — Turso

O projeto usa o [Turso](https://turso.tech) como banco de dados (SQLite distribuído). Siga os passos abaixo para criar sua própria instância gratuitamente.

### 1. Crie uma conta no Turso

Acesse https://turso.tech e cadastre-se com GitHub ou e-mail.

### 2. Instale a CLI do Turso

```bash
curl -sSfL https://get.tur.so/install.sh | bash
```

### 3. Faça login

```bash
turso auth login
```

### 4. Crie o banco de dados

```bash
turso db create pontualattes
```

### 5. Obtenha a URL do banco

```bash
turso db show pontualattes --url
# Exemplo: https://pontualattes-seuusuario.aws-us-east-1.turso.io
```

### 6. Gere o token de autenticação

```bash
turso db tokens create pontualattes
# Copie o token gerado — ele não será exibido novamente
```

### 7. Preencha o `.env`

```env
TURSO_URL=https://pontualattes-seuusuario.aws-us-east-1.turso.io
TURSO_AUTH_TOKEN=token_copiado_acima
```

As tabelas são criadas automaticamente na primeira execução (`turso_store.py`).

---

## Deploy no Vercel

### Pré-requisitos

- Conta no [Vercel](https://vercel.com) (plano Hobby é suficiente)
- Repositório hospedado no GitHub
- Banco Turso configurado (seção anterior)

### 1. Acesse o Vercel e crie um novo projeto

Vá em https://vercel.com/new e clique em **Import Git Repository**.

Selecione o repositório `PontuaLattes` (ou o fork que você criou).

### 2. Configure o projeto

Na tela de configuração, use os seguintes valores:

| Campo | Valor |
|---|---|
| Framework Preset | **Other** |
| Root Directory | *(deixe em branco ou `./`)* |
| Build Command | *(deixe em branco)* |
| Output Directory | *(deixe em branco)* |

### 3. Adicione as variáveis de ambiente

Ainda na tela de configuração, clique em **Environment Variables** e adicione:

| Nome | Valor |
|---|---|
| `TURSO_URL` | URL do banco Turso |
| `TURSO_AUTH_TOKEN` | Token de autenticação do Turso |
| `DEFAULT_DASHBOARD_USERNAME` | Nome de usuário do dashboard (ex: `admin`) |
| `DEFAULT_DASHBOARD_PASSWORD` | Senha do dashboard |

> **Atenção:** nunca comite o arquivo `.env` no repositório.

### 4. Faça o deploy

Clique em **Deploy**. O Vercel irá:

1. Clonar o repositório
2. Instalar as dependências de `api/requirements.txt`
3. Publicar `api/index.py` como função serverless Python
4. Rotear todas as requisições para essa função via `vercel.json`

### 5. Acesse a aplicação

Após o deploy bem-sucedido, o Vercel fornece uma URL no formato:

```
https://pontua-lattes-xxx.vercel.app
```

### Redeploy após mudanças

Qualquer `git push` para a branch `main` dispara um novo deploy automaticamente.

Para forçar um redeploy sem alterar código:

```bash
git commit --allow-empty -m "chore: redeploy" && git push origin main
```

### Limitações do plano Hobby

- Timeout máximo por requisição: **10 segundos**
- Currículos Lattes muito extensos podem ultrapassar esse limite
- Para eliminar o timeout, faça upgrade para o plano Pro e ajuste `maxDuration` em `vercel.json`

---

## Variáveis de ambiente — referência completa

| Variável | Obrigatória | Descrição |
|---|---|---|
| `TURSO_URL` | Sim | URL do banco Turso (ex: `https://...turso.io`) |
| `TURSO_AUTH_TOKEN` | Sim | Token JWT de autenticação do Turso |
| `DEFAULT_DASHBOARD_USERNAME` | Sim | Usuário administrador criado na primeira inicialização |
| `DEFAULT_DASHBOARD_PASSWORD` | Sim | Senha do usuário administrador |
| `HOST` | Não | Endereço de bind local (padrão: `0.0.0.0`) |
| `PORT` | Não | Porta local (padrão: `8000`) |

---

## Licença

Uso educacional — Projeto de extensão UEFS / EXA618.
