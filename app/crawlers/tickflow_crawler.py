import os
import pandas as pd
import numpy as np
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import deque
from app.crawlers.base import BaseCrawler
from app.core.logger import logger, log_function_call
from app.core.config import settings

try:
    from tickflow import TickFlow
    TICKFLOW_AVAILABLE = True
except ImportError:
    TICKFLOW_AVAILABLE = False
    logger.warning("TickFlow SDK 未安装，请安装: pip install tickflow")


class RateLimiter:
    """
    简单令牌桶限流器

    职责:
        基于令牌桶算法实现API调用频率控制，防止短时间内大量请求导致服务被拒绝。
        在指定时间窗口内限制最大调用次数，超出限制时阻塞或返回等待时间。

    被调用方:
        - TickFlowCrawler: 在发起TickFlow API请求前进行限流检查
    """

    def __init__(self, max_calls: int = 10, period_seconds: int = 60):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self.calls = deque()
        self._lock = threading.Lock()

    def acquire(self, timeout: float = 30.0) -> bool:
        """
        尝试获取一个调用令牌，返回是否成功

        参数:
            timeout: 最大等待时间（秒），超过此时间仍未获取到令牌则返回False

        返回值:
            bool: 成功获取令牌返回True，超时返回False

        调用关系:
            被调用: TickFlowCrawler.fetch_stock_data 在发起API请求前调用
            调用: 无（内部逻辑）

        关键逻辑:
            1. 清理过期调用记录（超出period_seconds的记录）
            2. 检查当前窗口内调用次数是否小于max_calls
            3. 若未满则记录当前时间并返回True
            4. 若已满则等待0.5秒后重试，直到超时
        """
        start_time = time.time()
        while True:
            with self._lock:
                now = time.time()
                # 清理过期的调用记录
                while self.calls and self.calls[0] < now - self.period_seconds:
                    self.calls.popleft()

                if len(self.calls) < self.max_calls:
                    self.calls.append(now)
                    return True

            # 超过超时时间
            if time.time() - start_time > timeout:
                return False

            # 等待一段时间后重试
            time.sleep(0.5)

    def get_wait_time(self) -> float:
        """
        获取需要等待的时间（秒）

        参数:
            无

        返回值:
            float: 需要等待的秒数，0.0表示无需等待即可获取令牌

        调用关系:
            被调用: TickFlowCrawler.fetch_stock_data 用于预先检查是否需要等待
            调用: 无（内部逻辑）

        关键逻辑:
            1. 清理过期调用记录
            2. 若当前调用次数未满则返回0.0
            3. 若已满则计算最早一个调用何时过期，返回剩余等待时间
        """
        with self._lock:
            now = time.time()
            while self.calls and self.calls[0] < now - self.period_seconds:
                self.calls.popleft()

            if len(self.calls) < self.max_calls:
                return 0.0

            # 计算最早一个调用何时过期
            if self.calls:
                wait = self.calls[0] + self.period_seconds - now
                return max(0.0, wait)
            return 0.0


