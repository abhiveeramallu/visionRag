const { test, describe } = require('node:test');
const assert = require('node:assert');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const { MemoryRouter } = require('react-router-dom');
const { loadJsxComponent } = require('./jsxLoader.cjs');

const ProcessingStatus = loadJsxComponent('../src/components/ProcessingStatus.jsx');

const renderWithRouter = (element) => {
  return ReactDOMServer.renderToStaticMarkup(
    React.createElement(MemoryRouter, null, element)
  );
};

describe('ProcessingStatus Component Lifecycle & Recovery UI', () => {
  test('Renders active progress and step for running OCR', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(ProcessingStatus, {
        jobStatus: {
          status: 'processing',
          current_step: 'Running OCR (45/120 frames)',
          progress: 0.52,
          elapsed_seconds: 42.5,
          last_heartbeat_seconds_ago: 3.0,
        },
        sourceId: 'src-test-1',
      })
    );

    assert.ok(markup.includes('Running OCR (45/120 frames)'), 'Shows granular OCR step');
    assert.ok(markup.includes('52%'), 'Shows 52% progress');
    assert.ok(markup.includes('Elapsed: 42s'), 'Shows elapsed duration');
    assert.ok(markup.includes('Building verified knowledge'), 'Shows active title');
  });

  test('Displays failed state with clear error and Retry Ingestion button', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(ProcessingStatus, {
        jobStatus: {
          status: 'failed',
          current_step: 'Failed',
          progress: 0.40,
          error: 'Tesseract encountered an unexpected error on frame 12',
          elapsed_seconds: 55.0,
        },
        sourceId: 'src-failed-1',
        onRetry: () => {},
      })
    );

    assert.ok(markup.includes('Processing failed'), 'Shows failure title');
    assert.ok(markup.includes('Tesseract encountered an unexpected error on frame 12'), 'Shows error message');
    assert.ok(markup.includes('Retry Ingestion'), 'Provides Retry Ingestion button');
  });

  test('Displays timed_out state with stage details and Retry Ingestion button', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(ProcessingStatus, {
        jobStatus: {
          status: 'timed_out',
          current_step: 'OCR analysis timed out',
          progress: 0.45,
          error: 'An ingestion stage timed out while processing. Click Retry to re-run.',
          elapsed_seconds: 300.0,
        },
        sourceId: 'src-timeout-1',
        onRetry: () => {},
      })
    );

    assert.ok(markup.includes('Stage timeout'), 'Shows stage timeout label');
    assert.ok(markup.includes('Processing timed out'), 'Shows timed out header');
    assert.ok(markup.includes('Retry Ingestion'), 'Provides Retry Ingestion button');
  });

  test('Displays stalled warning banner when heartbeat is delayed (>90s)', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(ProcessingStatus, {
        jobStatus: {
          status: 'processing',
          current_step: 'Running OCR',
          progress: 0.50,
          elapsed_seconds: 240.0,
          last_heartbeat_seconds_ago: 120.0,
        },
        sourceId: 'src-stalled-1',
        isStalled: true,
        onRetry: () => {},
      })
    );

    assert.ok(markup.includes('Heartbeat warning') || markup.includes('stalled'), 'Shows stalled/heartbeat warning');
    assert.ok(markup.includes('Restart Ingestion') || markup.includes('Retry'), 'Provides action to restart stalled ingestion');
    assert.ok(markup.includes('120s ago'), 'Indicates how long heartbeat has been missing');
  });

  test('Displays completed state with Ready step and link to Knowledge Units', () => {
    const markup = renderWithRouter(
      React.createElement(ProcessingStatus, {
        jobStatus: {
          status: 'completed',
          current_step: 'Done',
          progress: 1.0,
          elapsed_seconds: 88.0,
        },
        sourceId: 'src-completed-1',
      })
    );

    assert.ok(markup.includes('Your material is ready'), 'Shows material is ready');
    assert.ok(markup.includes('Start Learning'), 'Shows link to start learning');
    assert.ok(markup.includes('View Knowledge Units'), 'Shows link to view knowledge units');
  });
});
