from pydantic import BaseModel

class Book(BaseModel):
    title: str
    creator: str
    description: str
    language: str
    charters: list[str]