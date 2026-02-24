# xiaoclaw TODO — 30 Optimizations Roadmap

## Priority 1: Reliability & Error Handling
- [x] 1. LLM retry with exponential backoff
- [x] 2. Provider failover (auto-switch on failure)
- [x] 3. Better error messages (user-friendly, actionable)
- [x] 4. Rate limiting (per-user, per-tool)

## Priority 2: Core Features
- [x] 5. Token usage statistics (/stats command)
- [x] 6. Session restore command (/restore <id>)
- [x] 7. Skill enable/disable commands (/skill on/off)
- [x] 8. Conversation export (markdown/json)
- [x] 9. Log level control (--log-level, /loglevel)
- [x] 10. Command aliases (/q = /quit, /t = /tools, etc.)

## Priority 3: Better Intelligence
- [ ] 11. LLM-based compaction (summarize instead of truncate)
- [ ] 12. Prompt template system (customizable system prompts)
- [ ] 13. Multi-language support (i18n for UI strings)

## Priority 4: Built-in Skills
- [ ] 14. Time/date skill (timezone conversion, countdown)
- [ ] 15. Code execution skill (sandboxed Python eval)
- [ ] 16. Translation skill (via LLM)

## Priority 5: Security & Audit
- [ ] 17. Security audit log (tool calls, user actions)
- [ ] 18. Tool permission control (whitelist/blacklist per user)

## Priority 6: Server & API
- [ ] 19. Health check endpoint (/healthz)
- [ ] 20. API server mode (FastAPI)
- [ ] 21. Webhook server mode (receive HTTP callbacks)

## Priority 7: DevOps
- [ ] 22. CI/CD (GitHub Actions: lint, test, build)
- [ ] 23. Test coverage (pytest + coverage)
- [ ] 24. Documentation generation (auto API docs)

## Priority 8: Performance
- [ ] 25. Async tool execution (parallel tool calls)
- [ ] 26. Memory usage optimization (lazy loading)
- [ ] 27. Concurrent session support (multi-user)

## Priority 9: Extensibility
- [ ] 28. Plugin system (pip-installable plugins)
- [ ] 29. Config hot-reload (watch config.yaml changes)
- [ ] 30. More adapters (Discord, Slack, Feishu webhook)
