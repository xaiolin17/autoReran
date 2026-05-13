document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    setupEventListeners();
    checkLabeledData();
});

async function checkLabeledData() {
    const stockCode = document.getElementById('trainStockCode').value.trim();
    if (!stockCode) return;
    
    try {
        const response = await fetch(`/api/v1/ml/check-labeled-data?stock_code=${stockCode}`);
        const result = await response.json();
        
        const warningBox = document.getElementById('noLabeledDataWarning');
        if (!result.has_labeled_data) {
            warningBox.style.display = 'flex';
        } else {
            warningBox.style.display = 'none';
        }
    } catch (error) {
        console.error('检查标签数据失败:', error);
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

function setupEventListeners() {
    document.getElementById('trainForm').addEventListener('submit', trainModel);
    document.getElementById('trainStockCode').addEventListener('change', checkLabeledData);
    
    const predictBtn = document.getElementById('predictBtn');
    if (predictBtn) {
        predictBtn.addEventListener('click', makePrediction);
    }
    
    const predictSignalBtn = document.getElementById('predictSignalBtn');
    if (predictSignalBtn) {
        predictSignalBtn.addEventListener('click', makeSignalPrediction);
    }
    
    const ensemblePredictBtn = document.getElementById('ensemblePredictBtn');
    if (ensemblePredictBtn) {
        ensemblePredictBtn.addEventListener('click', makeEnsemblePrediction);
    }
}

async function trainModel(e) {
    e.preventDefault();
    
    const stockCode = document.getElementById('trainStockCode').value.trim();
    const modelName = document.getElementById('modelName').value.trim();
    const modelType = document.getElementById('modelType').value;
    const trainSize = parseFloat(document.getElementById('trainSize').value);
    const isClassification = document.querySelector('input[name="trainingMode"]:checked').value === 'classification';
    
    if (!stockCode) {
        showMessage('请输入股票代码！', 'warning');
        return;
    }
    
    if (!modelName) {
        showMessage('请输入模型名称！', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`/api/v1/ml/check-labeled-data?stock_code=${stockCode}`);
        const result = await response.json();
        
        if (!result.has_labeled_data) {
            showMessage('请先在数据查看页面标记买入/卖出数据后再进行模型训练', 'warning');
            return;
        }
    } catch (error) {
        console.error('检查标签数据失败:', error);
    }
    
    const statusDiv = document.getElementById('trainingStatus');
    statusDiv.style.display = 'block';
    statusDiv.className = 'status-message info';
    statusDiv.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 20px; height: 20px; border: 3px solid rgba(0,240,255,0.2); border-top: 3px solid #00f0ff; border-radius: 50%; animation: spin 1s linear infinite;"></div>
            <span>正在训练模型，请稍候...</span>
        </div>
    `;
    
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
            statusDiv.innerHTML = `
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 20px;">✅</span>
                    <span>训练完成！准确率: <strong>${(result.accuracy * 100).toFixed(2)}%</strong></span>
                </div>
            `;
            showMessage('模型训练成功！', 'success');
            loadModels();
        } else {
            const error = await response.json();
            statusDiv.className = 'status-message error';
            statusDiv.innerHTML = `
                <div style="display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 20px;">❌</span>
                    <span>${error.detail || '训练失败，请确保已有该股票数据'}</span>
                </div>
            `;
            showMessage(error.detail || '训练失败', 'error');
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
                <span style="font-size: 20px;">❌</span>
                <span>训练失败: ${error.message}</span>
            </div>
        `;
        showMessage('训练失败: ' + error.message, 'error');
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
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">🤖</span>
                <p>还没有训练模型，<strong>先在左侧填写信息开始训练</strong>！</p>
                <p style="font-size: 13px; color: #64748b; margin-top: 8px;">💡 提示：先确保已有该股票数据</p>
            </div>
        `;
        return;
    }

    container.innerHTML = models.map(model => `
        <div class="model-item">
            <div class="model-info">
                <h4>${model.model_name}</h4>
                <p>股票: ${model.stock_code} | 类型: ${model.model_type}</p>
                <p>准确率: <strong style="color: #00f0ff;">${(model.accuracy * 100).toFixed(2)}%</strong> | 创建时间: ${new Date(model.created_at).toLocaleDateString()}</p>
                <p style="font-size: 11px; color: #64748b;">Precision: ${(model.precision * 100).toFixed(1)}% | Recall: ${(model.recall * 100).toFixed(1)}% | F1: ${(model.f1_score * 100).toFixed(1)}%</p>
            </div>
            <button class="btn btn-danger" onclick="deleteModel(${model.id})">删除</button>
        </div>
    `).join('');
}

function updateModelSelect(models) {
    const predictSelect = document.getElementById('predictModel');
    if (predictSelect) {
        predictSelect.innerHTML = '<option value="">-- 请选择模型 --</option>';
        models.forEach(model => {
            predictSelect.innerHTML += `<option value="${model.id}">${model.model_name} (${model.stock_code})</option>`;
        });
    }
    
    const backtestSelect = document.getElementById('backtestModelSelect');
    if (backtestSelect) {
        backtestSelect.innerHTML = '<option value="">-- 请选择模型用于回测 --</option>';
        models.forEach(model => {
            backtestSelect.innerHTML += `<option value="${model.id}">${model.model_name} - ${model.model_type} (准确率: ${(model.accuracy * 100).toFixed(1)}%)</option>`;
        });
    }
    
    updateEnsembleModelsList(models);
}

function updateEnsembleModelsList(models) {
    const container = document.getElementById('ensembleModelsList');
    if (!container) return;
    
    if (!models || models.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="padding: 30px 20px;">
                <span class="empty-state-icon" style="font-size: 36px;">📊</span>
                <p style="font-size: 14px;">请先训练至少1个模型才能进行综合预测</p>
            </div>
        `;
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
        showMessage('模型已删除', 'success');
        loadModels();
    } catch (error) {
        console.error('删除模型失败:', error);
        showMessage('删除失败', 'error');
    }
}

async function makePrediction() {
    const modelId = document.getElementById('predictModel').value;
    const stockCode = document.getElementById('predictStock').value.trim();
    
    if (!modelId) {
        showMessage('请先选择一个模型！', 'warning');
        return;
    }
    
    if (!stockCode) {
        showMessage('请输入股票代码！', 'warning');
        return;
    }
    
    const container = document.getElementById('predictionResult');
    container.style.display = 'block';
    container.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <div style="display: inline-block; width: 40px; height: 40px; border: 4px solid rgba(0,240,255,0.2); border-top: 4px solid #00f0ff; border-radius: 50%; animation: spin 1s linear infinite;"></div>
            <p style="margin-top: 16px; color: #94a3b8;">正在预测...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/v1/ml/predict?model_id=${modelId}&stock_code=${stockCode}`, {
            method: 'POST'
        });
        const result = await response.json();
        displayPrediction(result);
        showMessage('预测完成！', 'success');
    } catch (error) {
        console.error('预测失败:', error);
        showMessage('预测失败: ' + error.message, 'error');
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">⚠️</span>
                <p>预测失败，请确保已有该股票数据</p>
            </div>
        `;
    }
}

