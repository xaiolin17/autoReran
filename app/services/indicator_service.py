from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date
import pandas as pd
from app.utils.technical_indicators import TechnicalIndicators
from app.core.logger import log_function_call, logger

# =============================================================================
# 模块级全局变量说明
# =============================================================================
# _xshg_calendar: exchange_calendars 交易所日历对象，用于精确判断A股交易日
# _HAS_EXCHANGE_CALENDARS: 布尔标志，标识是否成功加载 exchange_calendars 库
#
# 作用：
#   在整模块范围内提供统一的交易日判断能力，避免重复初始化和导入。
#   如果 exchange_calendars 不可用，则降级为仅排除周末的简单判断。
# =============================================================================

# 尝试导入 exchange_calendars 进行精确交易日判断
try:
    import exchange_calendars as ec
    _xshg_calendar = ec.get_calendar('XSHG')
    _HAS_EXCHANGE_CALENDARS = True
except Exception:
    _xshg_calendar = None
    _HAS_EXCHANGE_CALENDARS = False


def _is_trading_day(dt: date) -> bool:
    """
    判断给定日期是否为A股交易日。

    功能：
        使用 exchange_calendars 库精确判断日期是否为上海证券交易所的交易日；
        若该库不可用或发生异常，则降级为仅排除周六、周日的简单判断。

    参数：
        dt (date): 待判断的日期对象。

    返回值：
        bool: True 表示是交易日，False 表示非交易日。

    调用关系：
        被 _detect_missing_ranges 方法调用，用于在检测缺失数据时跳过非交易日。

    关键逻辑：
        1. 优先使用 _xshg_calendar.is_session() 精确判断；
        2. 异常或库缺失时，回退到 weekday() < 5 的简单判断。
    """
    if _HAS_EXCHANGE_CALENDARS and _xshg_calendar is not None:
        try:
            return _xshg_calendar.is_session(pd.Timestamp(dt))
        except Exception:
            pass

    # fallback: 只排除周末
    return dt.weekday() < 5


