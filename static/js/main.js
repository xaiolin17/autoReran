let optionRatioChart = null;
let currentOptionData = null;

document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    loadData();
    setupEventListeners();
    initOptionSection();
});

function setupEventListeners() {
    document.getElementById('fetchBtn').addEventListener('click', loadData);
    document.getElementById('generateBtn').addEventListener('click', generateSampleData);
    document.getElementById('loadOptionsBtn').addEventListener('click', loadOptionData);
    document.getElementById('refreshOptionsBtn').addEventListener('click', loadOptionData);
    document.getElementById('expireDateSelect').addEventListener('change', filterOptionData);
}

function initOptionSection() {
    // Show options section by default
    document.getElementById('optionsSection').style.display = 'block';
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

// ===== Options Functions =====
async function loadOptionData() {
    const stockCode = document.getElementById('stockCode').value.trim();
    
    if (!stockCode) {
        showMessage('请先输入股票代码！', 'warning');
        return;
    }
    
    // Show loading state
    document.getElementById('optionSummary').innerHTML = `
        <div class="empty-state" style="padding: 40px;">
            <div style="display: inline-block; width: 40px; height: 40px; border: 4px solid rgba(0,240,255,0.2); border-top: 4px solid #00f0ff; border-radius: 50%; animation: spin 1s linear infinite;"></div>
            <p style="margin-top: 16px; color: #94a3b8;">正在加载期权数据...</p>
        </div>
    `;
    
    try {
        // Load option chain and summary in parallel
        const [chainResponse, summaryResponse] = await Promise.all([
            fetch(`/api/v1/options/chain/${stockCode}`),
            fetch(`/api/v1/options/chain/${stockCode}/summary`)
        ]);
        
        currentOptionData = await chainResponse.json();
        const summary = await summaryResponse.json();
        
        // Update expire date select
        updateExpireDateSelect(currentOptionData.expire_dates);
        
        // Display data
        displayOptionSummary(summary);
        displayOptionChain(currentOptionData);
        drawOptionRatioChart(summary);
        
        // Show refresh button
        document.getElementById('loadOptionsBtn').style.display = 'none';
        document.getElementById('refreshOptionsBtn').style.display = 'inline-block';
        
        showMessage('期权数据加载成功！', 'success');
    } catch (error) {
        console.error('加载期权数据失败:', error);
        document.getElementById('optionSummary').innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">⚠️</span>
                <p>加载期权数据失败，请重试</p>
            </div>
        `;
        showMessage('加载期权数据失败: ' + error.message, 'error');
    }
}

function updateExpireDateSelect(expireDates) {
    const select = document.getElementById('expireDateSelect');
    select.innerHTML = '<option value="">全部</option>';
    
    if (expireDates && expireDates.length > 0) {
        expireDates.forEach(date => {
            const option = document.createElement('option');
            option.value = date;
            option.textContent = date;
            select.appendChild(option);
        });
    }
}

function displayOptionSummary(summary) {
    const container = document.getElementById('optionSummary');
    
    const callPutVolumeRatio = summary.call_put_volume_ratio ? summary.call_put_volume_ratio.toFixed(2) : '0.00';
    const callPutOiRatio = summary.call_put_oi_ratio ? summary.call_put_oi_ratio.toFixed(2) : '0.00';
    
    container.innerHTML = `
        <div class="option-summary-grid">
            <div class="option-summary-item call">
                <div class="option-summary-label">📈 看涨总成交量</div>
                <div class="option-summary-value call">${formatNumber(summary.total_call_volume || 0)}</div>
            </div>
            <div class="option-summary-item put">
                <div class="option-summary-label">📉 看跌总成交量</div>
                <div class="option-summary-value put">${formatNumber(summary.total_put_volume || 0)}</div>
            </div>
            <div class="option-summary-item call">
                <div class="option-summary-label">📈 看涨持仓量</div>
                <div class="option-summary-value call">${formatNumber(summary.total_call_oi || 0)}</div>
            </div>
            <div class="option-summary-item put">
                <div class="option-summary-label">📉 看跌持仓量</div>
                <div class="option-summary-value put">${formatNumber(summary.total_put_oi || 0)}</div>
            </div>
        </div>
        <div class="option-summary-grid">
            <div class="option-summary-item ${callPutVolumeRatio >= 1 ? 'call' : 'put'}">
                <div class="option-summary-label">📊 看多看空比(成交量)</div>
                <div class="option-summary-value ${callPutVolumeRatio >= 1 ? 'call' : 'put'}">${callPutVolumeRatio}</div>
                <div class="option-summary-sub">>1 偏多，<1 偏空</div>
            </div>
            <div class="option-summary-item ${callPutOiRatio >= 1 ? 'call' : 'put'}">
                <div class="option-summary-label">📊 看多看空比(持仓)</div>
                <div class="option-summary-value ${callPutOiRatio >= 1 ? 'call' : 'put'}">${callPutOiRatio}</div>
                <div class="option-summary-sub">>1 偏多，<1 偏空</div>
            </div>
        </div>
        <div class="option-summary-item neutral">
            <div class="option-summary-label">💡 最大痛点价位</div>
            <div class="option-summary-value">${summary.max_pain_strike ? summary.max_pain_strike.toFixed(2) : '-'}</div>
            <div class="option-summary-sub">标的价格: ¥${summary.stock_price ? summary.stock_price.toFixed(2) : '-'}</div>
        </div>
    `;
}

function displayOptionChain(data) {
    const tbody = document.getElementById('optionChainBody');
    const calls = data.calls || [];
    const puts = data.puts || [];
    const stockPrice = data.stock_price || 0;
    
    // 如果没有期权数据，显示友好提示
    if (calls.length === 0 && puts.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="19">
                    <div class="empty-state" style="padding: 40px;">
                        <span class="empty-state-icon">📊</span>
                        <p>暂无期权数据，或该标的暂无期权交易</p>
                        <p style="font-size: 14px; color: var(--text-secondary); margin-top: 10px;">
                            💡 提示: 请尝试期权标的: 510300(沪深300ETF), 510500(中证500ETF), 510050(上证50ETF)
                        </p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    // Group options by strike price
    const strikeMap = new Map();
    
    calls.forEach(call => {
        if (!strikeMap.has(call.strike_price)) {
            strikeMap.set(call.strike_price, { call: null, put: null });
        }
        strikeMap.get(call.strike_price).call = call;
    });
    
    puts.forEach(put => {
        if (!strikeMap.has(put.strike_price)) {
            strikeMap.set(put.strike_price, { call: null, put: null });
        }
        strikeMap.get(put.strike_price).put = put;
    });
    
    // Sort by strike price
    const sortedStrikes = Array.from(strikeMap.keys()).sort((a, b) => a - b);
    
    if (sortedStrikes.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="19">
                    <div class="empty-state" style="padding: 40px;">
                        <span class="empty-state-icon">📊</span>
                        <p>暂无期权数据</p>
                    </div>
                </td>
            </tr>
        `;
        return;
    }
    
    tbody.innerHTML = sortedStrikes.map(strike => {
        const pair = strikeMap.get(strike);
        const call = pair.call;
        const put = pair.put;
        
        // Determine ITM/ATM/OTM
        const isCallITM = call && stockPrice > strike;
        const isPutITM = put && stockPrice < strike;
        
        let rowClass = 'option-row';
        if (isCallITM) rowClass += ' itm-call';
        if (isPutITM) rowClass += ' itm-put';
        
        return `
            <tr class="${rowClass}">
                <!-- Call Side -->
                <td class="option-code">${call ? call.option_code : '-'}</td>
                <td class="option-price ${call && call.change_percent >= 0 ? 'up' : 'down'}">${call ? call.latest_price.toFixed(2) : '-'}</td>
                <td class="option-change ${call && call.change_percent >= 0 ? 'up' : 'down'}">${call ? (call.change_percent >= 0 ? '+' : '') + call.change_percent.toFixed(2) + '%' : '-'}</td>
                <td class="option-bid">${call ? call.bid_price.toFixed(2) : '-'}</td>
                <td class="option-bid">${call ? formatNumber(call.bid_volume) : '-'}</td>
                <td class="option-ask">${call ? call.ask_price.toFixed(2) : '-'}</td>
                <td class="option-ask">${call ? formatNumber(call.ask_volume) : '-'}</td>
                <td class="option-volume">${call ? formatNumber(call.volume) : '-'}</td>
                <td class="option-oi">${call ? formatNumber(call.open_interest) : '-'}</td>
                
                <!-- Strike Price -->
                <td class="strike-col">${strike.toFixed(2)}</td>
                
                <!-- Put Side -->
                <td class="option-oi">${put ? formatNumber(put.open_interest) : '-'}</td>
                <td class="option-volume">${put ? formatNumber(put.volume) : '-'}</td>
                <td class="option-ask">${put ? formatNumber(put.ask_volume) : '-'}</td>
                <td class="option-ask">${put ? put.ask_price.toFixed(2) : '-'}</td>
                <td class="option-bid">${put ? formatNumber(put.bid_volume) : '-'}</td>
                <td class="option-bid">${put ? put.bid_price.toFixed(2) : '-'}</td>
                <td class="option-change ${put && put.change_percent >= 0 ? 'up' : 'down'}">${put ? (put.change_percent >= 0 ? '+' : '') + put.change_percent.toFixed(2) + '%' : '-'}</td>
                <td class="option-price ${put && put.change_percent >= 0 ? 'up' : 'down'}">${put ? put.latest_price.toFixed(2) : '-'}</td>
                <td class="option-code">${put ? put.option_code : '-'}</td>
            </tr>
        `;
    }).join('');
}

function filterOptionData() {
    if (!currentOptionData) return;
    
    const selectedExpire = document.getElementById('expireDateSelect').value;
    
    let filteredCalls = currentOptionData.calls || [];
    let filteredPuts = currentOptionData.puts || [];
    
    if (selectedExpire) {
        filteredCalls = filteredCalls.filter(c => c.expire_date === selectedExpire);
        filteredPuts = filteredPuts.filter(p => p.expire_date === selectedExpire);
    }
    
    displayOptionChain({
        ...currentOptionData,
        calls: filteredCalls,
        puts: filteredPuts
    });
}

function drawOptionRatioChart(summary) {
    const ctx = document.getElementById('optionRatioChart').getContext('2d');
    
    if (optionRatioChart) {
        optionRatioChart.destroy();
    }
    
    optionRatioChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['成交量', '持仓量'],
            datasets: [
                {
                    label: '看涨',
                    data: [summary.total_call_volume || 0, summary.total_call_oi || 0],
                    backgroundColor: 'rgba(16, 185, 129, 0.7)',
                    borderColor: 'rgba(16, 185, 129, 1)',
                    borderWidth: 2,
                    borderRadius: 8
                },
                {
                    label: '看跌',
                    data: [summary.total_put_volume || 0, summary.total_put_oi || 0],
                    backgroundColor: 'rgba(239, 68, 68, 0.7)',
                    borderColor: 'rgba(239, 68, 68, 1)',
                    borderWidth: 2,
                    borderRadius: 8
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: {
                        color: '#94a3b8',
                        font: {
                            size: 12,
                            weight: '600'
                        },
                        padding: 16
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#94a3b8'
                    }
                },
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#94a3b8',
                        font: {
                            weight: '600'
                        }
                    }
                }
            }
        }
    });
}

function formatNumber(num) {
    if (num === null || num === undefined) return '-';
    if (num >= 10000) {
        return (num / 10000).toFixed(1) + '万';
    }
    return num.toLocaleString();
}
