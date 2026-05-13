document.addEventListener('DOMContentLoaded', () => {
    loadBacktests();
    loadMLModels();
    setupEventListeners();
    setDefaultDates();
});

function showMessage(message, type = 'info') {
    const msgDiv = document.createElement('div');
    msgDiv.style.cssText = `
        position: fixed;
        top: 24px;
        right: 24px;
        padding: 16px 24px;
        background: ${type === 'success' ? 'linear-gradient(135deg, rgba(16,185,129,0.95), rgba(16,185,129,0.85))' : 
                   type === 'error' ? 'linear-gradient(135deg, rgba(239,68,68,0.95), rgba(239,68,68,0.85))' : 
                   type === 'warning' ? 'linear-gradient(135deg, rgba(245,158,11,0.95), rgba(245,158,11,0.85))' :
                   'linear-gradient(135deg, rgba(0,240,255,0.95), rgba(139,92,246,0.85))'};
        color: white;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        z-index: 1000;
        animation: slideInRight 0.4s cubic-bezier(0.4,0,0.2,1);
        font-weight: 500;
        max-width: 400px;
    `;
    msgDiv.textContent = message;
    document.body.appendChild(msgDiv);
    
    setTimeout(() => {
        msgDiv.style.animation = 'slideOutRight 0.4s cubic-bezier(0.4,0,0.2,1)';
        setTimeout(() => msgDiv.remove(), 400);
    }, 3500);
}

function setupEventListeners() {
    document.getElementById('backtestForm').addEventListener('submit', runBacktest);
    document.getElementById('strategyName').addEventListener('change', handleStrategyTypeChange);
}

function handleStrategyTypeChange() {
    const strategyType = document.getElementById('strategyName').value;
    const mlModelGroup = document.getElementById('mlModelGroup');
    const noModelsMessage = document.getElementById('noModelsMessage');
    
    if (strategyType === 'ML') {
        mlModelGroup.style.display = 'block';
    } else {
        mlModelGroup.style.display = 'none';
        noModelsMessage.style.display = 'none';
    }
}

async function loadMLModels() {
    try {
        const response = await fetch('/api/v1/ml/models');
        const models = await response.json();
        updateMLModelSelect(models);
    } catch (error) {
        console.error('加载模型失败:', error);
    }
}

function updateMLModelSelect(models) {
    const select = document.getElementById('mlModelSelect');
    const noModelsMessage = document.getElementById('noModelsMessage');
    
    select.innerHTML = '<option value="">-- 请选择模型 --</option>';
    
    if (!models || models.length === 0) {
        const strategyType = document.getElementById('strategyName').value;
        if (strategyType === 'ML') {
            noModelsMessage.style.display = 'block';
        }
        return;
    }
    
    noModelsMessage.style.display = 'none';
    models.forEach(model => {
        select.innerHTML += `<option value="${model.id}">${model.model_name} (${model.stock_code})</option>`;
    });
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
    
    const stockCode = document.getElementById('backtestStockCode').value.trim();
    const strategyName = document.getElementById('strategyName').value;
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    const initialCapital = parseFloat(document.getElementById('initialCapital').value);
    
    if (!stockCode) {
        showMessage('请输入股票代码！', 'warning');
        return;
    }
    
    if (!startDate || !endDate) {
        showMessage('请选择日期范围！', 'warning');
        return;
    }
    
    const statusDiv = document.getElementById('backtestStatus');
    statusDiv.style.display = 'block';
    statusDiv.className = 'status-message info';
    statusDiv.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 20px; height: 20px; border: 3px solid rgba(0,240,255,0.2); border-top: 3px solid #00f0ff; border-radius: 50%; animation: spin 1s linear infinite;"></div>
            <span>正在运行回测，请稍候...</span>
        </div>
    `;
    
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
            statusDiv.innerHTML = `
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 20px;">✅</span>
                    <span>回测完成！收益: <strong>${(result.total_return * 100).toFixed(2)}%</strong></span>
                </div>
            `;
            showMessage('回测完成！', 'success');
            loadBacktests();
            displayBacktestResult(result);
        } else {
            const error = await response.json();
            statusDiv.className = 'status-message error';
            statusDiv.innerHTML = `
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 20px;">❌</span>
                    <span>${error.detail || '回测失败，请确保已有该股票数据'}</span>
                </div>
            `;
            showMessage(error.detail || '回测失败', 'error');
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 20px;">❌</span>
                <span>回测失败: ${error.message}</span>
            </div>
        `;
        showMessage('回测失败: ' + error.message, 'error');
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
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">📈</span>
                <p>还没有回测结果，<strong>先在左侧配置并运行回测</strong>！</p>
                <p style="font-size: 13px; color: #64748b; margin-top: 8px;">💡 提示：先确保已有该股票数据</p>
            </div>
        `;
        return;
    }

    container.innerHTML = backtests.map(bt => `
        <div class="model-item">
            <div class="model-info">
                <h4>${bt.strategy_name} - ${bt.stock_code}</h4>
                <p>收益: <strong style="color: ${bt.total_return >= 0 ? '#10b981' : '#ef4444'};">${(bt.total_return * 100).toFixed(2)}%</strong> | 回撤: ${(bt.max_drawdown * 100).toFixed(2)}%</p>
                <p>时间: ${new Date(bt.created_at).toLocaleDateString()}</p>
            </div>
            <div style="display: flex; gap: 10px;">
                <button class="btn btn-secondary" onclick="viewBacktest(${bt.id})">查看</button>
                <button class="btn btn-danger" onclick="deleteBacktest(${bt.id})">删除</button>
            </div>
        </div>
    `).join('');
}

async function viewBacktest(id) {
    try {
        const response = await fetch(`/api/v1/backtest/results/${id}`);
        const result = await response.json();
        displayBacktestResult(result);
        showMessage('回测详情已加载', 'success');
    } catch (error) {
        console.error('加载回测详情失败:', error);
        showMessage('加载失败', 'error');
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
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">📝</span>
                <p>暂无交易记录</p>
            </div>
        `;
        return;
    }

    container.innerHTML = tradeLog.map(trade => `
        <div class="trade-item ${trade.action}">
            <div>
                <strong>${trade.action === 'buy' ? '📈 买入' : '📉 卖出'}</strong>
                <span style="color: #94a3b8; font-size: 12px;">${trade.datetime}</span>
            </div>
            <div style="text-align: right;">
                <p>¥${trade.price.toFixed(2)} | ${trade.shares}股</p>
                ${trade.profit !== undefined ? `<p style="color: ${trade.profit >= 0 ? '#10b981' : '#ef4444'}; font-weight: 600;">${trade.profit >= 0 ? '+' : ''}¥${trade.profit.toFixed(2)}</p>` : ''}
            </div>
        </div>
    `).join('');
}

async function deleteBacktest(id) {
    if (!confirm('确定要删除这个回测结果吗？')) return;
    
    try {
        await fetch(`/api/v1/backtest/results/${id}`, { method: 'DELETE' });
        showMessage('回测结果已删除', 'success');
        loadBacktests();
        document.getElementById('backtestResultDetail').style.display = 'none';
    } catch (error) {
        console.error('删除回测结果失败:', error);
        showMessage('删除失败', 'error');
    }
}

const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    @keyframes slideInRight {
        from { transform: translateX(100px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100px); opacity: 0; }
    }
`;
document.head.appendChild(style);
