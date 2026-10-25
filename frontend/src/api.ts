import axios from 'axios'

/**
 * 职责: 创建默认携带 HttpOnly Session Cookie 的 Axios 客户端实例
 */
export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  withCredentials: true,
  timeout: 60000,
})
