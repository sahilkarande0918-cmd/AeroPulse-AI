# Integration guide

AeroPulse ingests four record types through `POST /api/ingestion/{source}` (multipart: `file`, `source_name`).
Roles: administrator or maintenance officer. Files: `.csv` (UTF-8, header row) or `.json` (list of objects or
`{"records": [...]}`), ≤ 5 MB. Sample files with deliberate faults live in `data/samples/`.

Every import produces an `IngestionBatch` with counts (accepted / updated / duplicates / conflicts / rejected), a
row-level report, the mapping version, the source identifier and a SHA-256 of the file. Re-uploading an identical
file returns the earlier batch (idempotent). Records keep their `batch_id` for provenance.

## Mapping configuration

`backend/app/mappings/mapping_v1.json` defines column aliases, required columns, enumerations, canonical sensor units,
unit aliases and conversions, and the timezone assumed for naive timestamps (`Asia/Kolkata`). To adapt to an
authorised source system, copy it to `mapping_v2.json`, change `version`, and point `MAPPING` at it — the version is
recorded on every batch.

## Contracts

### `sensor` — health-monitoring time series
| Column | Required | Notes |
|---|---|---|
| `engine_serial` (alias `esn`, `engine`) | yes | must match a registered engine; unknown assets are rejected, never auto-created |
| `cycle` | yes | integer ≥ 1 |
| `recorded_at` (alias `timestamp`, `time`) | yes | ISO 8601; offsets honoured, naive = mapping timezone; stored as UTC |
| `s1` … `s21` | any subset | optional unit in the header, e.g. `s3 [K]`; convertible units (K, degC → degR; kPa → psia; kg/s → lbm/s) are converted, unknown/incompatible units reject the batch; empty cells are stored as missing and flagged by TrustTwin |

Natural key: (engine, cycle). Identical → duplicate. Different values → **conflict, not merged**. Accepted rows trigger
a fresh prediction for the affected engines.

### `maintenance` — technical records
`source_record_id`, `aircraft_tail`, `performed_at`, `record_type` ∈ {inspection, repair, replacement, servicing,
defect}, `description`; optional `engine_serial` (must be fitted to that aircraft), `performed_by`.
Key: (source_name, source_record_id).

### `parts` — spare-part inventory snapshot
`part_number` (`[A-Z0-9][A-Z0-9-_.]{1,63}`), `name`, `on_hand`, `reorder_threshold`; optional `unit`,
`replenishment_qty`, `replenishment_eta`, `lead_time_days`. Key: part number. Same identity with new quantities →
updated (audited in the batch); same part number with a different name or unit → **identity conflict, rejected**.

### `work_orders`
`external_id`, `aircraft_tail`, `title`, `task_type` ∈ {inspection, replacement, servicing, troubleshooting},
`required_skill` ∈ {powerplant, avionics, ndt, airframe}, `duration_hours` 1–12, `priority` 1–4, `due_at`;
optional `engine_serial`, `parts` (`PN:qty;PN:qty` in CSV or a list in JSON), `predecessors` (external ids defined
earlier in the same source). Imported work orders arrive as `pending` approval.

## Replacing synthetic sources with authorised systems
1. Register real asset identifiers (aircraft, engines) through an administrative process — ingestion never creates assets.
2. Map the source system's export into the contracts above (or write a thin adapter that emits them).
3. Validate sensor semantics and units with domain engineers; extend `sensor_units` / conversions as needed.
4. Retrain and re-validate the model on authorised data before any prediction is shown to maintainers (see roadmap).
5. Schedule imports from the source system's export location; failed batches remain visible in the ingestion log.

No real defence-system API or proprietary data is used or assumed by this prototype.
