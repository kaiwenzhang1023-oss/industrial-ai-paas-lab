"""WMS inventory contract. This represents current stored balances, not historical ATP."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, computed_field

class InventoryBalance(BaseModel):
    material_id: str = Field(min_length=1)
    warehouse_id: str = Field(min_length=1)
    lot_id: str
    on_hand: Decimal = Field(ge=0)
    reserved: Decimal = Field(ge=0)
    blocked: Decimal = Field(ge=0)
    snapshot_at: datetime
    version: int = Field(ge=1)

    @computed_field(return_type=Decimal)
    @property
    def available(self) -> Decimal:
        return self.on_hand - self.reserved - self.blocked

class InventorySummary(BaseModel):
    material_id: str
    warehouse_id: str | None
    on_hand: Decimal
    reserved: Decimal
    blocked: Decimal
    available: Decimal
    balance_rows: int
    latest_snapshot_at: datetime | None
    source: str = 'postgresql'
