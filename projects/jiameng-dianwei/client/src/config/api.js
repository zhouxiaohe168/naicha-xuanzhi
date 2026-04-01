import axios from 'axios'

// 生产环境直连 Railway 后端（避免 Vercel 代理 307 问题），本地走 Vite 代理
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
})

// 请求拦截器：自动带 token + 确保URL末尾有斜杠（避免Railway 307重定向）
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // 生产直连后端：末尾不是数字ID的路径加斜杠（FastAPI 要求），带ID的路径不加
  if (BASE_URL.startsWith('http') && config.url) {
    const [path, query] = config.url.split('?')
    if (!path.endsWith('/') && !/\/\d+$/.test(path)) {
      config.url = path + '/' + (query ? '?' + query : '')
    }
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
