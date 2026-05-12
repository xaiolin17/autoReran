# ARN 数据获取系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 ARN 数据获取系统，只使用 AkShare 真实数据源，实现智能数据获取、增量更新、WebSocket 进度推送和混合模式指标管理。

**Architecture:** 
1. 重构 AkshareCrawler 作为唯一数据源
2. 更新 StockService 支持智能获取和增量更新
3. 重构 IndicatorService 实现混合模式指标管理
4. 更新 API 端点和 WebSocket 推送
5. 初始化上证指数默认数据
6. 更新前端集成刷新功能

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, AkShare, Pandas, WebSocket, ECharts

---

## 变更文件清单

### 修改文件
- `app/crawlers/akshare_crawler.py` - 重构，完善 API 调用
- `app/crawlers/data_processor.py` - 移除模拟数据生成（保留但禁用）
- `app/services/stock_service.py` - 重构，移除其他数据源，实现增量更新
- `app/services/indicator_service.py` - 重构，实现混合模式
- `app/services/initialization_service.py` - 添加初始化上证指数功能
- `app/api/v1/endpoints/stocks.py` - 添加刷新端点
- `app/api/v1/endpoints/indicators.py` - 更新 WebSocket 推送逻辑
- `app/main.py` - 集成初始化服务
- `static/js/main.js` - 添加刷新按钮和进度显示

---

## 任务分解

### Task 1: 重构 AkshareCrawler - 完善 API 调用和错误处理

**Files:**
- Modify: `app/crawlers/akshare_crawler.py`

- [ ] **Step 1: 重写 _fetch_index_data 方法，确保正确调用 AkShare API**

```python
def _fetch_index_data(self, index_code: str, period: str, 
                      start_date: Optional[str], end_date: Optional[str]) -> pd.DataFrame:
    """获取指数数据"""
    try:
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        
        # 提取纯数字代码，去除 sh/sz 前缀
        code = index_code[2:] if len(index_code) > 2 else index_code
        
        # 根据周期选择不同的 API
        if period == "1d":
            df = ak.index_zh_a_hist(symbol=code, period="daily", 
                                   start_date=start_date, end_date=end_date)
        elif period == "1w":
            df = ak.index_zh_a_hist(symbol=code, period="weekly", 
                                   start_date=start_date, end_date=end_date)
        elif period == "1M":
            df = ak.index_zh_a_hist(symbol=code, period="monthly", 
                                   start_date=start_date, end_date=end_date)
        else:
            # 分钟线数据
            df = ak.index_zh_a_hist_min_em(symbol=index_code, period="60", 
                                          start_date=start_date, end_date=end_date)
        
        if df is None or df.empty:
            logger.warning(f"AkShare 返回空数据: index={index_code}, period={period}")
            return pd.DataFrame()
        
        # 标准化列名
        result = []
        for _, row in df.iterrows():
            result.append({
                'datetime': pd.to_datetime(row.get('日期', row.get('time', ''))),
                'open_price': float(row.get('开盘', row.get('open', 0))),
                'high_price': float(row.get('最高', row.get('high', 0))),
                'low_price': float(row.get('最低', row.get('low', 0))),
                'close_price': float(row.get('收盘', row.get('close', 0))),
                'volume': float(row.get('成交量', row.get('volume', 0))),
                'amount': float(row.get('成交额', row.get('amount', 0))),
                'stock_code': index_code[2:] if len(index_code) > 2 else index_code,
                'stock_name': '上证指数' if index_code == 'sh000001' else 
                              '深证成指' if index_code == 'sz399001' else index_code,
                'period': period,
                'source': 'akshare'
            })
        
        df_result = pd.DataFrame(result)
        logger.info(f"✅ Akshare 获取指数数据成功: {index_code}, {len(df_result)} 条")
        return df_result
        
    except Exception as e:
        logger.error(f"获取指数数据失败: {index_code}, 错误: {str(e)}")
        return pd.DataFrame()
```

- [ ] **Step 2: 重写 _fetch_stock_data 方法，确保正确调用 AkShare API**

