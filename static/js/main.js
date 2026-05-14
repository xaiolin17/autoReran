let currentData = null;
let mainChart = null;
let currentIndicator = 'macd';
let wsConnection = null;
let dataCache = new Map();
let CACHE_TTL = 30000;
let currentStockCode = null;

let showSignalToggle = false;
let marks = new Map();
let markPopupTarget = null;

document.addEventListener('DOMContentLoaded', () => {
    console.log('=== DOMContentLoaded ===');
    initChart();
    initWebSocket();
    initIndicatorTabs();
    initDatePickers();
    initSignalToggle();
    initMarkPopupMenu();
    loadData();
    setupEventListeners();
});

function initDatePickers() {
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);

    const formatDate = (d) => {
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yyyy}-${mm}-${dd}`;
    };

    const startDateEl = document.getElementById('startDate');
    const endDateEl = document.getElementById('endDate');
    if (startDateEl) startDateEl.value = formatDate(thirtyDaysAgo);
    if (endDateEl) endDateEl.value = formatDate(today);
}

function initSignalToggle() {
    const toggle = document.getElementById('signalToggle');
    if (toggle) {
        toggle.addEventListener('change', () => {
            showSignalToggle = toggle.checked;
            if (currentData) {
                updateCharts(currentData);
            }
        });
    }
}

function initMarkPopupMenu() {
    const menu = document.getElementById('markPopupMenu');
    if (!menu) return;

    menu.addEventListener('click', async (e) => {
        const btn = e.target.closest('.mark-popup-btn');
        if (!btn) return;

        const action = btn.dataset.action;
        if (markPopupTarget && currentData && currentStockCode) {
            if (action === 'buy') {
                marks.set(markPopupTarget.index, { type: 'buy', symbol: 'B' });
                await saveMarkToDB(currentStockCode, markPopupTarget.date, '买入');
            } else if (action === 'sell') {
                marks.set(markPopupTarget.index, { type: 'sell', symbol: 'S' });
                await saveMarkToDB(currentStockCode, markPopupTarget.date, '卖出');
            } else if (action === 'clear') {
                marks.delete(markPopupTarget.index);
                await saveMarkToDB(currentStockCode, markPopupTarget.date, null);
            }
            updateCharts(currentData);
        }

        menu.style.display = 'none';
        markPopupTarget = null;
    });

    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target) && e.target !== mainChart?.getZr()?.dom) {
            menu.style.display = 'none';
            markPopupTarget = null;
        }
    });
}

async function saveMarkToDB(stockCode, date, label) {
    try {
        await fetch(`/api/v1/stocks/mark`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stock_code: stockCode, date, label })
        });
    } catch (error) {
        console.error('保存标记失败:', error);
    }
}

async function loadMarksFromDB(stockCode) {
    try {
        const response = await fetch(`/api/v1/stocks/marks?stock_code=${stockCode}`);
        if (!response.ok) return [];
        const marksData = await response.json();
        
        const marksMap = new Map();
        if (currentData) {
            const dateToIndex = new Map();
            currentData.forEach((d, i) => {
                const dateStr = new Date(d.datetime).toISOString().split('T')[0];
                dateToIndex.set(dateStr, i);
            });
            
            marksData.forEach(m => {
                const dateStr = new Date(m.datetime).toISOString().split('T')[0];
                const index = dateToIndex.get(dateStr);
                if (index !== undefined) {
                    marksMap.set(index, {
                        type: m.label === '买入' ? 'buy' : 'sell',
                        symbol: m.label === '买入' ? 'B' : 'S'
                    });
                }
            });
        }
        
        return marksMap;
    } catch (error) {
        console.error('加载标记失败:', error);
        return new Map();
    }
}

function setupEventListeners() {
    const fetchBtn = document.getElementById('fetchBtn');
    if (fetchBtn) {
        fetchBtn.addEventListener('click', debounce(loadData, 300));
    }

    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', debounce(refreshData, 300));
    }

    const forceRefreshBtn = document.getElementById('forceRefreshBtn');
    if (forceRefreshBtn) {
        forceRefreshBtn.addEventListener('click', debounce(forceRefreshData, 300));
    }

    // 股票代码输入框搜索
    const stockCodeInput = document.getElementById('stockCode');
    if (stockCodeInput) {
        let searchTimeout = null;
        stockCodeInput.addEventListener('input', (e) => {
            const keyword = e.target.value.trim();
            if (searchTimeout) clearTimeout(searchTimeout);
            if (keyword.length >= 2) {
                searchTimeout = setTimeout(() => searchStockCodes(keyword), 300);
            } else {
                hideSearchResults();
            }
        });
        stockCodeInput.addEventListener('focus', (e) => {
            const keyword = e.target.value.trim();
            if (keyword.length >= 2) {
                searchStockCodes(keyword);
            }
        });
        // 点击外部隐藏搜索结果
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.stock-code-search')) {
                hideSearchResults();
            }
        });
    }

    const closeBtn = document.getElementById('closeProgressBox');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            document.getElementById('progressBox').style.display = 'none';
        });
    }
}

async function searchStockCodes(keyword) {
    try {
        const response = await fetch(`/api/v1/stocks/search?keyword=${encodeURIComponent(keyword)}&limit=20`);
        if (!response.ok) return;
        const data = await response.json();
        showSearchResults(data.results || []);
    } catch (error) {
        console.error('搜索股票代码失败:', error);
    }
}

function showSearchResults(results) {
    const container = document.getElementById('searchResults');
    if (!container) return;

    if (results.length === 0) {
        container.innerHTML = '<div class="search-no-results">无匹配结果</div>';
        container.style.display = 'block';
        return;
    }

    const categoryLabels = {
        'stock': 'A股',
        'index': '指数',
        'futures': '期货',
        'bond': '债券',
        'hk_stock': '港股',
        'us_stock': '美股'
    };

    container.innerHTML = results.map(r => `
        <div class="search-result-item" data-code="${r.name}">
            <div>
                <span class="search-result-code">${r.code}</span>
                <span class="search-result-full">${r.name}</span>
            </div>
            <span class="search-result-category">${categoryLabels[r.category] || r.category}</span>
        </div>
    `).join('');

    // 绑定点击事件
    container.querySelectorAll('.search-result-item').forEach(item => {
        item.addEventListener('click', () => {
            const code = item.dataset.code;
            document.getElementById('stockCode').value = code;
            hideSearchResults();
            loadData();
        });
    });

    container.style.display = 'block';
}

function hideSearchResults() {
    const container = document.getElementById('searchResults');
    if (container) container.style.display = 'none';
}

function initIndicatorTabs() {
    const tabs = document.querySelectorAll('.indicator-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            currentIndicator = tab.dataset.indicator;
            if (currentData) {
                updateCharts(currentData);
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
    const progressBox = document.getElementById('progressBox');
    const fill = document.getElementById('progressBoxFill');
    const step = document.getElementById('progressBoxStep');
    const percent = document.getElementById('progressBoxPercent');

    if (!progressBox || !fill || !step || !percent) return;

    progressBox.style.display = 'block';
    fill.style.width = `${data.progress}%`;

    let stepText = data.step || data.message || '--';
    step.textContent = stepText;
    percent.textContent = `${data.progress}%`;

    if (data.status === 'completed') {
        if (data.new_data_available) {
            dataCache.clear();
            setTimeout(() => {
                loadData();
                progressBox.style.display = 'none';
            }, 500);
        } else {
            setTimeout(() => {
                progressBox.style.display = 'none';
            }, 2000);
        }
    } else if (data.status === 'error') {
        setTimeout(() => {
            progressBox.style.display = 'none';
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

async function forceRefreshData() {
    const stockCode = document.getElementById('stockCode').value.trim();

    if (!stockCode) {
        showMessage('请先输入股票代码！', 'warning');
        return;
    }

    // 确认对话框
    if (!confirm(`确定要强制刷新 ${stockCode} 的历史数据吗？\n将下载完整历史数据并对比更新数据库。`)) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/stocks/force-refresh/${stockCode}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();
        showMessage(result.message, 'info');

    } catch (error) {
        console.error('强制刷新失败:', error);
        showMessage('强制刷新失败: ' + error.message, 'error');
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

// 全局消息计数器，用于计算偏移位置
let messageOffsetIndex = 0;
const activeMessages = new Set();

function showMessage(message, type = 'info') {
    const msgDiv = document.createElement('div');
    const offsetIndex = messageOffsetIndex++;
    activeMessages.add(msgDiv);

    // 计算垂直偏移：每个消息框向下偏移一定距离
    const topOffset = 24 + offsetIndex * 70;

    msgDiv.style.cssText = `
        position: fixed;
        top: ${topOffset}px;
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
        setTimeout(() => {
            msgDiv.remove();
            activeMessages.delete(msgDiv);
            // 重新排列剩余的消息框
            rearrangeMessages();
        }, 400);
    }, 3500);
}

