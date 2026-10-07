# Backend Requests

1. `GET /v1/api-keys`: The UI spec asks for a `status` column for API keys. Currently, the API returns `expires_at`, `revoked_at`, etc. but no explicit `status` field (e.g., active, expired, revoked). Please add a `status` string field to the API Key response object.
