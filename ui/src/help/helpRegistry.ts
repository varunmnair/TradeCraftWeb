import { default as indexContent } from '../help/index.md?raw';

export type HelpId = 'app' | 'holdings' | 'buy-entries' | 'gtt-orders' | 'ai-analyst';

export interface HelpEntry {
  id: HelpId;
  title: string;
  content: string;
}

const helpRegistry: Record<HelpId, HelpEntry> = {
  app: {
    id: 'app',
    title: 'Help',
    content: indexContent,
  },
  holdings: {
    id: 'holdings',
    title: 'Holdings',
    content: '<!-- Holdings help content placeholder -->',
  },
  'buy-entries': {
    id: 'buy-entries',
    title: 'Buy Entries',
    content: '<!-- Buy entries help content placeholder -->',
  },
  'gtt-orders': {
    id: 'gtt-orders',
    title: 'GTT Orders',
    content: '<!-- GTT orders help content placeholder -->',
  },
  'ai-analyst': {
    id: 'ai-analyst',
    title: 'AI Analyst',
    content: '<!-- AI analyst help content placeholder -->',
  },
};

export function getHelpContent(helpId: HelpId): HelpEntry {
  return helpRegistry[helpId] || helpRegistry.app;
}

export function getAllHelpIds(): HelpId[] {
  return Object.keys(helpRegistry) as HelpId[];
}
