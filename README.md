# Ontology Marketplace Backend

FastAPI Server for serving the Ontology Marketplace API.

## Methodology

- Can be run as a single server or as multiple Google Cloud Run functions
- Calls are split into separate files, each able to be uploaded as individual Google Cloud Run functions
  - Auth is handled within each separate endpoint to support this

## Running as a single server

Using [uv](https://github.com/astral-sh/uv) for dependency management

```
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive docs will then be available at http://localhost:8000/docs

Getting Firebase Auth Token to test in docs

```
API_KEY="<firebase_web_api_key>"
EMAIL="<user_email>"
PASSWORD="<user_password>"

ID_TOKEN=$(curl -s "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"returnSecureToken\":true}" \
  | jq -r '.idToken')

echo "ID Token: $ID_TOKEN"
```

In the interactive docs, click on the "Authorize" button. In the dialog box, enter in the ID_TOKEN directly in the value field (do not prefix with Bearer).

## Environment Variables

### Required for Firebase Authentication
- `GOOGLE_PROJECT_ID` (or `GOOGLE_CLOUD_PROJECT`, `GCP_PROJECT`, `FIREBASE_PROJECT_ID`, `PROJECT_ID`): Firebase project ID
- `GOOGLE_APPLICATION_CREDENTIALS_JSON`: Stringified JSON of Firebase service account credentials

### Optional
- `CORS_ALLOWED_ORIGINS`: Comma-separated list of allowed origins for CORS (default: "*")
  - Example: `"https://yourdomain.com,https://www.yourdomain.com,http://localhost:3000"`
  - Use `"*"` to allow all origins (not recommended for production)

## Running in Leapcell

Entire repo can be referenced and run by Leapcell. Note all the .env variables need to be added, with one extra:

- GOOGLE_APPLICATION_CREDENTIALS_JSON : <stringified version of the service account .json from firebases console>
