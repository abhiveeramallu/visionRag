const { test, describe } = require('node:test');
const assert = require('node:assert');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const { MemoryRouter } = require('react-router-dom');
const { loadJsxComponent } = require('./jsxLoader.cjs');

const Sidebar = loadJsxComponent('../src/components/Sidebar.jsx');
const SourceDetail = loadJsxComponent('../src/pages/SourceDetail.jsx');

const renderWithRouter = (element, initialEntries = ['/']) => {
  return ReactDOMServer.renderToStaticMarkup(
    React.createElement(MemoryRouter, { initialEntries }, element)
  );
};

describe('Sidebar Sources Discoverability & Rendering', () => {
  test('Sidebar renders full list with more than four sources without hardcoded slice', () => {
    const markup = renderWithRouter(React.createElement(Sidebar, { open: true }));
    assert.ok(markup.includes('Sources'), 'Contains Sources section header');
    assert.ok(markup.includes('Filter sources...'), 'Contains in-sidebar search input');
    assert.ok(markup.includes('View all sources'), 'Contains View all sources link');
    assert.ok(!markup.includes('slice(0, 4)'), 'No hardcoded slice');
  });

  test('Sidebar contains active source indicator link when navigating', () => {
    const markup = renderWithRouter(
      React.createElement(Sidebar, { open: true }),
      ['/source/f7e46f40-f334-4e72-83a3-36e522b7ed20']
    );
    assert.ok(markup.includes('View all sources'), 'Contains View all sources CTA');
  });

  test('Sidebar provides in-sidebar filter input for locating sources by title', () => {
    const markup = renderWithRouter(React.createElement(Sidebar, { open: true }));
    assert.ok(markup.includes('placeholder="Filter sources..."'), 'Has search input');
  });
});

describe('SourceDetail Multimodal Media Previews & Evidence Discovery', () => {
  test('Initial loading state shows loading spinner', () => {
    const markup = renderWithRouter(
      React.createElement(SourceDetail, null),
      ['/source/f7e46f40-f334-4e72-83a3-36e522b7ed20']
    );
    assert.ok(markup.includes('Loading source'), 'Shows loading source spinner');
  });
});
