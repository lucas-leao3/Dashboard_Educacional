from pydantic import BaseModel, ConfigDict


class CrgSemestreOut(BaseModel):
    """Um ponto da trajetória acadêmica: o CRG de um aluno num semestre
    letivo, lido de `crg_semestre_vigente` (governança §4.6).

    `crg` NULL não é dado faltando por descuido: é semestre ainda não apurado
    na data de emissão do histórico. Quem desenha tem que virar lacuna, nunca
    zero -- zero seria uma queda que não aconteceu."""

    model_config = ConfigDict(from_attributes=True)

    matricula: int
    semestre: str          # '2024.1'
    crg: float | None
