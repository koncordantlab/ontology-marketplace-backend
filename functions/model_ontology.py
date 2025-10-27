from pydantic import BaseModel
from datetime import datetime, timezone
from typing import List, Optional
import uuid

class OntologyResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None

class NewOntology(BaseModel):
    name: str
    source_url: str
    image_url: str | None = None # Optional thumbnail image URL for the ontology
    description: str | None = None
    node_count: int | None = None
    score: float | None = None
    relationship_count: int | None = None
    is_public: bool = False

class UpdateOntology(BaseModel):
    name: str | None = None
    source_url: str | None = None
    image_url: str | None = None # Optional thumbnail image URL for the ontology
    description: str | None = None
    node_count: int | None = None
    score: float | None = None
    relationship_count: int | None = None
    is_public: bool | None = None

class Ontology(BaseModel):
    uuid: str
    name: str
    source_url: str
    image_url: str | None = None # Optional thumbnail image URL for the ontology
    description: str | None = None
    node_count: int | None = None
    score: float | None = None
    relationship_count: int | None = None
    is_public: bool = False
    created_at: datetime

    @classmethod
    def from_new_ontology(cls, new_ontology: NewOntology) -> 'Ontology':
        """
        Create an Ontology from a NewOntology with auto-generated fields.
        
        Args:
            new_ontology: The NewOntology instance to convert
            
        Returns:
            A new Ontology instance with auto-generated uuid and created_at
        """
        return cls(
            uuid=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            **new_ontology.model_dump()
        )

    @classmethod
    def from_new_ontologies(cls, new_ontologies: list[dict]) -> list['Ontology']:
        """
        Convert a list of NewOntology dictionaries to Ontology objects.
        
        Args:
            new_ontologies: List of dictionaries representing NewOntology objects
            
        Returns:
            List of Ontology objects with auto-generated fields
            
        Raises:
            ValidationError: If any of the input dictionaries are invalid
        """
        return [
            cls.from_new_ontology(NewOntology(**onto_data))
            for onto_data in new_ontologies
        ]