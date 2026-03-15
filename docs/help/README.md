# TradeCraftX Help System

## Overview
Phase 1 implements a minimal in-app documentation framework with a global Help button in the header.

## File Locations

### Authoring (Canonical)
- **Top-level help**: `docs/help/index.md` - Edit this file to add help content
- **Future help docs**: `docs/help/holdings.md`, `docs/help/buy-entries.md`, etc.

### Bundled with UI
- `ui/src/help/index.md` - Copied from `docs/help/index.md` for bundling
- **Note**: Keep these files in sync manually for now

## How to Add Help Content

1. Edit `docs/help/index.md` with your Markdown content
2. Copy the content to `ui/src/help/index.md`
3. Run `npm run dev` in the `ui/` directory to see changes

## Future Phases

### Phase 2: Per-Screen Docs
- Add more help files to `docs/help/` and `ui/src/help/`
- Update `helpRegistry.ts` with new helpId mappings
- Enable `HELP_ANCHOR_ENABLED` flag in `HelpAnchor.tsx`

### Phase 3: Tooltips
- Use `HelpTooltip` component to add contextual tooltips
- Populate tooltip content via `helpRegistry.ts`

## Components

- `HelpPanel`: Modal that renders markdown content
- `HelpAnchor`: Link component for page-level help (disabled in Phase 1)
- `HelpTooltip`: Wrapper for MUI Tooltip (ready for future use)
- `helpRegistry.ts`: Maps helpId to markdown content
