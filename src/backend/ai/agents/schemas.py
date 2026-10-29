from pydantic import BaseModel

class TranslationStatus(BaseModel):
    processed: int
    error: int
