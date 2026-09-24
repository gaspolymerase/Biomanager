// Vite builds the notebook bundle (TipTap editor + chips) into
// app/static/notebook-build/. The plasmid bundle is no longer Vite-built —
// it's the prebuilt UMD distribution of Open Vector Editor, copied into the
// same directory by `npm run build:plasmid` (a plain `cp`).
//
// Background: SeqViz was view-only, so we replaced it with TeselaGen's
// Open Vector Editor (OVE) which supports inline editing. OVE ships a UMD
// build via @deltablot/tg-oss-ove-umd; bundling it ourselves added no value
// and tripped on React/Redux + missing `process` globals.

import { defineConfig } from 'vite';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  build: {
    outDir: path.resolve(__dirname, '../app/static/notebook-build'),
    emptyOutDir: false, // keep the OVE plasmid bundle that npm cp'd in alongside us
    cssCodeSplit: false,
    sourcemap: false,
    lib: {
      entry: path.resolve(__dirname, 'src/main.js'),
      name: 'BiomanagerNotebook',
      formats: ['iife'],
      fileName: () => 'notebook-app.js',
    },
    rollupOptions: {
      output: {
        assetFileNames: (assetInfo) => {
          if (assetInfo.name && assetInfo.name.endsWith('.css')) return 'notebook-app.css';
          return assetInfo.name || 'notebook-app[extname]';
        },
      },
    },
  },
});
