// Separate config for the RLS integration suite: it talks to a real
// Supabase project over the network, so it must not run under the
// jest-expo preset (which mocks native modules and is meant for
// component tests) and must not be picked up by the default `npm test`.
module.exports = {
  testEnvironment: 'node',
  testMatch: ['<rootDir>/tests/**/*.integration.test.ts'],
  transform: { '^.+\\.tsx?$': ['babel-jest', { presets: ['babel-preset-expo'] }] },
};
