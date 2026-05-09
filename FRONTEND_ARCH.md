# 股票数据分析平台 - 前端架构规划

## 概述

本文档详细说明了股票数据分析平台的前端架构设计，提供了 Vue.js 和 React 两种主流框架的实现方案。

---

## 技术选型对比

| 特性 | Vue.js 方案 | React 方案 |
|------|-------------|------------|
| **学习曲线** | 相对平缓，模板语法直观 | 略陡，JSX 需要适应 |
| **生态系统** | Vue Router, Pinia, Element Plus | React Router, Redux/Zustand, Ant Design/Material-UI |
| **性能** | 虚拟 DOM + 响应式系统，优秀 | 虚拟 DOM，优秀 |
| **类型支持** | TypeScript 支持良好 | TypeScript 原生支持更好 |
| **社区规模** | 庞大，国内用户多 | 更大，国际用户多 |
| **图表库** | ECharts, Vue-ECharts | ECharts, Recharts, D3.js |

---

## 方案一：Vue.js + TypeScript + Element Plus

### 1. 技术栈

- **框架**: Vue 3 (Composition API)
- **语言**: TypeScript
- **状态管理**: Pinia
- **路由**: Vue Router 4
- **UI 组件库**: Element Plus
- **图表库**: ECharts + vue-echarts
- **HTTP 客户端**: Axios
- **构建工具**: Vite
- **CSS 预处理**: SCSS
- **代码规范**: ESLint + Prettier

### 2. 项目结构

```
frontend-vue/
├── public/
│   └── favicon.ico
├── src/
│   ├── api/                    # API 接口
│   │   ├── index.ts           # 基础配置
│   │   ├── auth.ts            # 认证接口
│   │   ├── stock.ts           # 股票接口
│   │   ├── indicator.ts       # 指标接口
│   │   ├── ml.ts              # 机器学习接口
│   │   └── backtest.ts        # 回测接口
│   ├── assets/                # 静态资源
│   │   ├── styles/
│   │   │   ├── index.scss     # 全局样式
│   │   │   └── variables.scss # 样式变量
│   │   └── images/
│   ├── components/            # 通用组件
│   │   ├── common/            # 基础组件
│   │   │   ├── TheHeader.vue
│   │   │   ├── TheSidebar.vue
│   │   │   └── TheFooter.vue
│   │   ├── charts/            # 图表组件
│   │   │   ├── StockChart.vue
│   │   │   ├── IndicatorChart.vue
│   │   │   └── BacktestChart.vue
│   │   └── forms/             # 表单组件
│   │       ├── LoginForm.vue
│   │       └── RegisterForm.vue
│   ├── composables/           # 组合式函数
│   │   ├── useAuth.ts
│   │   ├── useStock.ts
│   │   ├── useChart.ts
│   │   └── useWebSocket.ts
│   ├── router/                # 路由配置
│   │   └── index.ts
│   ├── stores/                # Pinia 状态管理
│   │   ├── index.ts
│   │   ├── user.ts
│   │   ├── stock.ts
│   │   └── app.ts
│   ├── types/                 # TypeScript 类型定义
│   │   ├── index.ts
│   │   ├── user.ts
│   │   ├── stock.ts
│   │   └── api.ts
│   ├── utils/                 # 工具函数
│   │   ├── request.ts         # 请求封装
│   │   ├── auth.ts            # 认证工具
│   │   └── format.ts          # 格式化工具
│   ├── views/                 # 页面视图
│   │   ├── HomeView.vue
│   │   ├── LoginView.vue
│   │   ├── RegisterView.vue
│   │   ├── StockListView.vue
│   │   ├── StockDetailView.vue
│   │   ├── MLView.vue
│   │   └── BacktestView.vue
│   ├── App.vue
│   └── main.ts
├── .env.development
├── .env.production
├── .eslintrc.cjs
├── .prettierrc
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

### 3. 核心功能实现

#### 3.1 认证系统

```typescript
// src/stores/user.ts
import { defineStore } from 'pinia'
import { login, register, getUserInfo } from '@/api/auth'
import { setToken, removeToken, getToken } from '@/utils/auth'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: getToken(),
    userInfo: null,
  }),
  
  actions: {
    async login(loginData) {
      const res = await login(loginData)
      this.token = res.data.access_token
      setToken(res.data.access_token)
      await this.getUserInfo()
    },
    
    async register(registerData) {
      await register(registerData)
    },
    
    async getUserInfo() {
      const res = await getUserInfo()
      this.userInfo = res.data
    },
    
    logout() {
      this.token = ''
      this.userInfo = null
      removeToken()
    },
  },
})
```

#### 3.2 股票图表组件

```vue
<!-- src/components/charts/StockChart.vue -->
<template>
  <div ref="chartRef" style="width: 100%; height: 400px;"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'
