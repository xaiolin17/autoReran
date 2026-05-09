from sqlalchemy import select, update, delete, exists
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession



class GoodsService:
    """
    商品服务类
    """
    def __init__(self, db: AsyncSession):
        self.goods_crud = GoodsCRUD(Goods, db)
        self.db = db

    async def create(self, goods_obj: GoodsCreate, user_id) -> Optional[bool]:
        """
        新增商品
        + 店铺商品
        + 总库存
        + 记录
        """
        # + 店铺商品 生成 goods id
        if goods_obj.brand and not goods_obj.brand_name:
            brand = select(Brand.name).where(Brand.id == goods_obj.brand)
            brand_result = await self.db.execute(brand)
            brand_name = brand_result.scalar_one_or_none()
            if brand_name:
                goods_obj.brand_name = brand_name

        if goods_obj.type and not goods_obj.type_name:
            category = select(Category.name).where(Category.id == goods_obj.type)
            category_result = await self.db.execute(category)
            category_name = category_result.scalar_one_or_none()
            if category_name:
                goods_obj.type_name = category_name

        if goods_obj.unit and not goods_obj.unit_name:
            unit = select(SysDictData.value).where(SysDictData.id == goods_obj.unit)
            unit_result = await self.db.execute(unit)
            unit_name = unit_result.scalar_one_or_none()
            if unit_name:
                goods_obj.unit_name = unit_name

        db_goods_info = await self.goods_crud.create(goods_obj)

        try:
            # + 总库存
            await GoodsTotalCRUD(GoodsTotal, self.db).create(
                GoodsTotalCreate(
                    store_id=goods_obj.store_id,
                    goods_id=db_goods_info.id,
                    stock=db_goods_info.stock
                )
            )
            # + 记录
            user_expand_info, user_info = None, None
            operator_result = None
            if user_id:
                user_expand_info = await self.db.get(UserExpandModel, user_id)
                user_info = await self.db.get(UserModel, user_id)
                if user_expand_info and user_expand_info.name:
                    operator_result = user_expand_info.name
                elif user_info and user_info.nick_name:
                    operator_result = user_info.nick_name

            self.db.add(
                StoreGoodsRecord(
                    store_id=goods_obj.store_id,
                    goods_id=db_goods_info.id,
                    stock_initial=0,
                    action="新增商品",
                    action_id=101,
                    stock_change=goods_obj.stock,
                    stock_completion=goods_obj.stock,
                    operator=operator_result,
                    operator_id=user_expand_info.user_id
                )
            )

            await self.db.commit()

            return True

        except Exception as e:
            await self.db.rollback()
            # 异常情况回退新增商品
            await self.db.execute(delete(Goods).where(Goods.id == db_goods_info.id))
            await self.db.commit()

            if isinstance(e.args, tuple) and isinstance(e.args[0], dict) and e.args[0].get("detail"):
                raise Exception({
                    "detail": e.args[0].get("detail"),
                    "exception": e
                })
            raise Exception({
                "detail": f"新增商品时发生错误",
                "exception": e
            })