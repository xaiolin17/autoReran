let currentData = null;
let klineChart = null;
let kdjChart = null;
let macdChart = null;
let wsConnection = null;
let dataCache = new Map();
let CACHE_TTL = 30000;

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    initWebSocket();
    initTabs();
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    const fetchBtn = document.getElementById('fetchBtn');
    if (fetchBtn) {
        fetchBtn.addEventListener('click', debounce(loadData, 300));
    }
    
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', debounce(refreshData, 300));
    }
    
    const loadHistoricalBtn = document.getElementById('loadHistoricalBtn');
    if (loadHistoricalBtn) {
        loadHistoricalBtn.addEventListener('click', debounce(loadHistoricalData, 300));
    }
}

function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            const tabName = tab.dataset.tab;
            document.querySelectorAll('.indicator-chart').forEach(chart => {
                chart.classList.add('hidden');
            });
            document.getElementById(`${tabName}Chart`).classList.remove('hidden');
            
            if (tabName === 'kdj' && kdjChart) {
                kdjChart.resize();
            } else if (tabName === 'macd' && macdChart) {
                macdChart.resize();
            }
        });
    });
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
        case 'download_progress':
            handleDownloadProgress(message.data);
            break;
    }
}

function handleDownloadProgress(data) {
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    
    if (!progressContainer || !progressBar || !progressText) return;
    
    progressContainer.style.display = 'block';
    progressBar.style.width = `${data.progress}%`;
    progressText.textContent = data.message;
    
    if (data.status === 'completed') {
        if (data.new_data_available) {
            setTimeout(() => {
                loadData();
                progressContainer.style.display = 'none';
            }, 500);
        } else {
            setTimeout(() => {
                progressContainer.style.display = 'none';
            }, 2000);
        }
    } else if (data.status === 'error') {
        setTimeout(() => {
            progressContainer.style.display = 'none';
        }, 3000);
    }
}

