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
    image_url: Optional[str] = None # Optional thumbnail image URL for the ontology
    description: Optional[str] = None
    node_count: Optional[int] = None
    score: Optional[float] = None
    relationship_count: Optional[int] = None
    is_public: bool = False

class UpdateOntology(BaseModel):
    name: Optional[str] = None
    source_url: Optional[str] = None
    image_url: Optional[str] = None # Optional thumbnail image URL for the ontology
    description: Optional[str] = None
    node_count: Optional[int] = None
    score: Optional[float] = None
    relationship_count: Optional[int] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None

class Ontology(BaseModel):
    uuid: str
    name: str
    source_url: str
    image_url: Optional[str] = None # Optional thumbnail image URL for the ontology
    description: Optional[str] = None
    node_count: Optional[int] = None
    score: Optional[float] = None
    relationship_count: Optional[int] = None
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

class UploadOntology(BaseModel):
    neo4j_uri: str
    neo4j_username: str
    neo4j_password: str
    neo4j_database: str = "neo4j"
    source_url: str
    root_label: Optional[str] = None