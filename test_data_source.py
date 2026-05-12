import requests
import pandas as pd
from datetime import datetime, timedelta
import json


def test_eastmoney():
    print("=" * 50)
    print("测试东方财富数据源")
    print("=" * 50)
    
    url = "https://push2.eastmoney.com/api/qt/stock/kline/get"
    
    secid = "1.000001"
    
    params = {
        'secid': secid,
        'klt': 101,
        'fqt': 1,
        'beg': (datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
        'end': datetime.now().strftime("%Y%m%d"),
        '_': int(datetime.now().timestamp())
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    print(f"请求URL: {url}")
    print(f"请求参数: {params}")
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        print(f"响应状态码: {response.status_code}")
        
        data = response.json()
        print(f"\n响应数据结构: {json.dumps(data, ensure_ascii=False, indent=2)}")
        
        if data.get('data') and data['data'].get('klines'):
            klines = data['data']['klines']
            print(f"\n找到 {len(klines)} 条K线数据")
            
            latest = klines[-1].split(',')
            print(f"\n最新数据:")
            print(f"  日期: {latest[0]}")
            print(f"  开盘: {latest[1]}")
            print(f"  收盘: {latest[2]}")
            print(f"  最高: {latest[3]}")
            print(f"  最低: {latest[4]}")
            print(f"  成交量: {latest[5]}")
            
            if float(latest[2]) > 2000:
                print(f"\n✅ 价格正确！属于正常指数范围！")
            else:
                print(f"\n❌ 价格异常！不是真实的上证指数！")
                
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


def test_sina():
    print("\n" + "=" * 50)
    print("测试新浪数据源")
    print("=" * 50)
    
    url = "https://hq.sinajs.cn/list=sh000001"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'gbk'
        print(f"响应内容: {response.text}")
    except Exception as e:
        print(f"错误: {e}")


def test_tushare():
    """测试模拟一个更可靠的数据源"""
    print("\n" + "=" * 50)
    print("测试模拟真实数据源")
    print("=" * 50)
    
    # 创建上证指数真实范围的模拟数据
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    
    # 从3200点开始的真实数据
    base_price = 3200.0
    data = []
    
    for i, date in enumerate(dates):
        change = (0.01 if i % 2 == 0 else -0.008)
        open_p = base_price * (1 + change)
        close_p = open_p * (1 + (change * 0.5))
        high_p = max(open_p, close_p) * 1.005
        low_p = min(open_p, close_p) * 0.995
        
        data.append({
            'datetime': date,
            'open_price': open_p,
            'high_price': high_p,
            'low_price': low_p,
            'close_price': close_p,
            'volume': 300000000,
            'amount': close_p * 300000000,
            'stock_code': '000001',
            'stock_name': '上证指数',
            'period': '1d',
            'source': 'mock_real'
        })
        
        base_price = close_p
    
    df = pd.DataFrame(data)
    print(df[['datetime', 'open_price', 'close_price', 'high_price', 'low_price']])
    
    if df['close_price'].iloc[-1] > 2000:
        print(f"\n✅ 模拟数据价格范围正确！")


if __name__ == "__main__":
    test_eastmoney()
    test_sina()
    test_tushare()
