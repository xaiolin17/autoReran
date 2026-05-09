from decimal import Decimal
from typing import Optional, List
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column
from common.database import Base
from sqlalchemy import (
    Integer,
    String,
    DECIMAL,
    Boolean,
    Numeric,
    DateTime,
    func,
    CheckConstraint, JSON,
)


class Goods(Base):
    __tablename__ = "goods"
    __table_args__ = {"comment": "店铺商品表"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    store_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="店铺ID")
    sku: Mapped[Optional[str]] = mapped_column(String(64), index=True, comment="产品SKU编码")
    brand: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="商品品牌 ID")
    brand_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True, comment="商品品牌名称")
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True, comment="商品名称")
    unit: Mapped[int] = mapped_column(Integer, nullable=False, comment="商品单位 ID")
    unit_name: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="商品单位名称")
    alias: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True, comment="商品别名")
    price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False, index=True, comment="商品售价")
    packaged_weight: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True, comment="带包装重量(kg)")
    type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="商品类型 ID")
    type_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="商品类型名称")
    cost_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True, comment="商品成本价")
    size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="商品规格 ID")
    size_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="商品规格名称")
    sales: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="销量", default=0)
    virtual_sales: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="虚拟销量", default=0)
    promotion_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True, comment="商品促销售价")
    cycle_bucket_status: Mapped[bool] = mapped_column(Boolean, nullable=False, comment="是否循环桶状态", default=False)
    binding_bucket_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="绑定桶id")
    self_pickup_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True, comment="商品自提价")
    use_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="商品用途类型 ID")
    use_type_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="商品用途类型名称")
    banner: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True, comment="商品图ID列表")
    description: Mapped[Optional[str]] = mapped_column(LONGTEXT , nullable=True, comment="商品描述")
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True, comment="商品状态(上下架)", default=False)
    stock: Mapped[int] = mapped_column(
        Integer,
        CheckConstraint("stock >= 0", name="ck_goods_stock_non_negative"),
        nullable=False,
        default=0,
        comment="库存数量"
    )
    warning_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="库存预警值")
    upstairs_delivery_fee: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True, comment="上楼配送费(步梯)", default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, index=True, default=False, comment="软删除标记")
    create_time: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), comment="创建时间")
    update_time: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self) -> str:
        return f"<Goods(id={self.id}, name={self.name}, stock={self.stock})>"
