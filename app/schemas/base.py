from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema class with shared configuration for Pydantic v2 models."""

    model_config = ConfigDict(
        from_attributes=True,  # Enables mapping from ORM/SQLAlchemy models
        populate_by_name=True,  # Allows serializing/deserializing via aliases
    )
