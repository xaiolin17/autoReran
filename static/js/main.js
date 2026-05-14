/**
 * ============================================================
 * 全局变量声明区域
 * ============================================================
 */

/** 当前加载的股票K线数据，数组格式，每个元素包含开盘/收盘/最高/最低/成交量等字段 */
let currentData = null;

/** ECharts 主图表实例，用于渲染K线图和指标 */
let mainChart = null;

/** 当前选中的技术指标类型，可选值: 'macd' | 'kdj'，默认 'macd' */
let currentIndicator = 'macd';

/** WebSocket 连接实例，用于接收实时数据下载进度和后台通知 */
let wsConnection = null;

/** 数据缓存 Map，键为请求URL，值为 { data, timestamp } 结构，减少重复请求 */
let dataCache = new Map();

/** 缓存有效期（毫秒），默认 30 秒，超过此时间缓存失效 */
let CACHE_TTL = 30000;

/** 当前正在查看的股票代码，如 '000001' */
let currentStockCode = null;

/** 交易信号显示开关，控制是否在图表上显示买卖信号标记 */
let showSignalToggle = false;

/** 用户手动添加的买卖标记 Map，键为数据索引，值为 { type, symbol } */
let marks = new Map();

/** 当前右键/点击弹出的标记菜单目标，包含 { index, dataIndex, date } */
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

/**
 * 初始化日期选择器
 * 功能：设置默认查询日期范围（最近30天），并格式化填充到页面输入框
 * 参数：无
 * 返回值：无
 * 调用关系：被 DOMContentLoaded 事件调用；内部定义 formatDate 辅助函数
 * 关键逻辑：
 *   - 结束日期设为今天，开始日期设为30天前
 *   - 日期格式化为 yyyy-MM-dd 字符串
 */
function initDatePickers() {
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);

    // 辅助函数：将 Date 对象格式化为 yyyy-MM-dd 字符串
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

/**
 * 初始化交易信号开关
 * 功能：绑定信号显示开关的 change 事件，控制图表上买卖信号的显示/隐藏
 * 参数：无
 * 返回值：无
 * 调用关系：被 DOMContentLoaded 事件调用；数据变化时调用 updateCharts 刷新图表
 * 关键逻辑：
 *   - 监听 id 为 'signalToggle' 的复选框变化
 *   - 更新全局变量 showSignalToggle 状态
 *   - 如果有数据，触发图表重绘以显示/隐藏信号
 */
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

/**
 * 初始化标记弹出菜单
 * 功能：绑定图表标记菜单的点击事件，处理买入/卖出/清除标记操作
 * 参数：无
 * 返回值：无
 * 调用关系：
 *   - 被 DOMContentLoaded 事件调用
 *   - 内部调用 saveMarkToDB 保存标记到数据库
 *   - 内部调用 updateCharts 刷新图表显示新标记
 *   - 被 initChart 中绑定的 click/contextmenu 事件触发显示
 * 关键逻辑：
 *   - 通过事件委托监听菜单按钮点击
 *   - 根据 data-action 区分 buy/sell/clear 三种操作
 *   - 操作完成后更新全局 marks Map 并持久化到数据库
 *   - 点击页面其他区域自动关闭菜单
 */
function initMarkPopupMenu() {
    const menu = document.getElementById('markPopupMenu');
    if (!menu) return;

    // 监听菜单按钮点击事件
    menu.addEventListener('click', async (e) => {
        const btn = e.target.closest('.mark-popup-btn');
        if (!btn) return;

        const action = btn.dataset.action;
        if (markPopupTarget && currentData && currentStockCode) {
            if (action === 'buy') {
                // 添加买入标记并保存到数据库
                marks.set(markPopupTarget.index, { type: 'buy', symbol: 'B' });
                await saveMarkToDB(currentStockCode, markPopupTarget.date, '买入');
            } else if (action === 'sell') {
                // 添加卖出标记并保存到数据库
                marks.set(markPopupTarget.index, { type: 'sell', symbol: 'S' });
                await saveMarkToDB(currentStockCode, markPopupTarget.date, '卖出');
            } else if (action === 'clear') {
                // 清除该位置的标记
                marks.delete(markPopupTarget.index);
                await saveMarkToDB(currentStockCode, markPopupTarget.date, null);
            }
            // 刷新图表以显示更新后的标记
            updateCharts(currentData);
        }

        // 关闭菜单并清空目标
        menu.style.display = 'none';
        markPopupTarget = null;
    });

    // 点击页面其他区域时关闭菜单
    document.addEventListener('click', (e) => {
        if (!menu.contains(e.target) && e.target !== mainChart?.getZr()?.dom) {
            menu.style.display = 'none';
            markPopupTarget = null;
        }
    });
}