class TickFlowCrawler(BaseCrawler):
    """
    TickFlow数据源爬虫

    职责:
        封装TickFlow SDK的调用，提供股票K线数据、实时行情数据的获取能力。
        负责股票代码标准化、日期处理、数据格式转换、限流控制等功能。
        继承自BaseCrawler，统一项目内爬虫接口。

    被调用方:
        - StockService: 调用fetch_stock_data获取股票历史数据
        - 其他服务层: 调用fetch_realtime_data获取实时行情

    调用方:
        - RateLimiter: 控制API调用频率
        - TickFlow SDK: 实际发起数据请求
        - StockCode模型: 查询股票代码映射
    """

    def __init__(self, db=None):
        self.available = TICKFLOW_AVAILABLE
        self.max_retries = 1  # 只重试1次
        self.retry_delay = 3
        self._tf = None
        self._symbol_map = {}  # 缓存股票代码映射 {short_code: full_symbol}
        self._universe_symbols = []  # CN_Equity_A 的 symbols 列表
        self._db = db  # 数据库会话，用于查询 StockCode 表
        self._rate_limiter = RateLimiter(max_calls=10, period_seconds=60)

    def _get_tickflow(self):
        """
        获取TickFlow实例（懒加载）

        参数:
            无

        返回值:
            TickFlow: TickFlow SDK实例，若初始化失败或API Key未设置则返回None

        调用关系:
            被调用: fetch_stock_data, fetch_realtime_data, fetch_realtime_data_as_df, _load_universe_symbols, get_universe_symbols
            调用: settings.TICKFLOW_API_KEY, os.getenv

        关键逻辑:
            1. 若已初始化则直接返回缓存实例
            2. 从settings或环境变量读取TICKFLOW_API_KEY
            3. 若API Key未设置则标记不可用并返回None
            4. 使用API Key初始化TickFlow客户端
        """
        if self._tf is None and self.available:
            # 优先从 settings 读取（支持 .env 文件），其次从环境变量读取
            api_key = settings.TICKFLOW_API_KEY or os.getenv("TICKFLOW_API_KEY")
            if not api_key:
                logger.error("TICKFLOW_API_KEY 未设置，请在 .env 文件中设置或配置环境变量")
                self.available = False
                return None
            self._tf = TickFlow(api_key=api_key)
            logger.info("TickFlow 客户端初始化成功")
        return self._tf

    def _retry_fetch(self, fetch_func, *args, **kwargs):
        """
        带指数退避的重试辅助方法

        参数:
            fetch_func: 实际执行数据获取的可调用函数
            *args: 传递给fetch_func的位置参数
            **kwargs: 传递给fetch_func的关键字参数

        返回值:
            Any: fetch_func的返回结果，若所有重试均失败则返回None

        调用关系:
            被调用: fetch_stock_data 在调用tf.klines.get时使用
            调用: fetch_func（传入的实际获取函数）

        关键逻辑:
            1. 最多重试max_retries次
            2. 每次重试等待时间呈指数增长: retry_delay * (2 ** attempt)
            3. 记录每次失败日志
            4. 所有重试失败后记录错误并返回None
        """
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                result = fetch_func(*args, **kwargs)
                return result
            except Exception as e:
                last_exception = e
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(f"第 {attempt + 1}/{self.max_retries} 次尝试失败: {str(e)}。{wait_time}秒后重试...")
                time.sleep(wait_time)
        logger.error(f"所有 {self.max_retries} 次尝试均失败。最后一次错误: {str(last_exception)}")
        return None

    def _normalize_stock_code(self, stock_code: str) -> str:
        """
        标准化股票代码，去除市场前缀，只保留6位数字

        参数:
            stock_code: 原始股票代码，可能包含SH/SZ前缀或后缀

        返回值:
            str: 纯6位数字代码

        调用关系:
            被调用: get_full_symbol, _get_full_symbol_from_db, _load_universe_symbols
            调用: 无（字符串处理）

        关键逻辑:
            1. 去除首尾空白并转为大写
            2. 去除SH/SZ前缀（如SH600000 -> 600000）
            3. 去除.SH/.SZ后缀（如600000.SH -> 600000）
            4. 返回6位数字代码
        """
        code = stock_code.strip().upper()
        # 去除 sh/sz/SH/SZ 前缀
        if len(code) > 6 and code[:2] in ('SH', 'SZ', 'sh', 'sz'):
            return code[2:]
        # 去除 .SH/.SZ 后缀
        if '.' in code:
            return code.split('.')[0]
        return code

    def _extract_suffix(self, stock_code: str) -> Optional[str]:
        """
        提取用户输入中的市场后缀（如 .SH / .SZ）

        参数:
            stock_code: 原始股票代码，可能包含.SH/.SZ后缀

        返回值:
            Optional[str]: 市场后缀"SH"或"SZ"，若无后缀则返回None

        调用关系:
            被调用: get_full_symbol 用于判断用户是否明确指定了市场
            调用: 无（字符串处理）

        关键逻辑:
            1. 去除首尾空白并转为大写
            2. 按"."分割代码
            3. 若第二部分为SH或SZ则返回该后缀
            4. 否则返回None
        """
        code = stock_code.strip().upper()
        if '.' in code:
            parts = code.split('.')
            if len(parts) == 2 and parts[1] in ('SH', 'SZ'):
                return parts[1]
        return None

    def _load_universe_symbols(self):
        """
        加载 CN_Equity_A 的 symbols 列表，用于代码映射

        参数:
            无

        返回值:
            无（结果缓存到self._universe_symbols和self._symbol_map）

        调用关系:
            被调用: get_full_symbol, fetch_stock_list, get_all_symbols, get_symbol_map
            调用: _get_tickflow, tf.universes.get

        关键逻辑:
            1. 若已加载则直接返回（避免重复请求）
            2. 获取TickFlow实例
            3. 调用tf.universes.get("CN_Equity_A")获取A股全量代码
            4. 构建短代码到完整代码的映射表 {short_code: full_symbol}
            5. 缓存到实例变量中
        """
        if self._universe_symbols:
            return

        tf = self._get_tickflow()
        if not tf:
            return

        try:
            logger.info("正在加载 CN_Equity_A universe symbols...")
            a_shares = tf.universes.get("CN_Equity_A")
            if a_shares and "symbols" in a_shares:
                self._universe_symbols = a_shares["symbols"]
                # 构建映射表 {short_code: full_symbol}
                for sym in self._universe_symbols:
                    short = sym.split('.')[0] if '.' in sym else sym
                    self._symbol_map[short] = sym
                logger.info(f"成功加载 {len(self._universe_symbols)} 只A股代码映射")
            else:
                logger.warning("无法获取 CN_Equity_A symbols")
        except Exception as e:
            logger.error(f"加载 universe symbols 失败: {e}")

    def _get_full_symbol_from_db(self, stock_code: str) -> Optional[str]:
        """
        从数据库查询完整代码

        参数:
            stock_code: 股票代码（短代码或带后缀的代码）

        返回值:
            Optional[str]: 数据库中存储的完整代码（如000001.SZ），未找到则返回None

        调用关系:
            被调用: get_full_symbol 作为代码解析的第二优先级
            调用: _normalize_stock_code, StockCode模型查询

        关键逻辑:
            1. 检查数据库会话是否存在
            2. 标准化股票代码为6位数字
            3. 查询StockCode表中code字段匹配的记录
            4. 返回第一条记录的name字段（完整代码）
            5. 异常时静默处理并返回None
        """
        if self._db is None:
            return None
        try:
            from app.models.stock_data import StockCode
            clean_code = self._normalize_stock_code(stock_code)
            record = self._db.query(StockCode).filter(StockCode.code == clean_code).first()
            if record:
                return record.name
        except Exception as e:
            logger.debug(f"从数据库查询完整代码失败: {e}")
        return None

    def get_full_symbol(self, stock_code: str) -> Optional[str]:
        """
        将短代码转换为完整代码（如 000001 -> 000001.SZ）

        参数:
            stock_code: 股票代码（短代码如000001，或带后缀如000001.SZ）

        返回值:
            Optional[str]: 完整代码（如000001.SZ），解析失败则返回None

        调用关系:
            被调用: fetch_stock_data, fetch_realtime_data, fetch_realtime_data_as_df, _convert_to_standard_format
            调用: _normalize_stock_code, _extract_suffix, _get_full_symbol_from_db, _load_universe_symbols

        关键逻辑:
            1. 若用户明确指定后缀（如.SH/.SZ），直接使用
            2. 否则先查数据库StockCode表
            3. 再查本地缓存的symbol_map
            4. 若缓存未命中则加载universe symbols
            5. 最后根据代码规则推断（600/601/603/605/688/689开头为.SH，其余为.SZ）
        """
        clean_code = self._normalize_stock_code(stock_code)
        user_suffix = self._extract_suffix(stock_code)

        # 如果用户明确指定了后缀（如 000001.SH），优先使用
        if user_suffix:
            return f"{clean_code}.{user_suffix}"

        # 先查数据库
        db_symbol = self._get_full_symbol_from_db(stock_code)
        if db_symbol:
            return db_symbol

        # 再查缓存
        if clean_code in self._symbol_map:
            return self._symbol_map[clean_code]

        # 加载 universe
        self._load_universe_symbols()

        # 再次查询缓存
        if clean_code in self._symbol_map:
            return self._symbol_map[clean_code]

        # 根据规则推断（fallback）
        if clean_code.startswith(('600', '601', '603', '605', '688', '689')):
            return f"{clean_code}.SH"
        else:
            return f"{clean_code}.SZ"

    def _parse_date(self, date_str: str) -> datetime:
        """
        解析日期字符串，支持多种格式

        参数:
            date_str: 日期字符串（如20240101、2024-01-01、2024/01/01）

        返回值:
            datetime: 解析后的日期时间对象

        调用关系:
            被调用: _get_start_end_dates
            调用: datetime.strptime

        关键逻辑:
            1. 依次尝试三种格式：%Y%m%d、%Y-%m-%d、%Y/%m/%d
            2. 任一格式解析成功则返回结果
            3. 所有格式均失败则抛出ValueError
        """
        formats = ["%Y%m%d", "%Y-%m-%d", "%Y/%m/%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        raise ValueError(f"无法解析日期: {date_str}")

    def _get_start_end_dates(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        default_months: float = 1.0
    ) -> tuple:
        """
        统一处理 start_date 和 end_date，返回毫秒时间戳

        参数:
            start_date: 开始日期字符串，None表示使用默认值
            end_date: 结束日期字符串，None表示使用当前日期
            default_months: 默认回溯月数（当start_date为None时使用）

        返回值:
            tuple: (start_ms, end_ms) 毫秒时间戳元组，日期无效返回(None, None)

        调用关系:
            被调用: fetch_stock_data
            调用: _parse_date

        关键逻辑:
            1. end_date为None则使用当前日期时间
            2. start_date为None则使用end_date回溯default_months个月
            3. 检查start_date是否大于end_date，若是则返回(None, None)
            4. 将日期转换为毫秒时间戳（TickFlow API需要）
        """
        if end_date is None:
            end_dt = datetime.now()
        else:
            end_dt = self._parse_date(end_date)

        if start_date is None:
            start_dt = end_dt - timedelta(days=int(default_months * 30))
        else:
            start_dt = self._parse_date(start_date)

        if start_dt > end_dt:
            logger.warning(f"无效日期范围: start_date={start_date} > end_date={end_date}")
            return None, None

        # 转换为毫秒时间戳
        start_ms = int(start_dt.timestamp() * 1000)
        end_ms = int(end_dt.timestamp() * 1000)
        return start_ms, end_ms

    @log_function_call()
    def fetch_stock_data(
        self,
        stock_code: str,
        period: str = "1d",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        获取股票K线数据

        参数:
            stock_code: 股票代码（如 000001 或 000001.SZ）
            period: 时间周期（TickFlow支持 1d, 1w, 1M 等）
            start_date: 开始日期 (YYYY-MM-DD 或 YYYYMMDD)
            end_date: 结束日期 (YYYY-MM-DD 或 YYYYMMDD)

        返回值:
            pd.DataFrame: 标准化后的股票K线数据，失败返回空DataFrame

        调用关系:
            被调用: StockService.fetch_and_save_stock_data 等上层服务
            调用: _rate_limiter.acquire/get_wait_time, _get_tickflow, get_full_symbol, _get_start_end_dates, _retry_fetch, _convert_to_standard_format

        关键逻辑:
            1. 检查TickFlow是否可用
            2. 限流检查：获取令牌或等待
            3. 将股票代码转换为完整代码
            4. 解析并转换日期范围为毫秒时间戳
            5. 调用TickFlow klines.get获取K线数据（带重试）
            6. 将原始数据转换为项目标准格式
            7. 异常时返回空DataFrame
        """
        logger.info(f"开始获取股票数据: stock_code={stock_code}, period={period}, start_date={start_date}, end_date={end_date}")

        if not self.available:
            logger.warning("TickFlow 不可用")
            return pd.DataFrame()

        # 限流检查
        wait_time = self._rate_limiter.get_wait_time()
        if wait_time > 0:
            logger.warning(f"TickFlow API 限流中，需等待 {wait_time:.1f} 秒")
            # 等待获取令牌
            if not self._rate_limiter.acquire(timeout=wait_time + 5):
                logger.error("TickFlow API 限流，无法获取调用令牌")
                return pd.DataFrame()
        else:
            self._rate_limiter.acquire(timeout=1.0)

        tf = self._get_tickflow()
        if not tf:
            return pd.DataFrame()

        try:
            full_symbol = self.get_full_symbol(stock_code)
            if not full_symbol:
                logger.warning(f"无法解析股票代码: {stock_code}")
                return pd.DataFrame()

            logger.debug(f"股票代码映射: {stock_code} -> {full_symbol}")

            start_ms, end_ms = self._get_start_end_dates(
                start_date=start_date,
                end_date=end_date,
                default_months=1.0
            )

            if start_ms is None or end_ms is None:
                logger.warning("日期处理失败，返回空DataFrame")
                return pd.DataFrame()

            logger.info(f"获取数据: {full_symbol} {period} [{start_date} ~ {end_date}]")

            # 调用TickFlow获取K线数据
            df = self._retry_fetch(
                tf.klines.get,
                full_symbol,
                period=period,
                start_time=start_ms,
                end_time=end_ms,
                as_dataframe=True
            )

            if df is None or df.empty:
                logger.warning(f"TickFlow 返回空数据: symbol={full_symbol}, period={period}")
                return pd.DataFrame()

            logger.info(f"TickFlow 返回原始数据: {len(df)} 条, 列名: {list(df.columns)}")

            # 转换为项目标准格式
            result = self._convert_to_standard_format(df, stock_code, period)
            logger.info(f"获取数据完成: {len(result)} 条记录")
            return result

        except Exception as e:
            logger.error(f"TickFlow获取 {stock_code} 数据失败: {str(e)}", exc_info=True)
            return pd.DataFrame()

    def _convert_to_standard_format(self, df: pd.DataFrame, stock_code: str, period: str) -> pd.DataFrame:
        """
        将TickFlow返回的数据转换为项目标准格式

        参数:
            df: TickFlow返回的原始DataFrame
            stock_code: 原始股票代码（用于获取完整代码）
            period: 时间周期

        返回值:
            pd.DataFrame: 符合项目标准格式的DataFrame

        调用关系:
            被调用: fetch_stock_data
            调用: get_full_symbol, safe_float（内部函数）

        关键逻辑:
            1. 获取完整代码用于显示
            2. 定义safe_float辅助函数处理None/NaN值
            3. 遍历原始DataFrame每一行
            4. 将毫秒时间戳转换为datetime对象
            5. 提取open/high/low/close/volume/amount等字段
            6. 组装为标准格式字典列表
            7. 返回新的DataFrame
        """
        result = []

        # 获取完整代码（带后缀）用于保存到数据库
        full_symbol = self.get_full_symbol(stock_code)
        display_code = full_symbol if full_symbol else stock_code

        def safe_float(value, default=0.0):
            if value is None or (isinstance(value, float) and np.isnan(value)):
                return default
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        for _, row in df.iterrows():
            # TickFlow返回的列: timestamp/trade_date, open, high, low, close, volume, amount
            # 注意: timestamp 是毫秒时间戳
            ts = row.get('timestamp', row.get('trade_time', 0))
            if isinstance(ts, (int, float)) and ts > 1e12:
                # 毫秒时间戳转datetime
                dt = pd.to_datetime(ts, unit='ms')
            else:
                dt = pd.to_datetime(row.get('trade_date', ts))

            result.append({
                'datetime': dt,
                'open_price': safe_float(row.get('open')),
                'high_price': safe_float(row.get('high')),
                'low_price': safe_float(row.get('low')),
                'close_price': safe_float(row.get('close')),
                'volume': safe_float(row.get('volume')),
                'amount': safe_float(row.get('amount')),
                'stock_code': display_code,
                'stock_name': row.get('name', ''),
                'period': period,
                'source': 'tickflow'
            })

        return pd.DataFrame(result)

    def fetch_realtime_data(self, stock_code: str) -> Dict:
        """
        获取实时行情数据

        参数:
            stock_code: 股票代码（短代码或完整代码）

        返回值:
            Dict: 实时行情数据字典，失败返回空字典

        调用关系:
            被调用: StockService等上层服务获取实时行情
            调用: _get_tickflow, get_full_symbol, tf.quotes.get

        关键逻辑:
            1. 检查TickFlow是否可用
            2. 获取TickFlow实例
            3. 将股票代码转换为完整代码
            4. 调用tf.quotes.get获取实时报价
            5. 返回第一条报价数据
            6. 异常时返回空字典
        """
        if not self.available:
            return {}

        tf = self._get_tickflow()
        if not tf:
            return {}

        try:
            full_symbol = self.get_full_symbol(stock_code)
            if not full_symbol:
                return {}

            quotes = tf.quotes.get(symbols=[full_symbol])
            if quotes and len(quotes) > 0:
                return quotes[0]
            return {}
        except Exception as e:
            logger.error(f"TickFlow获取实时数据失败: {e}")
            return {}

    def fetch_realtime_data_as_df(self, stock_code: str) -> pd.DataFrame:
        """
        获取实时行情数据并转换为DataFrame格式（用于保存到数据库）

        参数:
            stock_code: 股票代码（短代码或完整代码）

        返回值:
            pd.DataFrame: 单条实时行情数据的标准格式DataFrame，失败返回空DataFrame

        调用关系:
            被调用: StockService.fetch_and_save_stock_data 当source="realtime"时调用
            调用: _get_tickflow, get_full_symbol, tf.quotes.get

        关键逻辑:
            1. 检查TickFlow是否可用
            2. 获取TickFlow实例
            3. 将股票代码转换为完整代码
            4. 调用tf.quotes.get获取实时报价
            5. 提取报价中的价格字段（open/high/low/last_price/volume/amount）
            6. 组装为与历史K线一致的标准格式
            7. 使用当前日期作为datetime
            8. 返回单条数据的DataFrame
        """
        if not self.available:
            return pd.DataFrame()

        tf = self._get_tickflow()
        if not tf:
            return pd.DataFrame()

        try:
            full_symbol = self.get_full_symbol(stock_code)
            if not full_symbol:
                return pd.DataFrame()

            quotes = tf.quotes.get(symbols=[full_symbol])
            if not quotes or len(quotes) == 0:
                return pd.DataFrame()

            quote = quotes[0]
            if not quote:
                return pd.DataFrame()

            # 获取完整代码用于显示
            display_code = full_symbol if full_symbol else stock_code

            # 获取当前日期作为交易日期
            today = datetime.now().date()

            # 安全获取数值字段，处理 None 的情况
            def safe_float(value, default=0.0):
                if value is None:
                    return default
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return default

            result = {
                'datetime': pd.Timestamp(today),
                'open_price': safe_float(quote.get('open')),
                'high_price': safe_float(quote.get('high')),
                'low_price': safe_float(quote.get('low')),
                'close_price': safe_float(quote.get('last_price')),
                'volume': safe_float(quote.get('volume')),
                'amount': safe_float(quote.get('amount')),
                'stock_code': display_code,
                'stock_name': quote.get('ext', {}).get('name', ''),
                'period': '1d',
                'source': 'tickflow_realtime'
            }

            logger.info(f"获取实时行情数据: {display_code}, open={result['open_price']}, high={result['high_price']}, low={result['low_price']}, close={result['close_price']}, volume={result['volume']}")
            return pd.DataFrame([result])

        except Exception as e:
            logger.error(f"TickFlow获取实时数据失败: {e}")
            return pd.DataFrame()

    def fetch_stock_list(self) -> List[Dict]:
        """
        获取股票列表（从universe获取）

        参数:
            无

        返回值:
            List[Dict]: 股票列表，每项包含code和name字段，限制前100条

        调用关系:
            被调用: 上层服务获取股票列表
            调用: _load_universe_symbols

        关键逻辑:
            1. 加载universe symbols
            2. 取前100条限制返回数量
            3. 将完整代码拆分为短代码
            4. 组装为字典列表返回
        """
        self._load_universe_symbols()

        stocks = []
        for sym in self._universe_symbols[:100]:  # 限制数量避免过大
            short = sym.split('.')[0] if '.' in sym else sym
            stocks.append({"code": short, "name": sym})
        return stocks

    def get_all_symbols(self) -> List[str]:
        """
        获取所有A股完整代码列表

        参数:
            无

        返回值:
            List[str]: 所有A股完整代码列表（如["000001.SZ", "600000.SH", ...]）

        调用关系:
            被调用: 上层服务获取全量代码
            调用: _load_universe_symbols

        关键逻辑:
            1. 加载universe symbols
            2. 返回缓存的完整代码列表
        """
        self._load_universe_symbols()
        return self._universe_symbols

    def get_universe_symbols(self, universe_id: str) -> List[str]:
        """
        获取指定 universe 的 symbols 列表

        参数:
            universe_id: Universe标识符（如"CN_Equity_A"）

        返回值:
            List[str]: 指定universe的symbols列表，失败返回空列表

        调用关系:
            被调用: 上层服务按universe获取代码
            调用: _get_tickflow, tf.universes.get

        关键逻辑:
            1. 获取TickFlow实例
            2. 调用tf.universes.get(universe_id)获取universe数据
            3. 提取symbols列表
            4. 异常时返回空列表
        """
        tf = self._get_tickflow()
        if not tf:
            return []

        try:
            logger.info(f"正在加载 {universe_id} universe symbols...")
            universe = tf.universes.get(universe_id)
            if universe and "symbols" in universe:
                symbols = universe["symbols"]
                logger.info(f"成功加载 {universe_id}: {len(symbols)} 条")
                return symbols
            else:
                logger.warning(f"无法获取 {universe_id} symbols")
                return []
        except Exception as e:
            logger.error(f"加载 {universe_id} 失败: {e}")
            return []

    def get_symbol_map(self) -> Dict[str, str]:
        """
        获取股票代码映射表 {short_code: full_symbol}

        参数:
            无

        返回值:
            Dict[str, str]: 短代码到完整代码的映射字典副本

        调用关系:
            被调用: 上层服务需要代码映射时
            调用: _load_universe_symbols

        关键逻辑:
            1. 加载universe symbols（若未加载）
            2. 返回映射表的副本（避免外部修改）
        """
        self._load_universe_symbols()
        return self._symbol_map.copy()
