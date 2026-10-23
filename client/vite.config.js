import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig({
  plugins: [uni()],
  server: {
    // H5 开发服务器端口（避开可能被其他项目占用的 5173）
    port: 8081
  }
})