/**
 * 保存标记到数据库
 * 功能：将用户在图表上添加的买入/卖出标记持久化到后端数据库
 * 参数：
 *   - stockCode: string，股票代码
 *   - date: string，标记日期（yyyy-MM-dd 格式）
 *   - label: string|null，标记类型，'买入'/'卖出'/null（清除标记）
 * 返回值：无（Promise<void>）
 * 调用关系：被 initMarkPopupMenu 调用
 * 关键逻辑：
 *   - 使用 PUT 请求发送到 /api/v1/stocks/mark
 *   - 失败时仅控制台输出错误，不影响前端交互
 */
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

/**
 * 从数据库加载标记
 * 功能：获取指定股票的所有历史标记，并映射到当前数据的索引位置
 * 参数：
 *   - stockCode: string，股票代码
 * 返回值：Promise<Map>，键为数据索引，值为 { type, symbol } 的标记对象
 * 调用关系：
 *   - 被 loadData 调用，加载完股票数据后执行
 *   - 依赖全局变量 currentData 进行日期到索引的映射
 * 关键逻辑：
 *   - 通过 API 获取该股票的所有标记记录
 *   - 构建日期→索引的映射表，将数据库中的日期转换为数据数组索引
 *   - 仅加载与当前数据日期匹配的标记
 *   - 返回 Map 结构供 updateCharts 渲染使用
 */
async function loadMarksFromDB(stockCode) {
    try {
        const response = await fetch(`/api/v1/stocks/marks?stock_code=${stockCode}`);
        if (!response.ok) return [];
        const marksData = await response.json();
        
        const marksMap = new Map();
        if (currentData) {
            // 构建日期到数据索引的映射，用于快速查找
            const dateToIndex = new Map();
            currentData.forEach((d, i) => {
                const dateStr = new Date(d.datetime).toISOString().split('T')[0];
                dateToIndex.set(dateStr, i);
            });
            
            // 遍历数据库标记，将日期匹配到对应的数据索引
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

/**
 * 设置页面事件监听器
 * 功能：绑定所有按钮和输入框的事件处理，是页面交互的核心入口
 * 参数：无
 * 返回值：无
 * 调用关系：
 *   - 被 DOMContentLoaded 事件调用
 *   - 内部调用 debounce 防抖处理按钮点击
 *   - 内部调用 loadData、refreshData、forceRefreshData、searchStockCodes、hideSearchResults
 * 关键逻辑：
 *   - 获取/刷新/强制刷新按钮均使用 300ms 防抖避免重复触发
 *   - 股票代码输入框支持实时搜索（输入2个字符后触发）和聚焦搜索
 *   - 点击页面其他区域自动隐藏搜索结果下拉框
 *   - 进度框关闭按钮绑定
 */
function setupEventListeners() {
    // 绑定"获取数据"按钮
    const fetchBtn = document.getElementById('fetchBtn');
    if (fetchBtn) {
        fetchBtn.addEventListener('click', debounce(loadData, 300));
    }

    // 绑定"刷新数据"按钮
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', debounce(refreshData, 300));
    }

    // 绑定"强制刷新"按钮
    const forceRefreshBtn = document.getElementById('forceRefreshBtn');
    if (forceRefreshBtn) {
        forceRefreshBtn.addEventListener('click', debounce(forceRefreshData, 300));
    }

    // 股票代码输入框搜索功能
    const stockCodeInput = document.getElementById('stockCode');
    if (stockCodeInput) {
        let searchTimeout = null;
        
        // 输入时实时搜索（防抖 300ms）
        stockCodeInput.addEventListener('input', (e) => {
            const keyword = e.target.value.trim();
            if (searchTimeout) clearTimeout(searchTimeout);
            if (keyword.length >= 2) {
                searchTimeout = setTimeout(() => searchStockCodes(keyword), 300);
            } else {
                hideSearchResults();
            }
        });
        
        // 聚焦时如果有关键词则立即搜索
        stockCodeInput.addEventListener('focus', (e) => {
            const keyword = e.target.value.trim();
            if (keyword.length >= 2) {
                searchStockCodes(keyword);
            }
        });
        
        // 点击页面其他区域隐藏搜索结果
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.stock-code-search')) {
                hideSearchResults();
            }
        });
    }

    // 进度框关闭按钮
    const closeBtn = document.getElementById('closeProgressBox');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            document.getElementById('progressBox').style.display = 'none';
        });
    }
}

