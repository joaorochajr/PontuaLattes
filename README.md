# IC COLLECT

Projeto para coletar dados públicos do currículo Lattes e calcular o barema docente de seleção de bolsas de Iniciação Científica.

## Objetivo

O sistema recebe a URL de um currículo Lattes, consulta os dados públicos disponíveis no Buscatextual, organiza os indicadores encontrados e calcula automaticamente a pontuação do barema docente.

## Estado atual

Atualmente o projeto já possui:

- API HTTP local em Python
- página web integrada à API
- coleta do código interno do Lattes
- coleta do HTML de preview
- coleta do HTML de índices de produção
- extração das séries bibliográficas por ano
- cálculo inicial do barema docente

## Estrutura do projeto

```text
IC_COLLECT/
├── API/
│   ├── main.py
│   ├── controller.py
│   └── service.py
├── DB/
├── SPA/
│   ├── index.html
│   ├── app.js
│   └── styles.css
└── README.md
```

## Componentes principais

### Backend

- [API/main.py](API/main.py): inicia o servidor HTTP local, entrega a SPA e expõe o endpoint `/api/lattes`
- [API/controller.py](API/controller.py): armazena o resultado da coleta e calcula o barema
- [API/service.py](API/service.py): consulta o Lattes, normaliza a URL, obtém o código interno e coleta os HTMLs necessários

### Frontend

- [SPA/index.html](SPA/index.html): estrutura da página
- [SPA/app.js](SPA/app.js): integração com a API e renderização dos resultados
- [SPA/styles.css](SPA/styles.css): estilos da interface

## Requisitos para executar o projeto

Para rodar o projeto completo localmente, é necessário ter:

### Sistema e ambiente

- sistema operacional com terminal disponível, como Linux, macOS ou Windows
- navegador web moderno, como Chrome, Edge ou Firefox

### Python

- Python 3.10 ou superior
- comando `python3` disponível no terminal

### Bibliotecas Python utilizadas

O backend usa apenas bibliotecas padrão do Python e a biblioteca `requests`.

Dependências necessárias:

- `requests`

Se precisar instalar manualmente:

```bash
pip3 install requests
```

### Rede

- acesso à internet para consultar o Lattes e o Buscatextual do CNPq
- liberação de conexões HTTP/HTTPS para os domínios do Lattes

### Porta local

- porta `8000` livre para subir o servidor local

Se a porta estiver ocupada, será necessário encerrar o processo que a está usando ou alterar a constante `PORT` em [API/main.py](API/main.py).

### Estrutura esperada

Para funcionar corretamente, o projeto espera esta organização:

- [API](API) com os arquivos do backend
- [SPA](SPA) com `index.html`, `app.js` e `styles.css`
- [DB](DB), mesmo que ainda não esteja em uso

### Observação importante

O projeto depende do formato atual das páginas públicas do Lattes. Se o CNPq alterar a estrutura HTML ou os endpoints públicos, partes da coleta e do cálculo podem deixar de funcionar até ajuste no código.

## Como executar

Na pasta [API](API), execute:

```bash
python3 main.py
```

Depois abra no navegador:

```text
http://127.0.0.1:8000
```

## Endpoint disponível

### `POST /api/lattes`

Recebe um JSON com a URL do currículo:

```json
{
	"url": "https://lattes.cnpq.br/1431810842888468"
}
```

Retorna um JSON com:

- status da coleta
- URL normalizada
- código interno do currículo
- HTML de preview
- HTML de índices
- publicações agregadas por ano
- barema calculado

## O que já é calculado no barema

O cálculo atual contempla a estrutura abaixo:

### I - Titulação

- Doutorado: 12
- Mestrado: 8

### II - Produção

- Artigo completo publicado em periódico
- Livro
- Capítulo de livro
- Resumo publicado em periódico
- Resumo e trabalho publicado em anais de evento
- Outras produções bibliográficas
- Patente
- Produção artística/cultural
- Trabalho técnico

### III - Formação de recursos humanos

- Doutorado
- Mestrado
- IC, IT, TCC, Especialização, PIBID, PIBEX, PET e Monitoria

### IV - Participação em eventos/comitê

- Apresentação de trabalho

## Regra de período

O projeto não usa mais um ano fixo como 2021.

O barema considera dinamicamente os últimos 5 anos a partir do ano vigente:

$$ano\_minimo = ano\_atual - 5$$

Exemplo:

- em 2026, o período considerado começa em 2021
- em 2027, o período considerado começa em 2022

Essa regra é usada tanto no backend quanto na interface web.

## Limitações atuais

- algumas informações do Lattes não aparecem de forma estruturada nos HTMLs coletados
- a detecção de titulação ainda depende de texto disponível no conteúdo retornado
- a contagem de patentes depende da presença da seção correspondente no HTML acessível
- orientações concluídas e outras categorias podem ficar zeradas quando o índice público não expõe os dados de forma identificável

## Próximos passos

- melhorar a extração de titulação, orientações e patentes
- estruturar melhor os dados retornados pela API
- persistir resultados em [DB](DB)
- refinar a interface e a apresentação do barema
