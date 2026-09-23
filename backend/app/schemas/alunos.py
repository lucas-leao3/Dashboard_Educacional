from pydantic import BaseModel, ConfigDict


class AlunoCreate(BaseModel):
    """Dados recebidos no POST para cadastrar um aluno já consolidado
    (dados acadêmicos + socioeconômicos, ligados pela matrícula)."""

    # A correspondência entre dados acadêmicos e socioeconômicos é feita pela
    # matrícula (+ período, pra não duplicar o mesmo snapshot) -- por isso são
    # os únicos dois campos obrigatórios.
    matricula: int
    periodo: str

    # CRG é acadêmico e opcional: A fonte de dados não traz
    # esse campo. Quando não vem, o registro ainda é salvo -- só sem nota.
    CRG: float | None = None

    # Identificação (opcional)
    nome: str | None = None
    data_de_nascimento: str | None = None
    primeiro_ano_eletivo: str | None = None

    # Dados socioeconômicos (opcionais)
    genero: str | None = None
    polo: str | None = None
    cor_etnia: str | None = None
    pcd: str | None = None
    tipo_deficiencia: str | None = None
    renda: str | None = None
    deslocamento: str | None = None
    trabalho: str | None = None
    assistencia_estudantil: str | None = None
    saude_mental: str | None = None
    estresse: str | None = None
    acompanhamento: str | None = None
    escolaridade_pai: str | None = None
    escolaridade_mae: str | None = None
    # texto, não número -- as respostas vêm como "Acima de 3"
    qtd_computador: str | None = None
    qtd_celular: str | None = None
    computador_proprio: str | None = None
    gasto_internet: str | None = None
    acesso_internet: str | None = None
    tipo_moradia: str | None = None
    data_hora: str | None = None


class AlunoOut(AlunoCreate):
    """Dados devolvidos pela API: os mesmos campos do cadastro, mais o id do
    banco e os três campos derivados da matrícula pela view `aluno_vigente`
    (governança §4.8).

    Os derivados NÃO estão em AlunoCreate de propósito: ninguém os envia e
    ninguém os grava -- o banco os calcula. Ficam com default None só para o
    caso de a linha não vir da view; quando vem, o valor é o que o banco
    calculou, não algo remontado aqui."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ingestao_id: int

    #: Ano de ingresso, dígitos 1-4 da matrícula. None se ela fugir do padrão.
    turma: str | None = None
    #: Código do polo, dígitos 5-8 da matrícula.
    polo_cod: str | None = None
    #: Nome do polo, resolvido na tabela `polo`. None se o código for novo.
    polo_nome: str | None = None
