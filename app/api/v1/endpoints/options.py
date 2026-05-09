from fastapi import APIRouter, HTTPException
from typing import Optional
from app.schemas.option import OptionChainData
from app.crawlers.option_crawler import OptionCrawler

router = APIRouter()


@router.get("/chain/{stock_code}", response_model=OptionChainData)
def get_option_chain(
    stock_code: str,
    expire_date: Optional[str] = None
):
    """
    获取期权链数据
    
    - stock_code: 标的股票代码
    - expire_date: 可选，指定到期日，格式 YYYY-MM
    """
    try:
        crawler = OptionCrawler()
        option_chain = crawler.fetch_option_chain(stock_code)
        
        # 如果指定了到期日，只返回该到期日的数据
        if expire_date:
            filtered_calls = [
                opt for opt in option_chain.calls 
                if opt.expire_date == expire_date
            ]
            filtered_puts = [
                opt for opt in option_chain.puts 
                if opt.expire_date == expire_date
            ]
            option_chain.calls = filtered_calls
            option_chain.puts = filtered_puts
        
        return option_chain
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取期权数据失败: {str(e)}"
        )


@router.get("/chain/{stock_code}/summary")
def get_option_summary(stock_code: str):
    """
    获取期权摘要数据（多空统计等）
    """
    try:
        crawler = OptionCrawler()
        option_chain = crawler.fetch_option_chain(stock_code)
        
        # 计算多空统计
        total_call_volume = sum(opt.volume or 0 for opt in option_chain.calls)
        total_put_volume = sum(opt.volume or 0 for opt in option_chain.puts)
        total_call_oi = sum(opt.open_interest or 0 for opt in option_chain.calls)
        total_put_oi = sum(opt.open_interest or 0 for opt in option_chain.puts)
        
        # 计算最大痛点
        strike_oi = {}
        for opt in option_chain.calls + option_chain.puts:
            strike = opt.strike_price
            if strike not in strike_oi:
                strike_oi[strike] = 0
            strike_oi[strike] += opt.open_interest or 0
        
        max_pain_strike = max(strike_oi.items(), key=lambda x: x[1])[0] if strike_oi else None
        
        return {
            "stock_code": stock_code,
            "stock_price": option_chain.stock_price,
            "total_call_volume": total_call_volume,
            "total_put_volume": total_put_volume,
            "call_put_volume_ratio": round(total_call_volume / total_put_volume, 2) if total_put_volume > 0 else 0,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "call_put_oi_ratio": round(total_call_oi / total_put_oi, 2) if total_put_oi > 0 else 0,
            "max_pain_strike": max_pain_strike,
            "update_time": option_chain.update_time
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"获取期权摘要失败: {str(e)}"
        )