async function makeSignalPrediction() {
    const modelId = document.getElementById('predictModel').value;
    const stockCode = document.getElementById('predictStock').value.trim();
    
    if (!modelId) {
        showMessage('请先选择一个模型！', 'warning');
        return;
    }
    
    if (!stockCode) {
        showMessage('请输入股票代码！', 'warning');
        return;
    }
    
    const container = document.getElementById('predictionResult');
    container.style.display = 'block';
    container.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <div style="display: inline-block; width: 40px; height: 40px; border: 4px solid rgba(0,240,255,0.2); border-top: 4px solid #00f0ff; border-radius: 50%; animation: spin 1s linear infinite;"></div>
            <p style="margin-top: 16px; color: #94a3b8;">正在生成信号...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/v1/ml/predict-signal?model_id=${modelId}&stock_code=${stockCode}`, {
            method: 'POST'
        });
        const result = await response.json();
        displaySignalPrediction(result);
        showMessage('信号生成完成！', 'success');
    } catch (error) {
        console.error('信号预测失败:', error);
        showMessage('信号预测失败: ' + error.message, 'error');
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">⚠️</span>
                <p>信号生成失败，请确保已有该股票数据</p>
            </div>
        `;
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
        <h3 style="margin-bottom: 24px; font-size: 20px;">📊 预测结果</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
            <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);">
                <p style="color: #94a3b8; font-size: 13px; margin-bottom: 8px;">当前价格</p>
                <p style="font-size: 24px; font-weight: bold;">¥${result.current_price.toFixed(2)}</p>
            </div>
            <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);">
                <p style="color: #94a3b8; font-size: 13px; margin-bottom: 8px;">预测价格</p>
                <p class="prediction-value ${direction}" style="font-size: 32px; margin: 0;">¥${result.predicted_price.toFixed(2)}</p>
            </div>
            <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);">
                <p style="color: #94a3b8; font-size: 13px; margin-bottom: 8px;">预测变动</p>
                <p class="prediction-value ${direction}" style="font-size: 32px; margin: 0;">${arrow} ${Math.abs(changePercent)}%</p>
            </div>
        </div>
        <p style="color: #64748b; font-size: 12px; margin-top: 24px; text-align: center;">预测时间: ${new Date().toLocaleString()}</p>
    `;
}

function displaySignalPrediction(result) {
    const container = document.getElementById('predictionResult');
    
    let signalClass, signalIcon, signalBg;
    switch(result.signal) {
        case 'BUY':
            signalClass = 'signal-buy';
            signalIcon = '📈';
            signalBg = 'rgba(16, 185, 129, 0.1)';
            break;
        case 'SELL':
            signalClass = 'signal-sell';
            signalIcon = '📉';
            signalBg = 'rgba(239, 68, 68, 0.1)';
            break;
        default:
            signalClass = 'signal-hold';
            signalIcon = '⏸️';
            signalBg = 'rgba(148, 163, 184, 0.1)';
    }
    
    container.style.display = 'block';
    container.innerHTML = `
        <div class="signal-card" style="background: ${signalBg}; border-radius: 16px; padding: 32px; border: 1px solid rgba(255,255,255,0.1);">
            <h3 style="margin: 0 0 20px 0; font-size: 22px; letter-spacing: -0.5px;">${signalIcon} AI 交易信号</h3>
            <div style="display: flex; align-items: center; gap: 24px; margin-bottom: 24px; flex-wrap: wrap;">
                <div class="signal-badge ${signalClass}" style="font-size: 36px; padding: 20px 40px; border-radius: 12px; font-weight: bold;">
                    ${result.signal}
                </div>
                <div style="flex: 1; min-width: 250px;">
                    <div style="margin-bottom: 16px;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                            <span style="color: #94a3b8;">信号强度</span>
                            <span style="font-size: 18px; font-weight: 600;">${result.signal_strength.toFixed(1)}%</span>
                        </div>
                        <div style="width: 100%; height: 10px; background: rgba(0,0,0,0.3); border-radius: 6px; overflow: hidden;">
                            <div style="width: ${result.signal_strength}%; height: 100%; background: ${result.signal === 'BUY' ? '#10b981' : result.signal === 'SELL' ? '#ef4444' : '#94a3b8'}; transition: width 0.5s ease;"></div>
                        </div>
                    </div>
                    <p style="margin: 0; color: #94a3b8; font-size: 15px;">置信度: <strong style="color: #00f0ff;">${(result.confidence * 100).toFixed(0)}%</strong></p>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 24px;">
                <div style="background: rgba(0,0,0,0.25); padding: 16px; border-radius: 12px;">
                    <p style="color: #94a3b8; margin: 0 0 8px 0; font-size: 12px;">当前价格</p>
                    <p style="margin: 0; font-size: 20px; font-weight: bold;">¥${result.current_price.toFixed(2)}</p>
                </div>
                ${result.predicted_price ? `
                <div style="background: rgba(0,0,0,0.25); padding: 16px; border-radius: 12px;">
                    <p style="color: #94a3b8; margin: 0 0 8px 0; font-size: 12px;">预测价格</p>
                    <p style="margin: 0; font-size: 20px; font-weight: bold;">¥${result.predicted_price.toFixed(2)}</p>
                </div>
                ` : ''}
                ${result.predicted_change_percent ? `
                <div style="background: rgba(0,0,0,0.25); padding: 16px; border-radius: 12px;">
                    <p style="color: #94a3b8; margin: 0 0 8px 0; font-size: 12px;">预测涨跌幅</p>
                    <p style="margin: 0; font-size: 20px; font-weight: bold; color: ${result.predicted_change_percent >= 0 ? '#10b981' : '#ef4444'};">
                        ${result.predicted_change_percent >= 0 ? '+' : ''}${result.predicted_change_percent.toFixed(2)}%
                    </p>
                </div>
                ` : ''}
            </div>
            <div style="background: rgba(0,0,0,0.25); padding: 20px; border-radius: 12px; border-left: 4px solid ${result.signal === 'BUY' ? '#10b981' : result.signal === 'SELL' ? '#ef4444' : '#94a3b8'};">
                <p style="margin: 0; color: #e2e8f0; line-height: 1.7; font-size: 15px;">${result.signal_explanation}</p>
            </div>
            ${result.technical_indicators ? `
            <div style="margin-top: 24px;">
                <h4 style="margin: 0 0 16px 0; color: #94a3b8; font-size: 14px;">📈 技术指标</h4>
                <div style="display: flex; flex-wrap: wrap; gap: 12px;">
                    ${Object.entries(result.technical_indicators).map(([key, value]) => `
                        <div style="background: rgba(0,0,0,0.25); padding: 10px 16px; border-radius: 10px;">
                            <span style="color: #94a3b8; font-size: 12px;">${key.toUpperCase()}:</span>
                            <span style="color: #fff; font-weight: bold; margin-left: 8px;">${typeof value === 'number' ? value.toFixed(2) : value}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}
            <p style="color: #64748b; font-size: 12px; margin-top: 24px;">预测时间: ${new Date(result.prediction_date).toLocaleString()}</p>
        </div>
    `;
}

async function makeEnsemblePrediction() {
    const checkboxes = document.querySelectorAll('.model-checkbox:checked');
    const modelIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    const stockCode = document.getElementById('ensembleStock').value.trim();
    const ensembleMethod = document.querySelector('input[name="ensembleMethod"]:checked').value;
    
    if (modelIds.length === 0) {
        showMessage('请至少选择一个模型！', 'warning');
        return;
    }
    
    if (!stockCode) {
        showMessage('请输入股票代码！', 'warning');
        return;
    }
    
    const container = document.getElementById('ensembleResult');
    container.style.display = 'block';
    container.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <div style="display: inline-block; width: 40px; height: 40px; border: 4px solid rgba(0,240,255,0.2); border-top: 4px solid #00f0ff; border-radius: 50%; animation: spin 1s linear infinite;"></div>
            <p style="margin-top: 16px; color: #94a3b8;">正在进行综合预测...</p>
        </div>
    `;
    
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
        showMessage('综合预测完成！', 'success');
    } catch (error) {
        console.error('综合预测失败:', error);
        showMessage('综合预测失败: ' + error.message, 'error');
        container.innerHTML = `
            <div class="empty-state">
                <span class="empty-state-icon">⚠️</span>
                <p>综合预测失败，请确保已有该股票数据</p>
            </div>
        `;
    }
}

