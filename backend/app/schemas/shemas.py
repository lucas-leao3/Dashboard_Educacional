from pydantic import BaseModel, Field


class validacao(BaseModel):
    matricula: int
    periodo: str = Field(max_length=15, examples=['2024.(1 e 2)','2025.(3 e 4)'])
    crg: float