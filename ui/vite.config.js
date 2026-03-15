import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            '/auth': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/brokers': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/broker-connections': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/session': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/holdings': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/plan': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/risk': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/gtt': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/jobs': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/dynamic-avg': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
            '/dynamicavg': {
                target: 'http://localhost:8000',
                changeOrigin: true,
                rewrite: function (path) { return path.replace(/^\/dynamicavg/, '/dynamic-avg'); },
            },
        },
    },
});
