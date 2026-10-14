import { ReactNode } from 'react';
import { Pressable, StyleProp, StyleSheet, Text, TextStyle, View } from 'react-native';

import { colors, font, size } from './theme';

// A bordered box like the TUI's Sidebar/Content panes. `focused` gives it the
// accent border the TUI uses for the focused pane.
export function Pane({
  title,
  children,
  focused,
  tone,
}: {
  title?: string;
  children: ReactNode;
  focused?: boolean;
  tone?: 'error';
}) {
  return (
    <View
      style={[
        styles.pane,
        focused && { borderColor: colors.accent },
        tone === 'error' && { borderColor: colors.error },
      ]}>
      {title && (
        <Mono style={[styles.title, tone === 'error' && { color: colors.error }]}>
          {title.toUpperCase()}
        </Mono>
      )}
      {children}
    </View>
  );
}

export function Mono({ children, style }: { children: ReactNode; style?: StyleProp<TextStyle> }) {
  return <Text style={[styles.mono, style]}>{children}</Text>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <Mono style={styles.muted}>{children}</Mono>;
}

// One "key  value" line, like `  state           BLOCKED` on the TUI dashboard.
export function Field({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.field}>
      <Mono style={styles.fieldLabel}>{label}</Mono>
      <Mono style={color ? { color } : undefined}>{value}</Mono>
    </View>
  );
}

export function Button({
  title,
  onPress,
  primary,
  disabled,
}: {
  title: string;
  onPress: () => void;
  primary?: boolean;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        primary && styles.primary,
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}>
      <Mono style={[styles.buttonText, primary && styles.primaryText]}>{title}</Mono>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  pane: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
    paddingHorizontal: 14,
    paddingVertical: 12,
    gap: 10,
  },
  title: { color: colors.foreground, fontWeight: '700' },
  mono: { fontFamily: font.mono, fontSize: size.body, color: colors.foreground },
  muted: { color: colors.muted, lineHeight: 20 },
  field: { flexDirection: 'row' },
  fieldLabel: { width: 130, color: colors.muted },
  button: {
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    paddingVertical: 12,
    alignItems: 'center',
  },
  primary: { backgroundColor: colors.accent, borderColor: colors.accent },
  pressed: { opacity: 0.7 },
  disabled: { opacity: 0.35 },
  buttonText: { fontWeight: '700' },
  primaryText: { color: colors.background },
});
