# QA and verification

Outlaw Forge is verified in layers. Backend tests cover service and API behavior, frontend checks cover linting and the production build, and black-box scripts exercise a running API over HTTP.

## Verification matrix

| Check | Command | Requires running API |
| --- | --- | --- |
| Backend suite | `npm run test:backend` | No |
| Frontend lint | `npm run lint` | No |
| Frontend production build | `npm run build` | No |
| Health smoke test | `npm run test:smoke` | Yes |
| Critical workflow smoke test | `python tests/test_critical_workflow.py --base-url http://127.0.0.1:8000` | Yes |

The PowerShell orchestrator combines the backend suite, frontend build, and health smoke test:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

When a combined run times out, execute the layers independently. This distinguishes a failed check from a slow build or an unavailable local API.

## Quality expectations

- All automated tests pass.
- API responses remain compatible with the shared TypeScript contracts.
- Geometry calculations stay deterministic and use millimetres as the canonical distance unit.
- A source upload is never overwritten by a transformation.
- Unsupported methods and invalid input return a controlled API error.
- The frontend production build completes without type errors.

## Live troubleshooting

If the smoke test cannot connect, start Uvicorn from the repository root with `--app-dir apps/api`. If the frontend cannot reach the API, confirm that `NEXT_PUBLIC_API_BASE_URL` points to `http://127.0.0.1:8000` and that the API CORS origin includes `http://localhost:3000`.
