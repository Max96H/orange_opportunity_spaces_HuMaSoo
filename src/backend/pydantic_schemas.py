from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import List

class TechnologyExtract(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)

    rank: int
    theme: str
    source_article_ids: List[str] = Field(default_factory=list)

    @field_validator("source_article_ids", mode="before")
    @classmethod
    def ensure_list(cls, v):
        if v is None:
            return []
        if isinstance(v, (str, int, float)):
            return [str(v)]
        if isinstance(v, list):
            return [str(item) for item in v]
        return v


class Step1Response(BaseModel):
    domain: str
    top_5_trending_themes: List[TechnologyExtract]
