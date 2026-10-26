const { test, describe } = require('node:test');
const assert = require('node:assert');
const React = require('react');
const ReactDOMServer = require('react-dom/server');
const { loadJsxComponent } = require('./jsxLoader.cjs');

const MessageBubble = loadJsxComponent('../src/components/MessageBubble.jsx');
const EvidenceCard = loadJsxComponent('../src/components/EvidenceCard.jsx');

describe('VisionRAG-X AI Chat Response & Confidence Presentation', () => {
  test('MessageBubble does NOT render "Confidence: 0%" badge in header when confidence is 0', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(MessageBubble, {
        message: {
          role: 'assistant',
          content: 'Answer generation is not configured. Retrieved evidence is shown below:\n- Merge sort runs in O(n log n).',
          confidence: 0,
          evidence: [
            {
              text: 'Merge sort runs in O(n log n).',
              modality: 'ocr',
              page: 6,
              confidence: 0.95,
            },
          ],
        },
      })
    );

    // Verify misleading confidence badge is completely absent
    assert.strictEqual(
      markup.includes('Confidence: 0%'),
      false,
      'Misleading "Confidence: 0%" badge should not be present in response'
    );
    assert.strictEqual(
      markup.includes('Confidence: 0'),
      false,
      'No 0-confidence badge should be displayed in chat response'
    );
  });

  test('MessageBubble does NOT render uncalibrated confidence badge when confidence is 0.8 or arbitrary number', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(MessageBubble, {
        message: {
          role: 'assistant',
          content: 'Here is the verified explanation of the algorithm at 14:32.',
          confidence: 0.8,
          evidence: [],
        },
      })
    );

    // Header should not contain uncalibrated confidence badge
    assert.strictEqual(
      markup.includes('Confidence: 80%'),
      false,
      'Uncalibrated "Confidence: 80%" badge should not be present in response header'
    );
  });

  test('MessageBubble keeps the "VISIONRAG-X VERIFIED RESPONSE" header', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(MessageBubble, {
        message: {
          role: 'assistant',
          content: 'Verified answer regarding sorting algorithms.',
          confidence: 0,
          evidence: [],
        },
      })
    );

    assert.strictEqual(
      markup.includes('VisionRAG-X Verified Response'),
      true,
      'Authoritative "VisionRAG-X Verified Response" header must remain intact'
    );
  });

  test('MessageBubble keeps timestamp citations visible and formatted', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(MessageBubble, {
        message: {
          role: 'assistant',
          content: 'The instructor explained the time complexity at 14:32 and corrected it at 18:45.',
          evidence: [],
        },
      })
    );

    assert.strictEqual(
      markup.includes('14:32'),
      true,
      'Timestamp citation 14:32 must be rendered'
    );
    assert.strictEqual(
      markup.includes('18:45'),
      true,
      'Timestamp citation 18:45 must be rendered'
    );
    assert.strictEqual(
      markup.includes('timestamp-link'),
      true,
      'Clickable timestamp link style must be applied'
    );
  });

  test('MessageBubble keeps evidence provenance toggle and item counts visible', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(MessageBubble, {
        message: {
          role: 'assistant',
          content: 'Answer with evidence.',
          evidence: [
            { text: 'Sample text 1', modality: 'ocr', page: 1, confidence: 0.92 },
            { text: 'Sample text 2', modality: 'asr', timestamp_start: 120, confidence: 0.88 },
          ],
        },
      })
    );

    assert.strictEqual(
      markup.includes('View Provenance Evidence (2 items)'),
      true,
      'Provenance evidence button and count must be rendered'
    );
  });

  test('EvidenceCard preserves meaningful Knowledge Unit extraction confidence metadata', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(EvidenceCard, {
        evidence: {
          text: 'Algorithm complexity derivation.',
          modality: 'ocr',
          page: 3,
          confidence: 0.95,
        },
      })
    );

    assert.strictEqual(
      markup.includes('Confidence:'),
      true,
      'Extraction confidence label on EvidenceCard must be preserved'
    );
    assert.strictEqual(
      markup.includes('95%'),
      true,
      'Extracted atom confidence (95%) must be preserved on EvidenceCard'
    );
    assert.strictEqual(
      markup.includes('OCR Text'),
      true,
      'Modality badge must be displayed'
    );
    assert.strictEqual(
      markup.includes('Page 3'),
      true,
      'Location anchor must be displayed'
    );
  });

  test('MessageBubble renders cross-modal conflict badge when conflicts are present', () => {
    const markup = ReactDOMServer.renderToStaticMarkup(
      React.createElement(MessageBubble, {
        message: {
          role: 'assistant',
          content: 'Contradiction noted between speech and slide.',
          conflicts: [
            {
              conflict_type: 'complexity_disagreement',
              severity: 'high',
              sources: ['asr', 'ocr'],
              claims: ['Spoken: O(n^2)', 'Slide: O(n log n)'],
            },
          ],
        },
      })
    );

    assert.strictEqual(
      markup.includes('Cross-Modal Conflict Detected'),
      true,
      'Conflict alert must remain visible in assistant message'
    );
  });
});
