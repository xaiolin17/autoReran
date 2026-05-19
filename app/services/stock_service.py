from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.crawlers.data_processor import DataProcessor
from app.crawlers.tickflow_crawler import TickFlowCrawler
from app.models.stock_data import StockCode, StockData
from app.schemas.stock import StockDataCreate


class StockService:
    """
    股票数据服务类，提供股票数据的查询、保存、清洗、同步等核心功能。

    依赖注入关系:
        - db (Session): SQLAlchemy 数据库会话，由调用方传入，用于所有数据库操作
        - data_processor (DataProcessor): 数据处理器实例，内部自行创建，负责数据清洗
        - crawler (TickFlowCrawler): 爬虫实例，内部创建并注入 db，负责从外部数据源获取原始数据
    """

    def __init__(self, db: Session):
        """
        初始化 StockService 实例，完成依赖注入。

        参数:
            db (Session): SQLAlchemy 数据库会话对象，由外部（如 FastAPI 的 Depends）注入

        依赖注入关系:
            - self.db: 直接使用传入的数据库会话
            - self.data_processor: 内部实例化 DataProcessor，无外部依赖
            - self.crawler: 内部实例化 TickFlowCrawler，并将 db 传入
        """
        self.db = db
        self.data_processor = DataProcessor()
        self.crawler = TickFlowCrawler(db=db)

    def _resolve_stock_code(self, stock_code: str) -> str:
        """
        将短代码转换为完整代码（如 000001 -> 000001.SZ）。

        参数:
            stock_code (str): 股票代码，可以是短代码（如 000001）或完整代码（如 000001.SZ）

        返回值:
            str: 完整代码（含交易所后缀）；若无法解析则返回原始输入

        调用关系:
            - 被调用: get_stock_data、has_data、get_latest_date、delete_stock_data、
                     deduplicate_stock_data、get_earliest_date、get_latest_stock_data 等
            - 调用: self.crawler.get_full_symbol（当数据库无记录时的 fallback）

        关键逻辑说明:
            1. 若输入已含 '.'，直接返回原值
            2. 优先查询 StockCode 表，通过 code 字段匹配，返回 name 字段（完整代码）
            3. 数据库无记录时，调用爬虫的 get_full_symbol 作为兜底
        """
        if "." in stock_code:
            return stock_code
        # 查询数据库获取完整代码
        code_record = self.db.query(StockCode).filter(StockCode.code == stock_code).first()
        if code_record:
            return code_record.name
        #  fallback: 使用爬虫的映射
        full = self.crawler.get_full_symbol(stock_code)
        return full if full else stock_code

    def get_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[StockData]:
        """
        根据股票代码、周期及可选的时间范围查询股票数据列表。

        参数:
            stock_code (str): 股票代码（支持短代码或完整代码）
            period (str): 时间周期，默认为 "1d"（如 1d, 1h, 1w, 1M）
            start_date (Optional[datetime]): 开始日期时间，可选
            end_date (Optional[datetime]): 结束日期时间，可选
            limit (Optional[int]): 返回记录数量上限，可选

        返回值:
            List[StockData]: 符合条件的 StockData 对象列表，按时间升序排列

        调用关系:
            - 被调用: 外部 API 接口或其他服务层调用
            - 调用: _resolve_stock_code（解析完整代码）

        关键逻辑说明:
            1. 先调用 _resolve_stock_code 将短代码转为完整代码
            2. 构建基础查询：按 stock_code 和 period 过滤
            3. 根据 start_date / end_date 追加时间范围过滤
            4. 按 datetime 升序排列，若指定 limit 则限制返回条数
        """
        stock_code = self._resolve_stock_code(stock_code)
        query = self.db.query(StockData).filter(StockData.stock_code == stock_code, StockData.period == period)

        if start_date:
            query = query.filter(StockData.datetime >= start_date)
        if end_date:
            query = query.filter(StockData.datetime <= end_date)

        query = query.order_by(StockData.datetime)

        if limit:
            query = query.limit(limit)

        return query.all()

    def create_stock_data(self, stock_data: StockDataCreate) -> StockData:
        """
        将单条股票数据创建并保存到数据库。

        参数:
            stock_data (StockDataCreate): Pydantic 模型对象，包含待创建的股票数据字段

        返回值:
            StockData: 已持久化到数据库的 StockData ORM 对象（含自增 id）

        调用关系:
            - 被调用: 外部 API 接口（如数据录入接口）
            - 调用: 无（直接操作 ORM）

        关键逻辑说明:
            1. 将 Pydantic 模型转为字典并解包给 StockData ORM 对象
            2. 加入当前会话并提交事务
            3. refresh 以获取数据库生成的默认值（如自增主键）
        """
        db_stock = StockData(**stock_data.dict())
        self.db.add(db_stock)
        self.db.commit()
        self.db.refresh(db_stock)
        return db_stock

    def has_data(self, stock_code: str, period: str) -> bool:
        """
        判断指定股票代码和周期在数据库中是否已有数据。

        参数:
            stock_code (str): 股票代码（支持短代码或完整代码）
            period (str): 时间周期（如 1d, 1h, 1w, 1M）

        返回值:
            bool: 若存在至少一条记录返回 True，否则返回 False

        调用关系:
            - 被调用: initialize_default_data（用于判断是否需要初始化）
            - 调用: _resolve_stock_code（解析完整代码）

        关键逻辑说明:
            1. 解析完整代码后，执行 COUNT 查询
            2. 通过判断 count > 0 返回布尔结果
        """
        stock_code = self._resolve_stock_code(stock_code)
        count = self.db.query(StockData).filter(StockData.stock_code == stock_code, StockData.period == period).count()
        return count > 0

    def get_latest_date(self, stock_code: str, period: str) -> Optional[datetime]:
        """
        获取指定股票代码和周期的最新数据日期时间。

        参数:
            stock_code (str): 股票代码（支持短代码或完整代码）
            period (str): 时间周期（如 1d, 1h, 1w, 1M）

        返回值:
            Optional[datetime]: 最新的 datetime；若无数据则返回 None

        调用关系:
            - 被调用: fetch_and_save_stock_data（增量更新时计算实际起始日期）
            - 调用: _resolve_stock_code（解析完整代码）

        关键逻辑说明:
            1. 解析完整代码后，按 stock_code + period 过滤
            2. 按 datetime 降序排列，取第一条记录
            3. 返回该记录的 datetime 字段，无记录则返回 None
        """
        stock_code = self._resolve_stock_code(stock_code)
        latest = (
            self.db.query(StockData)
            .filter(StockData.stock_code == stock_code, StockData.period == period)
            .order_by(desc(StockData.datetime))
            .first()
        )
        return latest.datetime if latest else None

    def delete_stock_data(self, stock_code: str, period: str) -> int:
        """
        删除指定股票代码和周期的所有数据，返回删除的记录数。

        参数:
            stock_code (str): 股票代码（支持短代码或完整代码）
            period (str): 时间周期（如 1d, 1h, 1w, 1M）

        返回值:
            int: 实际删除的记录数；失败时返回 0

        调用关系:
            - 被调用: 外部管理接口或数据重刷场景
            - 调用: _resolve_stock_code（解析完整代码）

        关键逻辑说明:
            1. 解析完整代码后，按 stock_code + period 执行批量删除
            2. 提交事务并记录日志
            3. 异常时回滚事务，记录错误日志并返回 0
        """
        stock_code = self._resolve_stock_code(stock_code)
        try:
            count = (
                self.db.query(StockData).filter(StockData.stock_code == stock_code, StockData.period == period).delete()
            )
            self.db.commit()
            logger.info(f"已删除 {stock_code} {period} 的 {count} 条数据")
            return count
        except Exception as e:
            logger.error(f"删除数据失败: {e}")
            self.db.rollback()
            return 0

    def deduplicate_stock_data(self, stock_code: str, period: str) -> int:
        """
        清理指定股票代码和周期的重复数据，保留 id 最小的记录，返回删除的记录数。

        参数:
            stock_code (str): 股票代码（支持短代码或完整代码）
            period (str): 时间周期（如 1d, 1h, 1w, 1M）

        返回值:
            int: 实际删除的重复记录数；无重复或失败时返回 0

        调用关系:
            - 被调用: 外部数据维护接口或定时任务
            - 调用: _resolve_stock_code（解析完整代码）

        关键逻辑说明:
            1. 按 stock_code、period、datetime 分组，统计每组记录数
            2. 使用 HAVING 筛选出记录数 > 1 的重复组
            3. 对每组保留 id 最小的记录，删除其余记录
            4. 提交事务并记录日志；异常时回滚
        """
        from sqlalchemy import func

        stock_code = self._resolve_stock_code(stock_code)
        try:
            # 查找重复的记录组
            dup_groups = (
                self.db.query(
                    StockData.stock_code,
                    StockData.period,
                    StockData.datetime,
                    func.count(StockData.id).label("cnt"),
                    func.min(StockData.id).label("min_id"),
                )
                .filter(StockData.stock_code == stock_code, StockData.period == period)
                .group_by(StockData.stock_code, StockData.period, StockData.datetime)
                .having(func.count(StockData.id) > 1)
                .all()
            )

            if not dup_groups:
                return 0

            deleted_count = 0
            for group in dup_groups:
                # 删除该组中id大于最小id的所有记录
                ids_to_delete = (
                    self.db.query(StockData.id)
                    .filter(
                        StockData.stock_code == group.stock_code,
                        StockData.period == group.period,
                        StockData.datetime == group.datetime,
                        StockData.id > group.min_id,
                    )
                    .all()
                )

                for (id_to_delete,) in ids_to_delete:
                    self.db.query(StockData).filter(StockData.id == id_to_delete).delete()
                    deleted_count += 1

            self.db.commit()
            if deleted_count > 0:
                logger.info(f"已清理 {stock_code} {period} 的 {deleted_count} 条重复数据")
            return deleted_count
        except Exception as e:
            logger.error(f"清理重复数据失败: {e}")
            self.db.rollback()
            return 0

    def get_earliest_date(self, stock_code: str, period: str) -> Optional[datetime]:
        """
        获取指定股票代码和周期的最早数据日期时间。

        参数:
            stock_code (str): 股票代码（支持短代码或完整代码）
            period (str): 时间周期（如 1d, 1h, 1w, 1M）

        返回值:
            Optional[datetime]: 最早的 datetime；若无数据则返回 None

        调用关系:
            - 被调用: 外部 API 接口或数据分析模块
            - 调用: _resolve_stock_code（解析完整代码）

        关键逻辑说明:
            1. 解析完整代码后，按 stock_code + period 过滤
            2. 按 datetime 升序排列，取第一条记录
            3. 返回该记录的 datetime 字段，无记录则返回 None
        """
        stock_code = self._resolve_stock_code(stock_code)
        earliest = (
            self.db.query(StockData)
            .filter(StockData.stock_code == stock_code, StockData.period == period)
            .order_by(StockData.datetime)
            .first()
        )
        return earliest.datetime if earliest else None

    def fetch_and_save_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        incremental: bool = False,
        source: str = "history",
        force: bool = False,
    ) -> List[StockData]:
        """
        从外部数据源获取股票数据，经清洗后保存或更新到数据库。

        参数:
            stock_code (str): 股票代码（支持短代码或完整代码）
            period (str): 时间周期，默认为 "1d"（如 1d, 1h, 1w, 1M）
            start_date (Optional[str]): 开始日期（格式如 YYYYMMDD），可选
            end_date (Optional[str]): 结束日期（格式如 YYYYMMDD），可选
            incremental (bool): 是否增量更新；为 True 时自动从最新日期次日开始
            source (str): 数据源类型，"history" 为历史接口，"realtime" 为实时接口
            force (bool): 是否强制刷新已有数据；为 True 时下载数据为空则跳过该字段

        返回值:
            List[StockData]: 本次新增保存的 StockData 对象列表（不含更新的记录）

        调用关系:
            - 被调用: initialize_default_data、外部数据同步接口
            - 调用: get_latest_date（增量更新时获取最新日期）、
                    self.crawler.fetch_stock_data / fetch_realtime_data_as_df（获取原始数据）、
                    self.data_processor.clean_data（清洗数据）

        关键逻辑说明:
            1. 增量模式下，通过 get_latest_date 计算 actual_start_date，避免重复拉取
            2. 根据 source 选择历史接口或实时接口获取原始 DataFrame
            3. 调用 data_processor.clean_data 清洗数据
            4. 遍历清洗后的数据：不存在则插入，存在则对比字段值决定是否更新
            5. 浮点数比较使用 0.0001 容差；force 模式下空值字段跳过更新
            6. 最后统一提交事务，异常时回滚
        """
        # 获取完整代码和名称用于日志显示
        full_symbol = (
            self.crawler.get_full_symbol(stock_code) if hasattr(self.crawler, "get_full_symbol") else stock_code
        )
        display_code = full_symbol if full_symbol else stock_code

        # 查询股票名称
        stock_name = ""
        try:
            name_record = self.db.query(StockCode).filter(StockCode.name == display_code).first()
            if name_record and name_record.category:
                category_map = {
                    "stock": "A股",
                    "index": "指数",
                    "futures": "期货",
                    "bond": "债券",
                    "hk_stock": "港股",
                    "us_stock": "美股",
                }
                stock_name = f"[{category_map.get(name_record.category, name_record.category)}]"
        except Exception:
            pass

        # 增量更新模式下，先计算实际的start_date
        actual_start_date = start_date
        actual_end_date = end_date

        if incremental and not force:
            logger.debug("执行增量更新模式")
            latest_date = self.get_latest_date(stock_code, period)
            today = datetime.now().date()

            if latest_date:
                latest_date_only = latest_date.date()
                if latest_date_only >= today:
                    logger.info("已有数据已是最新 (截止 " + str(latest_date_only) + ")，无需更新")
                    return []

                actual_start_date = (latest_date_only + timedelta(days=1)).strftime("%Y%m%d")
                logger.info(
                    "增量更新: 从 "
                    + actual_start_date
                    + " 开始获取 "
                    + display_code
                    + stock_name
                    + " "
                    + period
                    + " 数据"
                )

        logger.info(
            "开始获取并保存股票数据: stock_code="
            + display_code
            + stock_name
            + ", period="
            + period
            + ", start_date="
            + str(actual_start_date)
            + ", end_date="
            + str(actual_end_date)
            + ", incremental="
            + str(incremental)
            + ", source="
            + str(source)
            + ", force="
            + str(force)
        )

        # 根据数据源类型选择获取方式
        if source == "realtime":
            logger.info("使用实时行情接口获取数据: " + display_code + stock_name)
            df = self.crawler.fetch_realtime_data_as_df(stock_code)
        else:
            logger.debug(
                "开始从爬虫获取数据: stock_code="
                + display_code
                + stock_name
                + ", period="
                + period
                + ", start_date="
                + str(start_date)
                + ", end_date="
                + str(end_date)
            )
            df = self.crawler.fetch_stock_data(
                stock_code=stock_code,
                period=period,
                start_date=actual_start_date,
                end_date=actual_end_date,
            )

        if df.empty:
            logger.warning(
                "未能从 TickFlow 获取到数据: "
                + display_code
                + stock_name
                + " "
                + period
                + " (source="
                + str(source)
                + ")"
            )
            return []

        logger.info(f"从数据源获取到 {len(df)} 条原始数据，开始清洗")
        cleaned_data = self.data_processor.clean_data(df)
        logger.info(f"数据清洗完成，剩余 {len(cleaned_data)} 条有效数据")

        saved_stocks = []
        updated_count = 0
        skipped_count = 0

        # 最终日期修正：确保保存到数据库的日期都是交易日
        from app.services.indicator_service import _fix_trading_date

        for idx, row in cleaned_data.iterrows():
            original_dt = row["datetime"]
            fixed_dt = _fix_trading_date(original_dt)
            if original_dt.date() != fixed_dt.date():
                logger.info(f"保存前日期修正: {original_dt.date()} -> {fixed_dt.date()} (非交易日修正为最近交易日)")
                cleaned_data.at[idx, "datetime"] = fixed_dt

        # 按日期去重：同一天保留时间较晚的数据（16:00:00 优先于 00:00:00）
        if not cleaned_data.empty and "datetime" in cleaned_data.columns:
            cleaned_data["_date"] = cleaned_data["datetime"].dt.date
            before_dedup = len(cleaned_data)
            cleaned_data = (
                cleaned_data.sort_values("datetime").groupby(["stock_code", "period", "_date"], as_index=False).last()
            )
            cleaned_data = cleaned_data.drop(columns=["_date"])
            after_dedup = len(cleaned_data)
            if before_dedup != after_dedup:
                logger.info(f"按日期去重: 从 {before_dedup} 条减少到 {after_dedup} 条")

        for _, row in cleaned_data.iterrows():
            try:
                existing = (
                    self.db.query(StockData)
                    .filter(
                        StockData.stock_code == row["stock_code"],
                        StockData.period == row["period"],
                        StockData.datetime == row["datetime"],
                    )
                    .first()
                )

                if not existing:
                    stock_data = StockData(
                        stock_code=row["stock_code"],
                        stock_name=row.get("stock_name"),
                        period=row["period"],
                        datetime=row["datetime"],
                        open_price=row["open_price"],
                        high_price=row["high_price"],
                        low_price=row["low_price"],
                        close_price=row["close_price"],
                        volume=row["volume"],
                        amount=row.get("amount"),
                        source=row.get("source", "tickflow"),
                    )
                    self.db.add(stock_data)
                    saved_stocks.append(stock_data)
                else:
                    # 检查数据是否有变化，有则更新
                    has_changes = False
                    fields = [
                        ("open_price", row.get("open_price")),
                        ("high_price", row.get("high_price")),
                        ("low_price", row.get("low_price")),
                        ("close_price", row.get("close_price")),
                        ("volume", row.get("volume")),
                        ("amount", row.get("amount")),
                        ("stock_name", row.get("stock_name")),
                        ("source", row.get("source", "tickflow")),
                    ]

                    for field_name, new_value in fields:
                        # 强制刷新模式下：下载数据为空则跳过该字段不更新
                        if new_value is None:
                            continue
                        old_value = getattr(existing, field_name)
                        # 处理浮点数比较
                        if isinstance(new_value, float) and isinstance(old_value, float):
                            if abs(new_value - old_value) > 0.0001:
                                setattr(existing, field_name, new_value)
                                has_changes = True
                        elif new_value != old_value:
                            setattr(existing, field_name, new_value)
                            has_changes = True

                    if has_changes:
                        updated_count += 1
                    else:
                        skipped_count += 1
            except Exception as e:
                logger.warning(f"处理单条数据时出错，跳过: {e}")
                continue

        logger.info(f"新增 {len(saved_stocks)} 条，更新 {updated_count} 条，跳过 {skipped_count} 条相同数据")

        try:
            self.db.commit()
            logger.info(
                f"✅ 成功保存了 {len(saved_stocks)} 条，更新了 {updated_count} 条 {display_code}{stock_name} {period} 数据"
            )
        except Exception as e:
            logger.error(f"保存数据时出错: {e}")
            self.db.rollback()
            return []

        logger.info(f"股票数据获取和保存完成: stock_code={display_code}{stock_name}, 新增数据条数={len(saved_stocks)}")
        return saved_stocks

    def initialize_default_data(self, stock_code: str = "000001.SH") -> bool:
        """
        初始化指定股票的默认日线数据，若已存在则跳过。

        参数:
            stock_code (str): 股票代码，默认为 "000001.SH"（上证指数）

        返回值:
            bool: 初始化成功返回 True；失败或无数据返回 False

        调用关系:
            - 被调用: 系统启动脚本或外部初始化接口
            - 调用: sync_universe_symbols（同步代码映射）、
                    has_data（检查是否已有数据）、
                    fetch_and_save_stock_data（拉取并保存数据）

        关键逻辑说明:
            1. 先调用 sync_universe_symbols 同步全量代码映射
            2. 检查该股票 1d 周期是否已有数据，有则直接返回 True
            3. 调用 fetch_and_save_stock_data 拉取日线数据
            4. 根据保存结果返回布尔状态，异常时捕获并返回 False
        """
        logger.info(f"开始初始化默认数据: {stock_code}")

        try:
            # 先同步 universe symbols 到数据库
            self.sync_universe_symbols()

            if self.has_data(stock_code, "1d"):
                logger.info(f"{stock_code} 已有数据，跳过初始化")
                return True

            saved_data = self.fetch_and_save_stock_data(stock_code, "1d")

            if saved_data:
                logger.info(f"✅ 成功初始化 {stock_code} 数据: {len(saved_data)} 条")
                return True
            else:
                logger.error(f"❌ 未能初始化 {stock_code} 数据")
                return False

        except Exception as e:
            logger.error(f"初始化默认数据失败: {e}")
            return False

    def get_latest_stock_data(self, stock_code: str, period: str = "1d") -> Optional[StockData]:
        """
        获取指定股票代码和周期的最新一条数据记录。

        参数:
            stock_code (str): 股票代码（支持短代码或完整代码）
            period (str): 时间周期，默认为 "1d"（如 1d, 1h, 1w, 1M）

        返回值:
            Optional[StockData]: 最新的 StockData ORM 对象；若无数据则返回 None

        调用关系:
            - 被调用: 外部 API 接口或实时行情展示模块
            - 调用: _resolve_stock_code（解析完整代码）

        关键逻辑说明:
            1. 解析完整代码后，按 stock_code + period 过滤
            2. 按 datetime 降序排列，取第一条记录
            3. 直接返回 ORM 对象，便于后续字段访问
        """
        stock_code = self._resolve_stock_code(stock_code)
        return (
            self.db.query(StockData)
            .filter(StockData.stock_code == stock_code, StockData.period == period)
            .order_by(desc(StockData.datetime))
            .first()
        )

    def get_available_stocks(self) -> List[str]:
        """
        获取数据库中已有数据的所有股票代码列表（去重）。

        参数:
            无

        返回值:
            List[str]: 去重后的股票完整代码列表

        调用关系:
            - 被调用: 外部 API 接口或数据概览模块
            - 调用: 无（直接查询 ORM）

        关键逻辑说明:
            1. 对 StockData.stock_code 执行 DISTINCT 查询
            2. 将结果元组列表展平为字符串列表后返回
        """
        result = self.db.query(StockData.stock_code).distinct().all()
        return [r[0] for r in result]

    def to_dataframe(self, stock_data_list: List[StockData]) -> pd.DataFrame:
        """
        将 StockData ORM 对象列表转换为 pandas DataFrame。

        参数:
            stock_data_list (List[StockData]): StockData 对象列表

        返回值:
            pd.DataFrame: 包含股票数据的 DataFrame，按 datetime 升序排列；空列表返回空 DataFrame

        调用关系:
            - 被调用: 外部数据分析接口或图表渲染模块
            - 调用: 无（纯数据转换逻辑）

        关键逻辑说明:
            1. 若输入为空列表，直接返回空 DataFrame
            2. 遍历列表，将每个 ORM 对象的字段提取为字典
            3. 使用 pd.DataFrame 构造 DataFrame
            4. 按 datetime 升序排序并重置索引
        """
        if not stock_data_list:
            return pd.DataFrame()

        data = []
        for stock in stock_data_list:
            data.append(
                {
                    "datetime": stock.datetime,
                    "open_price": stock.open_price,
                    "high_price": stock.high_price,
                    "low_price": stock.low_price,
                    "close_price": stock.close_price,
                    "volume": stock.volume,
                    "amount": stock.amount,
                    "stock_code": stock.stock_code,
                    "stock_name": stock.stock_name,
                    "period": stock.period,
                    "source": stock.source,
                }
            )

        df = pd.DataFrame(data)
        df = df.sort_values("datetime").reset_index(drop=True)
        return df

    def get_full_symbol(self, stock_code: str) -> Optional[str]:
        """
        从数据库查询完整代码（支持同一短代码多市场，优先匹配用户后缀）。

        参数:
            stock_code (str): 股票代码，可以是短代码（如 000001）或带后缀的代码（如 000001.SZ）

        返回值:
            Optional[str]: 匹配的完整代码；无记录则返回 None

        调用关系:
            - 被调用: 外部代码解析接口或 _resolve_stock_code 的 fallback 场景
            - 调用: 无（直接查询 ORM）

        关键逻辑说明:
            1. 提取短代码（clean_code）和用户指定的后缀（user_suffix）
            2. 查询 StockCode 表中所有 code 等于 clean_code 的记录
            3. 若用户指定了后缀，优先返回 name 以该后缀结尾的记录
            4. 无后缀或未匹配时，返回查询结果的第一条记录
        """
        clean_code = stock_code.split(".")[0] if "." in stock_code else stock_code
        user_suffix = None
        if "." in stock_code:
            parts = stock_code.split(".")
            if len(parts) == 2:
                user_suffix = parts[1].upper()

        # 查询所有匹配的完整代码
        records = self.db.query(StockCode).filter(StockCode.code == clean_code).all()
        if not records:
            return None

        # 如果用户指定了后缀，优先匹配
        if user_suffix:
            for r in records:
                if r.name.endswith(f".{user_suffix}"):
                    return r.name

        # 返回第一个（默认）
        return records[0].name

    def search_stock_codes(self, keyword: str, limit: int = 20) -> List[Dict]:
        """
        模糊查询股票代码（支持短代码和完整代码）。

        参数:
            keyword (str): 搜索关键词，会去除首尾空白并转为大写
            limit (int): 返回结果数量上限，默认为 20

        返回值:
            List[Dict]: 匹配结果列表，每项为包含 code、name、category 的字典

        调用关系:
            - 被调用: 外部搜索接口或自动补全组件
            - 调用: 无（直接查询 ORM）

        关键逻辑说明:
            1. 对 keyword 执行 strip().upper() 标准化
            2. 空关键词直接返回空列表
            3. 使用 SQL LIKE 同时匹配 StockCode.code 和 StockCode.name
            4. 限制返回条数，将 ORM 结果转为字典列表
        """
        keyword = keyword.strip().upper()
        if not keyword:
            return []

        # 同时匹配短代码和完整代码
        records = (
            self.db.query(StockCode)
            .filter((StockCode.code.like(f"%{keyword}%")) | (StockCode.name.like(f"%{keyword}%")))
            .limit(limit)
            .all()
        )

        result = []
        for r in records:
            result.append({"code": r.code, "name": r.name, "category": r.category or ""})
        return result

    def save_stock_codes(self, symbols: List[str], category: str = ""):
        """
        保存股票代码映射到数据库（以完整代码 name 为唯一键，支持同一短代码多市场）。

        参数:
            symbols (List[str]): 完整股票代码列表（如 ["000001.SZ", "000002.SZ"]）
            category (str): 股票类别标识（如 stock、index、futures 等），默认为空字符串

        返回值:
            无（通过日志输出保存、跳过、错误的统计信息）

        调用关系:
            - 被调用: sync_universe_symbols（批量同步各市场代码）
            - 调用: 无（直接操作 ORM）

        关键逻辑说明:
            1. 遍历 symbols，提取短代码（去掉后缀部分）
            2. 以完整代码 name 为唯一键查询，已存在则跳过
            3. 不存在则新建 StockCode 记录并加入会话
            4. 每累计 500 条提交一次，避免事务过大
            5. 异常时回滚当前批次，记录 debug 日志并继续处理后续代码
            6. 最后统一提交剩余记录，并输出保存统计日志
        """
        count = 0
        skip_count = 0
        error_count = 0
        for sym in symbols:
            short = sym.split(".")[0] if "." in sym else sym
            try:
                # 以完整代码（name）为唯一键查询
                existing = self.db.query(StockCode).filter(StockCode.name == sym).first()
                if not existing:
                    stock_code = StockCode(
                        code=short,
                        name=sym,
                        category=category,
                        updated_at=datetime.now(),
                    )
                    self.db.add(stock_code)
                    count += 1
                    # 每 500 条提交一次，避免事务过大
                    if count % 500 == 0:
                        self.db.commit()
                else:
                    skip_count += 1
            except Exception as e:
                error_count += 1
                self.db.rollback()
                logger.debug(f"跳过重复代码 {sym}: {e}")
                continue
        if count > 0:
            self.db.commit()
        if error_count > 0:
            logger.info(f"保存了 {count} 条，跳过 {skip_count} 条重复，{error_count} 条错误")
        elif skip_count > 0:
            logger.info(f"保存了 {count} 条股票代码映射到数据库（跳过 {skip_count} 条重复）")
        else:
            logger.info(f"保存了 {count} 条股票代码映射到数据库")

    def sync_universe_symbols(self) -> bool:
        """
        从 TickFlow 同步所有 universe symbols 到数据库。

        参数:
            无

        返回值:
            bool: 全部同步成功返回 True；任一类别失败返回 False

        调用关系:
            - 被调用: initialize_default_data（初始化前同步代码映射）
            - 调用: self.crawler.get_universe_symbols（按市场获取代码列表）、
                    save_stock_codes（批量保存代码映射）

        关键逻辑说明:
            1. 定义 universe_id 到 category 的映射字典，覆盖 A股、指数、期货、债券、港股、美股
            2. 遍历各 universe，调用爬虫接口获取代码列表
            3. 非空列表调用 save_stock_codes 保存，并累加统计
            4. 任一 universe 异常时记录错误日志，并将 all_saved 置为 False，继续处理其余类别
            5. 最后输出总计同步数量，返回整体成功状态
        """
        try:
            all_saved = True
            total_count = 0

            # universe 到类别的映射
            universe_categories = {
                "CN_Equity_A": "stock",
                "CN_Index": "index",
                "CN_Index_BJ": "index",
                "CN_Futures_CZCE": "futures",
                "CN_Futures_SHFE": "futures",
                "CN_Futures_CFFEX": "futures",
                "CN_Futures_INE": "futures",
                "CN_Futures_DCE": "futures",
                "CN_Bond": "bond",
                "HK_Equity": "hk_stock",
                "US_Equity": "us_stock",
            }

            for universe_id, category in universe_categories.items():
                try:
                    symbols = self.crawler.get_universe_symbols(universe_id)
                    if symbols:
                        self.save_stock_codes(symbols, category=category)
                        total_count += len(symbols)
                        logger.info(f"同步 {universe_id}: {len(symbols)} 条")
                    else:
                        logger.warning(f"{universe_id} 返回空数据")
                except Exception as e:
                    logger.error(f"同步 {universe_id} 失败: {e}")
                    all_saved = False

            logger.info(f"总计同步 {total_count} 条代码映射")
            return all_saved
        except Exception as e:
            logger.error(f"同步 universe symbols 失败: {e}")
            return False
