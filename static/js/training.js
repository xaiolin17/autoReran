document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('trainForm').addEventListener('submit', trainModel);
    document.getElementById('predictBtn').addEventListener('click', makePrediction);
    document.getElementById('predictSignalBtn').addEventListener('click', makeSignalPrediction);
    document.getElementById('ensemblePredictBtn').addEventListener('click', makeEnsemblePrediction);
}

async function trainModel(e) {
    e.preventDefault();
    
    const stockCode = document.getElementById('trainStockCode').value;
    const modelName = document.getElementById('modelName').value;
    const modelType = document.getElementById('modelType').value;
    const trainSize = parseFloat(document.getElementById('trainSize').value);
    const isClassification = document.querySelector('input[name="trainingMode"]:checked').value === 'classification';
    
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
                train_size: trainSize,
                is_classification: isClassification
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
                <p style="font-size: 11px; color: #718096;">Precision: ${(model.precision * 100).toFixed(1)}% | Recall: ${(model.recall * 100).toFixed(1)}% | F1: ${(model.f1_score * 100).toFixed(1)}%</p>
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
    
    updateEnsembleModelsList(models);
}

function updateEnsembleModelsList(models) {
    const container = document.getElementById('ensembleModelsList');
    if (!models || models.length === 0) {
        container.innerHTML = '<p style="color: #a0aec0; font-size: 13px;">请先训练模型</p>';
        return;
    }
    
    container.innerHTML = models.map(model => `
        <label class="checkbox-item">
            <input type="checkbox" value="${model.id}" class="model-checkbox">
            <span>${model.model_name} (${model.stock_code})</span>
            <span class="model-accuracy">准确率: ${(model.accuracy * 100).toFixed(1)}%</span>
        </label>
    `).join('');
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

async function makeSignalPrediction() {
    const modelId = document.getElementById('predictModel').value;
    const stockCode = document.getElementById('predictStock').value;
    
    if (!modelId) {
        alert('请先选择一个模型');
        return;
    }
    
    try {
        const response = await fetch(`/api/v1/ml/predict-signal?model_id=${modelId}&stock_code=${stockCode}`, {
            method: 'POST'
        });
        const result = await response.json();
        displaySignalPrediction(result);
    } catch (error) {
        console.error('信号预测失败:', error);
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

function displaySignalPrediction(result) {
    const container = document.getElementById('predictionResult');
    
    let signalClass, signalIcon, signalBg;
    switch(result.signal) {
        case 'BUY':
            signalClass = 'signal-buy';
            signalIcon = '📈';
            signalBg = 'rgba(72, 187, 120, 0.1)';
            break;
        case 'SELL':
            signalClass = 'signal-sell';
            signalIcon = '📉';
            signalBg = 'rgba(245, 101, 101, 0.1)';
            break;
        default:
            signalClass = 'signal-hold';
            signalIcon = '⏸️';
            signalBg = 'rgba(160, 174, 192, 0.1)';
    }
    
    container.style.display = 'block';
    container.innerHTML = `
        <div class="signal-card" style="background: ${signalBg}; border-radius: 12px; padding: 24px; border: 1px solid rgba(255,255,255,0.1);">
            <h3 style="margin: 0 0 16px 0; font-size: 20px;">${signalIcon} AI 交易信号</h3>
            <div class="signal-main" style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
                <div class="signal-badge ${signalClass}" style="font-size: 32px; padding: 16px 32px; border-radius: 8px; font-weight: bold;">
                    ${result.signal}
                </div>
                <div class="signal-details" style="flex: 1;">
                    <div class="signal-strength" style="margin-bottom: 12px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                            <span>信号强度</span>
                            <span>${result.signal_strength.toFixed(1)}%</span>
                        </div>
                        <div style="width: 100%; height: 8px; background: #2d3748; border-radius: 4px; overflow: hidden;">
                            <div style="width: ${result.signal_strength}%; height: 100%; background: ${result.signal === 'BUY' ? '#48bb78' : result.signal === 'SELL' ? '#f56565' : '#a0aec0'};"></div>
                        </div>
                    </div>
                    <p style="margin: 0; color: #a0aec0;">置信度: ${(result.confidence * 100).toFixed(0)}%</p>
                </div>
            </div>
            <div class="price-info" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 20px;">
                <div style="background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;">
                    <p style="color: #a0aec0; margin: 0 0 4px 0; font-size: 12px;">当前价格</p>
                    <p style="margin: 0; font-size: 18px; font-weight: bold;">${result.current_price.toFixed(2)}</p>
                </div>
                ${result.predicted_price ? `
                <div style="background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;">
                    <p style="color: #a0aec0; margin: 0 0 4px 0; font-size: 12px;">预测价格</p>
                    <p style="margin: 0; font-size: 18px; font-weight: bold;">${result.predicted_price.toFixed(2)}</p>
                </div>
                ` : ''}
                ${result.predicted_change_percent ? `
                <div style="background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;">
                    <p style="color: #a0aec0; margin: 0 0 4px 0; font-size: 12px;">预测涨跌幅</p>
                    <p style="margin: 0; font-size: 18px; font-weight: bold; color: ${result.predicted_change_percent >= 0 ? '#48bb78' : '#f56565'};">
                        ${result.predicted_change_percent >= 0 ? '+' : ''}${result.predicted_change_percent.toFixed(2)}%
                    </p>
                </div>
                ` : ''}
            </div>
            <div class="signal-explanation" style="background: rgba(0,0,0,0.2); padding: 16px; border-radius: 8px; border-left: 4px solid ${result.signal === 'BUY' ? '#48bb78' : result.signal === 'SELL' ? '#f56565' : '#a0aec0'};">
                <p style="margin: 0; color: #e2e8f0; line-height: 1.6;">${result.signal_explanation}</p>
            </div>
            ${result.technical_indicators ? `
            <div class="tech-indicators" style="margin-top: 20px;">
                <h4 style="margin: 0 0 12px 0; color: #a0aec0; font-size: 14px;">技术指标</h4>
                <div style="display: flex; flex-wrap: wrap; gap: 12px;">
                    ${Object.entries(result.technical_indicators).map(([key, value]) => `
                        <div style="background: rgba(0,0,0,0.2); padding: 8px 12px; border-radius: 6px;">
                            <span style="color: #a0aec0; font-size: 12px;">${key.toUpperCase()}:</span>
                            <span style="color: #fff; font-weight: bold; margin-left: 6px;">${typeof value === 'number' ? value.toFixed(2) : value}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}
            <p style="color: #a0aec0; font-size: 12px; margin-top: 16px;">预测时间: ${new Date(result.prediction_date).toLocaleString()}</p>
        </div>
    `;
}

async function makeEnsemblePrediction() {
    const checkboxes = document.querySelectorAll('.model-checkbox:checked');
    const modelIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    const stockCode = document.getElementById('ensembleStock').value;
    const ensembleMethod = document.querySelector('input[name="ensembleMethod"]:checked').value;
    
    if (modelIds.length === 0) {
        alert('请至少选择一个模型');
        return;
    }
    
    try {
        const response = await fetch('/api/v1/ml/ensemble-predict', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                model_ids: modelIds,
                stock_code: stockCode,
                ensemble_method: ensembleMethod
            })
        });
        
        const result = await response.json();
        displayEnsemblePrediction(result);
    } catch (error) {
        console.error('综合预测失败:', error);
    }
}

function displayEnsemblePrediction(result) {
    const container = document.getElementById('ensembleResult');
    
    let signalClass, signalIcon, signalBg;
    switch(result.final_signal) {
        case 'BUY':
            signalClass = 'signal-buy';
            signalIcon = '📈';
            signalBg = 'rgba(72, 187, 120, 0.1)';
            break;
        case 'SELL':
            signalClass = 'signal-sell';
            signalIcon = '📉';
            signalBg = 'rgba(245, 101, 101, 0.1)';
            break;
        default:
            signalClass = 'signal-hold';
            signalIcon = '⏸️';
            signalBg = 'rgba(160, 174, 192, 0.1)';
    }
    
    container.style.display = 'block';
    container.innerHTML = `
        <div class="ensemble-card">
            <div class="final-signal-card" style="background: ${signalBg}; border-radius: 12px; padding: 24px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 24px;">
                <h3 style="margin: 0 0 16px 0; font-size: 20px;">${signalIcon} 综合信号</h3>
                <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 20px;">
                    <div class="signal-badge ${signalClass}" style="font-size: 32px; padding: 16px 32px; border-radius: 8px; font-weight: bold;">
                        ${result.final_signal}
                    </div>
                    <div style="flex: 1;">
                        <div style="margin-bottom: 12px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span>信号强度</span>
                                <span>${result.final_signal_strength.toFixed(1)}%</span>
                            </div>
                            <div style="width: 100%; height: 8px; background: #2d3748; border-radius: 4px; overflow: hidden;">
                                <div style="width: ${result.final_signal_strength}%; height: 100%; background: ${result.final_signal === 'BUY' ? '#48bb78' : result.final_signal === 'SELL' ? '#f56565' : '#a0aec0'};"></div>
                            </div>
                        </div>
                        <p style="margin: 0; color: #a0aec0;">综合置信度: ${(result.confidence * 100).toFixed(0)}% | 方法: ${result.ensemble_method === 'voting' ? '投票制' : '加权制'}</p>
                    </div>
                </div>
                <div class="price-info" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 20px;">
                    <div style="background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;">
                        <p style="color: #a0aec0; margin: 0 0 4px 0; font-size: 12px;">当前价格</p>
                        <p style="margin: 0; font-size: 18px; font-weight: bold;">${result.current_price.toFixed(2)}</p>
                    </div>
                    ${result.predicted_change_percent ? `
                    <div style="background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;">
                        <p style="color: #a0aec0; margin: 0 0 4px 0; font-size: 12px;">预测涨跌幅</p>
                        <p style="margin: 0; font-size: 18px; font-weight: bold; color: ${result.predicted_change_percent >= 0 ? '#48bb78' : '#f56565'};">
                            ${result.predicted_change_percent >= 0 ? '+' : ''}${result.predicted_change_percent.toFixed(2)}%
                        </p>
                    </div>
                    ` : ''}
                </div>
                <div style="background: rgba(0,0,0,0.2); padding: 16px; border-radius: 8px; border-left: 4px solid ${result.final_signal === 'BUY' ? '#48bb78' : result.final_signal === 'SELL' ? '#f56565' : '#a0aec0'};">
                    <p style="margin: 0; color: #e2e8f0; line-height: 1.6;">${result.consensus_explanation}</p>
                </div>
                <div style="margin-top: 20px; display: flex; gap: 12px; flex-wrap: wrap;">
                    <div style="background: rgba(72, 187, 120, 0.1); padding: 8px 16px; border-radius: 6px; border: 1px solid #48bb78;">
                        看多: ${result.signal_breakdown.BUY || 0}
                    </div>
                    <div style="background: rgba(245, 101, 101, 0.1); padding: 8px 16px; border-radius: 6px; border: 1px solid #f56565;">
                        看空: ${result.signal_breakdown.SELL || 0}
                    </div>
                    <div style="background: rgba(160, 174, 192, 0.1); padding: 8px 16px; border-radius: 6px; border: 1px solid #a0aec0;">
                        看平: ${result.signal_breakdown.HOLD || 0}
                    </div>
                </div>
            </div>
            
            <h4 style="margin: 0 0 16px 0; color: #a0aec0; font-size: 16px;">📊 各模型预测详情</h4>
            <div class="model-predictions-list">
                ${result.model_predictions.map(pred => {
                    let predSignalClass, predSignalIcon;
                    switch(pred.signal) {
                        case 'BUY':
                            predSignalClass = 'signal-buy';
                            predSignalIcon = '📈';
                            break;
                        case 'SELL':
                            predSignalClass = 'signal-sell';
                            predSignalIcon = '📉';
                            break;
                        default:
                            predSignalClass = 'signal-hold';
                            predSignalIcon = '⏸️';
                    }
                    return `
                        <div class="model-prediction-item">
                            <div class="model-prediction-info">
                                <h5 style="margin: 0 0 8px 0;">${pred.model_name}</h5>
                                <p style="margin: 0; color: #a0aec0; font-size: 13px;">${pred.model_type} | 准确率: ${(pred.accuracy * 100).toFixed(1)}%</p>
                            </div>
                            <div class="model-prediction-signal">
                                <span class="small-signal-badge ${predSignalClass}">${predSignalIcon} ${pred.signal}</span>
                                <span class="signal-strength-text">${pred.signal_strength.toFixed(0)}%</span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
            <p style="color: #a0aec0; font-size: 12px; margin-top: 16px;">预测时间: ${new Date(result.prediction_date).toLocaleString()}</p>
        </div>
    `;
}
