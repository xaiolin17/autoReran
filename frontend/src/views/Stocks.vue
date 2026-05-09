<template>
  <div class="stocks-container">
    <el-card class="search-card">
      <div class="search-form">
        <el-input
          v-model="stockCode"
          placeholder="请输入股票代码（如：600000）"
          style="width: 300px"
          clearable
        />
        <el-button type="primary" @click="fetchStockData" :loading="loading">
          获取数据
        </el-button>
        <el-button @click="refreshChart">刷新图表</el-button>
      </div>
    </el-card>

    <el-card class="chart-card" v-loading="chartLoading">
      <template #header>
        <div class="card-header">
          <span>K线图</span>
          <el-tag v-if="currentStock" type="success">{{ currentStock }}</el-tag>
        </div>
      </template>
      <div ref="chartRef" class="chart"></div>
    </el-card>

    <el-card class="data-card">
      <template #header>
        <span>股票数据列表</span>
      </template>
      <el-table :data="stockData" style="width: 100%">
        <el-table-column prop="datetime" label="日期" width="180" />
        <el-table-column prop="open_price" label="开盘价" width="120" />
        <el-table-column prop="high_price" label="最高价" width="120" />
        <el-table-column prop="low_price" label="最低价" width="120" />
        <el-table-column prop="close_price" label="收盘价" width="120" />
        <el-table-column prop="volume" label="成交量" width="150" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import api from '@/utils/api'
import { ElMessage } from 'element-plus'

const chartRef = ref(null)
let chart = null
const stockCode = ref('600000')
const stockData = ref([])
const loading = ref(false)
const chartLoading = ref(false)
const currentStock = ref('')

const initChart = () => {
  if (chartRef.value) {
    chart = echarts.init(chartRef.value)
    chart.setOption({
      title: {
        text: '股票K线图'
      },
      tooltip: {
        trigger: 'axis',
        axisPointer: {
          type: 'cross'
        }
      },
      grid: [
        {
          left: '10%',
          right: '8%',
          height: '50%'
        },
        {
          left: '10%',
          right: '8%',
          top: '63%',
          height: '16%'
        }
      ],
      xAxis: [
        {
          type: 'category',
          data: [],
          boundaryGap: false,
          axisLine: { onZero: false },
          splitLine: { show: false },
          min: 'dataMin',
          max: 'dataMax'
        },
        {
          type: 'category',
          gridIndex: 1,
          data: [],
          boundaryGap: false,
          axisLine: { onZero: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { show: false }
        }
      ],
      yAxis: [
        {
          scale: true,
          splitArea: {
            show: true
          }
        },
        {
          scale: true,
          gridIndex: 1,
          splitNumber: 2,
          axisLabel: { show: false },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false }
        }
      ],
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0, 1],
          start: 50,
          end: 100
        },
        {
          show: true,
          xAxisIndex: [0, 1],
          type: 'slider',
          top: '90%',
          start: 50,
          end: 100
        }
      ],
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: [],
          itemStyle: {
            color: '#14b8a6',
            color0: '#f43f5e',
            borderColor: '#14b8a6',
            borderColor0: '#f43f5e'
          }
        },
        {
          name: '成交量',
          type: 'bar',
          xAxisIndex: 1,
          yAxisIndex: 1,
          data: [],
          itemStyle: {
            color: (params) => {
              const dataList = stockData.value
              const index = params.dataIndex
              if (dataList[index]) {
                return dataList[index].close_price >= dataList[index].open_price
                  ? '#14b8a6'
                  : '#f43f5e'
              }
              return '#14b8a6'
            }
          }
        }
      ]
    })

    window.addEventListener('resize', () => {
      chart.resize()
    })
  }
}

const fetchStockData = async () => {
  if (!stockCode.value) {
    ElMessage.warning('请输入股票代码')
    return
  }

  loading.value = true
  try {
    const response = await api.get(`/stocks/${stockCode.value}`)
    if (response.data && response.data.data) {
      stockData.value = response.data.data.slice(-100) // 只显示最近100条数据
      currentStock.value = stockCode.value
      updateChart()
      ElMessage.success('数据获取成功')
    }
  } catch (error) {
    ElMessage.error('数据获取失败')
    console.error('Error fetching stock data:', error)
  } finally {
    loading.value = false
  }
}

const updateChart = () => {
  if (!chart || !stockData.value.length) return

  chartLoading.value = true

  const dates = stockData.value.map(item => item.datetime)
  const candleData = stockData.value.map(item => [
    item.open_price,
    item.close_price,
    item.low_price,
    item.high_price
  ])
  const volumes = stockData.value.map(item => item.volume)

  chart.setOption({
    xAxis: [
      { data: dates },
      { data: dates }
    ],
    series: [
      { data: candleData },
      { data: volumes }
    ]
  })

  chartLoading.value = false
}

const refreshChart = () => {
  if (chart) {
    chart.resize()
  }
}

onMounted(() => {
  nextTick(() => {
    initChart()
    fetchStockData()
  })
})
</script>

<style scoped>
.stocks-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.search-card {
  margin-bottom: 0;
}

.search-form {
  display: flex;
  gap: 10px;
}

.chart-card {
  margin-top: 0;
}

.chart {
  width: 100%;
  height: 500px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
