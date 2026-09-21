import type { ReactNode } from 'react';
import { Modal, Pressable, View } from 'react-native';
import { Text } from './Text';
import { colors, radius, space } from './tokens';
import { useLayout } from './useLayout';

type Props = {
  visible: boolean;
  onClose: () => void;
  /** Accessible name for the backdrop's close button. */
  closeLabel: string;
  title?: string;
  children: ReactNode;
};

/**
 * A sheet that rises from the bottom on a phone and becomes a centred
 * modal on a wide screen — for a form or a picker that does not deserve a
 * whole new route. Returns `null` while not visible rather than relying on
 * `Modal`'s own `visible` prop to hide content, so nothing inside mounts
 * (and nothing is findable in tests) until it is actually open.
 */
export function Sheet({ visible, onClose, closeLabel, title, children }: Props) {
  const { isWide } = useLayout();
  if (!visible) return null;

  return (
    <Modal visible transparent animationType={isWide ? 'fade' : 'slide'} onRequestClose={onClose}>
      <Pressable
        role="button"
        accessibilityLabel={closeLabel}
        onPress={onClose}
        style={{
          flex: 1,
          backgroundColor: colors.overlay,
          justifyContent: isWide ? 'center' : 'flex-end',
          alignItems: isWide ? 'center' : 'stretch',
        }}
      >
        <Pressable
          testID="sheet-content"
          // Swallows the tap so touching the sheet itself does not close it.
          onPress={() => {}}
          style={{
            backgroundColor: colors.surface,
            borderTopLeftRadius: radius.card,
            borderTopRightRadius: radius.card,
            borderBottomLeftRadius: isWide ? radius.card : 0,
            borderBottomRightRadius: isWide ? radius.card : 0,
            padding: space.lg,
            width: isWide ? 420 : '100%',
            maxWidth: '100%',
          }}
        >
          {title ? (
            <Text variant="headline" style={{ marginBottom: space.md }}>
              {title}
            </Text>
          ) : null}
          {children}
        </Pressable>
      </Pressable>
    </Modal>
  );
}