/**
 * 搜索股票代码
 * 功能：根据关键词向后端搜索匹配的股票代码，并展示搜索结果
 * 参数：
 *   - keyword: string，搜索关键词（股票代码或名称片段）
 * 返回值：无（Promise<void>）
 * 调用关系：
 *   - 被 setupEventListeners 中输入框的 input/focus 事件调用
 *   - 内部调用 showSearchResults 渲染结果列表
 * 关键逻辑：
 *   - 调用 /api/v1/stocks/search 接口，限制返回 20 条
 *   - 对关键词进行 URL 编码防止特殊字符问题
 *   - 请求失败时仅控制台输出错误
 */
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

/**
 * 显示搜索结果
 * 功能：将搜索到的股票列表渲染到页面下拉框中
 * 参数：
 *   - results: Array<{code, name, category}>，搜索结果数组
 * 返回值：无
 * 调用关系：
 *   - 被 searchStockCodes 调用
 *   - 内部调用 hideSearchResults、loadData
 * 关键逻辑：
 *   - 无结果时显示"无匹配结果"提示
 *   - 按 category 映射为中文分类标签（A股/港股/美股等）
 *   - 点击结果项自动填充股票代码并触发数据加载
 *   - 使用 data-code 存储股票代码供点击事件使用
 */
function showSearchResults(results) {
    const container = document.getElementById('searchResults');
    if (!container) return;

    // 无匹配结果时显示提示
    if (results.length === 0) {
        container.innerHTML = '<div class="search-no-results">无匹配结果</div>';
        container.style.display = 'block';
        return;
    }

    // 分类标签映射表：将英文 category 转为中文显示
    const categoryLabels = {
        'stock': 'A股',
        'index': '指数',
        'futures': '期货',
        'bond': '债券',
        'hk_stock': '港股',
        'us_stock': '美股'
    };

    // 渲染搜索结果列表
    container.innerHTML = results.map(r => `
        <div class="search-result-item" data-code="${r.name}">
            <div>
                <span class="search-result-code">${r.code}</span>
                <span class="search-result-full">${r.name}</span>
            </div>
            <span class="search-result-category">${categoryLabels[r.category] || r.category}</span>
        </div>
    `).join('');

    // 绑定每个结果项的点击事件：选中后填充输入框并加载数据
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

/**
 * 隐藏搜索结果
 * 功能：隐藏股票搜索下拉结果框
 * 参数：无
 * 返回值：无
 * 调用关系：
 *   - 被 setupEventListeners（点击外部区域）、showSearchResults 调用
 * 关键逻辑：
 *   - 将 searchResults 容器的 display 设为 none
 */
function hideSearchResults() {
    const container = document.getElementById('searchResults');
    if (container) container.style.display = 'none';
}

/**
 * 初始化指标切换标签
 * 功能：绑定技术指标（MACD/KDJ）切换标签的点击事件
 * 参数：无
 * 返回值：无
 * 调用关系：
 *   - 被 DOMContentLoaded 事件调用
 *   - 切换后调用 updateCharts 重绘图表
 * 关键逻辑：
 *   - 点击时移除所有标签的 active 类，给当前标签添加 active
 *   - 更新全局 currentIndicator 变量
 *   - 如果有数据则立即刷新图表显示对应指标
 */
function initIndicatorTabs() {
    const tabs = document.querySelectorAll('.indicator-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // 切换 active 状态
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // 更新当前指标类型并刷新图表
            currentIndicator = tab.dataset.indicator;
            if (currentData) {
                updateCharts(currentData);
            }
        });
    });
}

/**
 * 防抖函数
 * 功能：限制函数执行频率，在指定等待时间内多次调用只执行最后一次
 * 参数：
 *   - func: Function，要防抖的原始函数
 *   - wait: number，等待时间（毫秒）
 * 返回值：Function，包装后的防抖函数
 * 调用关系：被 setupEventListeners 用于按钮点击事件
 * 关键逻辑：
 *   - 每次调用时清除之前的定时器
 *   - 重新设置定时器，在 wait 时间后执行
 *   - 使用闭包保存 timeout 状态
 */
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

