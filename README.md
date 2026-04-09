# Barema Automático - IC

Projeto de extensão desenvolvido na disciplina EXA618: Programação para Redes, da Universidade Estadual de Feira de Santana (UEFS), com foco na automatização da análise de currículos Lattes e no cálculo do barema para bolsas de Iniciação Científica.

- Edital IC UEFS 2026: http://www.pppg.uefs.br/arquivos/File/editais/IC/2026/Edital_IC_UEFS_2026.pdf
- Repositório: https://github.com/argalvao/IC_COLLECT
- Desenvolvedores: Abel Galvão, Alex Júnior e Bruno Campos

## Visão geral

O sistema recebe uma URL pública do currículo Lattes ou apenas o código do currículo, consulta os dados públicos disponíveis no CNPq/Buscatextual, extrai indicadores bibliográficos e calcula automaticamente a pontuação do barema docente.

Além da coleta e do cálculo, o projeto também oferece:

- autenticação exclusiva para acesso ao dashboard
- armazenamento das consultas em Google Sheets
- armazenamento do barema consolidado por currículo
- dashboard com histórico das consultas realizadas
- interface web integrada ao backend
- suporte a execução local e deploy no Render

## Funcionalidades atuais

### Coleta e processamento do Lattes

- recebe URL completa ou código público do Lattes
- normaliza a entrada automaticamente
- localiza o código interno do currículo
- coleta o HTML de preview do currículo
- coleta o HTML de índices/gráficos de produção
- extrai séries bibliográficas por ano
- calcula publicações no período dinâmico dos últimos 5 anos
- calcula o barema completo com limites por seção

### Autenticação

- login com geração de token de sessão
- logout com invalidação da sessão
- proteção do dashboard e do histórico por token
- criação automática de um usuário padrão no banco
- barema liberado sem autenticação

### Persistência e histórico

- grava consultas realizadas
- atualiza a consulta anterior quando o mesmo Lattes é consultado novamente
- grava o barema associado ao currículo consultado
- mantém nome da pessoa quando identificado
- lista consultas no dashboard com paginação

### Frontend

- página principal para consulta do currículo
- página de login
- dashboard com resumo de consultas
- visualização do barema por seção
- visualização das publicações por ano

## Estrutura do projeto

```text
IC_COLLECT/
├── API/
│   ├── controller.py
│   ├── database.py
│   ├── main.py
│   └── service.py
├── SPA/
│   ├── app.js
│   ├── auth.js
│   ├── cadastro.html
│   ├── dashboard.html
│   ├── dashboard.js
│   ├── index.html
│   ├── login.html
│   └── styles.css
├── requirements.txt
└── README.md
```

## Arquitetura do sistema

O projeto funciona como um serviço Python único que:

1. serve os arquivos estáticos da pasta [SPA](SPA)
2. expõe endpoints HTTP em [API/main.py](API/main.py)
3. consulta os dados públicos do Lattes em [API/service.py](API/service.py)
4. processa publicações e calcula o barema em [API/controller.py](API/controller.py)
5. persiste dados em Google Sheets por meio de [API/database.py](API/database.py)

## Componentes principais

### Backend

- [API/main.py](API/main.py)
	- inicia o servidor HTTP
	- serve a SPA
	- expõe endpoints de autenticação, consulta e histórico
	- lê `HOST` e `PORT` do ambiente

- [API/service.py](API/service.py)
	- normaliza a URL informada
	- consulta o currículo no Lattes
	- obtém o código interno do currículo
	- baixa o HTML de preview e o HTML de índices
	- utiliza a biblioteca `requests`

- [API/controller.py](API/controller.py)
	- extrai variáveis JavaScript do HTML de índices
	- normaliza anos e séries de publicações
	- calcula publicações por período
	- calcula pontuação do barema
	- produz o payload final retornado pela API


- [API/database.py](API/database.py)
	- inicializa a planilha usada como banco de dados
	- garante a existência das abas necessárias
	- registra consultas sem duplicar o mesmo Lattes
	- registra baremas
	- cria usuários
	- valida login
	- gerencia sessões por token

### Frontend

- [SPA/index.html](SPA/index.html)
	- página principal da aplicação
	- formulário para consulta do Lattes
	- área de exibição do barema e das publicações

- [SPA/app.js](SPA/app.js)
	- envia a consulta para `/api/lattes`
	- permite consulta sem login
	- renderiza resumo da coleta
	- renderiza publicações dos últimos 5 anos
	- renderiza o barema por blocos
	- exibe logout apenas quando existe sessão ativa

- [SPA/login.html](SPA/login.html) e [SPA/auth.js](SPA/auth.js)
	- autenticação para acesso ao dashboard
	- armazenamento do token no `localStorage`
	- redirecionamento para o histórico após login

- [SPA/cadastro.html](SPA/cadastro.html)
	- página legada de cadastro
	- não faz parte do fluxo principal atual

