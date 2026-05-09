import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isAuthenticated = computed(() => !!token.value)

  const login = async (email, password) => {
    try {
      const response = await api.post('/auth/login', {
        username: email,
        password: password
      })
      token.value = response.data.access_token
      localStorage.setItem('token', response.data.access_token)
      
      // 获取用户信息
      const userResponse = await api.get('/auth/me')
      user.value = userResponse.data
      localStorage.setItem('user', JSON.stringify(userResponse.data))
      
      return true
    } catch (error) {
      console.error('登录失败:', error)
      return false
    }
  }

  const register = async (email, username, password) => {
    try {
      await api.post('/auth/register', {
        email,
        username,
        password
      })
      return true
    } catch (error) {
      console.error('注册失败:', error)
      return false
    }
  }

  const logout = () => {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return {
    token,
    user,
    isAuthenticated,
    login,
    register,
    logout
  }
})
