# Cloudflare R2 — ProofPack object storage

ProofPack stores uploaded documents and generated packet PDFs in an S3-compatible object
store. **Cloudflare R2** is the recommended production backend (free egress, works with the
existing `S3ObjectStore` via boto3).

Railway still hosts the API, Celery worker, Postgres, and Redis. Only blobs move to R2.

## Quick setup

1. **Account ID** — Cloudflare dashboard → Overview → **Account ID** (right sidebar).

2. **Create bucket + env file:**

   ```bash
   export CLOUDFLARE_ACCOUNT_ID=your_32_char_account_id
   ./scripts/cloudflare_r2_setup.sh
   ```

   If `wrangler` cannot list accounts, run `wrangler login` first, or set `account_id` in
   `infra/cloudflare/wrangler.toml`.

3. **R2 API token** — [R2 Overview](https://dash.cloudflare.com/?to=/:account/r2/overview) →
   **Manage** (API Tokens) → **Object Read & Write** → scope to bucket `proofpack` → copy
   Access Key ID + Secret Access Key into `.cloudflare-r2.env` (gitignored).

4. **Apply to Railway** (API + worker must share the same bucket):

   ```bash
   ./scripts/railway_apply_r2.sh
   ```

5. **Verify:**

   ```bash
   set -a && source .cloudflare-r2.env && set +a
   export STORAGE_BACKEND=s3
   cd backend && python scripts/test_r2.py
   python scripts/smoke_test.py https://proofpack-api-production-ed2f.up.railway.app
   ```

## Environment variables

| Variable | R2 value |
| -------- | -------- |
| `STORAGE_BACKEND` | `s3` |
| `S3_ENDPOINT_URL` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `S3_BUCKET` | `proofpack` |
| `S3_REGION` | `auto` |
| `S3_ACCESS_KEY_ID` | from R2 API token |
| `S3_SECRET_ACCESS_KEY` | from R2 API token |

## Notes

- Existing blobs in a Railway bucket are **not** migrated automatically. New uploads go to R2
  after you switch env vars; re-upload documents for active claims if needed.
- EU / FedRAMP buckets use jurisdiction-specific endpoints (see Cloudflare R2 docs).
- Local Docker Compose defaults to `STORAGE_BACKEND=local`; no R2 required for dev.
