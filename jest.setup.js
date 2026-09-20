// @testing-library/react-native v14 no longer exposes an `/extend-expect`
// subpath; importing the package's main entry registers the same custom
// jest matchers as a side effect (see its dist/index.js).
require('@testing-library/react-native');
