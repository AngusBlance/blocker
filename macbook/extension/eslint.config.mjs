// Lints the Chrome extension in src/, a plain MV3 service worker: recommended
// rules plus the service worker and chrome.* globals.
import js from '@eslint/js';
import { defineConfig } from 'eslint/config';
import globals from 'globals';

export default defineConfig([
  {
    ignores: ['node_modules/'],
  },
  {
    files: ['src/**/*.js'],
    extends: [js.configs.recommended],
    languageOptions: {
      globals: { ...globals.serviceworker, ...globals.webextensions },
    },
  },
]);
