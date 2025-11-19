# file: app/db/seed.py

from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
import uuid

from app.db.session import engine
from app.models.vendors import Vendor


def run_seed():
    print("🔧 Iniciando seed...")

    now = datetime.utcnow()

    vendors = [
        {
            "vendor_id": str(uuid.uuid4()),
            "name": "Matheus",
            "phone": "554791584811",   # sem '+'

            # Chatwoot
            "agent_id": 148785,
            "inbox_identifier": "UiZjygWEE1ptqRRrdX68WfTm",

            # Z-API
            "instance_id": "3EA157C7D878A1DE59E526C865D6B97F",
            "instance_token": "EE6C71681687F2C59520BE11",

            "active": True,
            "created_at": now,
            "updated_at": now,
        },
        {
            "vendor_id": str(uuid.uuid4()),
            "name": "Frumar",
            "phone": "555189755983",

            # Chatwoot
            "agent_id": 149516,
            "inbox_identifier": "pVSBf3Y9fKLob764vow4g4qX",

            # Z-API
            "instance_id": "3EA5DE7641148263542C5ACC6E4ED72E",
            "instance_token": "70505F06CE0A2634AEA70EE4",

            "active": True,
            "created_at": now,
            "updated_at": now,
        },
    ]

    with Session(engine) as db:
        for v in vendors:
            exists = db.scalars(
                select(Vendor).where(Vendor.phone == v["phone"])
            ).first()

            if exists:
                print(f"⚠️ Vendor {v['name']} já existe, pulando...")
                continue

            vendor = Vendor(**v)
            db.add(vendor)

        db.commit()

    print("🎉 Seed concluído com sucesso!")


if __name__ == "__main__":
    run_seed()
