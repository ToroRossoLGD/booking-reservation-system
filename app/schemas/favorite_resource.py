from datetime import datetime

from pydantic import BaseModel


class FavoriteResourceRead(BaseModel):
    id: int
    user_id: int
    resource_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoriteResourceDetailsRead(BaseModel):
    favorite_id: int
    resource_id: int
    resource_name: str
    resource_type: str
    capacity: int
    venue_id: int
    venue_name: str
    venue_address: str
    created_at: datetime
