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

## Running in Leapcell

Entire repo can be referenced and run by Leapcell. Note all the .env variables need to be added, with one extra:

- GOOLGE_APPLICATION_CREDENTIALS_JSON : <stringified version of the service account .json from firebases console>
