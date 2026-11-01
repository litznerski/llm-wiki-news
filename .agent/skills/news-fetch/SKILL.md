---
name: news-fetch
description: Extracts today's Sudan conflict and war economy news from GDELT 2.0 via Google BigQuery, extracts full articles using Trafilatura into raw/articles/ with deduplication, and archives the processed feed JSON into news/archived/.
---

# News Fetch Skill (`news-fetch`)

> [!NOTE] Canonical Reference
> This skill is an alias for [`gdelt-news-fetch`](file:///Users/christoflitznerski/MyObsidian/news01/llm-wiki-news/.agent/skills/gdelt-news-fetch/SKILL.md).

## Quickstart

Run the orchestrator script to harvest today's news from GDELT BigQuery, extract full articles via Trafilatura to `raw/articles/`, and archive the feed JSON to `news/archived/`:

```bash
python3 scripts/harvest_daily_news.py
```

See [`.agent/skills/gdelt-news-fetch/SKILL.md`](file:///Users/christoflitznerski/MyObsidian/news01/llm-wiki-news/.agent/skills/gdelt-news-fetch/SKILL.md) for full documentation, manual step-by-step instructions, and BigQuery authentication details.
