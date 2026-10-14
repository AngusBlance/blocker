import { NativeModule, requireNativeModule } from 'expo';

declare class AndroidlibModule extends NativeModule {
  getBlockedDomains(): string[];
  block(domains: string[]): void;
  /** Returns false and changes nothing if the password is wrong. */
  unblock(password: string, domains: string[]): boolean;
  getUnlockPassword(): string;
  isServiceEnabled(): boolean;
  openAccessibilitySettings(): void;
}

export default requireNativeModule<AndroidlibModule>('Androidlib');
