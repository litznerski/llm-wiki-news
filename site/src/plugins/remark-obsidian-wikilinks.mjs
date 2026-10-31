import { visit } from 'unist-util-visit';

const WIKILINK_REGEX = /\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|([^\]]+))?\]\]/g;
const CALLOUT_HEADER_REGEX = /^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION|DANGER|EXAMPLE|INFO|QUESTION|QUOTE)\](?:\s*([^\n]*))?/i;

const CALLOUT_ICONS = {
  note: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>',
  tip: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/></svg>',
  important: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  warning: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
  caution: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  danger: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  example: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><polyline points="10 2 10 10 13 7 16 10 16 2"/></svg>',
};

function slugify(text) {
  if (!text) return '';
  return text
    .toString()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w-]+/g, '')
    .replace(/--+/g, '-');
}

/**
 * Remark plugin to transform Obsidian wikilinks and callouts into Astro-compatible HTML elements.
 */
export function remarkObsidianWikilinks(options = {}) {
  const urlPrefix = options.urlPrefix || '/wiki';

  return (tree) => {
    // 1. Process Wikilinks in Text nodes
    visit(tree, 'text', (node, index, parent) => {
      if (!node.value || !node.value.includes('[[')) return;

      const children = [];
      let lastIndex = 0;
      let match;

      WIKILINK_REGEX.lastIndex = 0;
      while ((match = WIKILINK_REGEX.exec(node.value)) !== null) {
        const [fullMatch, rawTarget, rawAnchor, rawAlias] = match;
        const matchStart = match.index;

        if (matchStart > lastIndex) {
          children.push({
            type: 'text',
            value: node.value.slice(lastIndex, matchStart),
          });
        }

        let targetName = rawTarget.trim().replace(/^wiki\//, '');
        // Remove folder prefix if present (e.g., sources/smith -> smith)
        const targetLeaf = targetName.split('/').pop() || targetName;
        const slug = slugify(targetLeaf);
        const anchor = rawAnchor ? `#${slugify(rawAnchor.trim())}` : '';
        const displayText = rawAlias
          ? rawAlias.trim()
          : (rawAnchor ? `${targetName} § ${rawAnchor.trim()}` : targetName);

        // Check if target is a raw evidence file (like PDFs or books)
        const isRawEvidence = 
          targetName.toLowerCase().startsWith('raw/') || 
          targetName.toLowerCase().endsWith('.pdf') ||
          targetName.toLowerCase().endsWith('.mp4');

        if (isRawEvidence) {
          const displayLabel = rawAlias ? rawAlias.trim() : targetLeaf;
          children.push({
            type: 'html',
            value: `<span class="wiki-link-unresolved" title="Primary raw evidence source: ${targetName}"><span class="unresolved-icon">📄</span>${displayLabel}</span>`,
          });
          lastIndex = matchStart + fullMatch.length;
          continue;
        }

        // Check if target is an un-published private vault primitive (like audit dossiers)
        const isPrivate = 
          targetName.toLowerCase().startsWith('ingestions/') ||
          targetName.toLowerCase().includes('/ingestions/');

        if (isPrivate) {
          const displayLabel = rawAlias ? rawAlias.trim() : targetName.replace(/^wiki\//, '');
          children.push({
            type: 'html',
            value: `<span class="wiki-link-unresolved" title="Internal audit primitive: ${targetName}"><span class="unresolved-icon">🔒</span>${displayLabel}</span>`,
          });
        } else {
          let cleanDisplayText = displayText;
          if (!rawAlias && !rawAnchor) {
            cleanDisplayText = targetLeaf;
          }

          children.push({
            type: 'link',
            url: `${urlPrefix}/${slug}${anchor}`,
            data: {
              hProperties: {
                className: ['wiki-link', 'published-link'],
                title: `Open knowledge primitive: ${targetName}`,
              },
            },
            children: [{ type: 'text', value: cleanDisplayText }],
          });
        }

        lastIndex = matchStart + fullMatch.length;
      }

      if (lastIndex < node.value.length) {
        children.push({
          type: 'text',
          value: node.value.slice(lastIndex),
        });
      }

      parent.children.splice(index, 1, ...children);
      return index + children.length;
    });

    // 2. Process Obsidian Callouts in Blockquote nodes
    visit(tree, 'blockquote', (node) => {
      if (!node.children || node.children.length === 0) return;
      const firstChild = node.children[0];
      if (firstChild.type !== 'paragraph' || !firstChild.children || firstChild.children.length === 0) return;

      const firstTextNode = firstChild.children[0];
      if (firstTextNode.type !== 'text') return;

      const match = firstTextNode.value.match(CALLOUT_HEADER_REGEX);
      if (!match) return;

      const typeKey = match[1].toLowerCase();
      const rawTitle = (match[2] || '').trim();
      const title = rawTitle || typeKey.toUpperCase();
      const icon = CALLOUT_ICONS[typeKey] || CALLOUT_ICONS.note;

      // Strip callout token from the first text node
      firstTextNode.value = firstTextNode.value.replace(CALLOUT_HEADER_REGEX, '').trimStart();
      if (!firstTextNode.value && firstChild.children.length === 1) {
        node.children.shift();
      }

      // Add callout classes to blockquote data
      node.data = node.data || {};
      node.data.hProperties = node.data.hProperties || {};
      node.data.hProperties.className = ['obsidian-callout', `callout-${typeKey}`];

      // Insert header before children
      node.children.unshift({
        type: 'html',
        value: `<div class="obsidian-callout-header"><span class="obsidian-callout-icon">${icon}</span><span class="obsidian-callout-title">${title}</span></div>`,
      });
    });
  };
}

export default remarkObsidianWikilinks;
