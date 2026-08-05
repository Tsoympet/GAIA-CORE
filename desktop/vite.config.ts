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
      '/runtime': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/tasks': 'http://127.0.0.1:8000',
      '/security': 'http://127.0.0.1:8000',
      '/voice': 'http://127.0.0.1:8000',
      '/audio': 'http://127.0.0.1:8000',
    },
  },
});
