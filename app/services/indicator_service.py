from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import pandas as pd
from app.utils.technical_indicators import TechnicalIndicators
from app.core.logger import log_function_call, logger


class IndicatorService:
    def __init__(self, db: Session):
        self.db = db
    
    def _stock_list_to_dataframe(self, stock_data_list):
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
    
    @log_function_call
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
        获取股票数据及技术指标
        
        Args:
            stock_code: 股票代码
            period: 时间周期（如 1d, 1h, 1w, 1M）
            start_date: 开始日期
            end_date: 结束日期
            limit: 返回数据条数限制
            auto_save: 是否自动保存计算结果到数据库
        
        Returns:
            Dict: 包含股票数据和缺失范围信息
        """
        logger.info(f"开始获取股票指标数据: stock_code={stock_code}, period={period}, start_date={start_date}, end_date={end_date}, limit={limit}")
        
        from app.models.stock_data import StockData
        from sqlalchemy import desc
        from datetime import datetime, timedelta

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
        return TechnicalIndicators.calculate_all_indicators(df)
    
    def calculate_indicators_for_df(self, df: pd.DataFrame) -> pd.DataFrame:
        return TechnicalIndicators.calculate_all_indicators(df)
    
    def get_kdj_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
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
        """检测数据中的缺失范围"""
        from datetime import timedelta
        from datetime import date
        
        logger.debug(f"开始检测缺失数据范围: 请求范围 {req_start.date()} ~ {req_end.date()}, 数据条数={len(stock_data_list) if stock_data_list else 0}")
        
        missing_ranges = []
        
        if not stock_data_list:
            logger.info(f"数据列表为空，整个范围缺失: {req_start.date()} ~ {req_end.date()}")
            # 如果完全没有数据，整个范围都缺失
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
        
        # 检查请求范围内的每一天是否存在
        current_date = req_start.date()
        while current_date <= req_end.date():
            # 检查当前日期是否在未来，如果是则跳过（因为无法获取未来数据）
            if current_date > date.today():
                logger.debug(f"跳过未来日期: {current_date}")
                current_date += timedelta(days=1)
                continue
                
            if current_date not in existing_dates:
                logger.debug(f"检测到缺失日期: {current_date}")
                # 找到缺失的起始日期，继续找到连续缺失的结束日期
                missing_start = current_date
                
                # 查找连续缺失的日期范围，跳过未来的日期
                while current_date <= req_end.date() and current_date not in existing_dates:
                    if current_date > date.today():
                        # 如果遇到未来日期，停止在这个缺失段的查找
                        break
                    current_date += timedelta(days=1)
                
                if missing_start < current_date:  # 确保我们找到了至少一个非未来的缺失日期
                    missing_end = min(current_date - timedelta(days=1), date.today())
                    
                    # 只有当缺失范围在今天或之前时才添加
                    if missing_start <= date.today():
                        missing_range = {
                            "start": missing_start.strftime("%Y-%m-%d"),
                            "end": missing_end.strftime("%Y-%m-%d")
                        }
                        missing_ranges.append(missing_range)
                        logger.info(f"检测到缺失范围: {missing_range['start']} ~ {missing_range['end']}")
                
                # 如果刚好到达循环条件，跳出循环
                if current_date > req_end.date():
                    break
            else:
                current_date += timedelta(days=1)
        
        logger.debug(f"缺失范围检测完成，总计 {len(missing_ranges)} 个范围: {missing_ranges}")
        return missing_ranges
    
    def _merge_overlapping_ranges(self, ranges):
        """合并重叠的日期范围"""
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
        kdj_signals = self.get_kdj_signals(df)
        macd_signals = self.get_macd_signals(df)
        return kdj_signals + macd_signals