import { useChart } from '@/composables/useChart'

const props = defineProps<{
  data: any[]
}>()

const chartRef = ref<HTMLElement>()
let chart: echarts.ECharts

const { initChart, updateChart } = useChart()

onMounted(() => {
  if (chartRef.value) {
    chart = initChart(chartRef.value)
    updateChart(chart, props.data)
  }
})

watch(() => props.data, (newData) => {
  if (chart && newData) {
    updateChart(chart, newData)
  }
})
</script>
```

---

## 方案二：React + TypeScript + Ant Design

### 1. 技术栈

- **框架**: React 18
- **语言**: TypeScript
- **状态管理**: Zustand (轻量级) 或 Redux Toolkit (大型应用)
- **路由**: React Router v6
- **UI 组件库**: Ant Design
- **图表库**: ECharts for React 或 Recharts
- **HTTP 客户端**: Axios 或 React Query (推荐)
- **构建工具**: Vite
- **CSS 解决方案**: Tailwind CSS 或 Styled Components
- **代码规范**: ESLint + Prettier

### 2. 项目结构

```
frontend-react/
├── public/
│   └── favicon.ico
├── src/
│   ├── api/                    # API 接口
│   │   ├── client.ts          # API 客户端
│   │   ├── auth.ts
│   │   ├── stock.ts
│   │   ├── indicator.ts
│   │   ├── ml.ts
│   │   └── backtest.ts
│   ├── assets/
│   │   ├── styles/
│   │   └── images/
│   ├── components/            # 组件
│   │   ├── layout/            # 布局组件
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Footer.tsx
│   │   ├── charts/            # 图表组件
│   │   │   ├── StockChart.tsx
│   │   │   ├── IndicatorChart.tsx
│   │   │   └── BacktestChart.tsx
│   │   ├── forms/
│   │   │   ├── LoginForm.tsx
│   │   │   └── RegisterForm.tsx
│   │   └── common/
│   ├── hooks/                 # 自定义 Hooks
│   │   ├── useAuth.ts
│   │   ├── useStock.ts
│   │   ├── useChart.ts
│   │   └── useWebSocket.ts
│   ├── pages/                 # 页面
│   │   ├── Home.tsx
│   │   ├── Login.tsx
│   │   ├── Register.tsx
│   │   ├── StockList.tsx
│   │   ├── StockDetail.tsx
│   │   ├── ML.tsx
│   │   └── Backtest.tsx
│   ├── router/                # 路由
│   │   ├── index.tsx
│   │   └── PrivateRoute.tsx
│   ├── store/                 # 状态管理
│   │   ├── index.ts
│   │   ├── useUserStore.ts
│   │   ├── useStockStore.ts
│   │   └── useAppStore.ts
│   ├── types/                 # 类型定义
│   │   ├── index.ts
│   │   ├── user.ts
│   │   ├── stock.ts
│   │   └── api.ts
│   ├── utils/                 # 工具函数
│   │   ├── request.ts
│   │   ├── auth.ts
│   │   └── format.ts
│   ├── App.tsx
│   └── main.tsx
├── .env.development
├── .env.production
├── .eslintrc.cjs
├── .prettierrc
├── index.html
├── package.json
├── tsconfig.json
├── tailwind.config.js (可选)
└── vite.config.ts
```

### 3. 核心功能实现

#### 3.1 认证状态管理

```typescript
// src/store/useUserStore.ts
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { login, register, getUserInfo } from '@/api/auth'