function displayEnsemblePrediction(result) {
    const container = document.getElementById('ensembleResult');
    
    let signalClass, signalIcon, signalBg;
    switch(result.final_signal) {
        case 'BUY':
            signalClass = 'signal-buy';
            signalIcon = '📈';
            signalBg = 'rgba(16, 185, 129, 0.1)';
            break;
        case 'SELL':
            signalClass = 'signal-sell';
            signalIcon = '📉';
            signalBg = 'rgba(239, 68, 68, 0.1)';
            break;
        default:
            signalClass = 'signal-hold';
            signalIcon = '⏸️';
            signalBg = 'rgba(148, 163, 184, 0.1)';
    }
    
    container.style.display = 'block';
    container.innerHTML = `
        <div class="ensemble-card">
            <div class="final-signal-card" style="background: ${signalBg}; border-radius: 16px; padding: 32px; border: 1px solid rgba(255,255,255,0.1); margin-bottom: 28px;">
                <h3 style="margin: 0 0 24px 0; font-size: 24px; letter-spacing: -0.5px;">${signalIcon} 综合信号</h3>
                <div style="display: flex; align-items: center; gap: 28px; margin-bottom: 28px; flex-wrap: wrap;">
                    <div class="signal-badge ${signalClass}" style="font-size: 36px; padding: 20px 40px; border-radius: 12px; font-weight: bold;">
                        ${result.final_signal}
                    </div>
                    <div style="flex: 1; min-width: 250px;">
                        <div style="margin-bottom: 16px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                                <span style="color: #94a3b8;">信号强度</span>
                                <span style="font-size: 18px; font-weight: 600;">${result.final_signal_strength.toFixed(1)}%</span>
                            </div>
                            <div style="width: 100%; height: 10px; background: rgba(0,0,0,0.3); border-radius: 6px; overflow: hidden;">
                                <div style="width: ${result.final_signal_strength}%; height: 100%; background: ${result.final_signal === 'BUY' ? '#10b981' : result.final_signal === 'SELL' ? '#ef4444' : '#94a3b8'}; transition: width 0.5s ease;"></div>
                            </div>
                        </div>
                        <p style="margin: 0; color: #94a3b8; font-size: 15px;">综合置信度: <strong style="color: #00f0ff;">${(result.confidence * 100).toFixed(0)}%</strong> | 方法: ${result.ensemble_method === 'voting' ? '投票制' : '加权制'}</p>
                    </div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 16px; margin-bottom: 24px;">
                    <div style="background: rgba(0,0,0,0.25); padding: 16px; border-radius: 12px;">
                        <p style="color: #94a3b8; margin: 0 0 8px 0; font-size: 12px;">当前价格</p>
                        <p style="margin: 0; font-size: 20px; font-weight: bold;">¥${result.current_price.toFixed(2)}</p>
                    </div>
                    ${result.predicted_change_percent ? `
                    <div style="background: rgba(0,0,0,0.25); padding: 16px; border-radius: 12px;">
                        <p style="color: #94a3b8; margin: 0 0 8px 0; font-size: 12px;">预测涨跌幅</p>
                        <p style="margin: 0; font-size: 20px; font-weight: bold; color: ${result.predicted_change_percent >= 0 ? '#10b981' : '#ef4444'};">
                            ${result.predicted_change_percent >= 0 ? '+' : ''}${result.predicted_change_percent.toFixed(2)}%
                        </p>
                    </div>
                    ` : ''}
                </div>
                <div style="background: rgba(0,0,0,0.25); padding: 20px; border-radius: 12px; border-left: 4px solid ${result.final_signal === 'BUY' ? '#10b981' : result.final_signal === 'SELL' ? '#ef4444' : '#94a3b8'};">
                    <p style="margin: 0; color: #e2e8f0; line-height: 1.7; font-size: 15px;">${result.consensus_explanation}</p>
                </div>
                <div style="margin-top: 24px; display: flex; gap: 16px; flex-wrap: wrap;">
                    <div style="background: rgba(16, 185, 129, 0.15); padding: 12px 24px; border-radius: 10px; border: 1px solid #10b981;">
                        📈 看多: <strong>${result.signal_breakdown.BUY || 0}</strong>
                    </div>
                    <div style="background: rgba(239, 68, 68, 0.15); padding: 12px 24px; border-radius: 10px; border: 1px solid #ef4444;">
                        📉 看空: <strong>${result.signal_breakdown.SELL || 0}</strong>
                    </div>
                    <div style="background: rgba(148, 163, 184, 0.15); padding: 12px 24px; border-radius: 10px; border: 1px solid #94a3b8;">
                        ⏸️ 看平: <strong>${result.signal_breakdown.HOLD || 0}</strong>
                    </div>
                </div>
            </div>
            
            <h4 style="margin: 0 0 20px 0; color: #94a3b8; font-size: 18px; font-weight: 600;">📊 各模型预测详情</h4>
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
                                <h5 style="margin: 0 0 8px 0; font-size: 16px;">${pred.model_name}</h5>
                                <p style="margin: 0; color: #94a3b8; font-size: 13px;">${pred.model_type} | 准确率: <strong style="color: #00f0ff;">${(pred.accuracy * 100).toFixed(1)}%</strong></p>
                            </div>
                            <div class="model-prediction-signal">
                                <span class="small-signal-badge ${predSignalClass}" style="padding: 10px 18px; border-radius: 10px;">${predSignalIcon} ${pred.signal}</span>
                                <span class="signal-strength-text" style="font-size: 18px;">${pred.signal_strength.toFixed(0)}%</span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
            <p style="color: #64748b; font-size: 12px; margin-top: 24px;">预测时间: ${new Date(result.prediction_date).toLocaleString()}</p>
        </div>
    `;
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
`;
document.head.appendChild(style);
