document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('trainForm').addEventListener('submit', trainModel);
    document.getElementById('predictBtn').addEventListener('click', makePrediction);
}

async function trainModel(e) {
    e.preventDefault();
    
    const stockCode = document.getElementById('trainStockCode').value;
    const modelName = document.getElementById('modelName').value;
    const modelType = document.getElementById('modelType').value;
    const trainSize = parseFloat(document.getElementById('trainSize').value);
    
    const statusDiv = document.getElementById('trainingStatus');
    statusDiv.style.display = 'block';
    statusDiv.className = 'status-message';
    statusDiv.textContent = '训练中...';
    
    try {
        const response = await fetch('/api/v1/ml/train', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                stock_code: stockCode,
                model_name: modelName,
                model_type: modelType,
                train_size: trainSize
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            statusDiv.className = 'status-message success';
            statusDiv.textContent = `训练完成！准确率: ${(result.accuracy * 100).toFixed(2)}%`;
            loadModels();
        } else {
            const error = await response.json();
            statusDiv.className = 'status-message error';
            statusDiv.textContent = error.detail || '训练失败';
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = '训练失败: ' + error.message;
    }
}

async function loadModels() {
    try {
        const response = await fetch('/api/v1/ml/models');
        const models = await response.json();
        displayModels(models);
        updateModelSelect(models);
    } catch (error) {
        console.error('加载模型失败:', error);
    }
}

function displayModels(models) {
    const container = document.getElementById('modelsList');
    if (!models || models.length === 0) {
        container.innerHTML = '<p class="empty-state">暂无模型</p>';
        return;
    }

    container.innerHTML = models.map(model => `
        <div class="model-item">
            <div class="model-info">
                <h4>${model.model_name}</h4>
                <p>股票: ${model.stock_code} | 类型: ${model.model_type}</p>
                <p>准确率: ${(model.accuracy * 100).toFixed(2)}% | 创建时间: ${new Date(model.created_at).toLocaleDateString()}</p>
            </div>
            <button class="btn btn-danger" onclick="deleteModel(${model.id})">删除</button>
        </div>
    `).join('');
}

function updateModelSelect(models) {
    const select = document.getElementById('predictModel');
    select.innerHTML = '<option value="">-- 请选择模型 --</option>';
    models.forEach(model => {
        select.innerHTML += `<option value="${model.id}">${model.model_name} (${model.stock_code})</option>`;
    });
}

async function deleteModel(id) {
    if (!confirm('确定要删除这个模型吗？')) return;
    
    try {
        await fetch(`/api/v1/ml/models/${id}`, { method: 'DELETE' });
        loadModels();
    } catch (error) {
        console.error('删除模型失败:', error);
    }
}

async function makePrediction() {
    const modelId = document.getElementById('predictModel').value;
    const stockCode = document.getElementById('predictStock').value;
    
    if (!modelId) {
        alert('请先选择一个模型');
        return;
    }
    
    try {
        const response = await fetch(`/api/v1/ml/predict?model_id=${modelId}&stock_code=${stockCode}`, {
            method: 'POST'
        });
        const result = await response.json();
        displayPrediction(result);
    } catch (error) {
        console.error('预测失败:', error);
    }
}

function displayPrediction(result) {
    const container = document.getElementById('predictionResult');
    const change = result.predicted_price - result.current_price;
    const changePercent = ((change / result.current_price) * 100).toFixed(2);
    const direction = change >= 0 ? 'up' : 'down';
    const arrow = change >= 0 ? '↑' : '↓';
    
    container.style.display = 'block';
    container.innerHTML = `
        <h3>预测结果</h3>
        <p>当前价格: ${result.current_price.toFixed(2)}</p>
        <p>预测价格: <span class="prediction-value ${direction}">${result.predicted_price.toFixed(2)}</span></p>
        <p>预测变动: <span class="prediction-value ${direction}">${arrow} ${Math.abs(changePercent)}%</span></p>
        <p style="color: #a0aec0; font-size: 12px;">预测时间: ${new Date().toLocaleString()}</p>
    `;
}
