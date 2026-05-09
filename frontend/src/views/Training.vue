<template>
  <div class="training-container">
    <el-card class="form-card">
      <template #header>
        <span>训练模型</span>
      </template>
      <el-form :model="trainingForm" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="股票代码">
              <el-input v-model="trainingForm.stock_code" placeholder="请输入股票代码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="模型名称">
              <el-input v-model="trainingForm.model_name" placeholder="请输入模型名称" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="模型类型">
              <el-select v-model="trainingForm.model_type" placeholder="请选择模型类型">
                <el-option label="随机森林" value="RandomForest" />
                <el-option label="线性回归" value="LinearRegression" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="训练集比例">
              <el-input-number v-model="trainingForm.train_size" :min="0.5" :max="0.95" :step="0.05" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" @click="startTraining" :loading="trainingLoading">
            开始训练
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="models-card">
      <template #header>
        <span>模型列表</span>
      </template>
      <el-table :data="models" style="width: 100%" v-loading="modelsLoading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="model_name" label="模型名称" width="150" />
        <el-table-column prop="stock_code" label="股票代码" width="120" />
        <el-table-column prop="model_type" label="模型类型" width="120" />
        <el-table-column prop="accuracy" label="准确率" width="100">
          <template #default="{ row }">
            {{ row.accuracy ? (row.accuracy * 100).toFixed(2) + '%' : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="predict(row)">
              预测
            </el-button>
            <el-button type="danger" size="small" @click="deleteModel(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="predictDialogVisible" title="预测结果" width="500px">
      <div v-if="predictionResult" class="prediction-result">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="股票代码">{{ predictionResult.stock_code }}</el-descriptions-item>
          <el-descriptions-item label="当前价格">{{ predictionResult.current_price.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="预测价格">{{ predictionResult.predicted_price.toFixed(2) }}</el-descriptions-item>
          <el-descriptions-item label="涨跌幅度">
            <span :style="{ color: predictionResult.change_percent >= 0 ? '#14b8a6' : '#f43f5e' }">
              {{ predictionResult.change_percent >= 0 ? '+' : '' }}{{ predictionResult.change_percent.toFixed(2) }}%
            </span>
          </el-descriptions-item>
          <el-descriptions-item label="预测时间">{{ predictionResult.prediction_date }}</el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const trainingForm = ref({
  stock_code: '600000',
  model_name: '',
  model_type: 'RandomForest',
  train_size: 0.8
})

const models = ref([])
const trainingLoading = ref(false)
const modelsLoading = ref(false)
const predictDialogVisible = ref(false)
const predictionResult = ref(null)

const fetchModels = async () => {
  modelsLoading.value = true
  try {
    const response = await api.get('/ml/models')
    if (response.data) {
      models.value = response.data.data || []
    }
  } catch (error) {
    ElMessage.error('获取模型列表失败')
    console.error('Error fetching models:', error)
  } finally {
    modelsLoading.value = false
  }
}

const startTraining = async () => {
  if (!trainingForm.value.stock_code || !trainingForm.value.model_name) {
    ElMessage.warning('请填写完整信息')
    return
  }

  trainingLoading.value = true
  try {
    const response = await api.post('/ml/train', trainingForm.value)
    if (response.data) {
      ElMessage.success('模型训练任务已提交，请稍后查看结果')
      fetchModels()
    }
  } catch (error) {
    ElMessage.error('模型训练失败')
    console.error('Error training model:', error)
  } finally {
    trainingLoading.value = false
  }
}

const predict = async (model) => {
  try {
    const response = await api.post('/ml/predict', {
      model_id: model.id,
      stock_code: model.stock_code
    })
    if (response.data) {
      predictionResult.value = response.data.data
      predictDialogVisible.value = true
    }
  } catch (error) {
    ElMessage.error('预测失败')
    console.error('Error predicting:', error)
  }
}

const deleteModel = async (modelId) => {
  try {
    await ElMessageBox.confirm('确定要删除这个模型吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    await api.delete(`/ml/models/${modelId}`)
    ElMessage.success('删除成功')
    fetchModels()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
      console.error('Error deleting model:', error)
    }
  }
}

onMounted(() => {
  fetchModels()
})
</script>

<style scoped>
.training-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.prediction-result {
  padding: 20px;
}
</style>
