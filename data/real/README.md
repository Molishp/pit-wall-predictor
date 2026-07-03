# Real race-data bundle

Put completed-race CSV sources here and import them into the app with:

```powershell
.\.venv\Scripts\python.exe -m src.real_data_importer --manifest data\real\source_manifest.csv --overwrite
```

The manifest must include these columns:

- `season`
- `race_name`
- `race_date`
- `country`
- `circuit`
- `status`
- either `source_url` or `local_csv`

Optional columns:

- `source_type`
- `source_note`
- `total_laps`

Recommended workflow:

1. Export or download one CSV per completed race from a credible source.
2. Fill the manifest with the race metadata and the CSV location.
3. Run the importer.
4. The app will prefer the imported real-data bundle automatically.
