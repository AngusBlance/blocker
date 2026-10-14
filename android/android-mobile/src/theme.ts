// Mirrors the TUI, which uses Textual's default "textual-dark" theme: near-black
// background, square single-line borders, orange accent on whatever has focus,
// monospace text. Keep these in step with tui/ so both front ends look alike.
export const colors = {
  background: '#121212',
  surface: '#1e1e1e',
  panel: '#24272b',
  foreground: '#e0e0e0',
  muted: '#8b8b8b',
  border: '#3a3a3a', // Textual $border-blurred
  accent: '#ffa62b', // Textual $accent: focused pane, active tab
  primary: '#0178d4',
  error: '#ba3c5b',
  success: '#4ebf71',
};

export const font = {
  mono: 'monospace',
};

export const size = {
  small: 12,
  body: 14,
  title: 16,
  big: 24,
};
