from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_db_session
from api.schemas.tenant import TenantCreate, TenantResponse
from db import models


router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db_session),
):
    existing = db.query(models.Tenant).filter(models.Tenant.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tenant name already exists")

    tenant = models.Tenant(name=payload.name)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant
