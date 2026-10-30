import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  return {
  build: { assetsDir: 'static' },
  server: {
    port: 5173,
    strictPort: true,
    watch: { usePolling: env.DOCKER_POLLING === 'true' },
    proxy: Object.fromEntries(['/api', '/assets', '/imgs'].map(path => [path, { target: env.API_PROXY_TARGET || 'http://127.0.0.1:8000' }])),
  },
  };
});
