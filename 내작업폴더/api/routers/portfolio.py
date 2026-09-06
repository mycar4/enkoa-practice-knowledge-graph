# -*- coding: utf-8 -*-
"""내 포트폴리오 (로그인 필요) - 보유종목 CRUD + 시세/리스크 신호 결합 요약."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from services.portfolio_service import add_holding, delete_holding, get_portfolio_summary

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class AddHoldingRequest(BaseModel):
    stock_code: str = Field(min_length=1)
    corp_name: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    avg_buy_price: float = Field(gt=0)


@router.get("/summary")
def portfolio_summary(current_user: dict = Depends(get_current_user)):
    return get_portfolio_summary(user_id=current_user["id"])


@router.post("/holdings", status_code=status.HTTP_201_CREATED)
def create_holding(body: AddHoldingRequest, current_user: dict = Depends(get_current_user)):
    add_holding(body.stock_code, body.corp_name, body.quantity, body.avg_buy_price, user_id=current_user["id"])
    return {"status": "created"}


@router.delete("/holdings/{holding_id}")
def remove_holding(holding_id: int, current_user: dict = Depends(get_current_user)):
    delete_holding(holding_id, user_id=current_user["id"])
    return {"status": "deleted"}