```python
def _fetch_stock_data(self, stock_code: str, period: str, 
                      start_date: Optional[str], end_date: Optional[str]) -> pd.DataFrame:
    """获取股票数据"""
    try:
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        
        # 确定市场并添加前缀
        if stock_code.startswith(('600', '601', '603', '605', '688')):
            symbol = f"sh{stock_code}"
        else:
            symbol = f"sz{stock_code}"
        
        # 根据周期选择不同的 API
        if period == "1d":
            df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                                   start_date=start_date, end_date=end_date)
        elif period == "1w":
            df = ak.stock_zh_a_hist(symbol=stock_code, period="weekly", 
                                   start_date=start_date, end_date=end_date)
        elif period == "1M":
            df = ak.stock_zh_a_hist(symbol=stock_code, period="monthly", 
                                   start_date=start_date, end_date=end_date)
        else:
            # 分钟线数据
            df = ak.stock_zh_a_hist_min_em(symbol=symbol, period="60", 
                                          start_date=start_date, end_date=end_date)
        
        if df is None or df.empty:
            logger.warning(f"AkShare 返回空数据: stock={stock_code}, period={period}")
            return pd.DataFrame()
        
        stock_name = df.iloc[0].get('股票名称', stock_code) if len(df) > 0 else stock_code
        
        # 标准化列名
        result = []
        for _, row in df.iterrows():
            result.append({
                'datetime': pd.to_datetime(row.get('日期', row.get('time', ''))),
                'open_price': float(row.get('开盘', row.get('open', 0))),
                'high_price': float(row.get('最高', row.get('high', 0))),
                'low_price': float(row.get('最低', row.get('low', 0))),
                'close_price': float(row.get('收盘', row.get('close', 0))),
                'volume': float(row.get('成交量', row.get('volume', 0))),
                'amount': float(row.get('成交额', row.get('amount', 0))),
                'stock_code': stock_code,
                'stock_name': stock_name,
                'period': period,
                'source': 'akshare'
            })
        
        df_result = pd.DataFrame(result)
        logger.info(f"✅ Akshare 获取股票数据成功: {stock_code}, {len(df_result)} 条")
        return df_result
        
    except Exception as e:
        logger.error(f"获取股票数据失败: {stock_code}, 错误: {str(e)}")
        return pd.DataFrame()
```

- [ ] **Step 3: 更新 fetch_stock_data 方法，使用重写后的内部方法**

```python
def fetch_stock_data(self, stock_code: str, period: str = "1d", 
                    start_date: Optional[str] = None, 
                    end_date: Optional[str] = None) -> pd.DataFrame:
    if not self.available:
        logger.warning("Akshare 不可用，请安装 Akshare: pip install akshare")
        return pd.DataFrame()
    
    try:
        # 处理指数代码转换
        if stock_code == "000001":
            return self._fetch_index_data("sh000001", period, start_date, end_date)
        elif stock_code == "399001":
            return self._fetch_index_data("sz399001", period, start_date, end_date)
        else:
            return self._fetch_stock_data(stock_code, period, start_date, end_date)
    except Exception as e:
        logger.error(f"Akshare 获取数据失败: {stock_code}, {str(e)}")
        return pd.DataFrame()
```

- [ ] **Step 4: 提交更改**

```bash
cd /workspace
git add app/crawlers/akshare_crawler.py
git commit -m "feat: improve AkshareCrawler with proper API calls"
```

---

### Task 2: 更新 DataProcessor - 禁用模拟数据生成

**Files:**
- Modify: `app/crawlers/data_processor.py`

- [ ] **Step 1: 修改 generate_sample_data 方法，抛出异常表示不使用模拟数据**

```python
@staticmethod
def generate_sample_data(stock_code: str, period: str = "1d", 
                        days: int = 365, base_price: float = 100.0) -> pd.DataFrame:
    """不使用模拟数据，抛出异常"""
    raise RuntimeError(
        f"模拟数据已禁用，请确保 Akshare 可用或从数据库加载数据。"
        f"股票代码: {stock_code}"
    )
```

- [ ] **Step 2: 提交更改**

```bash
cd /workspace
git add app/crawlers/data_processor.py
git commit -m "refactor: disable sample data generation"
```

---

### Task 3: 重构 StockService - 移除其他数据源，实现增量更新

**Files:**
- Modify: `app/services/stock_service.py`

- [ ] **Step 1: 更新 __init__ 方法，只使用 AkshareCrawler**

```python
def __init__(self, db: Session):
    self.db = db
    self.data_processor = DataProcessor()
    # 只使用 Akshare 作为唯一数据源
    self.crawler = AkshareCrawler()
```

- [ ] **Step 2: 添加 get_latest_date 方法**

