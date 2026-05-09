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
        chartsContainer.style.opacity = '0.5';
        chartsContainer.style.pointerEvents = 'none';
        signalsContainer.style.opacity = '0.5';
        signalsContainer.style.pointerEvents = 'none';
        
        const loader = document.createElement('div');
        loader.id = 'loader';
        loader.innerHTML = '<div style="text-align: center; padding: 40px;"><div style="display: inline-block; width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; animation: spin 1s linear infinite;"></div><p style="margin-top: 10px;">加载中...</p></div>';
        signalsContainer.innerHTML = '';
        signalsContainer.appendChild(loader);
    } else {
        chartsContainer.style.opacity = '1';
        chartsContainer.style.pointerEvents = 'auto';
        signalsContainer.style.opacity = '1';
        signalsContainer.style.pointerEvents = 'auto';
        const loader = document.getElementById('loader');
        if (loader) loader.remove();
    }
}

function showMessage(message, type = 'info') {
    const colors = {
        info: '#3498db',
        success: '#2ecc71',
        error: '#e74c3c',
        warning: '#f39c12'
    };
    
    const msgDiv = document.createElement('div');
    msgDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        background: ${colors[type]};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1000;
        animation: slideIn 0.3s ease;
    `;
    msgDiv.textContent = message;
    document.body.appendChild(msgDiv);
    
    setTimeout(() => {
        msgDiv.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => msgDiv.remove(), 300);
    }, 3000);
}

async function loadData() {
    const stockCode = document.getElementById('stockCode').value.trim();
    
    if (!stockCode) {
        showMessage('请输入股票代码', 'warning');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`/api/v1/indicators/${stockCode}`);
        const data = await response.json();
        
        if (data && data.length > 0) {
            updateCharts(data);
            loadSignals(stockCode);
            showMessage('数据加载成功', 'success');
        } else {
            showMessage('暂无数据，请先生成示例数据', 'warning');
            document.getElementById('signalsContainer').innerHTML = '<p class="empty-state">暂无交易信号</p>';
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
        showMessage('请输入股票代码', 'warning');
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`/api/v1/sample/generate/${stockCode}`, { method: 'POST' });
        const result = await response.json();
        
        if (result.success) {
            showMessage(result.message, 'success');
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
        document.getElementById('signalsContainer').innerHTML = '<p class="empty-state">加载信号失败</p>';
    }
}

function displaySignals(signals) {
    const container = document.getElementById('signalsContainer');
    
    if (!signals || signals.length === 0) {
        container.innerHTML = '<p class="empty-state">暂无交易信号</p>';
        return;
    }
    
    container.innerHTML = signals.map(signal => `
        <div class="signal-card ${signal.type}">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                <strong>${signal.type === 'buy' ? '📈 买入' : '📉 卖出'}</strong>
                <span style="color: #a0aec0;">${signal.indicator}</span>
            </div>
            <p>价格: ${signal.price.toFixed(2)}</p>
            <p style="color: #a0aec0; font-size: 12px;">${signal.reason}</p>
            <p style="color: #718096; font-size: 11px; margin-top: 8px;">${signal.datetime}</p>
        </div>
    `).join('');
}

const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    .signal-card {
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .signal-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    button {
        transition: all 0.2s ease;
    }
    button:hover {
        transform: translateY(-1px);
    }
    button:active {
        transform: translateY(0);
    }
`;
document.head.appendChild(style);
