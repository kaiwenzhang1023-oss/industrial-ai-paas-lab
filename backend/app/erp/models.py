"""V1.1 canonical ERP contracts, independent of database schema."""
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class OrderLine(BaseModel):
    line_no: int = Field(ge=1)
    product_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)

class SalesOrder(BaseModel):
    order_id: str = Field(min_length=1)
    due_date: date
    status: Literal['DRAFT','CONFIRMED','CANCELLED']
    priority: int = 0
    version: int = Field(ge=1)
    lines: list[OrderLine] = Field(min_length=1)
    source: Literal['legacy','v11']

    @model_validator(mode='after')
    def unique_lines(self):
        numbers = [line.line_no for line in self.lines]
        if len(set(numbers)) != len(numbers):
            raise ValueError('DUPLICATE_LINE_NO')
        return self

class OrderScope(BaseModel):
    mode: Literal['global','selected_orders']
    order_ids: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def validate_scope(self):
        if self.mode == 'global' and self.order_ids:
            raise ValueError('GLOBAL_SCOPE_CANNOT_HAVE_IDS')
        if self.mode == 'selected_orders':
            if not 1 <= len(self.order_ids) <= 50:
                raise ValueError('SELECTED_SCOPE_REQUIRES_1_TO_50_IDS')
            if any(not x.strip() for x in self.order_ids) or len(set(self.order_ids)) != len(self.order_ids):
                raise ValueError('INVALID_OR_DUPLICATE_ORDER_IDS')
        return self
