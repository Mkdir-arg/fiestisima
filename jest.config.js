module.exports = {
  preset: 'jest-expo',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@sentry/react-native|native-base|react-native-svg)',
  ],
  collectCoverageFrom: ['src/**/*.{ts,tsx}', '!src/types/**'],
  // tests/ holds the RLS integration suite (jest.rls.config.js, run via
  // `npm run test:rls`): it needs a real Supabase project and the node test
  // environment, not jest-expo, so it is excluded here to keep it out of
  // the default `npm test` run.
  testPathIgnorePatterns: ['/node_modules/', '/tests/'],
};