```python
def get_latest_date(self, stock_code: str, period: str) -> Optional[datetime]:
    """获取数据库中最新的数据日期"""
    from app.models.stock_data import StockData
    from sqlalchemy import desc
    
    latest = self.db.query(StockData).filter(
        StockData.stock_code == stock_code,
        StockData.period == period
    ).order_by(desc(StockData.datetime)).first()
    
    return latest.datetime if latest else None
```

- [ ] **Step 3: 添加 has_data 方法**

```python
def has_data(self, stock_code: str, period: str) -> bool:
    """检查是否有数据"""
    from app.models.stock_data import StockData
    
    count = self.db.query(StockData).filter(
        StockData.stock_code == stock_code,
        StockData.period == period
    ).count()
    
    return count > 0
```

- [ ] **Step 4: 更新 fetch_and_save_stock_data 方法，支持增量更新**

```python
def fetch_and_save_stock_data(
    self,
    stock_code: str,
    period: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    incremental: bool = False
) -> List[StockData]:
    from app.models.stock_data import StockData
    
    # 如果是增量更新，获取最新日期
    if incremental:
        latest_date = self.get_latest_date(stock_code, period)
        if latest_date:
            # 从最新日期的第二天开始获取
            start_date = (latest_date + timedelta(days=1)).strftime("%Y%m%d")
            logger.info(f"增量更新: 从 {start_date} 开始获取 {stock_code} {period} 数据")
    
    # 从 AkShare 获取数据
    df = self.crawler.fetch_stock_data(stock_code, period, start_date, end_date)
    
    if df.empty:
        logger.warning(f"未能从 Akshare 获取到数据: {stock_code} {period}")
        return []
    
    # 清理数据
    df = self.data_processor.clean_data(df)
    
    saved_stocks = []
    for _, row in df.iterrows():
        # 检查是否已存在
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
                source=row.get('source', 'akshare')
            )
            self.db.add(stock_data)
            saved_stocks.append(stock_data)
    
    try:
        self.db.commit()
        logger.info(f"✅ 保存了 {len(saved_stocks)} 条 {stock_code} {period} 数据")
    except Exception as e:
        logger.error(f"保存数据失败: {e}")
        self.db.rollback()
        return []
    
    return saved_stocks
```

- [ ] **Step 5: 添加 initialize_default_data 方法**

```python
def initialize_default_data(self, stock_code: str = "000001") -> bool:
    """
    初始化默认股票数据
    
    Args:
        stock_code: 默认 "000001" (上证指数)
    
    Returns:
        是否成功初始化
    """
    logger.info(f"开始初始化默认数据: {stock_code}")
    
    try:
        # 检查是否已有数据
        if self.has_data(stock_code, "1d"):
            logger.info(f"{stock_code} 已有数据，跳过初始化")
            return True
        
        # 获取一年的数据
        logger.info(f"正在从 Akshare 获取 {stock_code} 一年的数据...")
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
```

- [ ] **Step 6: 提交更改**

```bash
cd /workspace
git add app/services/stock_service.py
git commit -m "refactor: update StockService for Akshare-only and incremental updates"
```

---

### Task 4: 重构 IndicatorService - 实现混合模式指标管理

**Files:**
- Modify: `app/services/indicator_service.py`

- [ ] **Step 1: 重构 get_stock_data_with_indicators，实现混合模式**

```python
def get_stock_data_with_indicators(
    self,
    stock_code: str,
    period: str = "1d",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: Optional[int] = None,
    auto_save: bool = True
) -> List[Dict[str, Any]]:
    """
    获取带指标的数据（混合模式）
    
    混合模式:
    1. 优先从数据库读取已计算的指标
    2. 对于缺失的指标，实时计算
    3. 如果 auto_save=True，保存计算结果回数据库
    """
    from app.models.stock_data import StockData
    from sqlalchemy import desc
    
    query = self.db.query(StockData).filter(
        StockData.stock_code == stock_code,
        StockData.period == period
    )
    
    if limit:
        query = query.order_by(desc(StockData.datetime)).limit(limit)
    else:
        query = query.order_by(StockData.datetime)
    
    stock_data_list = query.all()
    
    if not stock_data_list:
        return []
    
    # 检查是否有缺失的指标
    has_missing_indicators = False
    for stock in stock_data_list:
        if (stock.ma5 is None or stock.k is None or 
            stock.macd is None):
            has_missing_indicators = True
            break
    
    # 如果指标完整，直接返回
    if not has_missing_indicators:
        return self._format_result(stock_data_list)
    
    # 否则，计算缺失的指标
    logger.info(f"检测到缺失指标，开始计算: {stock_code} {period}")
    df = self._stock_list_to_dataframe(stock_data_list)
    df = TechnicalIndicators.calculate_all_indicators(df)
    
    # 保存计算结果（如果需要）
    if auto_save:
        self._save_indicators_to_database(stock_data_list, df)
    
    # 返回带指标的数据
    return self._format_result_with_calculated_indicators(stock_data_list, df)
```

