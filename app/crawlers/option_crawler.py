import requests
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from app.schemas.option import OptionData, OptionChainData


class OptionCrawler:
    """期权数据爬虫 - 模拟实现（实际项目中需要接入真实数据源）"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_option_chain(self, stock_code: str) -> OptionChainData:
        """
        获取期权链数据
        注意：这是模拟实现，实际项目中需要接入真实数据源
        """
        try:
            # 生成模拟期权数据
            stock_price = self._get_stock_price(stock_code)
            expire_dates = self._generate_expire_dates()
            
            calls = []
            puts = []
            
            # 生成行权价（围绕当前股价）
            strike_prices = self._generate_strike_prices(stock_price)
            
            for expire_date in expire_dates:
                for strike in strike_prices:
                    # 生成看涨期权
                    call_data = self._generate_option_data(
                        stock_code, stock_price, strike, expire_date, 'call'
                    )
                    calls.append(call_data)
                    
                    # 生成看跌期权
                    put_data = self._generate_option_data(
                        stock_code, stock_price, strike, expire_date, 'put'
                    )
                    puts.append(put_data)
            
            return OptionChainData(
                stock_code=stock_code,
                stock_price=stock_price,
                expire_dates=expire_dates,
                calls=calls,
                puts=puts,
                update_time=datetime.now()
            )
            
        except Exception as e:
            print(f"获取期权链数据错误: {e}")
            # 即使出错也返回模拟数据
            return self._get_demo_option_chain(stock_code)
    
    def _get_stock_price(self, stock_code: str) -> float:
        """模拟获取标的价格"""
        base_prices = {
            '510300': 3.8,  # 沪深300ETF
            '510500': 6.2,  # 中证500ETF
            'SAMPLE': 50.0,
            'sh600000': 8.5,
            'sz000001': 12.3
        }
        base = base_prices.get(stock_code, 10.0)
        # 添加随机波动
        return round(base * (1 + (random.random() - 0.5) * 0.02), 2)
    
    def _generate_expire_dates(self) -> List[str]:
        """生成到期日"""
        dates = []
        today = datetime.now()
        # 生成接下来4个月的到期日
        for i in range(1, 5):
            month_day = today.replace(day=1) + timedelta(days=30 * i)
            # 期权通常是月的第4个星期三
            # 这里简化为当月的25号左右
            expire_date = month_day.replace(day=25).strftime('%Y-%m')
            dates.append(expire_date)
        return dates
    
    def _generate_strike_prices(self, stock_price: float) -> List[float]:
        """生成行权价"""
        strikes = []
        # 确定行权价间距
        interval = 0.1 if stock_price < 5 else 0.5 if stock_price < 50 else 2.0
        
        # 生成围绕当前价格的行权价
        start = stock_price - interval * 4
        for i in range(9):
            strike = round(start + interval * i, 2)
            if strike > 0:
                strikes.append(strike)
        return strikes
    
    def _generate_option_data(
        self, 
        stock_code: str, 
        stock_price: float, 
        strike_price: float, 
        expire_date: str, 
        option_type: str
    ) -> OptionData:
        """生成单个期权数据"""
        # 计算期权基本价值（简化的Black-Scholes模型模拟）
        moneyness = stock_price / strike_price
        
        # 根据实值/虚值程度计算价格
        if option_type == 'call':
            intrinsic_value = max(stock_price - strike_price, 0)
        else:
            intrinsic_value = max(strike_price - stock_price, 0)
        
        # 时间价值
        time_value = max(0.1, abs(stock_price - strike_price) * 0.15)
        option_price = round(intrinsic_value + time_value, 2)
        
        # 买卖价差
        spread = max(0.01, option_price * 0.02)
        bid_price = round(option_price - spread / 2, 2)
        ask_price = round(option_price + spread / 2, 2)
        
        # 成交量和持仓量
        volume = random.randint(100, 10000)
        open_interest = random.randint(5000, 50000)
        
        # 多空量
        bid_volume = random.randint(10, 500)
        ask_volume = random.randint(10, 500)
        
        # 希腊字母
        delta = self._calculate_delta(stock_price, strike_price, option_type)
        gamma = round(random.uniform(0.001, 0.05), 4)
        theta = round(-random.uniform(0.01, 0.1), 4)
        vega = round(random.uniform(0.1, 0.5), 4)
        
        # 隐含波动率
        iv = round(0.15 + random.random() * 0.2, 4)
        
        # 涨跌幅
        change_percent = round((random.random() - 0.5) * 10, 2)
        
        option_code = self._generate_option_code(stock_code, expire_date, strike_price, option_type)
        
        return OptionData(
            option_code=option_code,
            stock_code=stock_code,
            strike_price=strike_price,
            expire_date=expire_date,
            option_type=option_type,
            latest_price=option_price,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            volume=volume,
            open_interest=open_interest,
            change_percent=change_percent,
            implied_volatility=iv,
            delta=delta,
            theta=theta,
            gamma=gamma,
            vega=vega,
            update_time=datetime.now()
        )
    
    def _calculate_delta(self, stock_price: float, strike_price: float, option_type: str) -> float:
        """计算Delta（模拟）"""
        moneyness = stock_price / strike_price
        
        if option_type == 'call':
            if moneyness > 1.05:
                delta = 0.9 + random.random() * 0.1
            elif moneyness > 0.95:
                delta = 0.3 + random.random() * 0.4
            else:
                delta = random.random() * 0.2
        else:
            if moneyness < 0.95:
                delta = -0.9 - random.random() * 0.1
            elif moneyness < 1.05:
                delta = -0.3 - random.random() * 0.4
            else:
                delta = -random.random() * 0.2
        
        return round(delta, 4)
    
    def _generate_option_code(
        self, 
        stock_code: str, 
        expire_date: str, 
        strike_price: float, 
        option_type: str
    ) -> str:
        """生成期权代码"""
        type_code = 'C' if option_type == 'call' else 'P'
        strike_str = str(int(strike_price * 1000)).zfill(8)
        expire_str = expire_date.replace('-', '')[2:]  # 取后四位
        return f"{stock_code}{expire_str}{type_code}{strike_str}"
    
    def _get_demo_option_chain(self, stock_code: str) -> OptionChainData:
        """获取演示用的期权链数据"""
        stock_price = 50.0
        expire_dates = ['2026-06', '2026-07', '2026-08', '2026-09']
        calls = []
        puts = []
        
        strikes = [44.0, 46.0, 48.0, 50.0, 52.0, 54.0, 56.0]
        
        for expire in expire_dates:
            for strike in strikes:
                calls.append(self._generate_option_data(stock_code, stock_price, strike, expire, 'call'))
                puts.append(self._generate_option_data(stock_code, stock_price, strike, expire, 'put'))
        
        return OptionChainData(
            stock_code=stock_code,
            stock_price=stock_price,
            expire_dates=expire_dates,
            calls=calls,
            puts=puts,
            update_time=datetime.now()
        )
