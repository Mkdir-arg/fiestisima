// @testing-library/react-native v14 no longer exposes an `/extend-expect`
// subpath; importing the package's main entry registers the same custom
// jest matchers as a side effect (see its dist/index.js).
require('@testing-library/react-native');

// babel-preset-expo inlines EXPO_PUBLIC_* vars from .env files at bundle
// time, which does not happen under plain Jest. src/lib/api.ts throws at
// module load if this is missing, so tests need a value; it is never used
// for a real network call since fetch is mocked wherever this matters.
process.env.EXPO_PUBLIC_API_URL = process.env.EXPO_PUBLIC_API_URL || 'https://api.test.invalid';
