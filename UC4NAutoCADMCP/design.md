# U-C4N workspace design

Applied 2026-10-07 using `C:/Users/minhk/.claude/skills/redesign-existing-projects/SKILL.md` and its Hallmark foundation.

## Purpose

A CAD operator should focus on the conversation, understand the proposed changes, and approve execution deliberately. The existing chat and tool workflows remain the functional source of truth.

## Shared system

- Routes: `/chat` for conversation, `/` and `/settings` for MCP/Codex configuration. The existing manual tools page is hidden from navigation at `/tools`.
- Theme: paper workspace, warm neutral surfaces with a restrained red accent; dark variant retained in localStorage.
- Typography: locally hosted Be Vietnam Pro for interface text and Newsreader for page/welcome headings. Consolas for technical data.
- Canonical colors and font roles: `../UC4NAutoCADMCPClient/client/assets/tokens.css`.
- Shared components/layout: `../UC4NAutoCADMCPClient/client/assets/workspace.css`.
- Shared behavior: `../UC4NAutoCADMCPClient/client/assets/workspace.js`.
- Desktop chat: conversation and composer together, connection panel to the right. Mobile: compact connection controls above conversation.
- Parameters and raw MCP responses use disclosure controls. Never hide the approval action or fabricate a connected/success state.
- Decorative mark: simple CAD drafting corners, also used for the favicon. No external runtime assets or animation libraries.
- Interactions: visible keyboard focus, native disabled controls, local inline messages, reduced-motion support.

## Verification

Browser evidence: `../.harness/artifacts/uc4n-redesign/`.
Both themes checked at 320, 375, 414, 768, 1280 and 1440 px. Mocked UI checks cover file upload, chat, proposal approval and result rendering; no CAD calls were executed.

Self-review: Philosophy 4/5, Hierarchy 4/5, Execution 4/5, Specificity 4/5, Restraint 4/5, Variety 4/5. App pages intentionally share a single visual system.
