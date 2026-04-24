# Shared Contracts

This MVP keeps shared contracts lightweight. API response shapes are mirrored in:

- Backend Pydantic models: `apps/api/app/schemas/dto.py`
- Frontend TypeScript types: `apps/web/lib/api.ts`

TODO: promote these into generated OpenAPI TypeScript clients once the API stabilizes.