- [SPA/dashboard.html](SPA/dashboard.html) e [SPA/dashboard.js](SPA/dashboard.js)
	- exibição de histórico de consultas
	- cards de resumo
	- gráficos com Chart.js
	- tabela paginada

- [SPA/styles.css](SPA/styles.css)
	- estilos da interface

## Requisitos

### Ambiente

- Linux, macOS ou Windows
- navegador web moderno
- acesso à internet para consultar os serviços públicos do Lattes

### Python

- Python 3.10 ou superior
- `python3` disponível no terminal

### Dependências

As dependências estão em [requirements.txt](requirements.txt).

Instalação:

```bash
pip3 install -r requirements.txt
```

Dependências principais:

- `requests>=2.31.0`
- `gspread>=6.1.2`
- `google-auth>=2.38.0`

### Banco de dados

- Google Sheets como base persistente
- autenticação por conta de serviço do Google
- uma aba para cada entidade: `consultas`, `barema`, `users` e `sessions`

Variáveis de ambiente obrigatórias:

- `GOOGLE_SHEETS_SPREADSHEET_ID`
- `GOOGLE_SERVICE_ACCOUNT_JSON` ou `GOOGLE_SERVICE_ACCOUNT_FILE`

## Como executar localmente

Na raiz do projeto, instale as dependências:

```bash
pip3 install -r requirements.txt
```

Antes de iniciar, configure a planilha e a conta de serviço:

```bash
export GOOGLE_SHEETS_SPREADSHEET_ID="SEU_ID_DA_PLANILHA"
export GOOGLE_SERVICE_ACCOUNT_FILE="DB/pontuallates_key.json"
```

Depois inicie a aplicação:

```bash
cd API
python3 main.py
```

Em seguida, abra no navegador:

```text
http://127.0.0.1:8000
```

## Deploy no Render

O projeto está preparado para ser publicado no Render como um único serviço web Python.

### Configuração recomendada

- Build Command: `pip install -r requirements.txt`
- Start Command: `python3 API/main.py`

### Observações

- o servidor usa `0.0.0.0`
- a porta é lida da variável `PORT`
- os arquivos da pasta [SPA](SPA) são servidos pelo próprio backend
- frontend e API funcionam no mesmo domínio

## Fluxo da aplicação

### 1. Consulta pública do barema

Qualquer usuário pode:

- acessar [SPA/index.html](SPA/index.html)
- informar uma URL ou código do Lattes
- consultar e visualizar o barema sem autenticação

### 2. Consulta do currículo

Na página principal [SPA/index.html](SPA/index.html):

- o usuário informa uma URL ou código do Lattes
- o frontend envia a requisição para `/api/lattes`
- o backend consulta os dados públicos do currículo
- se o mesmo currículo já tiver sido consultado antes, o sistema substitui o registro anterior pela consulta mais recente
- o resultado é processado e devolvido ao frontend

### 3. Renderização dos resultados

O frontend mostra:

- nome do pesquisador
- código Lattes
- anos considerados
- publicações do período
- resumo do barema
- pontuação detalhada por seção
- observações automáticas quando necessário

### 4. Login para o dashboard

Quando o usuário clica em histórico:

- é redirecionado para [SPA/login.html](SPA/login.html)
- autentica com o usuário padrão do sistema
- recebe um token salvo no navegador
- acessa [SPA/dashboard.html](SPA/dashboard.html)

### 5. Histórico

Cada consulta é persistida no banco e pode ser visualizada no dashboard autenticado.

## Endpoints da API

## `GET /health`

Retorna um payload simples para verificar se o serviço está ativo.

Exemplo de resposta:

```json
{
	"status": "ok"
}
```

## `GET /api/consultas`

Lista o histórico de consultas registradas.

Esse endpoint exige autenticação via token.

Parâmetros opcionais de query:

- `start_date`
- `end_date`
- `success`

Exemplo:

```text
/api/consultas?start_date=2026-01-01&end_date=2026-12-31&success=1
```

Resposta:

```json
{
	"success": true,
	"consultas": []
}
```

## `POST /api/register`

Endpoint atualmente desabilitado.

O sistema trabalha com um usuário padrão para acesso ao dashboard e retorna erro caso alguém tente criar conta por esse endpoint.

## `POST /api/login`

Autentica um usuário e retorna um token.

Exemplo de body:

```json
{
	"username": "admin",
	"password": "pontualattes"
}
```

Exemplo de resposta de sucesso:

```json
{
	"success": true,
	"token": "...",
	"message": "Login efetuado com sucesso."
}
```

## `POST /api/logout`

Encerra a sessão atual.

Cabeçalho esperado:

```text
Authorization: Bearer <token>
```

## `POST /api/lattes`

Executa a coleta do currículo e retorna o barema calculado.

Esse endpoint não exige autenticação.

Exemplo de body:

```json
{
	"url": "https://lattes.cnpq.br/1431810842888468"
}
```

Também aceita:

