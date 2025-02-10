# Sistema Gamificado de Quiz

Este projeto tem como objetivo implementar um sistema de quiz, permitindo que milhares de alunos participem simultaneamente. O sistema é construído com FastAPI e utiliza o Redis como banco de dados em memória para garantir baixa latência, alta concorrência e apuração em tempo real.

## 📄 Documentação da API
Acesse a documentação completa no Postman:
[🔗 Documentação no Postman](https://documenter.getpostman.com/view/26303615/2sAYX9mfR9)

## Video
Acesse o video da explicação:
[🔗 Video explicando sobre o projeto](https://youtu.be/c1LVTiXJPOw)
)


## Sumário

- [Tecnologias Utilizadas](#tecnologias-utilizadas)
- [Requisitos do Projeto](#requisitos-do-projeto)
- [Estrutura de Dados no Redis](#estrutura-de-dados-no-redis)
- [Endpoints da API](#endpoints-da-api)
- [Como Executar o Projeto](#como-executar-o-projeto)
- [Diagrama da Modelagem dos Dados](#diagrama-da-modelagem-dos-dados)
- [Considerações Finais](#considerações-finais)

## Tecnologias Utilizadas

- **Linguagem:** Python 3.9+  
- **Framework:** FastAPI  
- **Banco de Dados em Memória:** Redis  
- **Contêineres:** Docker e Docker Compose  
- **Documentação da API:** Swagger (acessível via `/docs`)

## Requisitos do Projeto

O sistema foi desenvolvido considerando os seguintes pré-requisitos:
- **Baixa latência:** Resposta em menos de 50 milisegundos.
- **Alta concorrência:** Suporte a inúmeros inserts simultâneos.
- **Apuração em tempo real:** Votos e resultados atualizados instantaneamente.
- **Persistência durável:** Dados armazenados por 30 dias.
- **Integridade dos votos:** Um aluno só pode votar uma vez por pergunta.
- **Métricas e Rankings:** O sistema gera rankings com base em:
  - Alternativas mais votadas.
  - Questões com maior índice de acerto.
  - Questões com mais abstenções.
  - Tempo médio de resposta por questão.
  - Alunos com maior acerto e mais rápidos (rank final).
  - Alunos com maior acerto (independente do tempo).
  - Alunos mais rápidos (independente do número de acertos).

## Estrutura de Dados no Redis

Os dados são modelados no Redis utilizando diferentes estruturas:

- **Quiz:**  
  - **Chave:** `quiz:{quiz_id}` (Hash contendo campos como `title` e `professor`)  
  - **Lista de Perguntas:** `quiz:{quiz_id}:questions` (List contendo os IDs das perguntas)

- **Pergunta:**  
  - **Chave:** `question:{question_id}` (Hash com campos como `text`, alternativas, `correct_alternative`, `total_votes`, `correct_votes`, `response_time_sum` e `response_time_count`)
  - **Contagem de Votos:** `question:{question_id}:votes` (Hash com campos `A`, `B`, `C` e `D`)
  - **Votos por Aluno:** `question:{question_id}:student_votes` (Hash para garantir que cada aluno vote uma única vez)

- **Aluno:**  
  - **Chave:** `student:{student_id}` (Hash que armazena `correct_count`, `response_time_sum` e `response_time_count` para calcular a média e compor rankings)

- **Rankings:**  
  - **Ranking por Acertos:** `ranking:student:correct` (Sorted Set com score baseado no número de acertos)  
  - **Outras métricas:** Calculadas a partir dos dados armazenados nos hashes de alunos e perguntas.

## Endpoints da API

A API oferece os seguintes endpoints:

### CRUD e Votos

- **Criar Quiz:** `POST /quiz`  
    
    *Payload:*  
    ```json
    {
    "quiz_id": "1",
    "titulo": "Quiz de Geografia",
    "descricao": "Teste seus conhecimentos sobre geografia.",
    "professor": "Professor João"
    }```
  
- **Criar Pergunta:** `POST /quiz/{quiz_id}/pergunta/`
    
    *Payload:*
    ```json
    {
    "pergunta_id": "1",
    "texto": "Qual é a capital do Brasil?",
    "opcoes": {
        "A": "Paris",
        "B": "Brasilia",
        "C": "Roma",
        "D": "Berlim"
    },
    "resposta_correta": "B"
    }
    ```

- **Registrar Voto:** `POST /quiz/{quiz_id}/votar`
    
    *Payload:*
    ```json
    {
    "pergunta_id": "2",
    "opcao": "B",
    "aluno_id": "4"
    }
    ```

### Rankings

- **Alternativas Mais Votadas:**
    `GET /quiz/{quiz_id}/ranking/?pergunta_id={question_id}`

- **Questões Mais Acertadas:**
    `GET /quiz/{quiz_id}/questoes-mais-acertadas/`

- **Questões com Mais Abstenções:**
    `GET /quiz/{quiz_id}/questoes-com-mais-abstencoes/`

- **Tempo Médio de Resposta por Questão:**
    `GET /quiz/{quiz_id}/tempo-medio/?pergunta_id={question_id}`

- **Ranking Final dos Alunos (maior acerto e mais rápidos):**
    `GET /quiz/{quiz_id}/alunos-maior-acerto-mais-rapidos/`

- **Alunos com Maior Acerto:**
    `GET /quiz/{quiz_id}/alunos-com-mais-acertos/`

- **Alunos Mais Rápidos:**
    `GET /quiz/{quiz_id}/alunos-mais-rapidos/`

### Como Executar o Projeto

- **Pré-requisitos**

    Debian 12 (Certifique-se de que seu sistema está atualizado.)

    Docker & Docker Compose.
    
Instale com:

`sudo apt update`

`sudo apt install docker.io docker-compose -y`

`sudo systemctl enable docker`

`sudo systemctl start docker`

Para executar comandos do Docker sem sudo, adicione seu usuário ao grupo docker:

`sudo usermod -aG docker $USER`

`newgrp docker`

Python e pip (opcional, se executar localmente):

`sudo apt install python3 python3-pip -y`

Executando com Docker Compose

Clone o repositório:

`git clone https://github.com/seu-usuario/seu-projeto.git`

`cd seu-projeto`

Suba os containers:

`docker-compose up --build`

A API ficará disponível em: http://localhost:8000
A documentação interativa (Swagger) estará em: http://localhost:8000/docs

Executando Localmente (Sem Docker)

Instale as dependências:

`pip install -r requirements.txt`

Inicie o servidor da API:

`uvicorn main:app --host 0.0.0.0 --port 8000`

Certifique-se de que o Redis está rodando:

`sudo apt install redis-server -y`

`sudo systemctl start redis-server`

**Considerações Finais**

*Persistência:* Todos os dados (quizzes, perguntas, votos e rankings) possuem um tempo de expiração de 30 dias.

*Desempenho:* O uso de operações atômicas do Redis garante baixa latência e alta concorrência.

*Testes:* Utilize a documentação interativa (Swagger) ou a coleção do Postman para validar as funcionalidades.
