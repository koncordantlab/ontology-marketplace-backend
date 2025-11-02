# Ontology Marketplace Backend

FastAPI Server for serving the Ontology Marketplace API.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [API Documentation](#api-documentation)
- [Configuration](#environment-variables)
- [Development](#development)
- [Deployment](#deployment)
- [Caching](#caching)
- [Contributing](#contributing)
- [License](#license)

## Overview

The Ontology Marketplace Backend is a FastAPI-based REST API for managing and searching ontologies stored in Neo4j. It provides authentication via Firebase, supports CRUD operations on ontologies, tag management, and user profile management.

## Features

- 🔍 **Search & Discovery**: Search ontologies by name or description with pagination support
- 📦 **Ontology Management**: Create, read, update, and delete ontologies
- 🏷️ **Tagging System**: Organize ontologies with tags
- 👤 **User Management**: User profiles and permission management
- 🔐 **Authentication**: Firebase-based authentication and authorization
- ⚡ **Caching**: Built-in caching for improved performance (see [CACHING.md](CACHING.md))
- 📊 **Neo4j Integration**: Graph database for storing ontologies and relationships
- 🔄 **RDF Support**: Upload and process RDF/TTL ontology files

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11+** (Python 3.12 recommended)
- **Neo4j Database** (version 5.x or later)
  - Can be installed locally or use Neo4j Aura (cloud)
  - See [Neo4j Installation Guide](https://neo4j.com/docs/operations-manual/current/installation/)
- **Firebase Project** with:
  - Authentication enabled
  - Service account credentials
- **uv** package manager ([Installation Guide](https://github.com/astral-sh/uv))

## Quick Start

### 1. Clone the repository
```bash
git clone <repository-url>
cd ontology-marketplace-backend
```

### 2. Install dependencies
```bash
uv sync
```

### 3. Set up Neo4j

Start Neo4j locally or connect to Neo4j Aura:

```bash
# Local Neo4j (if using Docker)
docker run \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  neo4j:latest
```

### 4. Configure environment variables

Create a `.env` file or set environment variables:

```bash
# Neo4j Configuration
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USERNAME=neo4j
export NEO4J_PASSWORD=your-neo4j-password

# Firebase Configuration
export GOOGLE_PROJECT_ID=your-firebase-project-id
export GOOGLE_APPLICATION_CREDENTIALS_JSON='{"type":"service_account",...}'

# Optional: CORS Configuration
export CORS_ALLOWED_ORIGINS=http://localhost:3000
```

### 5. Run the server

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API**: http://localhost:8000
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## API Documentation

### Interactive Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Available Endpoints

#### Ontology Operations
- `GET /search_ontologies` - Search ontologies (supports pagination and search terms)
- `POST /add_ontologies` - Add new ontologies (requires authentication)
- `PUT /update_ontology/{ontology_uuid}` - Update an ontology (requires authentication)
- `DELETE /delete_ontologies` - Delete ontologies (requires authentication)
- `POST /upload_ontology` - Upload RDF/TTL ontology file (requires authentication)

#### Tag Operations
- `GET /get_tags` - Get all available tags
- `POST /add_tags` - Create new tags (requires authentication)

#### User Operations
- `GET /get_user` - Get current user profile (requires authentication)
- `PUT /update_user` - Update user profile (requires authentication)
- `GET /test-auth` - Test authentication status

#### Other
- `POST /like_ontology/{ontology_id}` - Like an ontology (placeholder, requires authentication)

## Environment Variables

### Required

#### Neo4j Database Configuration
- `NEO4J_URI` - Neo4j connection URI (default: `bolt://localhost:7687`)
- `NEO4J_USERNAME` - Neo4j username (default: `neo4j`)
- `NEO4J_PASSWORD` - Neo4j password (**required**, no default)

#### Firebase Authentication
- `GOOGLE_PROJECT_ID` (or `GOOGLE_CLOUD_PROJECT`, `GCP_PROJECT`, `FIREBASE_PROJECT_ID`, `PROJECT_ID`) - Firebase project ID
- `GOOGLE_APPLICATION_CREDENTIALS_JSON` - Stringified JSON of Firebase service account credentials

### Optional

#### CORS Configuration
- `CORS_ALLOWED_ORIGINS` - Comma-separated list of allowed origins (default: `"*"`)
  - Example: `"https://yourdomain.com,https://www.yourdomain.com,http://localhost:3000"`
  - ⚠️ Use `"*"` only for development, not recommended for production

#### Caching Configuration
- `CACHE_ENABLED` - Enable/disable caching (default: `true`)
- `CACHE_TTL_SECONDS` - Cache entry time-to-live in seconds (default: `300`)
- `CACHE_MAX_SIZE` - Maximum entries in in-memory cache (default: `128`)
- `USE_REDIS_CACHE` - Use Redis instead of in-memory cache (default: `false`)
- `REDIS_URL` - Redis connection URL (default: `redis://localhost:6379/0`)
  - See [CACHING.md](CACHING.md) for detailed caching documentation

#### Neo4j Database
- `NEO4J_DATABASE` - Neo4j database name (default: `neo4j`)

#### Development
- `ALLOW_DEV_AUTH_BYPASS` - Enable development auth bypass (default: `false`)
- `DEV_AUTH_EMAIL` - Default email for dev auth bypass

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

## Development

### Running as a Single Server

Using [uv](https://github.com/astral-sh/uv) for dependency management:

```bash
uv sync
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Methodology

- Can be run as a single server or as multiple Google Cloud Run functions
- Calls are split into separate files, each able to be uploaded as individual Google Cloud Run functions
  - Auth is handled within each separate endpoint to support this

### Updating Requirements

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

### Getting Firebase Auth Token

To test authenticated endpoints in the interactive docs:

```bash
API_KEY="<firebase_web_api_key>"
EMAIL="<user_email>"
PASSWORD="<user_password>"

ID_TOKEN=$(curl -s "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\",\"returnSecureToken\":true}" \
  | jq -r '.idToken')

echo "ID Token: $ID_TOKEN"
```

In the interactive docs, click on the "Authorize" button. In the dialog box, enter the ID_TOKEN directly in the value field (do not prefix with Bearer).

## Deployment

### Recommended Hosting Services

This FastAPI app can be deployed to container-based hosting platforms. Here are three recommended options:

#### 1. **Google Cloud Run** (Recommended - Best for Firebase integration)

Since you're already using Firebase/Google Cloud services, Cloud Run offers seamless integration:

1. **Install gcloud CLI** (if not already installed):
   ```bash
   # macOS
   brew install google-cloud-sdk
   
   # Or download from: https://cloud.google.com/sdk/docs/install
   ```

2. **Authenticate and set project**:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```

3. **Build and deploy**:
   ```bash
   # Build the container image
   gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/ontology-marketplace-backend
   
   # Deploy to Cloud Run
   gcloud run deploy ontology-marketplace-backend \
     --image gcr.io/YOUR_PROJECT_ID/ontology-marketplace-backend \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars "GOOGLE_PROJECT_ID=YOUR_PROJECT_ID,GOOGLE_APPLICATION_CREDENTIALS_JSON=$(cat path/to/credentials.json | jq -c .)"
   ```

   **Note**: For `GOOGLE_APPLICATION_CREDENTIALS_JSON`, you can also set it in the Cloud Run console under "Variables & Secrets".

4. **Set CORS origins** (if needed):
   ```bash
   gcloud run services update ontology-marketplace-backend \
     --set-env-vars "CORS_ALLOWED_ORIGINS=https://yourdomain.com"
   ```

**Benefits**: Pay-per-request pricing, auto-scaling, integrated with Firebase/Google Cloud services

---

#### 2. **Railway** (Easiest Docker deployment)

Railway offers simple Docker-based deployment with a great developer experience:

1. **Sign up** at [railway.app](https://railway.app)

2. **Connect your GitHub repository** or deploy from CLI:
   ```bash
   # Install Railway CLI
   npm i -g @railway/cli
   
   # Login and initialize
   railway login
   railway init
   ```

3. **Set environment variables** in Railway dashboard:
   - `GOOGLE_PROJECT_ID`
   - `GOOGLE_APPLICATION_CREDENTIALS_JSON` (paste full JSON string)
   - `CORS_ALLOWED_ORIGINS` (optional)

4. **Deploy**:
   ```bash
   railway up
   ```

Railway will automatically detect the Dockerfile and deploy. It provides a URL like `https://your-app.up.railway.app`

**Benefits**: Simple setup, automatic HTTPS, integrated monitoring, $5/month starter plan

---

#### 3. **Render** (Good free tier option)

Render offers free tier Docker hosting with easy deployment:

1. **Sign up** at [render.com](https://render.com)

2. **Create a new Web Service** and connect your GitHub repository

3. **Configure**:
   - **Build Command**: (leave empty, Render builds from Dockerfile)
   - **Start Command**: (leave empty, uses Dockerfile CMD)
   - **Environment**: `Docker`

4. **Set environment variables** in Render dashboard:
   - `GOOGLE_PROJECT_ID`: Your Firebase project ID
   - `GOOGLE_APPLICATION_CREDENTIALS_JSON`: **Important** - This must be a stringified JSON of your Firebase service account credentials. To get this:
     
     ```bash
     # Option 1: If you have the service account JSON file
     cat path/to/service-account-key.json | jq -c .
     
     # Option 2: Copy the entire JSON file content and minify it (remove all newlines/whitespace)
     # The entire JSON object should be on one line in the Render environment variable
     ```
     
     **Common mistake**: Don't set individual fields - paste the entire JSON object as a single-line string.
     
     Example format (all on one line):
     ```
     {"type":"service_account","project_id":"your-project-id","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}
     ```
   
   - `CORS_ALLOWED_ORIGINS` (optional): Comma-separated origins, e.g., `https://yourdomain.com,https://www.yourdomain.com`
   - `PORT` (optional - Render sets this automatically)

5. **Deploy**: Render will build and deploy automatically on git push

**Troubleshooting**: If you get `DefaultCredentialsError`, ensure `GOOGLE_APPLICATION_CREDENTIALS_JSON` is set correctly:
- The value must be a valid JSON object (all on one line)
- Copy the entire JSON from your Firebase service account key file
- Make sure there are no extra quotes or escaping issues
- Verify `GOOGLE_PROJECT_ID` matches the project in your credentials

**Benefits**: Free tier available, automatic deployments, built-in SSL

---

### Local Docker Testing

Before deploying, test the Docker image locally:

```bash
# Build the image
docker build -t ontology-marketplace-backend:latest .

# Run locally
docker run --rm -p 8080:8080 \
  -e PORT=8080 \
  -e GOOGLE_PROJECT_ID="$GOOGLE_PROJECT_ID" \
  -e GOOGLE_APPLICATION_CREDENTIALS_JSON="$GOOGLE_APPLICATION_CREDENTIALS_JSON" \
  -e CORS_ALLOWED_ORIGINS="http://localhost:3000" \
  ontology-marketplace-backend:latest
```

The API will be available at `http://localhost:8080/docs`

## Caching

The `/search_ontologies` endpoint includes built-in caching to improve performance and reduce database load. The caching system supports:

- In-memory caching (default)
- Redis caching (for distributed deployments)
- Automatic cache invalidation on data changes
- User-aware caching (respects permissions)

For detailed caching documentation, configuration options, and troubleshooting, see [CACHING.md](CACHING.md).

## Contributing

Contributions are welcome! To contribute:

1. **Open an issue** on GitHub to discuss your proposed changes before submitting a pull request. This helps ensure your contribution aligns with the project goals and avoids duplicate work.

2. **Submit a pull request** with your changes. Please ensure:
   - Your code follows the existing code style
   - Any new dependencies are added to `pyproject.toml`
   - You've tested your changes locally

3. **Wait for review**. The maintainers will review your PR and provide feedback.

Thank you for contributing to the Ontology Marketplace Backend!

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.