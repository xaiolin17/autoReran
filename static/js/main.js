let optionRatioChart = null;
let currentOptionData = null;
let wsConnection = null;
let dataCache = new Map();
let CACHE_TTL = 30000;

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    initWebSocket();
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    const fetchBtn = document.getElementById('fetchBtn');
    if (fetchBtn) {
        fetchBtn.addEventListener('click', debounce(loadData, 300));
    }
}

function debounce(func, wait) {
    let timeout;
    return function(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function initWebSocket() {
    const clientId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${clientId}`;
    
    wsConnection = new WebSocket(wsUrl);
    
    wsConnection.onopen = () => {
        console.log('WebSocket连接已建立');
        wsConnection.send(JSON.stringify({
            type: 'subscribe',
            channel: 'realtime'
        }));
    };
    
    wsConnection.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('解析WebSocket消息失败:', e);
        }
    };
    
    wsConnection.onclose = () => {
        console.log('WebSocket连接已关闭，尝试重新连接...');
        setTimeout(initWebSocket, 3000);
    };
    
    wsConnection.onerror = (error) => {
        console.error('WebSocket连接错误:', error);
    };
}

function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'pong':
            break;
        case 'subscribed':
            console.log('已订阅频道:', message.channel);
            break;
        case 'refresh_needed':
            break;
    }
}

function safeFetch(url, options = {}) {
    const cacheKey = `${options.method || 'GET'}_${url}`;
    const cached = getCachedData(cacheKey);
    if (cached && !options.skipCache) {
        return Promise.resolve(cached);
    }
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000);
    
    return fetch(url, {
        ...options,
        signal: controller.signal
    }).then(response => {
        clearTimeout(timeoutId);
        if (!response.ok) {
            console.warn(`请求 ${url} 返回 ${response.status}，继续尝试获取已有数据`);
            return null;
        }
        return response.text().then(text => {
            try {
                const data = JSON.parse(text);
                setCachedData(cacheKey, data);
                return data;
            } catch (e) {
                console.warn(`响应不是有效的JSON: ${text}`);
                return null;
            }
        });
    }).catch(error => {
        console.warn(`请求失败: ${error}`);
        return null;
    });
}

function getCachedData(key) {
    const cached = dataCache.get(key);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        return cached.data;
    }
    dataCache.delete(key);
    return null;
}

function setCachedData(key, data) {
    dataCache.set(key, { data, timestamp: Date.now() });
}

function showMessage(message, type = 'info') {
    const msgDiv = document.createElement('div');
    msgDiv.style.cssText = `
        position: fixed;
        top: 24px;
        right: 24px;
        padding: 16px 24px;
        background: ${type === 'success' ? 'linear-gradient(135deg, rgba(34, 197, 94, 0.95), rgba(34, 197, 94, 0.85))' : 
                    type === 'error' ? 'linear-gradient(135deg, rgba(239, 68, 68, 0.95), rgba(239, 68, 68, 0.85))' : 
                    type === 'warning' ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.95), rgba(245, 158, 11, 0.85))' :
                    'linear-gradient(135deg, rgba(6, 182, 212, 0.95), rgba(139, 92, 246, 0.85))'};
        color: white;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        z-index: 1000;
        font-weight: 500;
        max-width: 400px;
        animation: slideIn 0.4s ease;
    `;
    msgDiv.textContent = message;
    document.body.appendChild(msgDiv);
    
    setTimeout(() => {
        msgDiv.style.animation = 'slideOut 0.4s ease';
        setTimeout(() => msgDiv.remove(), 400);
    }, 3500);
}

let priceChart, volumeChart, kdjChart, macdChart;

function initCharts() {
    const priceCtx = document.getElementById('priceChart');
    if (priceCtx) {
        priceChart = new Chart(priceCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: '收盘价',
                    data: [],
                    borderColor: '#06b6d4',
                    backgroundColor: 'rgba(6, 182, 212, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    }
                }
            }
        });
    }

    const volumeCtx = document.getElementById('volumeChart');
    if (volumeCtx) {
        volumeChart = new Chart(volumeCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: '成交量',
                    data: [],
                    backgroundColor: 'rgba(139, 92, 246, 0.6)',
                    borderColor: '#8b5cf6',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    }
                }
            }
        });
    }

    const kdjCtx = document.getElementById('kdjChart');
    if (kdjCtx) {
        kdjChart = new Chart(kdjCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    { label: 'K', data: [], borderColor: '#06b6d4', tension: 0.4, borderWidth: 2, fill: false },
                    { label: 'D', data: [], borderColor: '#8b5cf6', tension: 0.4, borderWidth: 2, fill: false },
                    { label: 'J', data: [], borderColor: '#22c55e', tension: 0.4, borderWidth: 2, fill: false }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8' }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    }
                }
            }
        });
    }

    const macdCtx = document.getElementById('macdChart');
    if (macdCtx) {
        macdChart = new Chart(macdCtx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    { type: 'bar', label: 'MACD柱', data: [], backgroundColor: [], borderRadius: 4 },
                    { type: 'line', label: 'DIF', data: [], borderColor: '#06b6d4', tension: 0.4, borderWidth: 2, fill: false },
                    { type: 'line', label: 'DEA', data: [], borderColor: '#8b5cf6', tension: 0.4, borderWidth: 2, fill: false }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8' }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#94a3b8' }
                    }
                }
            }
        });
    }
}

async function loadData() {
    const stockCode = document.getElementById('stockCode').value.trim();
    
    if (!stockCode) {
        showMessage('请先输入股票代码！', 'warning');
        return;
    }

    try {
        let data = await safeFetch(`/api/v1/indicators/${stockCode}`);
        
        if (!data || data.length === 0) {
            showMessage('正在从真实数据源获取数据，请稍候...', 'info');
            await safeFetch(`/api/v1/stocks/fetch/${stockCode}`, { 
                method: 'POST',
                skipCache: true 
            });
            data = await safeFetch(`/api/v1/indicators/${stockCode}`, { skipCache: true });
        }
        
        if (data && data.length > 0) {
            updateCharts(data);
            loadSignals(stockCode);
            showMessage(`成功加载 ${data.length} 条数据！`, 'success');
        } else {
            showMessage('暂无数据，请确保已安装相关数据源库（akshare）或尝试其他股票', 'warning');
            const signalsContainer = document.getElementById('signalsContainer');
            if (signalsContainer) {
                signalsContainer.innerHTML = `
                    <div class="empty-state">
                        <span class="empty-state-icon">📊</span>
                        <p>该股票暂无数据，请确保后端已安装akshare库，或尝试其他代码</p>
                        <p style="font-size: 13px; color: #94a3b8; margin-top: 10px;">
                            提示：在后端运行 <code>pip install akshare</code> 可安装数据源
                        </p>
                    </div>
                `;
            }
        }
    } catch (error) {
        console.error('加载数据失败:', error);
        showMessage('加载数据失败: ' + error.message, 'error');
    }
}

function updateCharts(data) {
    if (!data || data.length === 0) return;

    const labels = data.map(d => new Date(d.datetime).toLocaleDateString('zh-CN'));
    const closes = data.map(d => d.close_price);
    const volumes = data.map(d => d.volume);
    const kValues = data.map(d => d.kdj_k);
    const dValues = data.map(d => d.kdj_d);
    const jValues = data.map(d => d.kdj_j);
    const difValues = data.map(d => d.macd_dif);
    const deaValues = data.map(d => d.macd_dea);
    const macdHistogram = data.map(d => d.macd_histogram);

    if (priceChart) {
        priceChart.data.labels = labels;
        priceChart.data.datasets[0].data = closes;
        priceChart.update('none');
    }

    if (volumeChart) {
        volumeChart.data.labels = labels;
        volumeChart.data.datasets[0].data = volumes;
        volumeChart.update('none');
    }

    if (kdjChart) {
        kdjChart.data.labels = labels;
        kdjChart.data.datasets[0].data = kValues;
        kdjChart.data.datasets[1].data = dValues;
        kdjChart.data.datasets[2].data = jValues;
        kdjChart.update('none');
    }

    if (macdChart) {
        macdChart.data.labels = labels;
        macdChart.data.datasets[0].data = macdHistogram;
        macdChart.data.datasets[0].backgroundColor = macdHistogram.map(v => 
            v >= 0 ? 'rgba(34, 197, 94, 0.7)' : 'rgba(239, 68, 68, 0.7)'
        );
        macdChart.data.datasets[1].data = difValues;
        macdChart.data.datasets[2].data = deaValues;
        macdChart.update('none');
    }
}

async function loadSignals(stockCode) {
    try {
        const result = await safeFetch(`/api/v1/indicators/signals/${stockCode}`);
        displaySignals(result.signals);
    } catch (error) {
        console.error('加载信号失败:', error);
        const signalsContainer = document.getElementById('signalsContainer');
        if (signalsContainer) {
            signalsContainer.innerHTML = `
                <div class="empty-state">
                    <span class="empty-state-icon">⚠️</span>
                    <p>加载信号失败，请刷新重试</p>
                </div>
            `;
        }
    }
}

function displaySignals(signals) {
    const container = document.getElementById('signalsContainer');
    if (!container) return;

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
            <p style="font-size: 16px; margin-bottom: 8px;">价格: <strong style="color: ${signal.type === 'buy' ? '#22c55e' : '#ef4444'};">¥${signal.price.toFixed(2)}</strong></p>
            <p style="color: #94a3b8; font-size: 13px; line-height: 1.6;">${signal.reason}</p>
            <p style="color: #64748b; font-size: 12px; margin-top: 12px;">${signal.datetime}</p>
        </div>
    `).join('');
}

const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100px); opacity: 0; }
    }
`;
document.head.appendChild(style);