- [ ] **Step 2: 添加辅助方法**

```python
def _stock_list_to_dataframe(self, stock_data_list) -> pd.DataFrame:
    """将 StockData 列表转换为 DataFrame"""
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

def _save_indicators_to_database(self, stock_data_list, df: pd.DataFrame) -> None:
    """保存计算的指标到数据库"""
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
            stock.macd = float(row['macd']) if pd.notna(row['macd']) else None
        if 'macd_signal' in row:
            stock.dea = float(row['macd_signal']) if pd.notna(row['macd_signal']) else None
        if 'macd_histogram' in row:
            stock.dif = float(row['macd_histogram']) if pd.notna(row['macd_histogram']) else None
        
        if 'rsi' in row:
            stock.rsi6 = float(row['rsi']) if pd.notna(row['rsi']) else None
        
        if 'bb_upper' in row:
            stock.upper = float(row['bb_upper']) if pd.notna(row['bb_upper']) else None
        if 'bb_middle' in row:
            stock.middle = float(row['bb_middle']) if pd.notna(row['bb_middle']) else None
        if 'bb_lower' in row:
            stock.lower = float(row['bb_lower']) if pd.notna(row['bb_lower']) else None
    
    self.db.commit()
    logger.info(f"✅ 已保存技术指标到数据库")

def _format_result(self, stock_data_list) -> List[Dict[str, Any]]:
    """从数据库读取指标并格式化"""
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
            'macd': float(stock.macd) if stock.macd else None,
            'macd_signal': float(stock.dea) if stock.dea else None,
            'macd_histogram': float(stock.dif) if stock.dif else None,
            'rsi': float(stock.rsi6) if stock.rsi6 else None,
            'bb_upper': float(stock.upper) if stock.upper else None,
            'bb_middle': float(stock.middle) if stock.middle else None,
            'bb_lower': float(stock.lower) if stock.lower else None
        }
        result.append(item)
    return result

def _format_result_with_calculated_indicators(self, stock_data_list, df: pd.DataFrame) -> List[Dict[str, Any]]:
    """用计算的指标格式化结果"""
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
        
        # 优先使用数据库中的值，缺失的用计算值
        item['ma5'] = float(stock.ma5) if stock.ma5 else (float(row['ma5']) if 'ma5' in row and pd.notna(row['ma5']) else None)
        item['ma10'] = float(stock.ma10) if stock.ma10 else (float(row['ma10']) if 'ma10' in row and pd.notna(row['ma10']) else None)
        item['ma20'] = float(stock.ma20) if stock.ma20 else (float(row['ma20']) if 'ma20' in row and pd.notna(row['ma20']) else None)
        item['ma60'] = float(stock.ma60) if stock.ma60 else (float(row['ma60']) if 'ma60' in row and pd.notna(row['ma60']) else None)
        
        item['kdj_k'] = float(stock.k) if stock.k else (float(row['kdj_k']) if 'kdj_k' in row and pd.notna(row['kdj_k']) else None)
        item['kdj_d'] = float(stock.d) if stock.d else (float(row['kdj_d']) if 'kdj_d' in row and pd.notna(row['kdj_d']) else None)
        item['kdj_j'] = float(stock.j) if stock.j else (float(row['kdj_j']) if 'kdj_j' in row and pd.notna(row['kdj_j']) else None)
        
        item['macd'] = float(stock.macd) if stock.macd else (float(row['macd']) if 'macd' in row and pd.notna(row['macd']) else None)
        item['macd_signal'] = float(stock.dea) if stock.dea else (float(row['macd_signal']) if 'macd_signal' in row and pd.notna(row['macd_signal']) else None)
        item['macd_histogram'] = float(stock.dif) if stock.dif else (float(row['macd_histogram']) if 'macd_histogram' in row and pd.notna(row['macd_histogram']) else None)
        
        item['rsi'] = float(stock.rsi6) if stock.rsi6 else (float(row['rsi']) if 'rsi' in row and pd.notna(row['rsi']) else None)
        
        item['bb_upper'] = float(stock.upper) if stock.upper else (float(row['bb_upper']) if 'bb_upper' in row and pd.notna(row['bb_upper']) else None)
        item['bb_middle'] = float(stock.middle) if stock.middle else (float(row['bb_middle']) if 'bb_middle' in row and pd.notna(row['bb_middle']) else None)
        item['bb_lower'] = float(stock.lower) if stock.lower else (float(row['bb_lower']) if 'bb_lower' in row and pd.notna(row['bb_lower']) else None)
        
        result.append(item)
    return result
```

