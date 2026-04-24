# Load test — 100 invoice uploads in one minute

Create or reuse a reviewer/admin user, then export an access token:

```bash
TOKEN=ey... \
API_URL=http://localhost:6200 \
k6 run scripts/load-test/k6-upload-100.js
```

The scenario sends 100 upload attempts per minute using the Sprint 5 PDF fixture by default.
HTTP `201` is a success, and `409` is accepted because duplicate checksum protection may reject repeated fixture uploads.

For staging, use:

```bash
TOKEN=ey... \
API_URL=https://staging-raijin.com/api \
PDF_PATH=frontend/e2e/fixtures/invoice-sprint5.pdf \
k6 run scripts/load-test/k6-upload-100.js
```
