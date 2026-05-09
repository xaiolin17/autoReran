document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('fetchBtn').addEventListener('click', loadData);
    document.getElementById('generateBtn').addEventListener('click', generateSampleData);
}

function showLoading(show = true) {
    const chartsContainer = document.querySelector('.charts-container');
    const signalsContainer = document.getElementById('signalsContainer');
    
    if (show) {
        chartsContainer.style.opacity = '0.3';
        chartsContainer.style.pointerEvents = 'none';
        signalsContainer.innerHTML = `
            <div style="text-align: center; padding: 60px 20px;">
                <div style="display: inline-block; width: 50px; height: 50px; border: 4px solid rgba(0,240,255,0.2); border-top: 4px solid #00f0ff; border-radius: 50%; animation: spin 1s linear infinite;"></div>
                <p style="margin-top: 20px; color: #94a3b8;">正在加载数据...</p>
            </div>
        `;
    } else {
        chartsContainer.style.opacity = '1';
        chartsContainer.style.pointerEvents = 'auto';
    }
}

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

async function loadData() {
    const stockCode = document.getElementById('stockCode').value.trim();
    
    if (!stockCode) {
        showMessage('请先输入股票代码！', 'warning');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`/api/v1/indicators/${stockCode}`);
        const data = await response.json();
        
        if (data && data.length > 0) {
            updateCharts(data);
            loadSignals(stockCode);
            showMessage(`成功加载 ${data.length} 条数据！`, 'success');
        } else {
            showMessage('暂无数据，请先生成示例数据', 'warning');
            document.getElementById('signalsContainer').innerHTML = `
                <div class="empty-state">
                    <span class="empty-state-icon">📊</span>
                    <p>该股票暂无数据，<strong>先生成示例数据</strong>开始体验！</p>
                    <span class="empty-state-action" onclick="generateSampleData()">立即生成示例数据</span>
                </div>
            `;
        }
    } catch (error) {
        console.error('加载数据失败:', error);
        showMessage('加载数据失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function generateSampleData() {
    const stockCode = document.getElementById('stockCode').value.trim();
    
    if (!stockCode) {
        showMessage('请先输入股票代码！', 'warning');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`/api/v1/sample/generate/${stockCode}`, { method: 'POST' });
        const result = await response.json();
        
        if (result.success) {
            showMessage(result.message || '示例数据生成成功！', 'success');
            loadData();
        } else {
            showMessage(result.message || '生成数据失败', 'error');
        }
    } catch (error) {
        console.error('生成数据失败:', error);
        showMessage('生成数据失败: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

async function loadSignals(stockCode) {
    try {
        const response = await fetch(`/api/v1/indicators/signals/${stockCode}`);
        const result = await response.json();
        displaySignals(result.signals);
    } catch (error) {
        console.error('加载信号失败:', error);
        document.getElementById('signalsContainer').innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">⚠️</span>
                <p>加载信号失败，请刷新重试</p>
            </div>
        `;
    }
}

function displaySignals(signals) {
    const container = document.getElementById('signalsContainer');
    
    if (!signals || signals.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">📊</span>
                <p>暂无交易信号，继续观察市场变化</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = signals.map(signal => `
        <div class="signal-card ${signal.type}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <strong style="font-size: 18px;">${signal.type === 'buy' ? '📈 买入信号' : '📉 卖出信号'}</strong>
                <span style="color: #94a3b8; font-size: 13px;">${signal.indicator}</span>
            </div>
            <p style="font-size: 16px; margin-bottom: 8px;">价格: <strong style="color: ${signal.type === 'buy' ? '#10b981' : '#ef4444'};">¥${signal.price.toFixed(2)}</strong></p>
            <p style="color: #94a3b8; font-size: 13px; line-height: 1.6;">${signal.reason}</p>
            <p style="color: #64748b; font-size: 12px; margin-top: 12px;">${signal.datetime}</p>
        </div>
    `).join('');
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
    .signal-card {
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    }
    .signal-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 32px rgba(0,0,0,0.2);
    }
`;
document.head.appendChild(style);