/**
 * 初始化 WebSocket 连接
 * 功能：建立与后端的 WebSocket 长连接，接收实时数据下载进度等推送消息
 * 参数：无
 * 返回值：无
 * 调用关系：
 *   - 被 DOMContentLoaded 事件调用
 *   - 连接断开时自动递归调用自身重连
 *   - 内部调用 handleWebSocketMessage 处理消息
 * 关键逻辑：
 *   - 生成唯一 clientId 用于服务端识别
 *   - 根据当前协议自动选择 ws:// 或 wss://
 *   - 连接成功后订阅 realtime 频道
 *   - 连接断开时 3 秒后自动重连
 */
function initWebSocket() {
    // 生成唯一客户端ID：时间戳 + 随机字符串
    const clientId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    // 根据当前页面协议选择 WebSocket 协议
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/${clientId}`;

    wsConnection = new WebSocket(wsUrl);

    // 连接建立后订阅 realtime 频道
    wsConnection.onopen = () => {
        console.log('WebSocket连接已建立');
        wsConnection.send(JSON.stringify({
            type: 'subscribe',
            channel: 'realtime'
        }));
    };

    // 接收消息并分发处理
    wsConnection.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('解析WebSocket消息失败:', e);
        }
    };

    // 连接关闭时自动重连
    wsConnection.onclose = () => {
        console.log('WebSocket连接已关闭，尝试重新连接...');
        setTimeout(initWebSocket, 3000);
    };

    wsConnection.onerror = (error) => {
        console.error('WebSocket连接错误:', error);
    };
}

/**
 * 处理 WebSocket 消息
 * 功能：根据消息类型分发处理不同的 WebSocket 推送内容
 * 参数：
 *   - message: Object，WebSocket 消息对象，包含 type 和 data 字段
 * 返回值：无
 * 调用关系：
 *   - 被 initWebSocket 的 onmessage 回调调用
 *   - 内部调用 handleDownloadProgress 处理下载进度
 * 关键逻辑：
 *   - pong: 心跳响应，无需处理
 *   - subscribed: 订阅确认，仅日志输出
 *   - refresh_needed: 数据刷新通知（当前未实现具体逻辑）
 *   - download_progress: 数据下载进度，更新进度条UI
 */
function handleWebSocketMessage(message) {
    switch (message.type) {
        case 'pong':
            // 心跳响应，无需处理
            break;
        case 'subscribed':
            console.log('已订阅频道:', message.channel);
            break;
        case 'refresh_needed':
            // 数据刷新通知，可在此触发数据重载
            break;
        case 'download_progress':
            // 处理数据下载进度更新
            handleDownloadProgress(message.data);
            break;
    }
}

/**
 * 处理数据下载进度
 * 功能：根据 WebSocket 推送的进度数据更新进度条UI
 * 参数：
 *   - data: Object，进度数据，包含 progress、step、message、status、new_data_available 等字段
 * 返回值：无
 * 调用关系：
 *   - 被 handleWebSocketMessage 调用（当消息类型为 download_progress 时）
 *   - 下载完成后调用 loadData 刷新数据
 * 关键逻辑：
 *   - 实时更新进度条宽度、步骤文本和百分比
 *   - completed 状态：如有新数据则清空缓存并刷新，否则 2 秒后隐藏
 *   - error 状态：3 秒后自动隐藏进度框
 *   - 进度框显示期间用户可手动关闭
 */
function handleDownloadProgress(data) {
    const progressBox = document.getElementById('progressBox');
    const fill = document.getElementById('progressBoxFill');
    const step = document.getElementById('progressBoxStep');
    const percent = document.getElementById('progressBoxPercent');

    if (!progressBox || !fill || !step || !percent) return;

    // 显示进度框并更新进度条
    progressBox.style.display = 'block';
    fill.style.width = `${data.progress}%`;

    // 更新步骤描述和百分比文本
    let stepText = data.step || data.message || '--';
    step.textContent = stepText;
    percent.textContent = `${data.progress}%`;

    if (data.status === 'completed') {
        // 下载完成：如果有新数据则清空缓存并刷新
        if (data.new_data_available) {
            dataCache.clear();
            setTimeout(() => {
                loadData();
                progressBox.style.display = 'none';
            }, 500);
        } else {
            // 无新数据，2秒后隐藏进度框
            setTimeout(() => {
                progressBox.style.display = 'none';
            }, 2000);
        }
    } else if (data.status === 'error') {
        // 下载出错，3秒后隐藏进度框
        setTimeout(() => {
            progressBox.style.display = 'none';
        }, 3000);
    }
}

/**
 * 刷新数据
 * 功能：触发后端增量刷新指定股票的最新数据
 * 参数：无（从输入框读取股票代码）
 * 返回值：无（Promise<void>）
 * 调用关系：
 *   - 被 setupEventListeners 中刷新按钮点击事件调用（经 debounce 防抖）
 *   - 内部调用 showMessage 显示操作结果
 * 关键逻辑：
 *   - 校验股票代码是否为空
 *   - 调用 POST /api/v1/stocks/refresh/{stockCode} 触发后端刷新
 *   - 刷新是增量更新，只获取最新缺失的数据
 */
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

/**
 * 强制刷新数据
 * 功能：触发后端全量重新下载并对比更新指定股票的历史数据
 * 参数：无（从输入框读取股票代码）
 * 返回值：无（Promise<void>）
 * 调用关系：
 *   - 被 setupEventListeners 中强制刷新按钮点击事件调用（经 debounce 防抖）
 *   - 内部调用 showMessage 显示操作结果
 * 关键逻辑：
 *   - 校验股票代码是否为空
 *   - 弹出确认对话框，提醒用户此操作将下载完整历史数据
 *   - 调用 POST /api/v1/stocks/force-refresh/{stockCode} 触发全量刷新
 *   - 与 refreshData 的区别：强制刷新会重新下载全部历史数据并对比更新
 */
async function forceRefreshData() {
    const stockCode = document.getElementById('stockCode').value.trim();

    if (!stockCode) {
        showMessage('请先输入股票代码！', 'warning');
        return;
    }

    // 确认对话框：提醒用户此操作将下载完整历史数据
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

/**
 * 安全请求封装
 * 功能：带缓存、超时和错误处理的 fetch 封装，提升请求可靠性
 * 参数：
 *   - url: string，请求地址
 *   - options: Object，可选配置，支持 skipCache（跳过缓存）、method、headers 等
 * 返回值：Promise<any>，解析后的 JSON 数据，失败时返回 null
 * 调用关系：
 *   - 被 loadData 调用获取股票指标数据
 *   - 内部调用 getCachedData 读取缓存、setCachedData 写入缓存
 * 关键逻辑：
 *   - 优先读取缓存，缓存有效期内直接返回（可通过 skipCache 跳过）
 *   - 设置 10 秒超时，超时自动中断请求
 *   - 非 2xx 响应不抛异常，返回 null 并输出警告
 *   - 响应非有效 JSON 时返回 null
 */
function safeFetch(url, options = {}) {
    const cacheKey = `${options.method || 'GET'}_${url}`;
    
    // 检查缓存，如果未设置 skipCache 且缓存有效则直接返回
    const cached = getCachedData(cacheKey);
    if (cached && !options.skipCache) {
        return Promise.resolve(cached);
    }

    // 设置 10 秒请求超时
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

/**
 * 获取缓存数据
 * 功能：根据键读取缓存数据，检查是否过期
 * 参数：
 *   - key: string，缓存键
 * 返回值：any | null，缓存数据或 null（已过期/不存在）
 * 调用关系：被 safeFetch 调用
 * 关键逻辑：
 *   - 检查缓存时间戳，超过 CACHE_TTL（30秒）视为过期
 *   - 过期时自动删除该缓存项
 */
function getCachedData(key) {
    const cached = dataCache.get(key);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        return cached.data;
    }
    dataCache.delete(key);
    return null;
}

/**
 * 设置缓存数据
 * 功能：将请求结果存入缓存，附带当前时间戳
 * 参数：
 *   - key: string，缓存键
 *   - data: any，要缓存的数据
 * 返回值：无
 * 调用关系：被 safeFetch 调用
 * 关键逻辑：
 *   - 使用 Map 存储，值为 { data, timestamp } 结构
 *   - timestamp 用于后续判断缓存是否过期
 */
function setCachedData(key, data) {
    dataCache.set(key, { data, timestamp: Date.now() });
}

/**
 * ============================================================
 * 消息提示系统全局变量
 * ============================================================
 */

/** 全局消息计数器，用于计算新消息框的垂直偏移位置 */
let messageOffsetIndex = 0;

/** 当前显示中的消息框集合，用于动态排列位置 */
const activeMessages = new Set();

/**
 * 显示消息提示
 * 功能：在页面右上角显示一个带动画的浮动消息提示框，支持多种类型
 * 参数：
 *   - message: string，要显示的消息文本
 *   - type: string，消息类型，可选 'info'/'success'/'error'/'warning'，默认 'info'
 * 返回值：无
 * 调用关系：
 *   - 被 loadData、refreshData、forceRefreshData 等多个函数调用
 *   - 内部调用 rearrangeMessages 在消息关闭后重新排列
 * 关键逻辑：
 *   - 根据类型显示不同颜色的渐变背景
 *   - 多个消息框垂直堆叠，间距 70px
 *   - 显示 3.5 秒后自动滑出消失
 *   - 消息关闭后重新计算剩余消息的位置
 */
function showMessage(message, type = 'info') {
    const msgDiv = document.createElement('div');
    const offsetIndex = messageOffsetIndex++;
    activeMessages.add(msgDiv);

    // 计算垂直偏移：每个消息框向下偏移 70px，避免重叠
    const topOffset = 24 + offsetIndex * 70;

    // 根据消息类型设置不同的渐变背景色
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

    // 3.5秒后自动移除消息框
    setTimeout(() => {
        msgDiv.style.animation = 'slideOut 0.4s ease';
        setTimeout(() => {
            msgDiv.remove();
            activeMessages.delete(msgDiv);
            // 重新排列剩余的消息框，消除空隙
            rearrangeMessages();
        }, 400);
    }, 3500);
}

/**
 * 重新排列消息框
 * 功能：当有消息框关闭后，重新计算所有活跃消息框的位置
 * 参数：无
 * 返回值：无
 * 调用关系：被 showMessage 在消息关闭后调用
 * 关键逻辑：
 *   - 遍历 activeMessages 集合，按索引重新计算 top 位置
 *   - 更新 messageOffsetIndex 为当前活跃消息数量
 *   - 确保消息框紧密排列，中间无空隙
 */
function rearrangeMessages() {
    const messages = Array.from(activeMessages);
    messages.forEach((msg, index) => {
        msg.style.top = `${24 + index * 70}px`;
    });
    messageOffsetIndex = messages.length;
}

/**
 * 计算移动平均线（MA）
 * 功能：计算指定周期的简单移动平均线（SMA）
 * 参数：
 *   - dayCount: number，移动平均周期（如 5、10、20）
 *   - data: Array<Object>，K线数据数组，每个元素需包含 close_price 字段
 * 返回值：Array<string|number>，计算结果数组，前 dayCount-1 个为 '-'，其余为保留两位小数的均价
 * 调用关系：被 updateCharts 调用，用于计算 MA5/MA10/MA20
 * 关键逻辑：
 *   - 前 dayCount-1 天数据不足，用 '-' 填充
 *   - 从第 dayCount 天开始，取前 dayCount 天收盘价的平均值
 *   - 结果保留两位小数
 */
function calculateMA(dayCount, data) {
    const result = [];
    for (let i = 0, len = data.length; i < len; i++) {
        // 数据不足 dayCount 天时，无法计算均线，用 '-' 占位
        if (i < dayCount - 1) {
            result.push('-');
            continue;
        }
        // 累加前 dayCount 天的收盘价
        let sum = 0;
        for (let j = 0; j < dayCount; j++) {
            sum += parseFloat(data[i - j].close_price);
        }
        // 计算平均值并保留两位小数
        result.push((sum / dayCount).toFixed(2));
    }
    return result;
}

/**
 * 初始化主图表
 * 功能：使用 ECharts 初始化股票K线图，绑定交互事件和窗口自适应
 * 参数：无
 * 返回值：无
 * 调用关系：
 *   - 被 DOMContentLoaded 事件调用
 *   - 内部调用 showMarkPopupMenu 显示标记菜单
 *   - 窗口 resize 时自动调整图表大小
 * 关键逻辑：
 *   - 初始化时显示"正在加载数据..."的空状态
 *   - 图表分为上下两个区域：上方 K 线（55%高度），下方指标（18%高度）
 *   - 支持左键点击 K 线打开标记菜单
 *   - 支持右键点击图表任意位置打开标记菜单
 *   - 监听窗口 resize 自动调整图表尺寸
 */
function initChart() {
    const dom = document.getElementById('mainChart');

    if (dom) {
        mainChart = echarts.init(dom);

        // 空状态配置：数据未加载时显示提示文字
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

        // 左键点击 K 线：打开标记菜单
        mainChart.on('click', (params) => {
            if (params.componentType === 'series' && params.seriesName === 'K线') {
                showMarkPopupMenu(params);
            }
        });

        // 右键点击图表：通过像素坐标转换为数据索引，打开标记菜单
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

    // 窗口大小变化时自动调整图表尺寸
    window.addEventListener('resize', () => {
        mainChart && mainChart.resize();
    });
}

/**
 * 显示标记弹出菜单
 * 功能：在图表点击位置显示买入/卖出/清除的标记操作菜单
 * 参数：
 *   - params: Object，包含 dataIndex（数据索引）和 event（鼠标事件信息）
 * 返回值：无
 * 调用关系：
 *   - 被 initChart 中的 click 和 contextmenu 事件调用
 *   - 被 initMarkPopupMenu 中的事件处理调用
 * 关键逻辑：
 *   - 从 currentData 获取对应日期的数据，构建 markPopupTarget
 *   - 计算菜单显示位置，默认在点击点右下方
 *   - 边界检测：菜单超出窗口时自动调整到左侧或上方
 *   - 使用 fixed 定位，通过 clientX/clientY 确定位置
 */
function showMarkPopupMenu(params) {
    const menu = document.getElementById('markPopupMenu');
    if (!menu) return;

    // 提取日期并格式化为 yyyy-MM-dd，构建标记目标对象
    const dateStr = currentData[params.dataIndex].datetime;
    const date = new Date(dateStr).toISOString().split('T')[0];
    markPopupTarget = { index: params.dataIndex, dataIndex: params.dataIndex, date: date };

    // 获取图表位置和鼠标坐标
    const chartRect = document.getElementById('mainChart').getBoundingClientRect();
    const eventX = params.event?.event?.clientX || chartRect.left + chartRect.width / 2;
    const eventY = params.event?.event?.clientY || chartRect.top + chartRect.height / 2;

    // 默认在点击位置右下方显示
    let left = eventX + 10;
    let top = eventY - 20;

    // 边界检测：防止菜单超出窗口右边界
    if (left + 150 > window.innerWidth) left = eventX - 160;
    // 边界检测：防止菜单超出窗口下边界
    if (top + 120 > window.innerHeight) top = eventY - 120;

    // 设置菜单位置并显示
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.style.display = 'flex';
}

/**
 * 加载股票数据
 * 功能：核心数据加载函数，获取股票K线数据、指标数据，处理数据缺失和后台下载
 * 参数：无（从页面输入框读取股票代码和日期范围）
 * 返回值：无（Promise<void>）
 * 调用关系：
 *   - 被 setupEventListeners（获取按钮）、DOMContentLoaded、showSearchResults 调用
 *   - 被 handleDownloadProgress（下载完成后）调用
 *   - 内部调用 safeFetch、loadMarksFromDB、updateCharts、showMessage
 * 关键逻辑：
 *   - 从输入框获取股票代码和日期范围
 *   - 优先读取缓存，支持新旧两种接口返回结构（数组或 {data, missing_ranges}）
 *   - 检测到数据缺失时启动后台异步下载，同时显示已有数据
 *   - 数据为空时触发同步下载
 *   - 加载完成后从数据库读取用户标记并渲染图表
 */
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

            // 显示进度框，提示用户正在下载
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

        // 无缺失或旧接口逻辑：数据为空时触发同步下载
        if (!data || data.length === 0) {
            showMessage('正在从真实数据源获取数据，请稍候...', 'info');
            await safeFetch(`/api/v1/stocks/fetch/${stockCode}`, {
                method: 'POST',
                skipCache: true
            });
            data = await safeFetch(url, { skipCache: true });
            if (!Array.isArray(data)) data = data.data || [];
        }

        // 数据加载成功，更新全局状态并渲染图表
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

/**
 * 获取指标图表配置
 * 功能：根据指标类型（MACD/KDJ）返回对应的 ECharts 系列配置
 * 参数：
 *   - indicatorType: string，指标类型，'macd' 或 'kdj'
 *   - data: Array<Object>，股票数据数组，包含 macd/macd_signal/macd_histogram 或 kdj_k/kdj_d/kdj_j 字段
 * 返回值：Object，包含 legendData（图例数组）和 series（ECharts 系列配置数组）
 * 调用关系：被 updateCharts 调用，用于构建指标区域的图表配置
 * 关键逻辑：
 *   - MACD：包含柱状图（MACD 柱状线，红涨绿跌）和两条折线（DIF、DEA）
 *   - KDJ：包含三条折线（K、D、J）
 *   - 所有系列均绑定到第二个 grid（gridIndex: 1）和第二个 y 轴（yAxisIndex: 1）
 *   - 未知类型默认返回 MACD 配置
 */
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
                        // MACD 柱状线颜色：正值红色，负值绿色
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

    // 未知类型默认返回 MACD 配置
    return indicatorConfigs[indicatorType] || indicatorConfigs.macd;
}

/**
 * 更新图表
 * 功能：核心图表渲染函数，根据数据构建完整的 ECharts 配置并渲染K线图、均线、成交量和指标
 * 参数：
 *   - data: Array<Object>，股票K线数据数组
 * 返回值：无
 * 调用关系：
 *   - 被 loadData、initMarkPopupMenu、initSignalToggle、initIndicatorTabs 调用
 *   - 内部调用 calculateMA 计算均线、getIndicatorSeries 获取指标配置
 * 关键逻辑：
 *   - 构建双 grid 布局：上方 K 线+均线（55%），下方成交量+指标（18%）
 *   - K 线颜色：涨（绿色 #22c55e）跌（红色 #ef4444）—— A股传统配色
 *   - 成交量颜色跟随 K 线涨跌
 *   - 叠加用户手动标记（买入/卖出三角形标记）
 *   - 支持 dataZoom 缩放和 tooltip 联动
 */
function updateCharts(data) {
    if (!data || data.length === 0 || !mainChart) {
        return;
    }

    const sortedData = data;
    // 提取日期用于 X 轴显示
    const dates = sortedData.map(d => new Date(d.datetime).toLocaleDateString('zh-CN'));

    // 构建 K 线数据：[开盘, 收盘, 最低, 最高]
    const klines = sortedData.map(d => [d.open_price, d.close_price, d.low_price, d.high_price]);
    // 构建成交量数据
    const volumes = sortedData.map(d => [d.volume]);

    // 计算三条移动平均线
    const ma5 = calculateMA(5, sortedData);
    const ma10 = calculateMA(10, sortedData);
    const ma20 = calculateMA(20, sortedData);

    // 获取当前选中指标（MACD/KDJ）的系列配置
    const indicatorSeries = getIndicatorSeries(currentIndicator, sortedData);

    // 构建 ECharts 完整配置
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
        // 双 grid 布局：上方 K 线区域，下方指标区域
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
        // 内置缩放和底部滑块
        dataZoom: [
            { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
            { show: true, xAxisIndex: [0, 1], type: 'slider', bottom: 10, start: 0, end: 100 }
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                data: klines,
                // A股配色：涨绿跌红
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
                    // 成交量颜色跟随 K 线涨跌：收盘 >= 开盘为绿色，否则红色
                    color: function(params) {
                        const dataIndex = params.dataIndex;
                        return klines[dataIndex][1] >= klines[dataIndex][0] ? 'rgba(34, 197, 94, 0.6)' : 'rgba(239, 68, 68, 0.6)';
                    }
                }
            },
            // 展开指标系列配置（MACD 或 KDJ）
            ...indicatorSeries.series
        ]
    };

    // 渲染用户手动标记（买入/卖出三角形），始终显示不依赖信号开关
    if (marks.size > 0) {
        const markSeriesData = [];
        marks.forEach((mark, index) => {
            if (index < sortedData.length) {
                const d = sortedData[index];
                const isBuy = mark.type === 'buy';
                markSeriesData.push({
                    name: isBuy ? '买入' : '卖出',
                    // 买入标记在最低价下方，卖出标记在最高价上方
                    value: [index, isBuy ? d.low_price : d.high_price],
                    symbol: isBuy ? 'triangle' : 'triangle',
                    symbolRotate: isBuy ? 0 : 180,  // 买入正三角，卖出倒三角
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

        // 将标记系列添加到图表中
        if (markSeriesData.length > 0) {
            option.series.push({
                name: '标记',
                type: 'scatter',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: markSeriesData,
                zlevel: 10,  // 确保标记在最上层
                emphasis: {
                    scale: 1.5
                }
            });
        }
    }

    // 应用配置到图表（true 表示不合并，完全替换）
    mainChart.setOption(option, true);
}