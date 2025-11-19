from pydantic import BaseModel

class VendorBase(BaseModel):
    name: str
    phone: str

    # Chatwoot
    agent_id: int
    inbox_identifier: str

    # Z-API
    instance_id: str
    instance_token: str

    active: bool = True


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None

    agent_id: int | None = None
    inbox_identifier: str | None = None

    instance_id: str | None = None
    instance_token: str | None = None

    active: bool | None = None


class VendorRead(VendorBase):
    vendor_id: str

    class Config:
        orm_mode = True
