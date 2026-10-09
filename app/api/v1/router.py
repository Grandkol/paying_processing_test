"""Сборка роутера первой версии API."""

from fastapi import APIRouter, Depends

from app.api.deps import require_api_key
from app.api.v1 import payments

api_router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])
api_router.include_router(payments.router)
