module.exports = {
  preset: 'jest-expo',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  // The default 5s per-test timeout is flaky once enough screen tests run
  // in parallel worker processes (CPU contention on a full `npm test` run,
  // not a real hang — every one of these passes in well under a second in
  // isolation or with --runInBand). Raised rather than reduced parallelism,
  // to keep the full suite fast.
  testTimeout: 15000,
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@sentry/react-native|native-base|react-native-svg)',
  ],
  collectCoverageFrom: ['src/**/*.{ts,tsx}', '!src/types/**'],
};
