const fs = require('fs');
const path = require('path');
const sucrase = require('sucrase');

const cache = {};

function loadJsxComponent(modulePath, fromDir = __dirname) {
  const resolved = path.resolve(fromDir, modulePath.endsWith('.jsx') ? modulePath : modulePath + '.jsx');
  if (cache[resolved]) {
    return cache[resolved];
  }

  const rawCode = fs.readFileSync(resolved, 'utf8');
  const compiled = sucrase.transform(rawCode, {
    transforms: ['jsx', 'imports'],
    production: true,
  });

  const moduleObj = { exports: {} };
  const customRequire = (importPath) => {
    if (importPath.startsWith('.')) {
      return loadJsxComponent(importPath, path.dirname(resolved));
    }
    return require(importPath);
  };

  const runner = new Function('require', 'module', 'exports', compiled.code);
  runner(customRequire, moduleObj, moduleObj.exports);

  const exported = moduleObj.exports.default || moduleObj.exports;
  cache[resolved] = exported;
  return exported;
}

module.exports = { loadJsxComponent };
