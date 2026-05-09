from typing import Optional, List
from _decimal import Decimal
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict


class GoodsCreate(BaseModel):
    sku: Optional[str] = Field(None, description="产品SKU编码  *必填", examples=['sku_1001'])
    name: str = Field(..., description="商品名称  *必填", examples=["百岁山1L"])
    price: Decimal = Field(..., description="商品售价，单位：元  *必填", examples=[10.0])
    store_id: Optional[int] = Field(None, description="店铺ID", examples=[12345678])
    brand: Optional[int] = Field(None, description="商品品牌 ID", examples=[3])
    brand_name: Optional[str] = Field(None, description="商品品牌名称", examples=["百岁山"])
    unit: int = Field(..., description="商品单位 ID  *必填", examples=[2])
    unit_name: Optional[str] = Field(None, description="商品单位名称", examples=["瓶"])
    status: bool = Field(False, description="商品状态(上下架)，True 为上架，False 为下架  *必填", examples=[True])
    type: Optional[int] = Field(None, description="商品类型 ID", examples=[2])
    type_name: Optional[str] = Field(None, description="商品类型名称", examples=["矿泉水"])
    size: Optional[int] = Field(None, description="商品规格 ID", examples=[5])
    size_name: Optional[str] = Field(None, description="商品规格名称", examples=["1L"])
    cost_price: Optional[Decimal] = Field(None, description="商品成本价，单位：元", examples=[6.0])
    promotion_price: Optional[Decimal] = Field(None, description="商品促销售价，单位：元", examples=[8.0])
    virtual_sales: Optional[int] = Field(None, description="虚拟销量，用于展示", examples=[100])
    cycle_bucket_status: Optional[bool] = Field(False, description="是否循环桶")
    binding_bucket_id: Optional[int] = Field(None, description="绑定桶id")
    banner: Optional[List[int]] = Field(None, description="商品图ID列表")
    description: Optional[str] = Field(None, description="商品描述", examples=["优质天然矿泉水"])
    use_type: Optional[int] = Field(None, description="商品用途类型 ID", examples=[1])
    use_type_name: Optional[str] = Field(None, description="商品用途类型名称", examples=["自用"])
    alias: Optional[str] = Field(None, description="商品别名", examples=["大瓶水"])
    self_pickup_price: Optional[Decimal] = Field(None, description="商品自提价，单位：元", examples=[9.0])
    stock: Optional[int] = Field(None, description="库存数量，必须为非负整数", examples=[50])
    warning_value: Optional[int] = Field(10, description="库存预警值", examples=[10])
    upstairs_delivery_fee: Optional[Decimal] = Field(None, description="上楼配送费(步梯)")

    model_config = ConfigDict(from_attributes=True)