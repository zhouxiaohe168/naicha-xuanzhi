import axios from 'axios'

// API基础配置
const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 请求拦截器：自动带 token + 确保URL末尾有斜杠（避免Railway 307重定向）
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // 确保路径末尾有斜杠（防止代理307重定向）
  if (config.url && !config.url.endsWith('/') && !config.url.includes('?')) {
    config.url = config.url + '/'
  }
  return config
})

// 响应拦截器：统一处理错误
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      // token过期，跳转登录
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api
