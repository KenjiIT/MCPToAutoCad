# 071026-uc4n-workspace-redesign

**Type:** draft
**Status:** proposed
**Tags:** redesign-existing-projects, output-report
**Proposed:** 2026-10-07

## What

Redesigned the U-C4N chat, settings, and hidden tools pages with a shared light/dark design system, self-hosted Vietnamese fonts and a conversation-focused layout.

## Output

- Integrated conversation/composer with inline file attachment.
- Added a settings page for the MCP endpoint, Codex agent mode, model, and reasoning level. Saved choices now apply to new chat jobs.
- Hid the manual tools page from the main navigation while preserving it at `/tools`.
- Secondary connection settings and explicit approval controls.
- Shared navigation, accessible focus states, responsive layouts, collapsible technical details.
- Browser screenshots and mocked workflow verification in `.harness/artifacts/uc4n-redesign/`.

## Files

| File | Action |
|------|--------|
| `UC4NAutoCADMCPClient/client/chat.html` | modified |
| `UC4NAutoCADMCPClient/client/index.html` | modified |
| `UC4NAutoCADMCPClient/client/settings.html` | created |
| `UC4NAutoCADMCPClient/client/api.py` | modified: static assets route |
| `UC4NAutoCADMCPClient/client/assets/` | created: styles, fonts, theme behavior, favicon |
| `UC4NAutoCADMCP/design.md` | created |
| `UC4NAutoCADMCP/.hallmark/log.json` | created |

## Notes

- Invoked via: `/redesign-existing-projects` skill from the user-specified `.claude/skills` directory.
- Used existing `.llmwiki/wiki` location rather than creating another wiki tree.
- Verified both themes at six viewport widths; API calls in interaction checks were mocked. No live CAD execution or AI generation was performed.
- Existing MCP/Coordinator execution logic was retained. Client restarted to serve the new static asset directory.

## Origin

- **Draft:** `wiki/draft/uiux/071026-uc4n-workspace-redesign.md`
- **Commit:** _(not committed)_
- **Date promoted:** _(not promoted)_
