# Printer profiles

Printer profiles store the build dimensions and nozzle size used by project preparation and printer-fit checks. The current profile contract is deliberately small. It does not model firmware, kinematics, bed shape, toolhead travel, temperature limits, speed, acceleration, or keep-out regions, and it does not generate machine instructions.

## Current profile fields

The FastAPI `PrinterProfile` model in `apps/api/app/models/printer.py` is the source of truth.

| Field | Meaning |
| --- | --- |
| `id` | Local profile identifier assigned by the service |
| `manufacturer` | Printer manufacturer |
| `model` | Printer model name |
| `build_width_mm` | X build dimension in millimetres; must be greater than zero |
| `build_depth_mm` | Y build dimension in millimetres; must be greater than zero |
| `build_height_mm` | Z build dimension in millimetres; must be greater than zero |
| `nozzle_diameter_mm` | Nozzle diameter in millimetres; must be greater than zero |
| `notes` | Optional descriptive text |
| `created_at` | Service timestamp when available |

These rectangular dimensions are used by the workbench's build-volume checks and viewport envelope. A profile is user-editable data and should be checked against the manufacturer's current documentation before relying on a pass/fail result. It is not a full printer or slicer configuration.

## Seeded local profiles

On database initialization, the API seeds these starter values if the profiles are absent:

| Manufacturer | Model | Build width x depth x height (mm) | Nozzle (mm) |
| --- | --- | ---: | ---: |
| Creality | Ender-3 | 220 x 220 x 250 | 0.4 |
| Creality | Ender-3 S1 | 220 x 220 x 270 | 0.4 |
| Bambu Lab | X1-Carbon | 256 x 256 x 256 | 0.4 |
| Prusa | Original Prusa MK4 | 250 x 210 x 220 | 0.4 |
| Voron | Voron 2.4 350 | 350 x 350 x 350 | 0.4 |
| Elegoo | Neptune 4 Pro | 225 x 225 x 265 | 0.4 |

These are starter database records from `apps/api/app/db/database.py`, not machine-tested profiles. Confirm the build dimensions for the exact printer variant and configuration in use.

## API operations

The local API exposes profile listing, creation, and lookup:

- `GET /api/v1/printers`
- `POST /api/v1/printers`
- `GET /api/v1/printers/{printer_id}`

Example create body:

```json
{
  "manufacturer": "Example",
  "model": "Printer Model",
  "build_width_mm": 220,
  "build_depth_mm": 220,
  "build_height_mm": 250,
  "nozzle_diameter_mm": 0.4,
  "notes": "Verify dimensions against the machine configuration."
}
```

Profiles are stored in the local SQLite database. They are not fetched from a vendor catalog or automatically updated.

## Current limits

- The profile schema is rectangular and has no center-origin or cylindrical-bed fields.
- Fit validation uses the profile dimensions; it does not simulate a specific motion system or toolhead collision envelope.
- No profile field is used to emit G-code or configure an external slicer.
- The native Qt viewport does not yet have native printer-profile persistence or printer-aware scene setup.

Printer profile implementation lives in `apps/api/app/models/printer.py`, `apps/api/app/repositories/printer_repo.py`, and `apps/api/app/db/database.py`. Keep any schema changes synchronized with `packages/shared/types/api.ts`.
