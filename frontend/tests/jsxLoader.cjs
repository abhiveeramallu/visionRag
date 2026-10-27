const fs = require('fs');
const path = require('path');
const sucrase = require('sucrase');

const cache = {};

function resolveModuleFile(fromDir, modulePath) {
  const p = path.resolve(fromDir, modulePath);
  if (fs.existsSync(p) && fs.statSync(p).isFile()) return p;
  if (fs.existsSync(p + '.jsx')) return p + '.jsx';
  if (fs.existsSync(p + '.js')) return p + '.js';
  if (fs.existsSync(p + '.json')) return p + '.json';
  return p + '.jsx';
}

function loadJsxComponent(modulePath, fromDir = __dirname) {
  const resolved = resolveModuleFile(fromDir, modulePath);
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
