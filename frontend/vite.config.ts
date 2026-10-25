import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

// 职责: 解析项目根目录共享 .env 配置，动态构建 Vite 服务与反向代理
export default defineConfig(({ mode }) => {
  // 1. 指定根目录路径并加载共享环境变量
  const rootDir = fileURLToPath(new URL('../', import.meta.url))
  const env = loadEnv(mode, rootDir, '')

  const backendPort = env.VITE_API_PORT || env.BACKEND_PORT || '8001'
  const frontendPort = Number(env.FRONTEND_PORT) || 5173

  return {
    envDir: rootDir,
    plugins: [vue()],
    server: {
      host: '0.0.0.0',
      port: frontendPort,
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