- [ ] **Step 3: 提交更改**

```bash
cd /workspace
git add app/services/indicator_service.py
git commit -m "refactor: implement hybrid indicator management in IndicatorService"
```

---

### Task 5: 更新 InitializationService - 添加上证指数初始化

**Files:**
- Modify: `app/services/initialization_service.py`

- [ ] **Step 1: 重写 check_and_initialize_default_data 方法**

```python
def check_and_initialize_default_data(self):
    """检查并初始化默认数据（上证指数）"""
    try:
        from app.services.stock_service import StockService
        from app.services.indicator_service import IndicatorService
        
        stock_service = StockService(self.db)
        indicator_service = IndicatorService(self.db)
        
        default_stock_code = "000001"
        
        # 检查是否已有数据
        has_data = stock_service.has_data(default_stock_code, "1d")
        
        if not has_data:
            print(f"⚙️ 正在初始化默认数据: 上证指数 ({default_stock_code})...")
            success = stock_service.initialize_default_data(default_stock_code)
            
            if success:
                print(f"✅ 默认数据初始化完成，正在计算技术指标...")
                indicator_service.calculate_and_save_indicators(default_stock_code, "1d")
                print(f"✅ 技术指标计算完成")
            else:
                print(f"⚠️  默认数据初始化失败（可能网络问题）")
        else:
            print(f"✅ 默认数据已存在: {default_stock_code}")
        
        return True
    except Exception as e:
        print(f"⚠️ 初始化服务出错: {e}")
        import traceback
        traceback.print_exc()
        return False
```

- [ ] **Step 2: 提交更改**

```bash
cd /workspace
git add app/services/initialization_service.py
git commit -m "feat: add SSE index initialization"
```

---

### Task 6: 更新 API 端点 - 添加刷新端点

**Files:**
- Modify: `app/api/v1/endpoints/stocks.py`

- [ ] **Step 1: 添加增量刷新端点**

```python
@router.post("/refresh/{stock_code}")
def refresh_stock_data(
    stock_code: str,
    period: str = "1d",
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    增量刷新股票数据
    
    只获取最新的数据，而不是全量重新下载
    """
    from app.services.stock_service import StockService
    from app.services.indicator_service import IndicatorService
    from app.core.websocket_manager import manager
    
    service = StockService(db)
    
    # 获取最新日期
    latest_date = service.get_latest_date(stock_code, period)
    if latest_date:
        message = f"发现现有数据，从 {latest_date.date()} 开始增量更新"
    else:
        message = f"没有现有数据，将下载完整数据"
    
    # 后台任务执行更新
    async def background_refresh():
        try:
            # 推送开始消息
            await manager.broadcast({
                "type": "download_progress",
                "data": {
                    "stock_code": stock_code,
                    "status": "downloading",
                    "progress": 10,
                    "message": "正在从 AkShare 获取数据..."
                }
            }, channel="realtime")
            
            # 执行增量更新
            saved_data = service.fetch_and_save_stock_data(
                stock_code, 
                period, 
                incremental=True
            )
            
            if saved_data:
                # 推送计算指标消息
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "calculating",
                        "progress": 70,
                        "message": "正在计算技术指标..."
                    }
                }, channel="realtime")
                
                # 计算指标
                indicator_service = IndicatorService(db)
                indicator_service.calculate_and_save_indicators(stock_code, period)
                
                # 推送完成消息
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "completed",
                        "progress": 100,
                        "message": f"刷新完成，新增 {len(saved_data)} 条数据",
                        "new_data_available": True
                    }
                }, channel="realtime")
            else:
                # 推送无新数据消息
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "completed",
                        "progress": 100,
                        "message": "已是最新数据，无需更新",
                        "new_data_available": False
                    }
                }, channel="realtime")
                
        except Exception as e:
            # 推送错误消息
            await manager.broadcast({
                "type": "download_progress",
                "data": {
                    "stock_code": stock_code,
                    "status": "error",
                    "progress": 0,
                    "message": f"刷新失败: {str(e)}"
                }
            }, channel="realtime")
    
    if background_tasks:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(background_refresh())
    
    return {
        "message": message,
        "stock_code": stock_code,
        "period": period,
        "incremental": latest_date is not None
    }
```

