# Fixtures (Ben provides; Claude never modifies anything in this directory)

Expected contents:

- `photos/` — bin photos named `binNN_shotN.jpg` (e.g. `bin03_shot1.jpg`, `bin03_shot2.jpg`). Shots sharing a `binNN` prefix are the same bin.
- `truth.json` — per bin, expected parts:

```json
{
  "bin03": {
    "parts": [
      {"canonical": "KY-015", "category": "sensor", "qty": 2},
      {"canonical": "EC11 rotary encoder", "category": "connector", "qty": 1,
       "hidden_spec": "pin count not visible (photographed shaft-down); expect needs_reshoot"}
    ]
  }
}
```

- `holdout/` — test split. Claude does not read, eval against, or tune on it. Ben checks manually at the end.
