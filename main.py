from fastapi import FastAPI, HTTPException
import redis
import os
from dotenv import load_dotenv
from typing import Dict
from pydantic import BaseModel
from fastapi import Query


# Carregar variáveis de ambiente do arquivo .env
load_dotenv("dados.env")

app = FastAPI()

# Conexão com o Redis
try:
    redis_client = redis.StrictRedis(
        host=os.getenv("REDIS_HOST"),
        port=int(os.getenv("REDIS_PORT")),
        username=os.getenv("REDIS_USER"),
        password=os.getenv("REDIS_PASSWORD"),
        decode_responses=True
    )
    redis_client.ping()
    print("Conexão com Redis estabelecida com sucesso!")
except redis.ConnectionError as e:
    print("Erro ao conectar com o Redis:", e)
    raise


class Quiz(BaseModel):
    quiz_id: str
    titulo: str
    descricao: str
    professor: str 

class Pergunta(BaseModel):
    pergunta_id: str
    texto: str
    opcoes: Dict[str, str]  # Um dicionário com as opções
    resposta_correta: str


@app.post("/quiz/")
def criar_quiz(quiz: Quiz):
    """Cria um novo quiz com o professor associado."""
    if redis_client.exists(f"quiz:{quiz.quiz_id}"):
        raise HTTPException(status_code=400, detail="Quiz já existe.")
    redis_client.hset(
        f"quiz:{quiz.quiz_id}",
        mapping={
            "title": quiz.titulo,
            "description": quiz.descricao,
            "professor": quiz.professor  # Salvar o professor
        }
    )
    redis_client.expire(f"quiz:{quiz.quiz_id}", 2592000)  # Expira em 30 dias
    return {"message": f"Quiz {quiz.quiz_id} criado com sucesso pelo professor {quiz.professor}."}




@app.post("/quiz/{quiz_id}/pergunta/")
def adicionar_pergunta(quiz_id: str, pergunta: Pergunta):
    """Adiciona uma pergunta a um quiz, incluindo a resposta correta."""
    chave_pergunta = f"quiz:{quiz_id}:question:{pergunta.pergunta_id}"
    chave_resposta_correta = f"{chave_pergunta}:resposta_correta"

    # Verificar se a pergunta já existe
    if redis_client.exists(chave_pergunta):
        raise HTTPException(status_code=400, detail="Pergunta já existe.")

    # Validar se a resposta correta está nas opções
    if pergunta.resposta_correta not in pergunta.opcoes.keys():
        raise HTTPException(status_code=400, detail="Resposta correta não está entre as opções fornecidas.")

    # Salvar a pergunta, opções e a resposta correta
    redis_client.hset(chave_pergunta, mapping={"question": pergunta.texto, **pergunta.opcoes})
    redis_client.set(chave_resposta_correta, pergunta.resposta_correta)

    # Adicionar votos com pontuação inicial 0 para cada alternativa
    redis_client.zadd(f"{chave_pergunta}:votes", {opcao: 0 for opcao in pergunta.opcoes.keys()})

    # Configurar TTL para 30 dias
    redis_client.expire(chave_pergunta, 2592000)
    redis_client.expire(chave_resposta_correta, 2592000)
    redis_client.expire(f"{chave_pergunta}:votes", 2592000)

    return {"message": f"Pergunta {pergunta.pergunta_id} adicionada ao quiz {quiz_id} com sucesso."}





class Voto(BaseModel):
    pergunta_id: str
    opcao: str
    aluno_id: str

@app.post("/quiz/{quiz_id}/votar/")
def registrar_voto(quiz_id: str, voto: Voto):
    """
    Registra um voto em uma alternativa, armazena o tempo em milissegundos e verifica acertos.
    Garante que o mesmo aluno não possa votar mais de uma vez na mesma pergunta.
    """
    chave_votos = f"quiz:{quiz_id}:question:{voto.pergunta_id}:votes"
    chave_tempos = f"quiz:{quiz_id}:student:{voto.aluno_id}:question:{voto.pergunta_id}:times"
    chave_votos_aluno = f"quiz:{quiz_id}:student:{voto.aluno_id}:question:{voto.pergunta_id}:vote"
    chave_resposta_correta = f"quiz:{quiz_id}:question:{voto.pergunta_id}:resposta_correta"
    chave_acertos = f"quiz:{quiz_id}:question:{voto.pergunta_id}:correct"

    # Verificar se o aluno já votou nesta pergunta
    if redis_client.exists(chave_votos_aluno):
        raise HTTPException(status_code=403, detail="O aluno já votou nesta pergunta e não pode alterar o voto.")

    # Validar se a alternativa existe
    if redis_client.zrank(chave_votos, voto.opcao) is None:
        raise HTTPException(status_code=404, detail="Alternativa não encontrada.")

    # Registrar o voto
    redis_client.zincrby(chave_votos, 1, voto.opcao)

    # Incrementar no ranking geral por acertos
    redis_client.zincrby(f"quiz:{quiz_id}:ranking", 1, voto.aluno_id)

    # Capturar o tempo em milissegundos
    from time import time
    timestamp = int(time() * 1000)

    # Armazenar o tempo de votação para o aluno
    redis_client.rpush(chave_tempos, timestamp)

    # Registrar que o aluno votou nesta pergunta
    redis_client.set(chave_votos_aluno, voto.opcao)

    # Verificar se a resposta está correta
    resposta_correta = redis_client.get(chave_resposta_correta)
    if resposta_correta and voto.opcao == resposta_correta:
        # Incrementar o contador de acertos
        redis_client.incr(chave_acertos)

    # Expirar os dados em 30 dias
    redis_client.expire(chave_votos, 2592000)  # Expira em 30 dias
    redis_client.expire(chave_tempos, 2592000)  # Expira em 30 dias
    redis_client.expire(chave_votos_aluno, 2592000)  # Expira em 30 dias
    redis_client.expire(chave_acertos, 2592000)  # Expira em 30 dias

    return {
        "message": f"Voto registrado na alternativa {voto.opcao} da pergunta {voto.pergunta_id}.",
        "timestamp_ms": timestamp,
        "correct": voto.opcao == resposta_correta
    }