- [ ] **Step 2: 提交更改**

```bash
cd /workspace
git add app/api/v1/endpoints/stocks.py
git commit -m "feat: add incremental refresh endpoint"
```

---

### Task 7: 更新 Indicators API - 完善 WebSocket 推送

**Files:**
- Modify: `app/api/v1/endpoints/indicators.py`

- [ ] **Step 1: 更新 /{stock_code}/download 端点，集成 WebSocket 推送**

```python
@router.post("/{stock_code}/download")
def download_stock_data(
    stock_code: str,
    period: str = "1d",
    download_all: bool = False,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """启动后台下载数据任务"""
    from app.services.stock_service import StockService
    from app.services.indicator_service import IndicatorService
    from app.core.websocket_manager import manager
    
    task_id = f"{stock_code}_{datetime.now().timestamp()}"
    
    stock_service = StockService(db)
    existing_data = stock_service.has_data(stock_code, period)
    
    async def background_download():
        try:
            periods_to_download = ["1d"]
            if download_all:
                periods_to_download = ["1h", "1d", "1w", "1M"]
            
            for i, p in enumerate(periods_to_download):
                progress = int(10 + (i / len(periods_to_download)) * 80)
                
                await manager.broadcast({
                    "type": "download_progress",
                    "data": {
                        "stock_code": stock_code,
                        "status": "downloading",
                        "progress": progress,
                        "message": f"正在下载 {p} 数据 ({i+1}/{len(periods_to_download)})..."
                    }
                }, channel="realtime")
                
                saved = stock_service.fetch_and_save_stock_data(
                    stock_code, p, incremental=existing_data
                )
                
                if saved:
                    indicator_service = IndicatorService(db)
                    indicator_service.calculate_and_save_indicators(stock_code, p)
            
            await manager.broadcast({
                "type": "download_progress",
                "data": {
                    "stock_code": stock_code,
                    "status": "completed",
                    "progress": 100,
                    "message": "数据下载完成",
                    "new_data_available": True
                }
            }, channel="realtime")
            
        except Exception as e:
            await manager.broadcast({
                "type": "download_progress",
                "data": {
                    "stock_code": stock_code,
                    "status": "error",
                    "progress": 0,
                    "message": f"下载失败: {str(e)}"
                }
            }, channel="realtime")
    
    if background_tasks:
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(background_download())
    
    return {
        "task_id": task_id,
        "message": "后台下载已启动" if existing_data else "开始下载数据",
        "has_existing_data": existing_data
    }
```

- [ ] **Step 2: 提交更改**

```bash
cd /workspace
git add app/api/v1/endpoints/indicators.py
git commit -m "feat: improve WebSocket progress notifications in download endpoint"
```

---

### Task 8: 更新 Main.py - 集成初始化服务

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: 在应用启动时初始化上证指数数据**

```python
# 在创建 FastAPI 应用后添加
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化默认数据"""
    from app.core.database import SessionLocal
    from app.services.initialization_service import InitializationService
    
    print("=" * 60)
    print("正在初始化 ARN 数据系统...")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        init_service = InitializationService(db)
        init_service.check_and_initialize_default_data()
    except Exception as e:
        print(f"⚠️ 初始化出错: {e}")
    finally:
        db.close()
    
    print("=" * 60)
    print("ARN 系统启动完成!")
    print("=" * 60)
```

- [ ] **Step 2: 提交更改**

```bash
cd /workspace
git add app/main.py
git commit -m "feat: integrate initialization service on app startup"
```

---

### Task 9: 更新前端 - 添加刷新按钮和进度显示

**Files:**
- Modify: `templates/index.html`
- Modify: `static/js/main.js`

- [ ] **Step 1: 在 index.html 中添加刷新按钮和进度指示器**

