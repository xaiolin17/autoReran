<template>
  <div class="backtest-container">
    <el-card class="form-card">
      <template #header>
        <span>回测配置</span>
      </template>
      <el-form :model="backtestForm" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="股票代码">
              <el-input v-model="backtestForm.stock_code" placeholder="请输入股票代码" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="策略名称">
              <el-select v-model="backtestForm.strategy_name" placeholder="请选择策略">
                <el-option label="KDJ策略" value="KDJ" />
                <el-option label="MACD策略" value="MACD" />
                <el-option label="KDJ+MACD策略" value="KDJ_MACD" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="开始日期">
              <el-date-picker
                v-model="backtestForm.start_date"
                type="date"
                placeholder="选择开始日期"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期">
              <el-date-picker
                v-model="backtestForm.end_date"
                type="date"
                placeholder="选择结束日期"
                value-format="YYYY-MM-DD"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="初始资金">
              <el-input-number v-model="backtestForm.initial_capital" :min="10000" :max="10000000" :step="10000" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item>
          <el-button type="primary" @click="startBacktest" :loading="backtestLoading">
            开始回测
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="results-card">
      <template #header>
        <span>回测结果</span>
      </template>
      <el-table :data="backtestResults" style="width: 100%" v-loading="resultsLoading">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="stock_code" label="股票代码" width="120" />
        <el-table-column prop="strategy_name" label="策略名称" width="150" />
        <el-table-column prop="initial_capital" label="初始资金" width="120">
          <template #default="{ row }">
            ¥{{ row.initial_capital.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="final_capital" label="最终资金" width="120">
          <template #default="{ row }">
            ¥{{ row.final_capital.toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_return" label="总收益率" width="120">
          <template #default="{ row }">
            <span :style="{ color: row.total_return >= 0 ? '#14b8a6' : '#f43f5e' }">
              {{ row.total_return >= 0 ? '+' : '' }}{{ row.total_return.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="annual_return" label="年化收益率" width="120">
          <template #default="{ row }">
            <span :style="{ color: row.annual_return >= 0 ? '#14b8a6' : '#f43f5e' }">
              {{ row.annual_return >= 0 ? '+' : '' }}{{ row.annual_return.toFixed(2) }}%
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="max_drawdown" label="最大回撤" width="120">
          <template #default="{ row }">
            <span style="color: #f43f5e">{{ row.max_drawdown.toFixed(2) }}%</span>
          </template>
        </el-table-column>
        <el-table-column prop="win_rate" label="胜率" width="100">
          <template #default="{ row }">
            {{ row.win_rate.toFixed(2) }}%
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDetail(row)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="detailDialogVisible" title="回测详情" width="800px">
      <div v-if="currentBacktest" class="backtest-detail">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-statistic title="初始资金" :value="currentBacktest.initial_capital" :precision="2" prefix="¥" />
          </el-col>
          <el-col :span="12">
            <el-statistic title="最终资金" :value="currentBacktest.final_capital" :precision="2" prefix="¥" />
          </el-col>
        </el-row>
        <el-divider />
        <el-row :gutter="20">
          <el-col :span="6">
            <el-statistic title="总收益率">
              <template #value>
                <span :style="{ color: currentBacktest.total_return >= 0 ? '#14b8a6' : '#f43f5e' }">
                  {{ currentBacktest.total_return >= 0 ? '+' : '' }}{{ currentBacktest.total_return.toFixed(2) }}%
                </span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="6">
            <el-statistic title="年化收益率">
              <template #value>
                <span :style="{ color: currentBacktest.annual_return >= 0 ? '#14b8a6' : '#f43f5e' }">
                  {{ currentBacktest.annual_return >= 0 ? '+' : '' }}{{ currentBacktest.annual_return.toFixed(2) }}%
                </span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="6">
            <el-statistic title="最大回撤">
              <template #value>
                <span style="color: #f43f5e">{{ currentBacktest.max_drawdown.toFixed(2) }}%</span>
              </template>
            </el-statistic>
          </el-col>
          <el-col :span="6">
            <el-statistic title="胜率" :value="currentBacktest.win_rate" :precision="2" suffix="%" />
          </el-col>
        </el-row>
        <el-divider />
        <el-row :gutter="20">
          <el-col :span="8">
            <el-statistic title="总交易次数" :value="currentBacktest.total_trades" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="盈利次数" :value="currentBacktest.winning_trades" />
          </el-col>
          <el-col :span="8">
            <el-statistic title="亏损次数" :value="currentBacktest.losing_trades" />
          </el-col>
        </el-row>
        <el-divider />
        <div v-if="currentBacktest.trade_log && currentBacktest.trade_log.length">
          <h4>交易记录</h4>
          <el-table :data="currentBacktest.trade_log" style="width: 100%" max-height="300">
            <el-table-column prop="datetime" label="时间" width="180" />
            <el-table-column prop="action" label="操作" width="80">
              <template #default="{ row }">
                <el-tag :type="row.action === 'buy' ? 'success' : 'danger'">
                  {{ row.action === 'buy' ? '买入' : '卖出' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="price" label="价格" width="100" />
            <el-table-column prop="shares" label="数量" width="100" />
            <el-table-column prop="profit" label="利润" width="120" v-if="currentBacktest.trade_log[0]?.profit !== undefined">
              <template #default="{ row }">
                <span v-if="row.profit !== undefined" :style="{ color: row.profit >= 0 ? '#14b8a6' : '#f43f5e' }">
                  {{ row.profit >= 0 ? '+' : '' }}{{ row.profit.toFixed(2) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/utils/api'
import { ElMessage } from 'element-plus'

const backtestForm = ref({
  stock_code: '600000',
  strategy_name: 'KDJ',
  start_date: '',
  end_date: '',
  initial_capital: 100000
})

const backtestResults = ref([])
const backtestLoading = ref(false)
const resultsLoading = ref(false)
const detailDialogVisible = ref(false)
const currentBacktest = ref(null)

const fetchBacktestResults = async () => {
  resultsLoading.value = true
  try {
    const response = await api.get('/backtest/results')
    if (response.data) {
      backtestResults.value = response.data.data || []
    }
  } catch (error) {
    ElMessage.error('获取回测结果失败')
    console.error('Error fetching backtest results:', error)
  } finally {
    resultsLoading.value = false
  }
}

const startBacktest = async () => {
  if (!backtestForm.value.stock_code || !backtestForm.value.strategy_name ||
      !backtestForm.value.start_date || !backtestForm.value.end_date) {
    ElMessage.warning('请填写完整信息')
    return
  }

  backtestLoading.value = true
  try {
    const response = await api.post('/backtest/run', backtestForm.value)
    if (response.data) {
      ElMessage.success('回测任务已提交，请稍后查看结果')
      fetchBacktestResults()
    }
  } catch (error) {
    ElMessage.error('回测失败')
    console.error('Error running backtest:', error)
  } finally {
    backtestLoading.value = false
  }
}

const viewDetail = (backtest) => {
  currentBacktest.value = backtest
  detailDialogVisible.value = true
}

onMounted(() => {
  fetchBacktestResults()
})
</script>

<style scoped>
.backtest-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.backtest-detail {
  padding: 20px;
}
</style>
