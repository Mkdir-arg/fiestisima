import { View } from 'react-native';
import { Button } from './Button';
import { Icon, type IconName } from './Icon';
import { Text } from './Text';
import { colors, space } from './tokens';

type Props = {
  icon: IconName;
  title: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
};

/**
 * Replaces a bare grey sentence: an icon, a headline, one explanatory
 * line, and an optional primary action. Used for "there is nothing here
 * yet", "nothing matches", and "this is not built yet" alike — the
 * difference is entirely in the props the caller passes.
 */
export function EmptyState({ icon, title, message, actionLabel, onAction }: Props) {
  return (
    <View style={{ alignItems: 'center', paddingVertical: space.xxl, paddingHorizontal: space.lg }}>
      <View
        style={{
          width: 64,
          height: 64,
          borderRadius: 32,
          backgroundColor: colors.fill,
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: space.lg,
        }}
      >
        <Icon name={icon} size={30} color={colors.textSecondary} />
      </View>
      <Text variant="headline" style={{ textAlign: 'center', marginBottom: message ? space.xs : 0 }}>
        {title}
      </Text>
      {message ? (
        <Text
          variant="subhead"
          tone="secondary"
          style={{ textAlign: 'center', maxWidth: 320, marginBottom: space.lg }}
        >
          {message}
        </Text>
      ) : null}
      {actionLabel && onAction ? (
        <View style={{ marginTop: message ? 0 : space.lg, alignSelf: 'stretch', maxWidth: 280 }}>
          <Button title={actionLabel} onPress={onAction} />
        </View>
      ) : null}
    </View>
  );
}
