from pydantic import BaseModel
from typing import Optional

class CustomerLookupResponse(BaseModel):
    found: bool
    customer_name: Optional[str] = None
    customer_city: Optional[str] = None
    customer_state: Optional[str] = None
    