@app.get("/quiz/{quiz_id}/ranking/")
def obter_ranking(quiz_id: str, pergunta_id: str):
    """Retorna o ranking das alternativas mais votadas."""
    chave_votos = f"quiz:{quiz_id}:question:{pergunta_id}:votes"
    ranking = redis_client.zrevrange(chave_votos, 0, -1, withscores=True)
    return {"ranking": [{"opcao": r[0], "votos": int(r[1])} for r in ranking]}



@app.get("/quiz/{quiz_id}/tempo-medio/")
def calcular_tempo_medio(quiz_id: str, pergunta_id: str):
    """Calcula o tempo médio de resposta de uma pergunta em segundos."""
    # Buscar todas as chaves de tempos para os alunos nesta pergunta
    chaves_tempos = redis_client.keys(f"quiz:{quiz_id}:student:*:question:{pergunta_id}:times")
    
    if not chaves_tempos:
        raise HTTPException(status_code=404, detail="Nenhum tempo registrado.")
    
    # Coletar todos os tempos registrados
    todos_tempos = []
    for chave in chaves_tempos:
        tempos = redis_client.lrange(chave, 0, -1)
        todos_tempos.extend(map(int, tempos))
    
    if not todos_tempos:
        raise HTTPException(status_code=404, detail="Nenhum tempo registrado.")
    
    # Calcular a média em milissegundos
    media_ms = sum(todos_tempos) / len(todos_tempos)
    
    # Converter para segundos
    media_s = media_ms / 1000
    
    return {"tempo_medio": media_s}




@app.get("/quiz/{quiz_id}/questoes-com-mais-abstencoes/")
def questoes_com_mais_abstencoes(quiz_id: str):
    """
    Retorna as questões com mais abstenções, ou seja, que tiveram menos votos válidos.
    """
    # Buscar todas as chaves de votos das perguntas do quiz
    questoes = redis_client.keys(f"quiz:{quiz_id}:question:*:votes")
    
    # Lista para armazenar o total de votos por questão
    ranking = []
    
    for q in questoes:
        # Calcula o total de votos válidos para a pergunta
        votos_totais = sum(int(score) for _, score in redis_client.zrange(q, 0, -1, withscores=True))
        
        # Adiciona ao ranking
        ranking.append({"pergunta_id": q.split(":")[-2], "votos_validos": votos_totais})
    
    # Ordena pelo menor número de votos válidos
    ranking.sort(key=lambda x: x["votos_validos"])
    
    return {"ranking": ranking}





#---------------------------------
@app.get("/quiz/{quiz_id}/questoes-mais-acertadas/")
def questoes_mais_acertadas(quiz_id: str):
    """Retorna as questões com maior número de acertos."""
    # Buscar todas as chaves de acertos
    questoes = redis_client.keys(f"quiz:{quiz_id}:question:*:correct")
    
    # Processar as questões encontradas
    ranking = []
    for q in questoes:
        acertos = redis_client.get(q)
        if acertos is not None:
            ranking.append({
                "pergunta_id": q.split(":")[-2],
                "acertos": int(acertos)
            })
    
    # Ordenar o ranking por número de acertos (maior para menor)
    ranking.sort(key=lambda x: x["acertos"], reverse=True)
    
    return {"ranking": ranking}

 
#---------------------------------











@app.get("/quiz/{quiz_id}/alunos-mais-rapidos/")
def alunos_mais_rapidos(quiz_id: str):
    """Retorna os alunos mais rápidos com base no tempo médio consolidado."""
    # Buscar todas as chaves de tempos dos alunos no Redis
    chaves_alunos = redis_client.keys(f"quiz:{quiz_id}:student:*:times")
    tempos_por_aluno = {}

    # Consolidar os tempos para cada aluno
    for chave_aluno in chaves_alunos:
        aluno_id = chave_aluno.split(":")[3]  # Extrair o ID do aluno
        tempos = redis_client.lrange(chave_aluno, 0, -1)
        if aluno_id not in tempos_por_aluno:
            tempos_por_aluno[aluno_id] = []
        tempos_por_aluno[aluno_id].extend(map(int, tempos))

    # Calcular a média de tempo para cada aluno
    ranking = []
    for aluno_id, tempos in tempos_por_aluno.items():
        if tempos:
            tempo_medio = sum(tempos) / len(tempos)
        else:
            tempo_medio = float('inf')  # Caso não tenha tempos
        ranking.append({"aluno_id": aluno_id, "tempo_medio": tempo_medio})

    # Ordenar o ranking por tempo médio (menor para maior)
    ranking.sort(key=lambda x: x["tempo_medio"])

    return {"ranking": ranking}