在头部控制区域添加：

```html
<div class="controls">
    <div class="stock-selector">
        <input type="text" id="stockCode" value="000001" placeholder="输入股票代码">
        <button id="fetchBtn">获取数据</button>
        <button id="refreshBtn" class="refresh-btn">🔄 刷新数据</button>
    </div>
    <div class="period-selector">
        <button class="period-btn active" data-period="1d">日线</button>
        <button class="period-btn" data-period="1h">小时</button>
        <button class="period-btn" data-period="1w">周线</button>
    </div>
    <div id="progressContainer" class="progress-container" style="display: none;">
        <div class="progress-bar">
            <div id="progressBar" class="progress-fill"></div>
        </div>
        <span id="progressText">加载中...</span>
    </div>
</div>
```

在 CSS 中添加：

```css
.refresh-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    transition: transform 0.2s, box-shadow 0.2s;
}
.refresh-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}
.refresh-btn:active {
    transform: translateY(0);
}

.progress-container {
    margin-top: 15px;
    padding: 15px;
    background: #f8f9fa;
    border-radius: 8px;
    border-left: 4px solid #667eea;
}
.progress-bar {
    width: 100%;
    height: 8px;
    background: #e9ecef;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 8px;
}
.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    width: 0%;
    transition: width 0.3s ease;
    border-radius: 4px;
}
```

- [ ] **Step 2: 在 main.js 中添加刷新功能和 WebSocket 进度处理**

```javascript
// 在 setupEventListeners 中添加
const refreshBtn = document.getElementById('refreshBtn');
if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
        const stockCode = document.getElementById('stockCode').value;
        const period = currentPeriod;
        await refreshStockData(stockCode, period);
    });
}

// 添加刷新数据函数
async function refreshStockData(stockCode, period) {
    try {
        showProgress(0, '正在刷新...');
        const response = await fetch(`/api/v1/stocks/refresh/${stockCode}?period=${period}`, {
            method: 'POST'
        });
        const result = await response.json();
        console.log('刷新任务已启动:', result);
        showProgress(10, result.message);
    } catch (error) {
        console.error('刷新失败:', error);
        hideProgress();
        alert('刷新失败，请检查网络连接');
    }
}

// 添加进度显示函数
function showProgress(progress, message) {
    const container = document.getElementById('progressContainer');
    const bar = document.getElementById('progressBar');
    const text = document.getElementById('progressText');
    
    if (container) {
        container.style.display = 'block';
    }
    if (bar) {
        bar.style.width = `${progress}%`;
    }
    if (text) {
        text.textContent = message;
    }
}

function hideProgress() {
    const container = document.getElementById('progressContainer');
    if (container) {
        container.style.display = 'none';
    }
}

// 在 WebSocket 消息处理中添加进度处理
if (data.type === 'download_progress') {
    const progressData = data.data;
    if (progressData.stock_code === currentStockCode) {
        showProgress(progressData.progress, progressData.message);
        
        if (progressData.status === 'completed') {
            setTimeout(() => {
                hideProgress();
                if (progressData.new_data_available) {
                    loadData(); // 重新加载数据
                }
            }, 1500);
        } else if (progressData.status === 'error') {
            setTimeout(() => {
                hideProgress();
                alert(progressData.message);
            }, 1500);
        }
    }
}
```

- [ ] **Step 3: 提交更改**

```bash
cd /workspace
git add templates/index.html static/js/main.js
git commit -m "feat: add refresh button and progress display in frontend"
```

---

### Task 10: 推送所有更改到 main 分支

**Files:**
- Push: All changes

- [ ] **Step 1: 推送所有更改**

```bash
cd /workspace
git push origin main
```

---

## 验收测试

- [ ] 应用启动时自动初始化上证指数数据
- [ ] 输入新股票代码能正确从 AkShare 获取数据
- [ ] 数据保存到数据库，重复请求不重新下载
- [ ] 点击刷新按钮触发增量更新
- [ ] WebSocket 实时推送下载进度
- [ ] 技术指标混合模式正常工作
- [ ] 没有使用模拟数据

---

## 注意事项

1. **AkShare 依赖**: 确保已安装 `akshare>=1.12.72`
2. **网络连接**: 需要能够访问 AkShare 的数据源
3. **数据库**: 首次运行会自动创建 SQLite 数据库
4. **数据量**: 一年的日线数据约 250 条记录，加载很快