```json
{
	"url": "1431810842888468"
}
```

O retorno inclui, entre outros campos:

- `success`
- `message`
- `url`
- `code`
- `nome`
- `preview_html`
- `index_html`
- `publicacoes`
- `barema`

## Estrutura do barema calculado

O cálculo atual está dividido em quatro blocos.

### I - Titulação

- Doutorado: 12 pontos
- Mestrado: 8 pontos

### II - Produção

- artigo completo publicado em periódico
- livro
- capítulo de livro
- resumo publicado em periódico
- resumo e trabalho publicado em anais de evento
- outras produções bibliográficas
- patente
- produção artística/cultural
- trabalho técnico

Limite da seção: 30 pontos.

### III - Formação de recursos humanos

- doutorado como orientador
- mestrado como orientador
- IC, IT, TCC, Especialização, PIBID, PIBEX, PET e Monitoria

Limite da seção: 12 pontos.

### IV - Participação em eventos/comitê

- apresentação de trabalho

Limite da seção: 6 pontos.

### Total

O total final é limitado a 60 pontos.

## Regra de período

O projeto considera dinamicamente os últimos 5 anos com base no ano atual:

$$ano\_minimo = ano\_atual - 5$$

Exemplo:

- em 2026, o período começa em 2021
- em 2027, o período começa em 2022

Essa regra é aplicada no backend e refletida na interface.

## Persistência em banco de dados

O banco agora é uma planilha do Google Sheets.

Na primeira execução, a aplicação cria automaticamente as abas:

- `users`
- `sessions`
- `consultas`
- `barema`

### Aba `users`

Armazena usuários do sistema.

Atualmente, a aplicação garante a existência automática de um usuário padrão para acesso ao dashboard:

- usuário: `admin`
- senha padrão: `pontualattes`

Esses valores podem ser sobrescritos pelas variáveis de ambiente `DEFAULT_DASHBOARD_USERNAME` e `DEFAULT_DASHBOARD_PASSWORD`.

Campos principais:

- `id`
- `username`
- `password_hash`
- `salt`

### Aba `sessions`

Armazena sessões autenticadas.

Campos principais:

- `token`
- `user_id`
- `created_at`

### Aba `consultas`

Armazena somente a versão mais recente de cada consulta de Lattes.

Quando a mesma URL pública ou o mesmo código do Lattes é consultado novamente, o registro anterior é atualizado em vez de duplicado.

Campos principais:

- `id`
- `url_informada`
- `url_consultada`
- `code`
- `success`
- `message`
- `created_at`

### Aba `barema`

Armazena o barema consolidado por currículo.

Campos principais:

- `id`
- `consulta_id`
- `code`
- `nome`
- `titulacao_bruto`
- `titulacao_limitado`
- `producao_bruto`
- `producao_limitado`
- `formacao_bruto`
- `formacao_limitado`
- `eventos_bruto`
- `eventos_limitado`
- `total_bruto`
- `total_limitado`
- `barema_json`
- `updated_at`

## Interface web

### Página inicial

Arquivo: [SPA/index.html](SPA/index.html)

Contém:

- apresentação do projeto
- link para o edital
- acesso ao histórico com redirecionamento para login
- botão de logout
- formulário de consulta
- resultado detalhado do barema

### Login

Arquivo: [SPA/login.html](SPA/login.html)

Contém:

- formulário de autenticação
- mensagem de erro ou sucesso
- acesso exclusivo ao histórico de consultas

### Cadastro

Arquivo: [SPA/cadastro.html](SPA/cadastro.html)

Contém:

- uma interface legada de cadastro
- não é utilizada no fluxo principal atual

### Dashboard

Arquivos: [SPA/dashboard.html](SPA/dashboard.html) e [SPA/dashboard.js](SPA/dashboard.js)

Contém:

- total de consultas
- total de sucessos
- total de falhas
- taxa de sucesso
- gráfico de acessos por dia
- gráfico de status das consultas
- gráfico de top consultas com sucesso
- tabela paginada de histórico

## Limitações e observações atuais

- o projeto depende da estrutura atual das páginas públicas do Lattes e do Buscatextual
- alterações no HTML externo podem quebrar parte da extração
- a identificação automática da titulação depende de texto encontrado no HTML de preview
- algumas informações do currículo podem não aparecer de forma estruturada
- o acesso ao histórico depende do usuário padrão configurado no banco ou por variável de ambiente
- o arquivo [SPA/dashboard.js](SPA/dashboard.js) referencia `/api/grafico-nomes`, mas esse endpoint não está implementado atualmente no backend; o código já evita falha se o gráfico não existir na página

## Possíveis melhorias futuras

- implementar o endpoint `/api/grafico-nomes`
- adicionar expiração de sessão
- melhorar tratamento de erros de rede com o Lattes
- criar testes automatizados
- documentar exemplos completos de resposta da API
- adicionar paginação e filtros avançados também no backend do dashboard