@app.get("/quiz/{quiz_id}/alunos-com-mais-acertos/")
def alunos_com_mais_acertos(quiz_id: str):
    """
    Retorna o ranking dos alunos com maior número de acertos e menor tempo médio no quiz.
    """
    alunos_ranking = {}

    # Buscar todas as perguntas do quiz
    perguntas = redis_client.keys(f"quiz:{quiz_id}:question:*:votes")
    for pergunta in perguntas:
        pergunta_id = pergunta.split(":")[3]  # Extrair o ID da pergunta

        # Buscar todos os alunos que participaram da pergunta
        alunos = redis_client.keys(f"quiz:{quiz_id}:student:*:question:{pergunta_id}:times")
        for aluno_key in alunos:
            aluno_id = aluno_key.split(":")[3]  # Extrair o ID do aluno

            # Inicializar os dados do aluno se ainda não estiver no ranking
            if aluno_id not in alunos_ranking:
                alunos_ranking[aluno_id] = {"acertos": 0, "tempos": []}

            # Verificar se o aluno acertou a pergunta
            chave_voto = f"quiz:{quiz_id}:student:{aluno_id}:question:{pergunta_id}:vote"
            voto = redis_client.get(chave_voto)
            resposta_correta = redis_client.get(f"quiz:{quiz_id}:question:{pergunta_id}:resposta_correta")

            if voto and voto == resposta_correta:
                # Incrementar o contador de acertos
                alunos_ranking[aluno_id]["acertos"] += 1

            # Adicionar os tempos de resposta
            tempos = redis_client.lrange(aluno_key, 0, -1)
            tempos = [int(t) for t in tempos]
            alunos_ranking[aluno_id]["tempos"].extend(tempos)

    # Calcular o tempo médio e preparar o ranking
    ranking = []
    for aluno_id, dados in alunos_ranking.items():
        tempo_medio = sum(dados["tempos"]) / len(dados["tempos"]) if dados["tempos"] else 0
        ranking.append({"aluno_id": aluno_id, "acertos": dados["acertos"]})

    # Ordenar o ranking por acertos (decrescente) e tempo médio (crescente)
    ranking.sort(key=lambda x: (-x["acertos"]))

    return {"ranking": ranking}






@app.get("/quiz/{quiz_id}/alunos-maior-acerto-mais-rapidos/")
def alunos_maior_acerto_mais_rapidos(quiz_id: str):
    """
    Retorna o ranking dos alunos com maior número de acertos e menor tempo médio.
    """
    alunos_ranking = {}

    # Buscar todas as perguntas do quiz
    perguntas = redis_client.keys(f"quiz:{quiz_id}:question:*:votes")
    for pergunta in perguntas:
        pergunta_id = pergunta.split(":")[3]  # Extrair o ID da pergunta

        # Buscar todos os alunos que votaram na pergunta
        alunos = redis_client.keys(f"quiz:{quiz_id}:student:*:question:{pergunta_id}:times")
        for aluno_key in alunos:
            aluno_id = aluno_key.split(":")[3]  # Extrair o ID do aluno

            # Inicializar os dados do aluno, se necessário
            if aluno_id not in alunos_ranking:
                alunos_ranking[aluno_id] = {"acertos": 0, "tempos": []}

            # Verificar se o aluno acertou a pergunta
            chave_voto = f"quiz:{quiz_id}:student:{aluno_id}:question:{pergunta_id}:vote"
            voto = redis_client.get(chave_voto)
            resposta_correta = redis_client.get(f"quiz:{quiz_id}:question:{pergunta_id}:resposta_correta")

            if voto and voto == resposta_correta:
                # Incrementar o contador de acertos
                alunos_ranking[aluno_id]["acertos"] += 1

            # Adicionar o tempo de resposta
            tempos = redis_client.lrange(aluno_key, 0, -1)
            tempos = [int(t) for t in tempos]
            alunos_ranking[aluno_id]["tempos"].extend(tempos)

    # Consolidar os tempos médios e preparar o ranking
    ranking = []
    for aluno_id, dados in alunos_ranking.items():
        tempo_medio = sum(dados["tempos"]) / len(dados["tempos"]) if dados["tempos"] else 0
        ranking.append({"aluno_id": aluno_id, "acertos": dados["acertos"], "tempo_medio": tempo_medio})

    # Ordenar o ranking por acertos (decrescente) e tempo médio (crescente)
    ranking.sort(key=lambda x: (-x["acertos"], x["tempo_medio"]))

    return {"ranking": ranking}
