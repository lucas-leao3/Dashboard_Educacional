"""aluno_vigente: o 'valor de agora' de cada (matricula, periodo) -- a linha
da ingestão mais recente (docs/governanca_dados.md, 4.5) -- mais turma e polo
derivados da matrícula (§4.8).

A view existe no banco (criada pelas migrações do Alembic) para quem
consulta por SQL, e aqui como Table para o código consultar com select().
Ela fica num MetaData separado de propósito: o autogenerate do Alembic
não deve tratá-la como tabela (ver migrations/env.py, include_object).

**Por que a derivação mora na view, e não em coluna gerada como o DDL da
§4.8 sugere.** Dois motivos:

1. Coluna gerada não dispensa a view. Ela resolveria `turma` e `polo_cod`,
   que são recortes da matrícula, mas `polo_nome` sai de um LEFT JOIN com a
   tabela `polo` -- e coluna gerada não pode consultar outra tabela. Seria a
   derivação em dois lugares para entregar um valor só.
2. `usuarios` é tabela de auditoria: append-only, existe para registrar o que
   a fonte mandou. Valor calculado pertence ao modelo de leitura. Com a regra
   na view, reinterpretá-la amanhã é uma revisão que troca a view, sem tocar
   em uma linha de dado histórico.
"""
from sqlalchemy import Column, Float, Integer, MetaData, String, Table

from app.db.engine import CrgSemestre, Usuarios
from app.db.matricula import sql_codigo_polo, sql_turma

_TURMA = sql_turma("ranked")
_POLO_COD = sql_codigo_polo("ranked")

VIEW_SQL = f"""
CREATE VIEW aluno_vigente AS
SELECT
    ranked.*,
    {_TURMA} AS turma,
    {_POLO_COD} AS polo_cod,
    polo.nome AS polo_nome
FROM (
    SELECT u.*, ROW_NUMBER() OVER (
        PARTITION BY u.matricula, u.periodo ORDER BY u.ingestao_id DESC, u.id DESC
    ) AS rn
    FROM usuarios u
) ranked
LEFT JOIN polo ON polo.codigo = {_POLO_COD}
WHERE ranked.rn = 1
"""
# u.id DESC desempata quando duas linhas nascem na mesma ingestão -- acontece
# no passo manual (0), que é reaproveitado entre chamadas de POST /alunos.
# O LEFT JOIN (e não JOIN) é deliberado: matrícula fora do padrão, ou código
# de polo que ainda não está na tabela, continua aparecendo na view com
# polo_nome NULL, em vez de sumir do dashboard.

aluno_vigente = Table(
    "aluno_vigente",
    MetaData(),
    *[Column(c.name, c.type) for c in Usuarios.__table__.columns],
    Column("rn", Integer),
    # Derivadas pela própria view; nenhuma delas existe em `usuarios`.
    Column("turma", String(4)),
    Column("polo_cod", String(4)),
    Column("polo_nome", String(50)),
)


# ---------------------------------------------------------------------------
# crg_semestre_vigente: o mesmo "valor de agora", agora por (matricula,
# semestre). crg_semestre também é append-only -- sua chave inclui
# ingestao_id, então rodar um segundo lote grava o mesmo semestre de novo.
# Sem esta view um gráfico de trajetória desenharia o semestre duas vezes.
#
# `crg` NULL é informação, não ausência de linha: significa semestre ainda não
# apurado na data de emissão do histórico (governança §4.6, a regra do zero).
# Quem consome desenha lacuna ali -- nunca zero, que seria uma queda inventada.
# ---------------------------------------------------------------------------

VIEW_CRG_SQL = """
CREATE VIEW crg_semestre_vigente AS
SELECT matricula, semestre, crg, ingestao_id
FROM (
    SELECT c.*, ROW_NUMBER() OVER (
        PARTITION BY c.matricula, c.semestre ORDER BY c.ingestao_id DESC
    ) AS rn
    FROM crg_semestre c
) ranked
WHERE rn = 1
"""

crg_semestre_vigente = Table(
    "crg_semestre_vigente",
    MetaData(),
    *[Column(c.name, c.type) for c in CrgSemestre.__table__.columns],
)


# ---------------------------------------------------------------------------
# aluno_integrado: a base dos dashboards (docs/governanca_simplificada.md).
# `aluno_vigente` restrita a quem passou pelo cruzamento -- tem socioeconômico
# (linha em usuarios) E acadêmico (CRG por semestre lido de um histórico).
# Quem tem só uma das fontes fica fora de KPI, gráfico e total; aparece no
# relatório de não integrados (app.services.relatorio), com o motivo.
#
# O critério acadêmico é crg_semestre, e não a tabela historico, porque o
# lote L01 é anterior a ela e tem os semestres gravados.
# ---------------------------------------------------------------------------

VIEW_INTEGRADO_SQL = """
CREATE VIEW aluno_integrado AS
SELECT av.*
FROM aluno_vigente av
WHERE EXISTS (SELECT 1 FROM crg_semestre c WHERE c.matricula = av.matricula)
"""

aluno_integrado = Table(
    "aluno_integrado",
    MetaData(),
    *[Column(c.name, c.type) for c in aluno_vigente.columns],
)
