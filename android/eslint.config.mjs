// Lint config for the Expo app and its native module: Expo's recommended rules.
import expoConfig from 'eslint-config-expo/flat.js';
import { defineConfig } from 'eslint/config';

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
]);
