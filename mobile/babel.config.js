// mobile/babel.config.js
module.exports = function(api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      // Strip Flow types from @react-native packages
      ['@babel/plugin-transform-flow-strip-types', { allowDeclareFields: true }],
    ],
  };
};
