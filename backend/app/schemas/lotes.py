from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LoteCreate(BaseModel):
    # Também é nome de pasta em raw/lotes/: só letras, dígitos, '-' e '_'.
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{3,20}$", examples=["2026-09-L01"])
    periodos_cobertos: list[str] = Field(min_length=1, examples=[["2025.2", "2026.1"]])
    executado_por: str | None = None
    observacao: str | None = None


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
    periodos_cobertos: list[str]
    executado_por: str | None
    observacao: str | None
    ingestoes: list[IngestaoOut]
    excecoes_por_motivo: dict[str, int]


class FechamentoOut(LoteOut):
    arquivos_gerados: list[str]


class ExcecaoOut(BaseModel):
    ingestao_id: int
    passo: int
    matricula: int | None
    periodo: str | None
    motivo: str
    detalhe: str | None


class HistoricosOut(BaseModel):
    lote: str
    gravados: list[str]
    ja_existiam: list[str]
    ignorados: list[str]
    # Só com ?executar=true: contadores de cada passo, ou "ja_executado" se
    # o passo já tinha rodado neste lote. None quando não se pediu para rodar.
    sincronizar: dict | Literal["ja_executado"] | None = None
    atualizar_crg: dict | Literal["ja_executado"] | None = None


class CorrespondenciaOut(BaseModel):
    matricula: int
    nome: str | None
    academico: bool
    socioeconomico: bool
    faltando: Literal["", "Academico", "SocioEconomico", "Ambos"]