function rearrangeMessages() {
    const messages = Array.from(activeMessages);
    messages.forEach((msg, index) => {
        msg.style.top = `${24 + index * 70}px`;
    });
    messageOffsetIndex = messages.length;
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

function initChart() {
    const dom = document.getElementById('mainChart');

    if (dom) {
        mainChart = echarts.init(dom);

        const emptyOption = {
            backgroundColor: 'transparent',
            animation: false,
            title: {
                text: '正在加载数据...',
                left: 'center',
                top: 'center',
                textStyle: {
                    color: '#94a3b8',
                    fontSize: 16
                }
            },
            grid: [
                { left: '10%', right: '8%', top: '10%', height: '55%' },
                { left: '10%', right: '8%', top: '70%', height: '18%' }
            ],
            xAxis: [
                { type: 'category', data: [] },
                { type: 'category', gridIndex: 1, data: [] }
            ],
            yAxis: [
                { type: 'value' },
                { type: 'value', gridIndex: 1 }
            ],
            series: []
        };

        mainChart.setOption(emptyOption);

        // 支持左键点击和右键点击打开标记菜单
        mainChart.on('click', (params) => {
            if (params.componentType === 'series' && params.seriesName === 'K线') {
                showMarkPopupMenu(params);
            }
        });

        // 右键菜单
        mainChart.getZr().on('contextmenu', (event) => {
            event.event.preventDefault();
            const point = [event.offsetX, event.offsetY];
            const dataIndex = mainChart.convertFromPixel({ seriesIndex: 0 }, point);
            if (dataIndex != null && currentData && currentData[dataIndex]) {
                showMarkPopupMenu({
                    dataIndex: dataIndex,
                    event: { event: { clientX: event.event.clientX, clientY: event.event.clientY } }
                });
            }
        });
    }

    window.addEventListener('resize', () => {
        mainChart && mainChart.resize();
    });
}

function showMarkPopupMenu(params) {
    const menu = document.getElementById('markPopupMenu');
    if (!menu) return;

    const dateStr = currentData[params.dataIndex].datetime;
    const date = new Date(dateStr).toISOString().split('T')[0];
    markPopupTarget = { index: params.dataIndex, dataIndex: params.dataIndex, date: date };

    const chartRect = document.getElementById('mainChart').getBoundingClientRect();
    const eventX = params.event?.event?.clientX || chartRect.left + chartRect.width / 2;
    const eventY = params.event?.event?.clientY || chartRect.top + chartRect.height / 2;

    let left = eventX + 10;
    let top = eventY - 20;

    if (left + 150 > window.innerWidth) left = eventX - 160;
    if (top + 120 > window.innerHeight) top = eventY - 120;

    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.style.display = 'flex';
}

async function loadData() {
    const stockCode = document.getElementById('stockCode').value.trim();
    const startDateEl = document.getElementById('startDate');
    const endDateEl = document.getElementById('endDate');

    const startDate = startDateEl ? startDateEl.value : '';
    const endDate = endDateEl ? endDateEl.value : '';

    if (!stockCode) {
        console.log('loadData: No stock code provided, waiting for user input');
        return;
    }

    try {
        currentStockCode = stockCode;
        let url = `/api/v1/indicators/${stockCode}`;
        const params = new URLSearchParams();
        if (startDate) params.set('start_date', startDate);
        if (endDate) params.set('end_date', endDate);
        if (params.toString()) url += `?${params.toString()}`;

        let response = await safeFetch(url);

        // 更新股票名称显示 (代码 + 名称) - 尽早更新，不受后续逻辑影响
        const stockNameDisplay = document.getElementById('stockNameDisplay');
        if (stockNameDisplay) {
            const stockCodeVal = document.getElementById('stockCode').value.trim();
            const stockName = response.stock_name || '';
            if (stockName) {
                stockNameDisplay.textContent = `${stockCodeVal} · ${stockName}`;
            } else {
                stockNameDisplay.textContent = stockCodeVal;
            }
        }

        // 处理新返回结构: {data, missing_ranges} 或 旧数组
        let data, missingRanges = [];
        if (Array.isArray(response)) {
            data = response;
            // 旧接口（无 missing_ranges）保持原行为：空数组才下载
        } else {
            data = response.data || [];
            missingRanges = response.missing_ranges || [];
        }

        // 关键修复：只要 missingRanges.length > 0 就触发下载，不管 data 是否为空
        if (missingRanges.length > 0) {
            const downloadStart = missingRanges[0].start;  // 最早的缺失起点
            const today = new Date().toISOString().split('T')[0];

            showMessage('检测到数据缺失，后台下载中...', 'info');

            // 显示进度框
            const progressBox = document.getElementById('progressBox');
            const fill = document.getElementById('progressBoxFill');
            const step = document.getElementById('progressBoxStep');
            const percent = document.getElementById('progressBoxPercent');
            if (progressBox && fill && step && percent) {
                progressBox.style.display = 'block';
                fill.style.width = '10%';
                step.textContent = '正在连接数据源...';
                percent.textContent = '10%';
            }

            // 启动后台异步下载（从缺失起点到今日）
            await safeFetch(`/api/v1/stocks/fetch-async/${stockCode}?start_date=${downloadStart}&end_date=${today}`, {
                method: 'POST',
                skipCache: true
            });

            // 显示已有数据（如果有），等待 WebSocket 通知下载完成后再刷新
            if (data.length > 0) {
                currentData = data;
                marks = await loadMarksFromDB(stockCode);
                updateCharts(data);
                showMessage(`已显示现有 ${data.length} 条数据，缺失部分后台下载中...`, 'info');
            } else {
                // 数据为空，清空图表
                currentData = [];
                updateCharts([]);
                showMessage('数据下载中，请稍候...', 'info');
            }
            // handleDownloadProgress 会在 WebSocket 收到 completed 时自动调用 loadData() 刷新
            return;
        }

        // 无缺失或旧接口逻辑
        if (!data || data.length === 0) {
            showMessage('正在从真实数据源获取数据，请稍候...', 'info');
            await safeFetch(`/api/v1/stocks/fetch/${stockCode}`, {
                method: 'POST',
                skipCache: true
            });
            data = await safeFetch(url, { skipCache: true });
            if (!Array.isArray(data)) data = data.data || [];
        }

        if (data && data.length > 0) {
            currentData = data;
            marks = await loadMarksFromDB(stockCode);
            updateCharts(data);
            showMessage(`成功加载 ${data.length} 条数据！`, 'success');
        } else {
            showMessage('暂无数据，请确保已配置 TickFlow API Key 或尝试其他股票', 'warning');
        }
    } catch (error) {
        console.error('加载数据失败:', error);
        showMessage('加载数据失败: ' + error.message, 'error');
    }
}

function getIndicatorSeries(indicatorType, data) {
    const indicatorConfigs = {
        macd: {
            legendData: ['MACD', 'DIF', 'DEA'],
            series: [
                {
                    name: 'MACD',
                    type: 'bar',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: data.map(d => d.macd_histogram),
                    itemStyle: {
                        color: function(params) {
                            return params.value >= 0 ? '#ef4444' : '#22c55e';
                        }
                    }
                },
                {
                    name: 'DIF',
                    type: 'line',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: data.map(d => d.macd),
                    smooth: true,
                    lineStyle: { width: 1 },
                    showSymbol: false,
                    color: '#06b6d4'
                },
                {
                    name: 'DEA',
                    type: 'line',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: data.map(d => d.macd_signal),
                    smooth: true,
                    lineStyle: { width: 1 },
                    showSymbol: false,
                    color: '#8b5cf6'
                }
            ]
        },
        kdj: {
            legendData: ['K', 'D', 'J'],
            series: [
                {
                    name: 'K',
                    type: 'line',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: data.map(d => d.kdj_k),
                    smooth: true,
                    lineStyle: { width: 1 },
                    showSymbol: false,
                    color: '#06b6d4'
                },
                {
                    name: 'D',
                    type: 'line',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: data.map(d => d.kdj_d),
                    smooth: true,
                    lineStyle: { width: 1 },
                    showSymbol: false,
                    color: '#8b5cf6'
                },
                {
                    name: 'J',
                    type: 'line',
                    xAxisIndex: 1,
                    yAxisIndex: 1,
                    data: data.map(d => d.kdj_j),
                    smooth: true,
                    lineStyle: { width: 1 },
                    showSymbol: false,
                    color: '#22c55e'
                }
            ]
        }
    };

    return indicatorConfigs[indicatorType] || indicatorConfigs.macd;
}

function updateCharts(data) {
    if (!data || data.length === 0 || !mainChart) {
        return;
    }

    const sortedData = data;
    const dates = sortedData.map(d => new Date(d.datetime).toLocaleDateString('zh-CN'));

    const klines = sortedData.map(d => [d.open_price, d.close_price, d.low_price, d.high_price]);
    const volumes = sortedData.map(d => [d.volume]);

    const ma5 = calculateMA(5, sortedData);
    const ma10 = calculateMA(10, sortedData);
    const ma20 = calculateMA(20, sortedData);

    const indicatorSeries = getIndicatorSeries(currentIndicator, sortedData);

    const option = {
        backgroundColor: 'transparent',
        animation: false,
        legend: {
            top: 10,
            left: 'center',
            data: ['K线', 'MA5', 'MA10', 'MA20', ...indicatorSeries.legendData],
            textStyle: { color: '#94a3b8' }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                link: [{ xAxisIndex: 'all' }]
            },
            backgroundColor: 'rgba(15, 23, 42, 0.9)',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            textStyle: { color: '#f8fafc' }
        },
        grid: [
            { left: '10%', right: '8%', top: '10%', height: '55%' },
            { left: '10%', right: '8%', top: '70%', height: '18%' }
        ],
        xAxis: [
            {
                type: 'category',
                data: dates,
                boundaryGap: false,
                axisLine: { lineStyle: { color: '#475569' } },
                axisLabel: { color: '#94a3b8' },
                splitLine: { show: false }
            },
            {
                type: 'category',
                gridIndex: 1,
                data: dates,
                boundaryGap: false,
                axisLine: { lineStyle: { color: '#475569' } },
                axisLabel: { color: '#94a3b8' },
                axisTick: { show: false },
                splitLine: { show: false }
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
                splitNumber: 3,
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
            },
            ...indicatorSeries.series
        ]
    };

    // 渲染用户标记（始终显示，不依赖交易信号开关）
    if (marks.size > 0) {
        const markSeriesData = [];
        marks.forEach((mark, index) => {
            if (index < sortedData.length) {
                const d = sortedData[index];
                const isBuy = mark.type === 'buy';
                markSeriesData.push({
                    name: isBuy ? '买入' : '卖出',
                    value: [index, isBuy ? d.low_price : d.high_price],
                    symbol: isBuy ? 'triangle' : 'triangle',
                    symbolRotate: isBuy ? 0 : 180,
                    symbolSize: 14,
                    itemStyle: {
                        color: isBuy ? '#22c55e' : '#ef4444',
                        borderWidth: 2,
                        borderColor: isBuy ? '#22c55e' : '#ef4444'
                    },
                    label: {
                        show: true,
                        formatter: isBuy ? '买' : '卖',
                        position: isBuy ? 'bottom' : 'top',
                        fontSize: 11,
                        color: isBuy ? '#22c55e' : '#ef4444',
                        fontWeight: 'bold',
                        distance: 5
                    }
                });
            }
        });

        if (markSeriesData.length > 0) {
            option.series.push({
                name: '标记',
                type: 'scatter',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: markSeriesData,
                zlevel: 10,
                emphasis: {
                    scale: 1.5
                }
            });
        }
    }

    mainChart.setOption(option, true);
}