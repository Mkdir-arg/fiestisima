export const colors = {
  background: '#F2F2F7',
  surface: '#FFFFFF',
  separator: '#E5E5EA',
  fill: '#EFEFF4',
  text: '#000000',
  textSecondary: '#6C6C70',
  textTertiary: '#8E8E93',
  blue: '#0066E0',
  blueTint: '#EAF2FE',
  redText: '#C9251B',
  redTint: '#FFE5E3',
  amberText: '#9A5400',
  amberTint: '#FFF0D9',
  chevron: '#C4C4C6',
  // The tab bar sits on top of `background`, so it is a touch
  // brighter than `surface` and its hairline a touch darker than
  // `separator` - the same relationship iOS uses.
  tabBar: '#FBFBFD',
  tabBarBorder: '#D8D8DC',
  // Backdrop behind a `Sheet`. Black rather than a token colour tinted,
  // because it sits over arbitrary content and needs to darken it evenly.
  overlay: 'rgba(0, 0, 0, 0.35)',
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { pill: 100, card: 12, control: 10, small: 8 } as const;

/** Minimum height for anything tappable. Used with wet hands. */
export const HIT_SIZE = 44;

export const type = {
  largeTitle: { fontSize: 34, fontWeight: '700', letterSpacing: -0.8 },
  title: { fontSize: 22, fontWeight: '700', letterSpacing: -0.5 },
  headline: { fontSize: 17, fontWeight: '600', letterSpacing: -0.3 },
  body: { fontSize: 17, fontWeight: '400' },
  subhead: { fontSize: 14, fontWeight: '400' },
  footnote: { fontSize: 13, fontWeight: '400' },
  caption: { fontSize: 12, fontWeight: '500' },
} as const;

export type TypeVariant = keyof typeof type;
