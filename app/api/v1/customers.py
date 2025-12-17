# file: app/api/v1/customers.py

import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.customers import CustomerLookupResponse
from app.services.customers_service import get_customer_by_cnpj

router = APIRouter()
logger = logging.getLogger("customer_lookup")
logger.setLevel(logging.INFO)


@router.get("", response_model=CustomerLookupResponse)
def lookup_customer(
    cnpj: str = Query(..., description="CNPJ do cliente para verificação"),
    db: Session = Depends(get_db),
):
    logger.info(f"[CustomerLookup] Consulta iniciada: cnpj={cnpj}")

    result = get_customer_by_cnpj(cnpj)

    logger.info(f"[CustomerLookup] Resultado: {result}")

    return result
