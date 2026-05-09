document.addEventListener('DOMContentLoaded', () => {
    loadBacktests();
    setupEventListeners();
    setDefaultDates();
});

function setupEventListeners() {
    document.getElementById('backtestForm').addEventListener('submit', runBacktest);
}

function setDefaultDates() {
    const endDate = new Date();
    const startDate = new Date();
    startDate.setMonth(startDate.getMonth() - 6);
    
    document.getElementById('startDate').value = startDate.toISOString().split('T')[0];
    document.getElementById('endDate').value = endDate.toISOString().split('T')[0];
}

async function runBacktest(e) {
    e.preventDefault();
    
    const stockCode = document.getElementById('backtestStockCode').value;
    const strategyName = document.getElementById('strategyName').value;
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    const initialCapital = parseFloat(document.getElementById('initialCapital').value);
    
    const statusDiv = document.getElementById('backtestStatus');
    statusDiv.style.display = 'block';
    statusDiv.className = 'status-message';
    statusDiv.textContent = '回测中...';
    
    try {
        const response = await fetch('/api/v1/backtest/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stock_code: stockCode,
                strategy_name: strategyName,
                start_date: startDate,
                end_date: endDate,
                initial_capital: initialCapital
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            statusDiv.className = 'status-message success';
            statusDiv.textContent = '回测完成！';
            loadBacktests();
            displayBacktestResult(result);
        } else {
            const error = await response.json();
            statusDiv.className = 'status-message error';
            statusDiv.textContent = error.detail || '回测失败';
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = '回测失败: ' + error.message;
    }
}

async function loadBacktests() {
    try {
        const response = await fetch('/api/v1/backtest/results');
        const backtests = await response.json();
        displayBacktests(backtests);
    } catch (error) {
        console.error('加载回测结果失败:', error);
    }
}

function displayBacktests(backtests) {
    const container = document.getElementById('backtestsList');
    if (!backtests || backtests.length === 0) {
        container.innerHTML = '<p class="empty-state">暂无回测结果</p>';
        return;
    }

    container.innerHTML = backtests.map(bt => `
        <div class="model-item" onclick="viewBacktest(${bt.id})" style="cursor: pointer;">
            <div class="model-info">
                <h4>${bt.strategy_name} - ${bt.stock_code}</h4>
                <p>收益: ${(bt.total_return * 100).toFixed(2)}% | 回撤: ${(bt.max_drawdown * 100).toFixed(2)}%</p>
                <p>时间: ${new Date(bt.created_at).toLocaleDateString()}</p>
            </div>
            <button class="btn btn-danger" onclick="event.stopPropagation(); deleteBacktest(${bt.id})">删除</button>
        </div>
    `).join('');
}

async function viewBacktest(id) {
    try {
        const response = await fetch(`/api/v1/backtest/results/${id}`);
        const result = await response.json();
        displayBacktestResult(result);
    } catch (error) {
        console.error('加载回测详情失败:', error);
    }
}

function displayBacktestResult(result) {
    const detailDiv = document.getElementById('backtestResultDetail');
    detailDiv.style.display = 'block';
    
    document.getElementById('totalReturn').textContent = `${(result.total_return * 100).toFixed(2)}%`;
    document.getElementById('annualReturn').textContent = `${(result.annual_return * 100).toFixed(2)}%`;
    document.getElementById('maxDrawdown').textContent = `${(result.max_drawdown * 100).toFixed(2)}%`;
    document.getElementById('winRate').textContent = `${(result.win_rate * 100).toFixed(2)}%`;
    document.getElementById('totalTrades').textContent = result.total_trades;
    document.getElementById('finalCapital').textContent = `¥${result.final_capital.toFixed(2)}`;
    
    displayTradeLog(result.trade_log);
}

function displayTradeLog(tradeLog) {
    const container = document.getElementById('tradeLog');
    if (!tradeLog || tradeLog.length === 0) {
        container.innerHTML = '<p class="empty-state">暂无交易记录</p>';
        return;
    }

    container.innerHTML = tradeLog.map(trade => `
        <div class="trade-item ${trade.action}">
            <div>
                <strong>${trade.action === 'buy' ? '买入' : '卖出'}</strong>
                <span style="color: #a0aec0; font-size: 12px;">${trade.datetime}</span>
            </div>
            <div style="text-align: right;">
                <p>¥${trade.price.toFixed(2)} | ${trade.shares}股</p>
                ${trade.profit !== undefined ? `<p style="color: ${trade.profit >= 0 ? '#00ff88' : '#ff6b6b'}">${trade.profit >= 0 ? '+' : ''}¥${trade.profit.toFixed(2)}</p>` : ''}
            </div>
        </div>
    `).join('');
}

async function deleteBacktest(id) {
    if (!confirm('确定要删除这个回测结果吗？')) return;
    
    try {
        await fetch(`/api/v1/backtest/results/${id}`, { method: 'DELETE' });
        loadBacktests();
        document.getElementById('backtestResultDetail').style.display = 'none';
    } catch (error) {
        console.error('删除回测结果失败:', error);
    }
}
