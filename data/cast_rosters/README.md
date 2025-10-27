# Cast Roster Directory

Each subfolder provides canonical cast rosters grouped by show and season.

```
data/cast_rosters/<show-slug>/season-<nn>/<Canonical Name>/
  aliases.txt      # Known nicknames and common misspellings
  metadata.json    # Show, season, slug, and role metadata
```

The directory name for each cast member MUST match the correct public spelling. Analyzer services merge these aliases with the database roster to recognize fan misspellings during ingestion.
