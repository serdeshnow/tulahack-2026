import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react-swc';
import tsconfigPaths from 'vite-tsconfig-paths';
import tailwindcss from '@tailwindcss/vite';

function manualChunks(id: string) {
	if (!id.includes('node_modules')) {
		return;
	}

	if (id.includes('react-router')) {
		return 'router';
	}

	if (id.includes('@tanstack/react-query') || id.includes('@tanstack/react-query-devtools')) {
		return 'query';
	}

	if (id.includes('@tanstack/react-table')) {
		return 'table';
	}

	if (id.includes('recharts')) {
		return 'charts';
	}

	if (id.includes('wavesurfer.js')) {
		return 'audio';
	}

	if (id.includes('react-dropzone')) {
		return 'upload';
	}

	if (id.includes('lucide-react')) {
		return 'icons';
	}

	if (id.includes('framer-motion') || id.includes('/motion/')) {
		return 'motion';
	}

	if (id.includes('@radix-ui') || id.includes('@base-ui') || id.includes('sonner') || id.includes('@floating-ui')) {
		return 'ui';
	}

	if (id.includes('react-error-boundary')) {
		return 'errors';
	}

	if (id.includes('mobx') || id.includes('mobx-react-lite') || id.includes('mobx-keystone')) {
		return 'state';
	}

	if (id.includes('zod') || id.includes('axios') || id.includes('dayjs')) {
		return 'data';
	}

	return 'vendor';
}

// https://vite.dev/config/
export default defineConfig({
	cacheDir: '.vite-temp',
	publicDir: 'public',
	plugins: [react({tsDecorators: true}), tsconfigPaths(), tailwindcss()],
	server: {
		port: 3000,
		open: true,
	},
	build: {
		assetsDir: 'static',
		outDir: 'build',
		target: 'es2022',
		modulePreload: {
			polyfill: false,
		},
		rollupOptions: {
			output: {
				manualChunks,
				chunkFileNames: 'static/chunks/[name]-[hash].js',
				entryFileNames: 'static/entry/[name]-[hash].js',
				assetFileNames: 'static/assets/[name]-[hash][extname]',
			},
		},
	},
	test: {
		fileParallelism: false,
	},
});
