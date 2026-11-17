from pydantic import BaseModel, ConfigDict


class Contract(BaseModel):
    """Base for every shared contract: immutable, no unknown fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")
