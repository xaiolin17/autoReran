from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import pandas as pd
from app.core.logger import logger, log_function_call
from app.models.stock_data import StockData, StockCode
from app.schemas.stock import StockDataCreate
from app.crawlers.tickflow_crawler import TickFlowCrawler
from app.crawlers.data_processor import DataProcessor


class StockService:
    def __init__(self, db: Session):
        self.db = db
        self.data_processor = DataProcessor()
        self.crawler = TickFlowCrawler(db=db)

    def _resolve_stock_code(self, stock_code: str) -> str:
        """将短代码转换为完整代码（如 000001 -> 000001.SZ）"""
        if '.' in stock_code:
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
        limit: Optional[int] = None
    ) -> List[StockData]:
        stock_code = self._resolve_stock_code(stock_code)
        query = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        )
        
        if start_date:
            query = query.filter(StockData.datetime >= start_date)
        if end_date:
            query = query.filter(StockData.datetime <= end_date)
        
        query = query.order_by(StockData.datetime)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def create_stock_data(self, stock_data: StockDataCreate) -> StockData:
        db_stock = StockData(**stock_data.dict())
        self.db.add(db_stock)
        self.db.commit()
        self.db.refresh(db_stock)
        return db_stock
    
    def has_data(self, stock_code: str, period: str) -> bool:
        stock_code = self._resolve_stock_code(stock_code)
        count = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).count()
        return count > 0

    def get_latest_date(self, stock_code: str, period: str) -> Optional[datetime]:
        stock_code = self._resolve_stock_code(stock_code)
        latest = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(desc(StockData.datetime)).first()
        return latest.datetime if latest else None

    def delete_stock_data(self, stock_code: str, period: str) -> int:
        """删除指定股票代码和周期的所有数据，返回删除的记录数"""
        stock_code = self._resolve_stock_code(stock_code)
        try:
            count = self.db.query(StockData).filter(
                StockData.stock_code == stock_code,
                StockData.period == period
            ).delete()
            self.db.commit()
            logger.info(f"已删除 {stock_code} {period} 的 {count} 条数据")
            return count
        except Exception as e:
            logger.error(f"删除数据失败: {e}")
            self.db.rollback()
            return 0

    def deduplicate_stock_data(self, stock_code: str, period: str) -> int:
        """清理指定股票代码和周期的重复数据，保留id最小的记录，返回删除的记录数"""
        from sqlalchemy import func
        stock_code = self._resolve_stock_code(stock_code)
        try:
            # 查找重复的记录组
            dup_groups = self.db.query(
                StockData.stock_code,
                StockData.period,
                StockData.datetime,
                func.count(StockData.id).label('cnt'),
                func.min(StockData.id).label('min_id')
            ).filter(
                StockData.stock_code == stock_code,
                StockData.period == period
            ).group_by(
                StockData.stock_code, StockData.period, StockData.datetime
            ).having(func.count(StockData.id) > 1).all()

            if not dup_groups:
                return 0

            deleted_count = 0
            for group in dup_groups:
                # 删除该组中id大于最小id的所有记录
                ids_to_delete = self.db.query(StockData.id).filter(
                    StockData.stock_code == group.stock_code,
                    StockData.period == group.period,
                    StockData.datetime == group.datetime,
                    StockData.id > group.min_id
                ).all()

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
        stock_code = self._resolve_stock_code(stock_code)
        earliest = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(StockData.datetime).first()
        return earliest.datetime if earliest else None
    
    @log_function_call()
    def fetch_and_save_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        incremental: bool = False,
        source: str = "history",
        force: bool = False
    ) -> List[StockData]:
        """
        获取并保存股票数据

        Args:
            stock_code: 股票代码
            period: 时间周期（如 1d, 1h, 1w, 1M）
            start_date: 开始日期
            end_date: 结束日期
            incremental: 是否增量更新
            source: 数据源类型（history 历史接口 / realtime 实时接口）
            force: 是否强制刷新（对比更新所有已有数据，下载数据为空则不更新该字段）

        Returns:
            List[StockData]: 保存的数据列表
        """
        # 获取完整代码和名称用于日志显示
        full_symbol = self.crawler.get_full_symbol(stock_code) if hasattr(self.crawler, 'get_full_symbol') else stock_code
        display_code = full_symbol if full_symbol else stock_code

        # 查询股票名称
        stock_name = ""
        try:
            name_record = self.db.query(StockCode).filter(StockCode.name == display_code).first()
            if name_record and name_record.category:
                category_map = {
                    "stock": "A股", "index": "指数", "futures": "期货",
                    "bond": "债券", "hk_stock": "港股", "us_stock": "美股"
                }
                stock_name = f"[{category_map.get(name_record.category, name_record.category)}]"
        except Exception:
            pass

        # 增量更新模式下，先计算实际的start_date
        actual_start_date = start_date
        actual_end_date = end_date

        if incremental and not force:
            logger.debug(f"执行增量更新模式")
            latest_date = self.get_latest_date(stock_code, period)
            today = datetime.now().date()

            if latest_date:
                latest_date_only = latest_date.date()
                if latest_date_only >= today:
                    logger.info(f"已有数据已是最新 (截止 {latest_date_only})，无需更新")
                    return []

                actual_start_date = (latest_date_only + timedelta(days=1)).strftime("%Y%m%d")
                logger.info(f"增量更新: 从 {actual_start_date} 开始获取 {display_code}{stock_name} {period} 数据")

        logger.info(f"开始获取并保存股票数据: stock_code={display_code}{stock_name}, period={period}, start_date={actual_start_date}, end_date={actual_end_date}, incremental={incremental}, source={source}, force={force}")

        # 根据数据源类型选择获取方式
        if source == "realtime":
            logger.info(f"使用实时行情接口获取数据: {display_code}{stock_name}")
            df = self.crawler.fetch_realtime_data_as_df(stock_code)
        else:
            logger.debug(f"开始从爬虫获取数据: stock_code={display_code}{stock_name}, period={period}, start_date={start_date}, end_date={end_date}")
            df = self.crawler.fetch_stock_data(
                stock_code=stock_code,
                period=period,
                start_date=actual_start_date,
                end_date=actual_end_date
            )

        if df.empty:
            logger.warning(f"未能从 TickFlow 获取到数据: {display_code}{stock_name} {period} (source={source})")
            return []

        logger.info(f"从数据源获取到 {len(df)} 条原始数据，开始清洗")
        cleaned_data = self.data_processor.clean_data(df)
        logger.info(f"数据清洗完成，剩余 {len(cleaned_data)} 条有效数据")

        saved_stocks = []
        updated_count = 0
        skipped_count = 0

        for _, row in cleaned_data.iterrows():
            existing = self.db.query(StockData).filter(
                StockData.stock_code == row['stock_code'],
                StockData.period == row['period'],
                StockData.datetime == row['datetime']
            ).first()

            if not existing:
                stock_data = StockData(
                    stock_code=row['stock_code'],
                    stock_name=row.get('stock_name'),
                    period=row['period'],
                    datetime=row['datetime'],
                    open_price=row['open_price'],
                    high_price=row['high_price'],
                    low_price=row['low_price'],
                    close_price=row['close_price'],
                    volume=row['volume'],
                    amount=row.get('amount'),
                    source=row.get('source', 'tickflow')
                )
                self.db.add(stock_data)
                saved_stocks.append(stock_data)
            else:
                # 检查数据是否有变化，有则更新
                has_changes = False
                fields = [
                    ('open_price', row.get('open_price')),
                    ('high_price', row.get('high_price')),
                    ('low_price', row.get('low_price')),
                    ('close_price', row.get('close_price')),
                    ('volume', row.get('volume')),
                    ('amount', row.get('amount')),
                    ('stock_name', row.get('stock_name')),
                    ('source', row.get('source', 'tickflow'))
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

        logger.info(f"新增 {len(saved_stocks)} 条，更新 {updated_count} 条，跳过 {skipped_count} 条相同数据")

        try:
            self.db.commit()
            logger.info(f"✅ 成功保存了 {len(saved_stocks)} 条，更新了 {updated_count} 条 {display_code}{stock_name} {period} 数据")
        except Exception as e:
            logger.error(f"保存数据时出错: {e}")
            self.db.rollback()
            return []

        logger.info(f"股票数据获取和保存完成: stock_code={display_code}{stock_name}, 新增数据条数={len(saved_stocks)}")
        return saved_stocks
    
    def initialize_default_data(self, stock_code: str = "000001.SH") -> bool:
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
        stock_code = self._resolve_stock_code(stock_code)
        return self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(desc(StockData.datetime)).first()
    
    def get_available_stocks(self) -> List[str]:
        result = self.db.query(StockData.stock_code).distinct().all()
        return [r[0] for r in result]
    
    def to_dataframe(self, stock_data_list: List[StockData]) -> pd.DataFrame:
        if not stock_data_list:
            return pd.DataFrame()

        data = []
        for stock in stock_data_list:
            data.append({
                'datetime': stock.datetime,
                'open_price': stock.open_price,
                'high_price': stock.high_price,
                'low_price': stock.low_price,
                'close_price': stock.close_price,
                'volume': stock.volume,
                'amount': stock.amount,
                'stock_code': stock.stock_code,
                'stock_name': stock.stock_name,
                'period': stock.period,
                'source': stock.source
            })

        df = pd.DataFrame(data)
        df = df.sort_values('datetime').reset_index(drop=True)
        return df

    def get_full_symbol(self, stock_code: str) -> Optional[str]:
        """从数据库查询完整代码（支持同一短代码多市场，优先匹配用户后缀）"""
        clean_code = stock_code.split('.')[0] if '.' in stock_code else stock_code
        user_suffix = None
        if '.' in stock_code:
            parts = stock_code.split('.')
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
        """模糊查询股票代码（支持短代码和完整代码）"""
        keyword = keyword.strip().upper()
        if not keyword:
            return []

        # 同时匹配短代码和完整代码
        records = self.db.query(StockCode).filter(
            (StockCode.code.like(f"%{keyword}%")) |
            (StockCode.name.like(f"%{keyword}%"))
        ).limit(limit).all()

        result = []
        for r in records:
            result.append({
                "code": r.code,
                "name": r.name,
                "category": r.category or ""
            })
        return result

    def save_stock_codes(self, symbols: List[str], category: str = ""):
        """保存股票代码映射到数据库（以完整代码 name 为唯一键，支持同一短代码多市场）"""
        count = 0
        skip_count = 0
        error_count = 0
        for sym in symbols:
            short = sym.split('.')[0] if '.' in sym else sym
            try:
                # 以完整代码（name）为唯一键查询
                existing = self.db.query(StockCode).filter(StockCode.name == sym).first()
                if not existing:
                    stock_code = StockCode(
                        code=short,
                        name=sym,
                        category=category,
                        updated_at=datetime.now()
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
        """从 TickFlow 同步所有 universe symbols 到数据库"""
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