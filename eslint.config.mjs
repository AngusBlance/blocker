// One lint config for every JS/TS front end: the Expo app and module use
// Expo's recommended rules, the Chrome extension plain recommended rules.
import js from '@eslint/js';
import expoConfig from 'eslint-config-expo/flat.js';
import { defineConfig } from 'eslint/config';
import globals from 'globals';

export default defineConfig([
  {
    ignores: [
      '**/node_modules/',
      'android-mobile/android/',
      'android-mobile/.expo/',
      'androidlib/android/',
    ],
  },
  {
    files: ['android-mobile/**', 'androidlib/**'],
    extends: [expoConfig],
    rules: {
      // Guards against quotes breaking HTML; React Native <Text> has no such issue.
      'react/no-unescaped-entities': 'off',
    },
  },
  {
    files: ['extension/**/*.js'],
    extends: [js.configs.recommended],
    languageOptions: {
      globals: { ...globals.serviceworker, ...globals.webextensions },
    },
  },
]);
