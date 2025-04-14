from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId

class User(BaseModel):
    username: str
    email: str
    hashed_password: str

class PoemRequest(BaseModel):
    text: str
    user_id: str
    favourite: Optional[bool] = False