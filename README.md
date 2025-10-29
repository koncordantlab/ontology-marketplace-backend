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

### Updating requirements.txt with uv

`requirements.txt` is generated from `pyproject.toml` using `uv`. After changing dependencies in `pyproject.toml`, regenerate the lock file with:

```bash
uv pip compile pyproject.toml -o requirements.txt
```

Optionally, to upgrade all pinned versions to the latest compatible releases:

```bash
uv pip compile --upgrade pyproject.toml -o requirements.txt
```

### Using Python 3.12 with uv (if `uv run python -V` shows 3.13)

If your environment or lock files were created with Python 3.13, recreate them for 3.12:

```bash
# Ensure Python 3.12 is available to uv
uv python install 3.12

# Remove any existing virtual environment
rm -rf .venv

# (Optional) regenerate lock/pins for 3.12
uv lock --python 3.12 || true
# Or, if using requirements.txt pins
uv pip compile --upgrade pyproject.toml -o requirements.txt

# Sync dependencies for Python 3.12
uv sync --python 3.12

# Verify the version uv will run
uv run --python 3.12 python -V
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

### Local Development Testing

For local frontend testing without Firebase authentication, you can enable a development auth bypass:

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. In your `.env` file, set:
   ```bash
   ALLOW_DEV_AUTH_BYPASS=1
   DEV_AUTH_EMAIL=your-email@example.com
   ```

3. When making HTTP requests from your frontend, include the `X-Dev-Email` header:
   ```javascript
   fetch('http://localhost:8000/search_ontologies', {
     headers: {
       'X-Dev-Email': 'your-email@example.com',
       'Content-Type': 'application/json'
     }
   })
   ```

Alternatively, if you set `DEV_AUTH_EMAIL` in the `.env` file, you don't need to include the header - the backend will automatically use that email.

**Note**: This bypass should NEVER be enabled in production!