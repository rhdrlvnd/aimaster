import { defineConfig } from 'vite';
export default defineConfig({
  server: {
    port: 5173,
    strictPort: true,
    proxy: {'/api': 'http://127.0.0.1:8000'},
    // Office may lock generated images while exporting them on Windows.
    // These directories contain runtime data, not frontend source.
    watch: {ignored: ['**/data/**', '**/.artifact-build/**', '**/outputs/**']},
  },
});
