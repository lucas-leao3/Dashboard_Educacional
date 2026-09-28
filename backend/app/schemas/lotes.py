from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IngestaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    passo: int
    arquivo_sha256: str | None
    executado_em: datetime
    registros_lidos: int
    registros_aceitos: int
    registros_rejeitados: int


class LoteOut(BaseModel):
    id: str
    executado_em: datetime
    fechado_em: datetime | None
    #: Extraídos dos históricos (semestre letivo da data de emissão).
    periodos_cobertos: list[str]
    #: O responsável pela importação.
    executado_por: str | None
    observacao: str | None
    ingestoes: list[IngestaoOut]
    excecoes_por_motivo: dict[str, int]


class ExcecaoOut(BaseModel):
    ingestao_id: int
    passo: int
    matricula: int | None
    periodo: str | None
    motivo: str
    detalhe: str | None


class ArquivosImportados(BaseModel):
    gravados: list[str]
    ja_existiam: list[str]
    ignorados: list[str]


class ResumoRelatorio(BaseModel):
    total: int
    integrados: int
    nao_integrados: int
    #: Não integrados por código de motivo (ver LinhaNaoIntegrada.motivo).
    por_motivo: dict[str, int]
    preenchimento_medio_integrados: float | None


class ImportacaoOut(LoteOut):
    """Resposta de POST /lotes/importar: o lote já fechado, mais o que a
    execução fez (arquivos do .zip, contadores de cada passo, arquivos
    gerados no fechamento) e o resumo dos relatórios."""
    arquivos: ArquivosImportados
    sincronizar: dict
    atualizar_crg: dict
    arquivos_gerados: list[str]
    resumo: ResumoRelatorio


class LinhaRelatorio(BaseModel):
    matricula: int | None
    nome: str | None
    academico: bool
    socioeconomico: bool
    #: Campos das fontes que o registro tem (CRG se tem acadêmico; os do
    #: questionário se tem socioeconômico; tipo_deficiencia só se pcd = Sim).
    campos_avaliados: int
    qtd_campos_sem_resposta: int
    campos_sem_resposta: list[str]
    #: 0-100; null quando não há campo a avaliar (registro sem matrícula).
    percentual_preenchimento: float | None


class LinhaIntegrada(LinhaRelatorio):
    status: str                    # "Integrado com sucesso"


class LinhaNaoIntegrada(LinhaRelatorio):
    #: sem_academico | sem_socioeconomico | falha_identificacao | matricula_nao_encontrada
    motivo: str
    motivo_descricao: str
    detalhe: str | None


class RelatorioOut(BaseModel):
    lote: str
    resumo: ResumoRelatorio
    integrados: list[LinhaIntegrada]
    nao_integrados: list[LinhaNaoIntegrada]
