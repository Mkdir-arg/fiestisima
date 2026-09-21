import { useWindowDimensions } from 'react-native';

/** Above this width there is a sidebar; below it, bottom tabs. */
export const WIDE_BREAKPOINT = 768;

export function useLayout() {
  const { width } = useWindowDimensions();
  return { isWide: width >= WIDE_BREAKPOINT };
}