interface UserState {
  token: string | null
  userInfo: any | null
  login: (data: any) => Promise<void>
  register: (data: any) => Promise<void>
  getUserInfo: () => Promise<void>
  logout: () => void
}

export const useUserStore = create<UserState>()(
  persist(
    (set, get) => ({
      token: null,
      userInfo: null,
      
      login: async (loginData) => {
        const res = await login(loginData)
        set({ token: res.data.access_token })
        await get().getUserInfo()
      },
      
      register: async (registerData) => {
        await register(registerData)
      },
      
      getUserInfo: async () => {
        const res = await getUserInfo()
        set({ userInfo: res.data })
      },
      
      logout: () => {
        set({ token: null, userInfo: null })
      },
    }),
    {
      name: 'user-storage',
    }
  )
)
```

#### 3.2 路由保护

```tsx
// src/router/PrivateRoute.tsx
import { Navigate } from 'react-router-dom'
import { useUserStore } from '@/store/useUserStore'

interface PrivateRouteProps {
  children: React.ReactNode
}

export const PrivateRoute: React.FC<PrivateRouteProps> = ({ children }) => {
  const token = useUserStore((state) => state.token)
  
  if (!token) {
    return <Navigate to="/login" replace />
  }
  
  return <>{children}</>
}
```

---

## 公共功能设计

### 1. API 层封装

```typescript
// 两种方案通用
import axios from 'axios'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
})

apiClient.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // 处理未授权
    }
    return Promise.reject(error)
  }
)

export default apiClient
```

### 2. 页面路由设计

| 路径 | 页面 | 权限 |
|------|------|------|
| / | 首页 | 公开 |
| /login | 登录 | 公开 |
| /register | 注册 | 公开 |
| /stocks | 股票列表 | 需要登录 |
| /stocks/:code | 股票详情 | 需要登录 |
| /ml | 机器学习 | 需要登录 |
| /backtest | 回测系统 | 需要登录 |
| /profile | 用户中心 | 需要登录 |

### 3. 实时数据更新

- 使用 WebSocket 或 SSE (Server-Sent Events) 实现实时数据推送
- 监听股票价格变化，实时更新图表
- 任务状态实时通知

---

## 开发建议

### Vue.js 方案推荐理由

- 国内文档和教程丰富，团队学习成本低
- Element Plus 组件库成熟，适合快速开发
- Composition API 代码组织灵活
- 适合中大型项目，性能优秀

### React 方案推荐理由

- 生态系统最丰富，第三方库选择多
- TypeScript 支持更完善
- 国际招聘市场更受欢迎
- React Query 处理服务器状态非常强大
- 适合需要高度定制化的项目

### 共同最佳实践

1. **TypeScript**: 两种方案都强烈建议使用 TypeScript
2. **组件化**: 合理拆分组件，提高复用性
3. **状态管理**: 区分本地状态和全局状态
4. **错误处理**: 统一的错误处理和用户提示
5. **性能优化**: 图表数据虚拟滚动，防抖节流
6. **测试**: 单元测试 + E2E 测试

---

## 快速开始模板

### Vue 项目初始化

```bash
npm create vite@latest frontend-vue -- --template vue-ts
cd frontend-vue
npm install
npm install vue-router pinia element-plus axios echarts vue-echarts
npm run dev
```

### React 项目初始化

```bash
npm create vite@latest frontend-react -- --template react-ts
cd frontend-react
npm install
npm install react-router-dom zustand antd axios react-query echarts-for-react
npm run dev
```

---

## 总结

两种方案都能很好地满足股票数据分析平台的需求。选择哪种主要取决于：

1. 团队的技术栈和经验
2. 项目的长期维护计划
3. 招聘市场的人才供给

建议根据团队实际情况做出选择，本文档提供的架构可以作为基础框架进行扩展。
