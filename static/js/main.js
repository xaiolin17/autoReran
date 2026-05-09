document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('fetchBtn').addEventListener('click', loadData);
    document.getElementById('generateBtn').addEventListener('click', generateSampleData);
}

async function loadData() {
    const stockCode = document.getElementById('stockCode').value;
    try {
        const response = await fetch(`/api/v1/indicators/${stockCode}`);
        const data = await response.json();
        if (data && data.length > 0) {
            updateCharts(data);
            loadSignals(stockCode);
        } else {
            alert('暂无数据，请先生成示例数据');
        }
    } catch (error) {
        console.error('加载数据失败:', error);
    }
}

async function generateSampleData() {
    const stockCode = document.getElementById('stockCode').value;
    try {
        const response = await fetch(`/api/v1/sample/generate/${stockCode}`, { method: 'POST' });
        const result = await response.json();
        alert(result.message);
        loadData();
    } catch (error) {
        console.error('生成数据失败:', error);
    }
}

async function loadSignals(stockCode) {
    try {
        const response = await fetch(`/api/v1/indicators/signals/${stockCode}`);
        const result = await response.json();
        displaySignals(result.signals);
    } catch (error) {
        console.error('加载信号失败:', error);
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
        </div>
    `).join('');
}
