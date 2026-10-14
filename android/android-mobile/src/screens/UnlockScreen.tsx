import { useState } from 'react';
import { StyleSheet, TextInput } from 'react-native';

import { SITES, Site, isSiteBlocked } from '../sites';
import { colors, font } from '../theme';
import { Button, Mono, Muted, Pane } from '../ui';
import type { Blocker } from '../useBlocker';

export function UnlockScreen({
  blocker,
  site,
  done,
}: {
  blocker: Blocker;
  site: Site | null;
  done: () => void;
}) {
  const [typed, setTyped] = useState('');
  const [wrong, setWrong] = useState(false);
  const [password] = useState(() => blocker.unlockPassword());

  const targets = site ? [site] : SITES.filter((s) => isSiteBlocked(s, blocker.blocked));
  if (!targets.length) {
    return (
      <Pane title="Unlock">
        <Muted>nothing is blocked right now.</Muted>
      </Pane>
    );
  }

  function submit() {
    const ok = blocker.unblock(typed, targets);
    if (ok) {
      setTyped('');
      done();
    } else {
      setWrong(true);
    }
  }

  return (
    <>
      <Pane title={site ? `Unlock ${site.name}` : 'Unlock everything'} focused>
        <Muted>type the password below to unlock. paste is off on purpose.</Muted>
        <Mono style={styles.password}>{password}</Mono>
        <TextInput
          style={styles.input}
          value={typed}
          onChangeText={(t) => {
            setTyped(t);
            setWrong(false);
          }}
          placeholder="type the password here"
          placeholderTextColor={colors.muted}
          selectionColor={colors.accent}
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="off"
          contextMenuHidden
          multiline
        />
        <Mono style={wrong ? styles.wrong : styles.count}>
          {wrong ? "that doesn't match." : `${typed.length} / ${password.length}`}
        </Mono>
        <Button
          primary
          title="unlock"
          disabled={typed.length !== password.length}
          onPress={submit}
        />
      </Pane>
      {site && <Button title="keep it blocked" onPress={done} />}
    </>
  );
}

const styles = StyleSheet.create({
  password: {
    fontSize: 12,
    lineHeight: 18,
    backgroundColor: colors.surface,
    padding: 10,
  },
  input: {
    fontFamily: font.mono,
    fontSize: 12,
    color: colors.foreground,
    borderWidth: 1,
    borderColor: colors.accent,
    backgroundColor: colors.background,
    padding: 10,
    minHeight: 80,
    textAlignVertical: 'top',
  },
  count: { fontSize: 12, color: colors.muted },
  wrong: { fontSize: 12, color: colors.error },
});