async function refreshData() {
    const stockCode = document.getElementById('stockCode').value.trim();
    
    if (!stockCode) {
        showMessage('请先输入股票代码！', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`/api/v1/stocks/refresh/${stockCode}`, { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        showMessage(result.message, 'info');
        
    } catch (error) {
        console.error('刷新数据失败:', error);
        showMessage('刷新数据失败: ' + error.message, 'error');
    }
}

async function loadHistoricalData() {
    const stockCode = document.getElementById('stockCode').value.trim();
    
    if (!stockCode) {
        showMessage('请先输入股票代码！', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`/api/v1/stocks/load-historical/${stockCode}`, { 
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        showMessage(result.message, 'info');
        
    } catch (error) {
        console.error('加载历史数据失败:', error);
        showMessage('加载历史数据失败: ' + error.message, 'error');
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

function calculateMA(dayCount, data) {
    const result = [];
    for (let i = 0, len = data.length; i < len; i++) {
        if (i < dayCount - 1) {
            result.push('-');
            continue;
        }
        let sum = 0;
        for (let j = 0; j < dayCount; j++) {
            sum += parseFloat(data[i - j].close_price);
        }
        result.push((sum / dayCount).toFixed(2));
    }
    return result;
}

function initCharts() {
    const klineDom = document.getElementById('klineChart');
    if (klineDom) {
        klineChart = echarts.init(klineDom);
    }
    
    const kdjDom = document.getElementById('kdjChart');
    if (kdjDom) {
        kdjChart = echarts.init(kdjDom);
    }
    
    const macdDom = document.getElementById('macdChart');
    if (macdDom) {
        macdChart = echarts.init(macdDom);
    }
    
    window.addEventListener('resize', () => {
        klineChart && klineChart.resize();
        kdjChart && kdjChart.resize();
        macdChart && macdChart.resize();
    });
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
            currentData = data;
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
    if (!data || data.length === 0 || !klineChart) return;

    const sortedData = [...data].reverse();
    const dates = sortedData.map(d => new Date(d.datetime).toLocaleDateString('zh-CN'));
    const klines = sortedData.map(d => [d.open_price, d.close_price, d.low_price, d.high_price]);
    const volumes = sortedData.map(d => [d.volume]);
    const closes = sortedData.map(d => d.close_price);
    
    const ma5 = calculateMA(5, sortedData);
    const ma10 = calculateMA(10, sortedData);
    const ma20 = calculateMA(20, sortedData);

    const kdjK = sortedData.map(d => d.kdj_k);
    const kdjD = sortedData.map(d => d.kdj_d);
    const kdjJ = sortedData.map(d => d.kdj_j);
    
    const macd = sortedData.map(d => d.macd);
    const macdSignal = sortedData.map(d => d.macd_signal);
    const macdHistogram = sortedData.map(d => d.macd_histogram);
    
    const macdColors = macdHistogram.map(v => v >= 0 ? '#ef4444' : '#22c55e');

    const klineOption = {
        backgroundColor: 'transparent',
        animation: false,
        legend: {
            top: 10,
            left: 'center',
            data: ['K线', 'MA5', 'MA10', 'MA20'],
            textStyle: { color: '#94a3b8' }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            textStyle: { color: '#f8fafc' }
        },
        grid: [
            { left: '10%', right: '8%', top: '10%', height: '50%' },
            { left: '10%', right: '8%', top: '70%', height: '16%' }
        ],
        xAxis: [
            {
                type: 'category',
                data: dates,
                scale: true,
                boundaryGap: false,
                axisLine: { lineStyle: { color: '#475569' } },
                axisLabel: { color: '#94a3b8' },
                min: 'dataMin',
                max: 'dataMax'
            },
            {
                type: 'category',
                gridIndex: 1,
                data: dates,
                scale: true,
                boundaryGap: false,
                axisLine: { lineStyle: { color: '#475569' } },
                axisLabel: { color: '#94a3b8', show: false },
                axisTick: { show: false },
                splitLine: { show: false },
                min: 'dataMin',
                max: 'dataMax'
            }
        ],
        yAxis: [
            {
                scale: true,
                splitArea: { show: true, areaStyle: { color: 'rgba(255, 255, 255, 0.02)' } },
                axisLine: { lineStyle: { color: '#475569' } },
                axisLabel: { color: '#94a3b8' },
                splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
            },
            {
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                axisLine: { lineStyle: { color: '#475569' } },
                axisLabel: { color: '#94a3b8' },
                axisTick: { show: false },
                splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } }
            }
        ],
        dataZoom: [
            { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
            { show: true, xAxisIndex: [0, 1], type: 'slider', bottom: 10, start: 0, end: 100 }
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                data: klines,
                itemStyle: {
                    color: '#22c55e',
                    color0: '#ef4444',
                    borderColor: '#22c55e',
                    borderColor0: '#ef4444'
                }
            },
            { name: 'MA5', type: 'line', data: ma5, smooth: true, lineStyle: { width: 1, opacity: 0.7 }, showSymbol: false, color: '#06b6d4' },
            { name: 'MA10', type: 'line', data: ma10, smooth: true, lineStyle: { width: 1, opacity: 0.7 }, showSymbol: false, color: '#f59e0b' },
            { name: 'MA20', type: 'line', data: ma20, smooth: true, lineStyle: { width: 1, opacity: 0.7 }, showSymbol: false, color: '#8b5cf6' },
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: volumes,
                itemStyle: {
                    color: function(params) {
                        const dataIndex = params.dataIndex;
                        return klines[dataIndex][1] >= klines[dataIndex][0] ? 'rgba(34, 197, 94, 0.6)' : 'rgba(239, 68, 68, 0.6)';
                    }
                }
            }
        ]
    };
    
    klineChart.setOption(klineOption);

    const kdjOption = {
        backgroundColor: 'transparent',
        animation: false,
        legend: {
            top: 10,
            left: 'center',
            data: ['K', 'D', 'J'],
            textStyle: { color: '#94a3b8' }
        },
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            textStyle: { color: '#f8fafc' }
        },
        grid: { left: '10%', right: '8%', top: '15%', bottom: '10%' },
        xAxis: {
            type: 'category',
            data: dates,
            axisLine: { lineStyle: { color: '#475569' } },
            axisLabel: { color: '#94a3b8' }
        },
        yAxis: {
            scale: true,
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
            axisLine: { lineStyle: { color: '#475569' } },
            axisLabel: { color: '#94a3b8' }
        },
        dataZoom: [
            { type: 'inside', start: 0, end: 100 }
        ],
        series: [
            { name: 'K', type: 'line', data: kdjK, smooth: true, lineStyle: { width: 1 }, showSymbol: false, color: '#06b6d4' },
            { name: 'D', type: 'line', data: kdjD, smooth: true, lineStyle: { width: 1 }, showSymbol: false, color: '#8b5cf6' },
            { name: 'J', type: 'line', data: kdjJ, smooth: true, lineStyle: { width: 1 }, showSymbol: false, color: '#22c55e' }
        ]
    };
    
    kdjChart.setOption(kdjOption);

    const macdOption = {
        backgroundColor: 'transparent',
        animation: false,
        legend: {
            top: 10,
            left: 'center',
            data: ['MACD', 'DIF', 'DEA'],
            textStyle: { color: '#94a3b8' }
        },
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            textStyle: { color: '#f8fafc' }
        },
        grid: { left: '10%', right: '8%', top: '15%', bottom: '10%' },
        xAxis: {
            type: 'category',
            data: dates,
            axisLine: { lineStyle: { color: '#475569' } },
            axisLabel: { color: '#94a3b8' }
        },
        yAxis: {
            scale: true,
            splitLine: { lineStyle: { color: 'rgba(255, 255, 255, 0.05)' } },
            axisLine: { lineStyle: { color: '#475569' } },
            axisLabel: { color: '#94a3b8' }
        },
        dataZoom: [
            { type: 'inside', start: 0, end: 100 }
        ],
        series: [
            {
                name: 'MACD',
                type: 'bar',
                data: macdHistogram,
                itemStyle: {
                    color: function(params) {
                        return params.value >= 0 ? '#ef4444' : '#22c55e';
                    }
                }
            },
            { name: 'DIF', type: 'line', data: macd, smooth: true, lineStyle: { width: 1 }, showSymbol: false, color: '#06b6d4' },
            { name: 'DEA', type: 'line', data: macdSignal, smooth: true, lineStyle: { width: 1 }, showSymbol: false, color: '#8b5cf6' }
        ]
    };
    
    macdChart.setOption(macdOption);
}

async function loadSignals(stockCode) {
    try {
        const result = await safeFetch(`/api/v1/indicators/signals/${stockCode}`);
        displaySignals(result && result.signals ? result.signals : null);
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
