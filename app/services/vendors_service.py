from sqlalchemy.orm import Session
from app.models.vendors import Vendor
from app.schemas.vendors import VendorCreate, VendorUpdate


def create_vendor(db: Session, data: VendorCreate) -> Vendor:
    vendor = Vendor(**data.model_dump())
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return vendor


def list_vendors(db: Session):
    return db.query(Vendor).all()


def get_vendor(db: Session, vendor_id: str) -> Vendor | None:
    return db.query(Vendor).filter(Vendor.vendor_id == vendor_id).first()


def get_vendor_by_instance(db: Session, instance_id: str) -> Vendor | None:
    return db.query(Vendor).filter(Vendor.instance_id == instance_id).first()

def get_vendor_by_agent_id(db: Session, agent_id: int):
    return db.query(Vendor).filter(Vendor.agent_id == agent_id).first()

def get_vendor_by_inbox(db: Session, inbox_identifier: str) -> Vendor | None:
    return db.query(Vendor).filter(Vendor.inbox_identifier == inbox_identifier).first()

def get_vendor_by_phone(db: Session, phone: str) -> Vendor | None:
    return db.query(Vendor).filter(Vendor.phone == phone).first()

def update_vendor(db: Session, vendor: Vendor, data: VendorUpdate) -> Vendor:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(vendor, field, value)
    db.commit()
    db.refresh(vendor)
    return vendor


def deactivate_vendor(db: Session, vendor: Vendor) -> Vendor:
    vendor.active = False
    db.commit()
    db.refresh(vendor)
    return vendor
