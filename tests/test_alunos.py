"""GET /alunos e GET /alunos/{matricula}: leitura da view `aluno_integrado`.

A API de alunos é só leitura. Aluno entra por POST /lotes/importar (ver
tests/test_importacao.py) e só aparece aqui se passou pelo cruzamento: tem
socioeconômico E acadêmico. Os dados são semeados direto no banco pelo
fixture `semear` (tests/conftest.py).
"""


async def test_lista_alunos_comeca_vazia(client):
    resposta = await client.get("/alunos")
    assert resposta.status_code == 200
    assert resposta.json() == []


async def test_lista_traz_o_aluno_integrado(client, semear):
    semear(123456, CRG=8.5)
    corpo = (await client.get("/alunos")).json()
    assert [a["matricula"] for a in corpo] == [123456]
    assert corpo[0]["ingestao_id"] > 0


async def test_buscar_aluno_existente(client, semear):
    semear(111)
    resposta = await client.get("/alunos/111")
    assert resposta.status_code == 200
    assert resposta.json()["matricula"] == 111


async def test_buscar_aluno_inexistente_da_404(client):
    assert (await client.get("/alunos/999")).status_code == 404


async def test_aluno_sem_academico_nao_aparece(client, semear):
    """Só socioeconômico (respondeu o FasiTech, não tem histórico): fica fora
    de todo total do dashboard -- está no relatório de não integrados."""
    semear(1)
    semear(2, academico=False)
    assert [a["matricula"] for a in (await client.get("/alunos")).json()] == [1]
    assert (await client.get("/alunos/2")).status_code == 404


async def test_get_mostra_so_o_vigente_por_matricula_e_periodo(client, semear):
    """Append-only: duas linhas do mesmo (matricula, periodo) em ingestões
    diferentes, mas a leitura devolve só a mais recente."""
    semear(5, renda="A", passo=1)
    semear(5, renda="B", passo=2)
    lista = (await client.get("/alunos")).json()
    assert [(a["matricula"], a["renda"]) for a in lista] == [(5, "B")]


async def test_um_registro_por_periodo_do_aluno_integrado(client, semear):
    semear(7, periodo="2025.(3 e 4)")
    semear(7, periodo="2026.(1 e 2)")
    lista = (await client.get("/alunos")).json()
    assert [(a["matricula"], a["periodo"]) for a in lista] == [(7, "2025.(3 e 4)"), (7, "2026.(1 e 2)")]
    assert (await client.get("/alunos/7")).json()["periodo"] == "2026.(1 e 2)"
