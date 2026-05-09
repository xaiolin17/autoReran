let priceChart, volumeChart, kdjChart, macdChart;

function initCharts() {
    const chartOptions = {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: {
                labels: {
                    color: '#a0aec0'
                }
            }
        },
        scales: {
            x: {
                ticks: { color: '#a0aec0' },
                grid: { color: '#333a54' }
            },
            y: {
                ticks: { color: '#a0aec0' },
                grid: { color: '#333a54' }
            }
        }
    };

    const priceCtx = document.getElementById('priceChart').getContext('2d');
    priceChart = new Chart(priceCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '收盘价',
                data: [],
                borderColor: '#00ff88',
                backgroundColor: 'rgba(0, 255, 136, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: chartOptions
    });

    const volumeCtx = document.getElementById('volumeChart').getContext('2d');
    volumeChart = new Chart(volumeCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: '成交量',
                data: [],
                backgroundColor: 'rgba(78, 205, 196, 0.6)'
            }]
        },
        options: chartOptions
    });

    const kdjCtx = document.getElementById('kdjChart').getContext('2d');
    kdjChart = new Chart(kdjCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'K', data: [], borderColor: '#00ff88', tension: 0.4 },
                { label: 'D', data: [], borderColor: '#4ecdc4', tension: 0.4 },
                { label: 'J', data: [], borderColor: '#a855f7', tension: 0.4 }
            ]
        },
        options: chartOptions
    });

    const macdCtx = document.getElementById('macdChart').getContext('2d');
    macdChart = new Chart(macdCtx, {
        type: 'bar',
        data: {
            labels: [],
            datasets: [
                {
                    type: 'line',
                    label: 'MACD',
                    data: [],
                    borderColor: '#00ff88',
                    yAxisID: 'y'
                },
                {
                    type: 'line',
                    label: 'Signal',
                    data: [],
                    borderColor: '#4ecdc4',
                    yAxisID: 'y'
                },
                {
                    type: 'bar',
                    label: 'Histogram',
                    data: [],
                    backgroundColor: ctx => ctx.raw < 0 ? 'rgba(255, 107, 107, 0.6)' : 'rgba(0, 255, 136, 0.6)',
                    yAxisID: 'y'
                }
            ]
        },
        options: chartOptions
    });
}

function updateCharts(data) {
    const labels = data.map(d => d.datetime.split('T')[0]);
    const closePrices = data.map(d => d.close_price);
    const volumes = data.map(d => d.volume);
    const kdjK = data.map(d => d.kdj_k);
    const kdjD = data.map(d => d.kdj_d);
    const kdjJ = data.map(d => d.kdj_j);
    const macd = data.map(d => d.macd);
    const macdSignal = data.map(d => d.macd_signal);
    const macdHistogram = data.map(d => d.macd_histogram);

    priceChart.data.labels = labels;
    priceChart.data.datasets[0].data = closePrices;
    priceChart.update();

    volumeChart.data.labels = labels;
    volumeChart.data.datasets[0].data = volumes;
    volumeChart.update();

    kdjChart.data.labels = labels;
    kdjChart.data.datasets[0].data = kdjK;
    kdjChart.data.datasets[1].data = kdjD;
    kdjChart.data.datasets[2].data = kdjJ;
    kdjChart.update();

    macdChart.data.labels = labels;
    macdChart.data.datasets[0].data = macd;
    macdChart.data.datasets[1].data = macdSignal;
    macdChart.data.datasets[2].data = macdHistogram;
    macdChart.update();
}
