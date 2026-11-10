import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    proxy: {
      '/kernel': 'http://127.0.0.1:8000',
      '/organism': 'http://127.0.0.1:8000',
      '/runtime': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/tasks': 'http://127.0.0.1:8000',
      '/security': 'http://127.0.0.1:8000',
      '/voice': 'http://127.0.0.1:8000',
      '/audio': 'http://127.0.0.1:8000',
      '/chat': 'http://127.0.0.1:8000',
      '/agents': 'http://127.0.0.1:8000',
      '/memory': 'http://127.0.0.1:8000',
      '/models': 'http://127.0.0.1:8000',
      '/tools': 'http://127.0.0.1:8000',
      '/workspaces': 'http://127.0.0.1:8000',
      '/self-model': 'http://127.0.0.1:8000',
      '/metacognition': 'http://127.0.0.1:8000',
      '/cognition': 'http://127.0.0.1:8000',
      '/dreaming': 'http://127.0.0.1:8000',
      '/idle-cognition': 'http://127.0.0.1:8000',
      '/version': 'http://127.0.0.1:8000',
      '/capabilities': 'http://127.0.0.1:8000',
    },
  },
});
