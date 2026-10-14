import { NativeModule, requireNativeModule } from 'expo';

declare class AndroidlibModule extends NativeModule {
  getBlockedDomains(): string[];
  /** Package names, e.g. com.google.android.youtube. */
  getBlockedApps(): string[];
  block(domains: string[], apps: string[]): void;
  /** Returns false and changes nothing if the password is wrong. */
  unblock(password: string, domains: string[], apps: string[]): boolean;
  getUnlockPassword(): string;
  isServiceEnabled(): boolean;
  openAccessibilitySettings(): void;
}

export default requireNativeModule<AndroidlibModule>('Androidlib');
