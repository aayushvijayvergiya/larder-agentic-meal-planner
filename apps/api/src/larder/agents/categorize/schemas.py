from pydantic import BaseModel

from larder.schemas.common import PantryCategory


class CategoryAssignment(BaseModel):
    name: str
    category: PantryCategory


class CategoryAssignments(BaseModel):
    assignments: list[CategoryAssignment]