class IndicatorService:
    """
    技术指标服务类。

    功能：
        提供股票数据的查询、技术指标计算、信号生成以及缺失范围检测等能力。
        所有数据库操作均通过 SQLAlchemy Session 进行，指标计算委托给 TechnicalIndicators 工具类。

    调用关系：
        通常由 API 层（如 FastAPI 路由）实例化并调用其公共方法。
    """

    def __init__(self, db: Session):
        """
        初始化 IndicatorService 实例。

        参数：
            db (Session): SQLAlchemy 数据库会话对象，用于执行 ORM 查询和提交事务。

        返回值：
            无。

        调用关系：
            由上层业务代码（如 API 路由）在创建服务实例时调用。
        """
        self.db = db

    def _stock_list_to_dataframe(self, stock_data_list):
        """
        将股票数据对象列表转换为 pandas DataFrame，并按时间升序排列。

        参数：
            stock_data_list (List[StockData]): StockData ORM 对象列表，
                每个对象包含 datetime、open_price、high_price、low_price、close_price、volume、amount 等属性。

        返回值：
            pd.DataFrame: 包含股票行情数据的 DataFrame，列名为 datetime、open_price、high_price、low_price、close_price、volume、amount，
                已按 datetime 升序排序并重置索引。

        调用关系：
            被 get_stock_data_with_indicators、calculate_and_save_indicators 调用，
            用于将 ORM 查询结果转换为 TechnicalIndicators 可处理的 DataFrame 格式。

        关键逻辑：
            1. 遍历 stock_data_list，提取每个对象的字段到字典列表；
            2. 使用 pd.DataFrame 构造数据框；
            3. 按 datetime 列排序并 reset_index(drop=True) 清理索引。
        """
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
            })
        df = pd.DataFrame(data)
        return df.sort_values('datetime').reset_index(drop=True)
    
    def _save_indicators_to_database(self, stock_data_list, df):
        """
        将计算得到的技术指标回写到数据库对应的 StockData 记录中。

        参数：
            stock_data_list (List[StockData]): StockData ORM 对象列表，与 df 行一一对应。
            df (pd.DataFrame): 包含技术指标列（如 ma5、kdj_k、macd、rsi、bb_upper 等）的 DataFrame。

        返回值：
            无（通过 self.db.commit() 提交事务）。

        调用关系：
            被 get_stock_data_with_indicators（当 auto_save=True 时）和 calculate_and_save_indicators 调用。

        关键逻辑：
            1. 按索引遍历 stock_data_list 和 df 的每一行；
            2. 检查 DataFrame 中是否存在对应指标列，若存在且值有效（pd.notna），则赋值给 ORM 对象；
            3. 支持的指标包括：MA（5/10/20/60）、KDJ（K/D/J）、MACD（DIF/DEA/MACD）、RSI、布林带（上/中/下轨）；
            4. 遍历结束后执行 self.db.commit() 持久化修改。
        """
        for i, stock in enumerate(stock_data_list):
            if i >= len(df):
                break
            row = df.iloc[i]
            
            if 'ma5' in row:
                stock.ma5 = float(row['ma5']) if pd.notna(row['ma5']) else None
            if 'ma10' in row:
                stock.ma10 = float(row['ma10']) if pd.notna(row['ma10']) else None
            if 'ma20' in row:
                stock.ma20 = float(row['ma20']) if pd.notna(row['ma20']) else None
            if 'ma60' in row:
                stock.ma60 = float(row['ma60']) if pd.notna(row['ma60']) else None
            
            if 'kdj_k' in row:
                stock.k = float(row['kdj_k']) if pd.notna(row['kdj_k']) else None
            if 'kdj_d' in row:
                stock.d = float(row['kdj_d']) if pd.notna(row['kdj_d']) else None
            if 'kdj_j' in row:
                stock.j = float(row['kdj_j']) if pd.notna(row['kdj_j']) else None
            
            if 'macd' in row:
                stock.dif = float(row['macd']) if pd.notna(row['macd']) else None
            if 'macd_signal' in row:
                stock.dea = float(row['macd_signal']) if pd.notna(row['macd_signal']) else None
            if 'macd_histogram' in row:
                stock.macd = float(row['macd_histogram']) if pd.notna(row['macd_histogram']) else None
            
            if 'rsi' in row:
                stock.rsi6 = float(row['rsi']) if pd.notna(row['rsi']) else None
            
            if 'bb_upper' in row:
                stock.upper = float(row['bb_upper']) if pd.notna(row['bb_upper']) else None
            if 'bb_middle' in row:
                stock.middle = float(row['bb_middle']) if pd.notna(row['bb_middle']) else None
            if 'bb_lower' in row:
                stock.lower = float(row['bb_lower']) if pd.notna(row['bb_lower']) else None
        
        self.db.commit()
    
    def _format_result(self, stock_data_list):
        """
        将 StockData ORM 对象列表格式化为标准字典列表，用于 API 响应返回。

        参数：
            stock_data_list (List[StockData]): 数据库查询得到的 StockData ORM 对象列表。

        返回值：
            List[Dict[str, Any]]: 包含股票行情及指标数据的字典列表，每个字典的键包括：
                datetime、open_price、high_price、low_price、close_price、volume、amount、
                ma5、ma10、ma20、ma60、kdj_k、kdj_d、kdj_j、macd、macd_signal、macd_histogram、
                rsi、bb_upper、bb_middle、bb_lower。
                所有数值字段均转为 float 或 None。

        调用关系：
            被 get_stock_data_with_indicators 调用，用于在数据库已有完整指标时直接返回格式化数据。

        关键逻辑：
            1. 遍历 stock_data_list；
            2. 将 datetime 转为 ISO 格式字符串；
            3. 将各价格、成交量及指标字段转为 float（若存在），否则置为 None；
            4. 收集为字典并追加到结果列表。
        """
        result = []
        for stock in stock_data_list:
            item = {
                'datetime': stock.datetime.isoformat() if hasattr(stock.datetime, 'isoformat') else str(stock.datetime),
                'open_price': float(stock.open_price) if stock.open_price else None,
                'high_price': float(stock.high_price) if stock.high_price else None,
                'low_price': float(stock.low_price) if stock.low_price else None,
                'close_price': float(stock.close_price) if stock.close_price else None,
                'volume': float(stock.volume) if stock.volume else None,
                'amount': float(stock.amount) if stock.amount else None,
                'ma5': float(stock.ma5) if stock.ma5 else None,
                'ma10': float(stock.ma10) if stock.ma10 else None,
                'ma20': float(stock.ma20) if stock.ma20 else None,
                'ma60': float(stock.ma60) if stock.ma60 else None,
                'kdj_k': float(stock.k) if stock.k else None,
                'kdj_d': float(stock.d) if stock.d else None,
                'kdj_j': float(stock.j) if stock.j else None,
                'macd': float(stock.dif) if stock.dif else None,
            'macd_signal': float(stock.dea) if stock.dea else None,
            'macd_histogram': float(stock.macd) if stock.macd else None,
                'rsi': float(stock.rsi6) if stock.rsi6 else None,
                'bb_upper': float(stock.upper) if stock.upper else None,
                'bb_middle': float(stock.middle) if stock.middle else None,
                'bb_lower': float(stock.lower) if stock.lower else None
            }
            result.append(item)
        return result
    
    def _format_result_with_calculated_indicators(self, stock_data_list, df):
        """
        将 StockData ORM 对象与刚计算出的指标 DataFrame 合并，格式化为标准字典列表。

        参数：
            stock_data_list (List[StockData]): 数据库查询得到的 StockData ORM 对象列表。
            df (pd.DataFrame): 刚通过 TechnicalIndicators.calculate_all_indicators 计算得到的指标 DataFrame，
                包含 ma5、kdj_k、macd、rsi、bb_upper 等列。

        返回值：
            List[Dict[str, Any]]: 合并后的股票数据字典列表，优先使用数据库中已保存的指标值；
                若数据库值为空，则回退到使用 DataFrame 中刚计算出的指标值。

        调用关系：
            被 get_stock_data_with_indicators 调用，用于在检测到缺失指标并重新计算后返回结果。

        关键逻辑：
            1. 遍历 stock_data_list，按索引对齐 df 的对应行；
            2. 基础行情字段（open_price、close_price 等）直接从 ORM 对象读取；
            3. 指标字段采用“数据库优先”策略：
               - 若 ORM 对象上已有该指标值（非 None），直接使用；
               - 否则从 df 对应行中读取（若列存在且值有效）；
               - 仍无则置为 None；
            4. 所有数值转为 float，datetime 转为 ISO 格式字符串。
        """
        result = []
        for i, stock in enumerate(stock_data_list):
            if i >= len(df):
                break
            row = df.iloc[i]
            
            item = {
                'datetime': stock.datetime.isoformat() if hasattr(stock.datetime, 'isoformat') else str(stock.datetime),
                'open_price': float(stock.open_price) if stock.open_price else None,
                'high_price': float(stock.high_price) if stock.high_price else None,
                'low_price': float(stock.low_price) if stock.low_price else None,
                'close_price': float(stock.close_price) if stock.close_price else None,
                'volume': float(stock.volume) if stock.volume else None,
                'amount': float(stock.amount) if stock.amount else None,
            }
            
            item['ma5'] = float(stock.ma5) if stock.ma5 else (float(row['ma5']) if 'ma5' in row and pd.notna(row['ma5']) else None)
            item['ma10'] = float(stock.ma10) if stock.ma10 else (float(row['ma10']) if 'ma10' in row and pd.notna(row['ma10']) else None)
            item['ma20'] = float(stock.ma20) if stock.ma20 else (float(row['ma20']) if 'ma20' in row and pd.notna(row['ma20']) else None)
            item['ma60'] = float(stock.ma60) if stock.ma60 else (float(row['ma60']) if 'ma60' in row and pd.notna(row['ma60']) else None)
            
            item['kdj_k'] = float(stock.k) if stock.k else (float(row['kdj_k']) if 'kdj_k' in row and pd.notna(row['kdj_k']) else None)
            item['kdj_d'] = float(stock.d) if stock.d else (float(row['kdj_d']) if 'kdj_d' in row and pd.notna(row['kdj_d']) else None)
            item['kdj_j'] = float(stock.j) if stock.j else (float(row['kdj_j']) if 'kdj_j' in row and pd.notna(row['kdj_j']) else None)
            
            item['macd'] = float(stock.dif) if stock.dif else (float(row['macd']) if 'macd' in row and pd.notna(row['macd']) else None)
            item['macd_signal'] = float(stock.dea) if stock.dea else (float(row['macd_signal']) if 'macd_signal' in row and pd.notna(row['macd_signal']) else None)
            item['macd_histogram'] = float(stock.macd) if stock.macd else (float(row['macd_histogram']) if 'macd_histogram' in row and pd.notna(row['macd_histogram']) else None)
            
            item['rsi'] = float(stock.rsi6) if stock.rsi6 else (float(row['rsi']) if 'rsi' in row and pd.notna(row['rsi']) else None)
            
            item['bb_upper'] = float(stock.upper) if stock.upper else (float(row['bb_upper']) if 'bb_upper' in row and pd.notna(row['bb_upper']) else None)
            item['bb_middle'] = float(stock.middle) if stock.middle else (float(row['bb_middle']) if 'bb_middle' in row and pd.notna(row['bb_middle']) else None)
            item['bb_lower'] = float(stock.lower) if stock.lower else (float(row['bb_lower']) if 'bb_lower' in row and pd.notna(row['bb_lower']) else None)
            
            result.append(item)
        return result
    
    @log_function_call()
    def get_stock_data_with_indicators(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
        auto_save: bool = True
    ) -> Dict[str, Any]:
        """
        获取指定股票在指定周期和日期范围内的行情数据及技术指标。

        功能：
            1. 将短代码转换为完整代码（如 000001 -> 000001.SZ）；
            2. 检测请求日期范围内是否存在数据缺失，并标记缺失区间；
            3. 查询数据库获取已有数据；
            4. 检查指标完整性，若缺失则调用 TechnicalIndicators 重新计算；
            5. 根据 auto_save 参数决定是否将计算结果回写数据库；
            6. 返回格式化后的数据及缺失区间信息。

        参数：
            stock_code (str): 股票代码，可为短代码（如 000001）或完整代码（如 000001.SZ）。
            period (str): 时间周期，如 "1d"（日线）、"1h"（小时线）、"1w"（周线）、"1M"（月线）。
            start_date (Optional[str]): 开始日期，格式 "%Y-%m-%d"；为 None 时不限制起始时间。
            end_date (Optional[str]): 结束日期，格式 "%Y-%m-%d"；为 None 时不限制结束时间。
            limit (Optional[int]): 返回数据条数上限；为 None 时返回全部数据。
            auto_save (bool): 是否在计算完缺失指标后自动保存到数据库，默认为 True。

        返回值：
            Dict[str, Any]: 包含两个键：
                - "data" (List[Dict]): 格式化后的股票行情及指标数据列表；
                - "missing_ranges" (List[Dict]): 数据缺失的日期区间列表，每个元素包含 start、end，
                  若包含今天则可能带有 "source": "realtime" 标记。

        调用关系：
            由 API 层（如 FastAPI 路由）调用，是 IndicatorService 的核心公共入口方法。
            内部调用：
                - _detect_missing_ranges、_merge_overlapping_ranges（检测并合并缺失区间）
                - _stock_list_to_dataframe（转换为 DataFrame）
                - TechnicalIndicators.calculate_all_indicators（计算指标）
                - _save_indicators_to_database（保存指标，可选）
                - _format_result / _format_result_with_calculated_indicators（格式化返回）

        关键逻辑：
            1. 代码转换：若 stock_code 不含 "."，则从 StockCode 表查询对应的完整代码；
            2. 缺失检测：在 start_date ~ end_date 范围内，遍历每个交易日检查数据库是否存在数据；
               若缺失且包含今天，则将今天单独标记为 realtime 来源；
            3. 数据查询：应用日期过滤和 limit 限制，limit 时先 DESC 取最近 N 条再反转回 ASC；
            4. 指标检查：遍历数据检查 ma5、k、macd 是否存在 None，若全部存在则直接返回；
            5. 指标计算：缺失时转换为 DataFrame 并调用 calculate_all_indicators；
            6. 自动保存：auto_save 为 True 时，调用 _save_indicators_to_database 回写数据库；
            7. 结果返回：根据是否重新计算，选择 _format_result 或 _format_result_with_calculated_indicators。
        """
        # 将短代码转换为完整代码（如 000001 -> 000001.SZ）
        from app.models.stock_data import StockCode
        full_symbol = None
        if '.' not in stock_code:
            # 查询完整代码
            code_record = self.db.query(StockCode).filter(StockCode.code == stock_code).first()
            if code_record:
                full_symbol = code_record.name
        if not full_symbol:
            full_symbol = stock_code

        logger.info(f"开始获取股票指标数据: stock_code={stock_code}(完整代码:{full_symbol}), period={period}, start_date={start_date}, end_date={end_date}, limit={limit}")

        from app.models.stock_data import StockData
        from sqlalchemy import desc
        from datetime import datetime, timedelta

        # 使用完整代码查询数据库
        stock_code = full_symbol

        # 检查是否需要下载数据
        missing_ranges = []
        if start_date and end_date:
            logger.debug(f"检查日期范围内数据: {start_date} ~ {end_date}")
            req_start = datetime.strptime(start_date, "%Y-%m-%d")
            req_end = datetime.strptime(end_date, "%Y-%m-%d")
            
            # 查询指定范围内的所有数据
            all_query = self.db.query(StockData).filter(
                StockData.stock_code == stock_code,
                StockData.period == period,
                StockData.datetime >= req_start,
                StockData.datetime <= req_end
            ).order_by(StockData.datetime)
            
            all_requested_data = all_query.all()
            logger.debug(f"查询到指定范围内数据条数: {len(all_requested_data)}")
            
            if not all_requested_data:
                # 完全没有数据，需要下载整个范围
                logger.info(f"指定日期范围内无数据，标记下载范围: {start_date} ~ {end_date}")
                missing_ranges.append({
                    "start": start_date,
                    "end": end_date
                })
            else:
                # 检查是否有间隙
                logger.debug(f"检测数据缺失范围")
                missing_ranges = self._detect_missing_ranges(
                    all_requested_data, req_start, req_end
                )
                logger.debug(f"检测到缺失范围数量: {len(missing_ranges)}")
        
        # 重新查询完整的数据集（不在这里同步下载，由 API 层的 BackgroundTasks 处理后台下载）
        logger.debug(f"查询数据库中股票数据: stock_code={stock_code}, period={period}")
        query = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        )

        # 处理日期范围过滤
        if start_date:
            try:
                if isinstance(start_date, str):
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                else:
                    start_dt = start_date
                query = query.filter(StockData.datetime >= start_dt)
                logger.debug(f"应用开始日期过滤: {start_dt}")
            except (ValueError, TypeError):
                logger.warning(f"开始日期格式错误: {start_date}")

        if end_date:
            try:
                if isinstance(end_date, str):
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    # 包含结束日期当天
                    end_dt = end_dt + timedelta(days=1)
                else:
                    end_dt = end_date
                query = query.filter(StockData.datetime < end_dt)
                logger.debug(f"应用结束日期过滤: {end_dt}")
            except (ValueError, TypeError):
                logger.warning(f"结束日期格式错误: {end_date}")

        if limit:
            # 先按DESC排序获取最近的N条，然后反转为ASC顺序
            logger.debug(f"应用数据条数限制: {limit}")
            query = query.order_by(desc(StockData.datetime)).limit(limit)
            stock_data_list = query.all()
            stock_data_list = stock_data_list[::-1]  # 反转为ASC
        else:
            query = query.order_by(StockData.datetime)
            stock_data_list = query.all()

        logger.info(f"查询到股票数据条数: {len(stock_data_list)}")

        if not stock_data_list:
            logger.info(f"股票 {stock_code} 在数据库中无数据")
            return {"data": [], "missing_ranges": missing_ranges}

        # 重新检测缺失范围 (可能还有未覆盖的范围)
        if start_date and end_date:
            req_start = datetime.strptime(start_date, "%Y-%m-%d")
            req_end = datetime.strptime(end_date, "%Y-%m-%d")
            
            new_missing_ranges = self._detect_missing_ranges(
                stock_data_list, req_start, req_end
            )
            if new_missing_ranges:
                logger.debug(f"再次检测到缺失范围: {len(new_missing_ranges)} 个")
                missing_ranges.extend(new_missing_ranges)
                # 合并重复的范围
                missing_ranges = self._merge_overlapping_ranges(missing_ranges)
                logger.debug(f"合并后缺失范围总数: {len(missing_ranges)}")

        has_missing_indicators = False
        for stock in stock_data_list:
            if (stock.ma5 is None or stock.k is None or stock.macd is None):
                has_missing_indicators = True
                break

        logger.debug(f"指标完整性检查: has_missing_indicators={has_missing_indicators}")

        if not has_missing_indicators:
            logger.info(f"股票 {stock_code} 数据完整，直接返回")
            return {"data": self._format_result(stock_data_list), "missing_ranges": missing_ranges}

        logger.info(f"检测到缺失指标，开始计算: {stock_code} {period}")
        df = self._stock_list_to_dataframe(stock_data_list)
        df = TechnicalIndicators.calculate_all_indicators(df)

        if auto_save:
            logger.info(f"自动保存指标计算结果到数据库")
            self._save_indicators_to_database(stock_data_list, df)

        logger.info(f"股票指标数据获取完成: stock_code={stock_code}, 数据条数={len(stock_data_list)}")
        return {"data": self._format_result_with_calculated_indicators(stock_data_list, df), "missing_ranges": missing_ranges}
    
    def calculate_and_save_indicators(self, stock_code: str, period: str = "1d"):
        """
        为指定股票的全部历史数据计算技术指标并保存到数据库。

        参数：
            stock_code (str): 股票完整代码（如 000001.SZ）。
            period (str): 时间周期，默认为 "1d"（日线）。

        返回值：
            int: 实际处理并保存的数据条数；若数据库中无该股票数据则返回 0。

        调用关系：
            可由后台任务或管理接口调用，用于批量补全某只股票的历史指标。
            内部调用：
                - _stock_list_to_dataframe（转换为 DataFrame）
                - TechnicalIndicators.calculate_all_indicators（计算指标）
                - _save_indicators_to_database（保存到数据库）

        关键逻辑：
            1. 查询数据库中该股票指定周期的全部数据，按时间升序排列；
            2. 若数据为空，直接返回 0；
            3. 转换为 DataFrame 后调用 calculate_all_indicators 计算全套指标；
            4. 调用 _save_indicators_to_database 将结果回写数据库并提交事务；
            5. 返回处理的数据条数。
        """
        from app.models.stock_data import StockData
        from sqlalchemy import desc

        query = self.db.query(StockData).filter(
            StockData.stock_code == stock_code,
            StockData.period == period
        ).order_by(StockData.datetime)
        
        stock_data_list = query.all()
        
        if not stock_data_list:
            return 0
        
        df = self._stock_list_to_dataframe(stock_data_list)
        df = TechnicalIndicators.calculate_all_indicators(df)
        
        self._save_indicators_to_database(stock_data_list, df)
        return len(stock_data_list)
    
    @staticmethod
    def calculate_indicators_for_df_static(df: pd.DataFrame) -> pd.DataFrame:
        """
        静态方法：为给定的行情 DataFrame 计算全套技术指标。

        参数：
            df (pd.DataFrame): 包含股票行情数据的 DataFrame，
                必须包含 datetime、open_price、high_price、low_price、close_price、volume 等列。

        返回值：
            pd.DataFrame: 在原 DataFrame 基础上追加指标列后的新 DataFrame，
                包含 ma5、ma10、ma20、ma60、kdj_k、kdj_d、kdj_j、macd、macd_signal、macd_histogram、rsi、bb_upper、bb_middle、bb_lower 等列。

        调用关系：
            可在不实例化 IndicatorService 的情况下直接调用，适用于纯数据处理场景。
            内部调用 TechnicalIndicators.calculate_all_indicators 完成实际计算。

        关键逻辑：
            直接委托给 TechnicalIndicators.calculate_all_indicators，保持与实例方法一致的计算逻辑。
        """
        return TechnicalIndicators.calculate_all_indicators(df)

    def calculate_indicators_for_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        实例方法：为给定的行情 DataFrame 计算全套技术指标。

        参数：
            df (pd.DataFrame): 包含股票行情数据的 DataFrame，
                必须包含 datetime、open_price、high_price、low_price、close_price、volume 等列。

        返回值：
            pd.DataFrame: 在原 DataFrame 基础上追加指标列后的新 DataFrame，
                包含 ma5、ma10、ma20、ma60、kdj_k、kdj_d、kdj_j、macd、macd_signal、macd_histogram、rsi、bb_upper、bb_middle、bb_lower 等列。

        调用关系：
            由需要结合服务实例上下文（如日志、数据库会话）的调用方使用。
            内部调用 TechnicalIndicators.calculate_all_indicators 完成实际计算。

        关键逻辑：
            直接委托给 TechnicalIndicators.calculate_all_indicators，与静态方法功能一致，
            但以实例方法形式提供，便于在类体系内统一调用。
        """
        return TechnicalIndicators.calculate_all_indicators(df)
    
    def get_kdj_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        从行情 DataFrame 中识别 KDJ 指标的金叉/死叉交易信号。

        参数：
            df (pd.DataFrame): 包含股票行情数据的 DataFrame，
                需包含 datetime、close_price 列；KDJ 相关列（kdj_k、kdj_d、kdj_j）可由本方法内部计算生成。

        返回值：
            List[Dict[str, Any]]: KDJ 信号列表，每个元素为字典，包含：
                - datetime (str): 信号发生时间的 ISO 格式字符串；
                - type (str): 信号类型，"buy"（金叉买入）或 "sell"（死叉卖出）；
                - indicator (str): 指标名称，固定为 "KDJ"；
                - reason (str): 信号原因描述；
                - price (float): 信号发生时的收盘价。

        调用关系：
            被 get_all_signals 调用，也可单独用于获取 KDJ 专项信号。
            内部调用 TechnicalIndicators.calculate_kdj 计算 KDJ 指标。

        关键逻辑：
            1. 调用 TechnicalIndicators.calculate_kdj(df) 确保 DataFrame 包含 kdj_k、kdj_d、kdj_j 列；
            2. 从第 1 行开始遍历（需与前一行比较）；
            3. 买入信号（金叉）：前一日 K <= D，当日 K > D，且当日 K < 20（超卖区域）；
            4. 卖出信号（死叉）：前一日 K >= D，当日 K < D，且当日 K > 80（超买区域）；
            5. 仅当涉及的所有值均有效（pd.notna）时才生成信号。
        """
        signals = []
        df = TechnicalIndicators.calculate_kdj(df)
        
        for i in range(1, len(df)):
            prev_k = df.iloc[i-1]['kdj_k']
            prev_d = df.iloc[i-1]['kdj_d']
            curr_k = df.iloc[i]['kdj_k']
            curr_d = df.iloc[i]['kdj_d']
            curr_j = df.iloc[i]['kdj_j']
            
            if pd.notna(prev_k) and pd.notna(prev_d) and pd.notna(curr_k) and pd.notna(curr_d):
                if prev_k <= prev_d and curr_k > curr_d and curr_k < 20:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'].isoformat() if hasattr(df.iloc[i]['datetime'], 'isoformat') else str(df.iloc[i]['datetime']),
                        'type': 'buy',
                        'indicator': 'KDJ',
                        'reason': 'K线上穿D线，超卖区域金叉',
                        'price': float(df.iloc[i]['close_price'])
                    })
                elif prev_k >= prev_d and curr_k < curr_d and curr_k > 80:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'].isoformat() if hasattr(df.iloc[i]['datetime'], 'isoformat') else str(df.iloc[i]['datetime']),
                        'type': 'sell',
                        'indicator': 'KDJ',
                        'reason': 'K线下穿D线，超买区域死叉',
                        'price': float(df.iloc[i]['close_price'])
                    })
        
        return signals
    
    def get_macd_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        从行情 DataFrame 中识别 MACD 指标的金叉/死叉交易信号。

        参数：
            df (pd.DataFrame): 包含股票行情数据的 DataFrame，
                需包含 datetime、close_price 列；MACD 相关列（macd、macd_signal）可由本方法内部计算生成。

        返回值：
            List[Dict[str, Any]]: MACD 信号列表，每个元素为字典，包含：
                - datetime (str): 信号发生时间的 ISO 格式字符串；
                - type (str): 信号类型，"buy"（金叉买入）或 "sell"（死叉卖出）；
                - indicator (str): 指标名称，固定为 "MACD"；
                - reason (str): 信号原因描述；
                - price (float): 信号发生时的收盘价。

        调用关系：
            被 get_all_signals 调用，也可单独用于获取 MACD 专项信号。
            内部调用 TechnicalIndicators.calculate_macd 计算 MACD 指标。

        关键逻辑：
            1. 调用 TechnicalIndicators.calculate_macd(df) 确保 DataFrame 包含 macd、macd_signal 列；
            2. 从第 1 行开始遍历（需与前一行比较）；
            3. 买入信号（金叉）：前一日 MACD <= 信号线，当日 MACD > 信号线；
            4. 卖出信号（死叉）：前一日 MACD >= 信号线，当日 MACD < 信号线；
            5. 仅当涉及的所有值均有效（pd.notna）时才生成信号。
        """
        signals = []
        df = TechnicalIndicators.calculate_macd(df)
        
        for i in range(1, len(df)):
            prev_macd = df.iloc[i-1]['macd']
            prev_signal = df.iloc[i-1]['macd_signal']
            curr_macd = df.iloc[i]['macd']
            curr_signal = df.iloc[i]['macd_signal']
            
            if pd.notna(prev_macd) and pd.notna(prev_signal) and pd.notna(curr_macd) and pd.notna(curr_signal):
                if prev_macd <= prev_signal and curr_macd > curr_signal:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'].isoformat() if hasattr(df.iloc[i]['datetime'], 'isoformat') else str(df.iloc[i]['datetime']),
                        'type': 'buy',
                        'indicator': 'MACD',
                        'reason': 'MACD上穿信号线，金叉',
                        'price': float(df.iloc[i]['close_price'])
                    })
                elif prev_macd >= prev_signal and curr_macd < curr_signal:
                    signals.append({
                        'datetime': df.iloc[i]['datetime'].isoformat() if hasattr(df.iloc[i]['datetime'], 'isoformat') else str(df.iloc[i]['datetime']),
                        'type': 'sell',
                        'indicator': 'MACD',
                        'reason': 'MACD下穿信号线，死叉',
                        'price': float(df.iloc[i]['close_price'])
                    })
        
        return signals
    
    def _detect_missing_ranges(self, stock_data_list, req_start, req_end):
        """
        检测请求日期范围内数据库中缺失的数据区间（仅针对交易日）。

        参数：
            stock_data_list (List[StockData]): 已查询到的股票数据 ORM 对象列表，按时间升序排列。
            req_start (datetime): 请求范围的起始日期时间。
            req_end (datetime): 请求范围的结束日期时间。

        返回值：
            List[Dict[str, Any]]: 缺失区间列表，每个元素为字典，包含：
                - start (str): 缺失区间开始日期，格式 "%Y-%m-%d"；
                - end (str): 缺失区间结束日期，格式 "%Y-%m-%d"；
                - source (str, 可选): 若缺失区间仅为今天，标记为 "realtime"，表示建议用实时接口获取。

        调用关系：
            被 get_stock_data_with_indicators 调用，用于识别用户请求范围内尚未入库的数据区间。
            内部调用 _is_trading_day 辅助函数判断是否为交易日。

        关键逻辑：
            1. 若 stock_data_list 为空，整个请求范围视为缺失；
               若范围跨越今天，则将今天之前的部分和今天分开处理（今天标记 realtime）；
            2. 将已有数据的日期提取为集合 existing_dates，便于 O(1) 查找；
            3. 从 req_start 到 req_end 逐日遍历，跳过未来日期和非交易日；
            4. 发现缺失日期时，向前查找连续缺失的结束位置；
            5. 对包含今天的缺失范围进行拆分：今天之前用历史接口，今天单独标记 realtime；
            6. 仅在今天及之前的日期范围内生成缺失记录，未来日期不纳入缺失范围。
        """
        from datetime import timedelta
        from datetime import date

        logger.debug(f"开始检测缺失数据范围: 请求范围 {req_start.date()} ~ {req_end.date()}, 数据条数={len(stock_data_list) if stock_data_list else 0}")

        missing_ranges = []
        today = date.today()

        if not stock_data_list:
            logger.info(f"数据列表为空，整个范围缺失: {req_start.date()} ~ {req_end.date()}")
            # 如果完全没有数据，整个范围都缺失
            # 但如果范围包含今天，将今天之前的部分和今天分开处理
            if req_end.date() >= today and req_start.date() < today:
                # 今天之前有缺失，用历史接口
                missing_ranges.append({
                    "start": req_start.strftime("%Y-%m-%d"),
                    "end": (today - timedelta(days=1)).strftime("%Y-%m-%d")
                })
                # 今天单独标记为实时接口
                if _is_trading_day(today):
                    missing_ranges.append({
                        "start": today.strftime("%Y-%m-%d"),
                        "end": today.strftime("%Y-%m-%d"),
                        "source": "realtime"
                    })
            else:
                missing_ranges.append({
                    "start": req_start.strftime("%Y-%m-%d"),
                    "end": req_end.strftime("%Y-%m-%d")
                })
            logger.debug(f"标记缺失范围: {missing_ranges}")
            return missing_ranges

        # 创建日期集合以便快速查找
        existing_dates = set()
        for stock in stock_data_list:
            existing_dates.add(stock.datetime.date())

        logger.debug(f"已存在的日期数量: {len(existing_dates)}")

        # 检查请求范围内的每个交易日是否存在
        current_date = req_start.date()
        while current_date <= req_end.date():
            # 检查当前日期是否在未来，如果是则跳过
            if current_date > today:
                current_date += timedelta(days=1)
                continue

            # 跳过非交易日（周末）
            if not _is_trading_day(current_date):
                current_date += timedelta(days=1)
                continue

            if current_date not in existing_dates:
                logger.debug(f"检测到缺失日期: {current_date}")
                # 找到缺失的起始日期，继续找到连续缺失的结束日期
                missing_start = current_date

                # 查找连续缺失的日期范围，跳过未来日期和非交易日
                while current_date <= req_end.date() and current_date not in existing_dates:
                    if current_date > today:
                        break
                    current_date += timedelta(days=1)

                if missing_start < current_date:
                    missing_end = min(current_date - timedelta(days=1), today)

                    # 只有当缺失范围在今天或之前时才添加
                    if missing_start <= today:
                        # 如果缺失范围包含今天，将今天之前的部分和今天分开
                        if missing_end >= today and missing_start < today:
                            # 今天之前的部分用历史接口
                            missing_ranges.append({
                                "start": missing_start.strftime("%Y-%m-%d"),
                                "end": (today - timedelta(days=1)).strftime("%Y-%m-%d")
                            })
                            # 今天单独标记为实时接口
                            missing_ranges.append({
                                "start": today.strftime("%Y-%m-%d"),
                                "end": today.strftime("%Y-%m-%d"),
                                "source": "realtime"
                            })
                        elif missing_start == today and missing_end == today:
                            # 只有今天缺失，用实时接口
                            missing_ranges.append({
                                "start": today.strftime("%Y-%m-%d"),
                                "end": today.strftime("%Y-%m-%d"),
                                "source": "realtime"
                            })
                        else:
                            # 不包含今天，用历史接口
                            missing_range = {
                                "start": missing_start.strftime("%Y-%m-%d"),
                                "end": missing_end.strftime("%Y-%m-%d")
                            }
                            missing_ranges.append(missing_range)
                        logger.info(f"检测到缺失范围: {missing_start} ~ {missing_end}")

                # 如果刚好到达循环条件，跳出循环
                if current_date > req_end.date():
                    break
            else:
                current_date += timedelta(days=1)

        logger.debug(f"缺失范围检测完成，总计 {len(missing_ranges)} 个范围: {missing_ranges}")
        return missing_ranges
    
    def _merge_overlapping_ranges(self, ranges):
        """
        合并重叠或相邻的日期范围，减少冗余的缺失区间记录。

        参数：
            ranges (List[Dict[str, Any]]): 缺失区间列表，每个元素包含 start（"%Y-%m-%d"）和 end（"%Y-%m-%d"）键。

        返回值：
            List[Dict[str, Any]]: 合并后的区间列表，按开始日期升序排列，
                重叠或相邻的区间已被合并为一个连续区间。

        调用关系：
            被 get_stock_data_with_indicators 调用，在多次检测缺失范围后用于去重和合并。

        关键逻辑：
            1. 若输入为空，直接返回空列表；
            2. 按 start 日期字符串排序（字典序即时间序，因为格式为 "%Y-%m-%d"）；
            3. 初始化 merged 列表，放入第一个区间；
            4. 遍历后续区间：
               - 若当前区间的 start <= 上一个区间的 end + 1 天（相邻也合并），
                 则更新上一个区间的 end 为两者较大值；
               - 否则将当前区间作为新区间追加；
            5. 返回合并后的列表。
        """
        if not ranges:
            return []
        
        # 按开始日期排序
        sorted_ranges = sorted(ranges, key=lambda x: x["start"])
        merged = [sorted_ranges[0].copy()]
        
        for current in sorted_ranges[1:]:
            last = merged[-1]
            
            # 解析日期进行比较
            last_end = datetime.strptime(last["end"], "%Y-%m-%d").date()
            curr_start = datetime.strptime(current["start"], "%Y-%m-%d").date()
            
            # 如果当前范围与上一个范围重叠或相邻，则合并
            if curr_start <= last_end + timedelta(days=1):
                last["end"] = max(last["end"], current["end"])
            else:
                merged.append(current.copy())
        
        return merged

    def get_all_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        综合获取 KDJ 和 MACD 两种技术指标的全部交易信号。

        参数：
            df (pd.DataFrame): 包含股票行情数据的 DataFrame，
                需包含 datetime、close_price、high_price、low_price、open_price、volume 等列。

        返回值：
            List[Dict[str, Any]]: KDJ 与 MACD 信号的合并列表，元素顺序为 KDJ 信号在前，MACD 信号在后。
                每个信号字典包含 datetime、type、indicator、reason、price 等键。

        调用关系：
            由 API 层或业务逻辑层调用，用于一次性获取多种指标的交易信号。
            内部调用：
                - get_kdj_signals（计算 KDJ 金叉/死叉信号）
                - get_macd_signals（计算 MACD 金叉/死叉信号）

        关键逻辑：
            1. 分别调用 get_kdj_signals 和 get_macd_signals 生成各自信号列表；
            2. 将两个列表拼接后返回，不做去重或排序；
            3. 调用方可根据 datetime 或 indicator 字段进一步筛选、排序。
        """
        kdj_signals = self.get_kdj_signals(df)
        macd_signals = self.get_macd_signals(df)
        return kdj_signals + macd_signals