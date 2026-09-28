# ✈️ Travel Concierge Assistant (`travel-concierge-agent`)

A personalized, multimodal AI travel concierge agent built with **Google ADK (Agent Development Kit)** and **Google Cloud AI Platform**. The agent helps travelers discover destinations, search catalog items, retrieve weather and local time, find nearby points of interest, convert currencies, generate AI visual artwork and short video previews, and render dynamic interactive **A2UI (Agent-to-User Interface)** cards.

---

## 🌟 Architecture & Features

The agent is powered by **Gemini 2.5 Flash** as its core reasoning engine and incorporates long-term memory, cloud storage, database persistence, and multimodal generation tools.

```
                  +-----------------------------------+
                  |   Custom Web Frontend / A2UI UI   |
                  +-----------------+-----------------+
                                    |
                                    v
                  +-----------------+-----------------+
                  |      FastAPI Proxy Server         |
                  +-----------------+-----------------+
                                    |
                                    v
                  +-----------------+-----------------+
                  |     travel-concierge-agent       |
                  |     (Google ADK / Gemini 2.5)     |
                  +-----------------+-----------------+
                                    |
       +----------------------------+----------------------------+
       |                            |                            |
       v                            v                            v
+--------------+           +------------------+        +-------------------+
|  Firestore   |           |  Cloud Storage   |        |  Memory Bank      |
| Destination  |           | Media Bucket     |        | (Vertex AI        |
| Catalog      |           | (Images & Videos)|        |  Memory Bank)     |
+--------------+           +------------------+        +-------------------+
```

---

## 🛠️ Implemented Tools & Google Cloud Integrations

Based on the implementation in [`app/agent.py`](file:///config/Desktop/Session1/travel-concierge-agent/app/agent.py) and [`agents-cli-manifest.yaml`](file:///config/Desktop/Session1/travel-concierge-agent/agents-cli-manifest.yaml), the following tools and services are fully integrated:

### 1. 🧠 Long-Term Memory & User Context
- **Vertex AI Memory Bank Service**: Connects to Vertex AI Memory Bank (`VertexAiMemoryBankService`) to recall user dietary restrictions, travel preferences, budget constraints, and past trip history (`preload_memory_tool`, `load_memory_tool`).

### 2. 🗄️ Database & Catalog Management
- **Google Cloud Firestore**: Persists destination catalogs, tags, categories, and estimated costs in collection `destinations` (`search_destinations`, `add_destination`, `get_destination_details`).

### 3. 🎨 Multimodal Media Generation & Storage
- **Google Cloud Storage**: Stores generated destination assets in a dedicated public bucket (`travel-concierge-media-11269a8adae1`).
- **AI Image Generation**: Generates scenic destination artwork using **Gemini 3.1 Flash Lite Image** (`gemini-3.1-flash-lite-image` in `global` region) and uploads directly to Cloud Storage (`generate_destination_artwork`).
- **AI Video Generation**: Generates short 3-second animated video previews using **Google Omni** (`gemini-omni-flash-preview` in `global` region via `client.interactions.create`). Saves artifacts to ADK ToolContext and uploads to Cloud Storage (`generate_destination_video`).

### 4. 🎛️ Dynamic UI Rendering (A2UI)
- **A2UI (Agent-to-User Interface)**: Implements `a2ui_callback` and `BasicCatalog` schemas to render structured interactive components (Cards, Columns, Rows, Images) directly inside the chat interface.

### 5. 🧮 Secure Code Execution
- **Agent Engine Sandbox Code Executor**: Integrates `AgentEngineSandboxCodeExecutor` for executing Python code in a sandboxed environment for expense calculations and budget breakdowns.

### 6. 🌍 Location, Weather & Travel Utilities
- **Google Maps Geocoding API**: Resolves address strings to geographic coordinates (`geocode_address`).
- **Google Places API (New)**: Searches nearby points of interest (restaurants, hotels, attractions, cafes) (`find_nearby_places`).
- **Open-Meteo Weather API**: Retrieves real-time weather forecasts and temperature for travel destinations (`get_weather`).
- **Open Exchange Rates API**: Performs real-time currency conversions for budget planning (`convert_currency`).
- **Wikipedia REST API**: Fetches historical summaries and key background facts for destinations (`get_destination_wiki_summary`).
- **Timezone API**: Looks up current local date and time by IANA timezone (`get_current_time`).

---

## 📁 Repository Structure

```
travel-concierge-agent/
├── app/                        # Core Agent Package
│   ├── agent.py                # Main agent definition, system prompt, and tool implementations
│   ├── a2ui_utils.py           # A2UI catalog schema, card formatting, and response callback
│   ├── fast_api_app.py         # FastAPI application wrapper
│   └── app_utils/              # Framework helper utilities
├── frontend/                   # Web Client & Proxy Server
│   ├── main.py                 # FastAPI proxy wiring frontend to Agent Platform
│   ├── requirements.txt        # Frontend dependencies
│   └── static/
│       └── index.html          # Responsive Web UI with Dark Mode, Quick Filters, Lightbox & A2UI renderer
├── agents-cli-manifest.yaml    # Deployment manifest for agents-cli
├── deployment_metadata.json    # Deployed Agent Runtime metadata
├── pyproject.toml              # Python project dependencies
└── README.md                   # Project documentation
```

---

## 🚀 Setup & Local Execution

### Prerequisites
- Python 3.11+
- `uv` package manager (`pip install uv`)
- `agents-cli` (`uv tool install google-agents-cli`)
- Google Cloud SDK (`gcloud`) with credentials configured

### 1. Install Dependencies

```bash
uv sync
```

### 2. Set Up Environment Variables

Create or update your `.env` file in the project root:

```bash
export GOOGLE_CLOUD_PROJECT="<your-gcp-project-id>"
export GOOGLE_CLOUD_LOCATION="us-east1"
export GOOGLE_MAPS_API_KEY="<your-google-maps-api-key>"
```

### 3. Run Agent Locally in Development Playground

```bash
agents-cli playground
```

Or run an interactive query via CLI:

```bash
agents-cli run "Find me top destinations in Japan under $2000 and generate artwork for Kyoto."
```

### 4. Run Web Frontend Locally

Navigate to the `frontend/` directory and start the local proxy server:

```bash
cd frontend
pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="<your-agent-engine-resource-name>"
export AGENT_DIRECTORY="app"
python main.py
```

Open a web browser and navigate to port `8080` to access the chat application.

---

## ☁️ Deployment

### Deploy Agent to Agent Runtime

Deploy the agent to Google Cloud Vertex AI Agent Runtime:

```bash
agents-cli deploy --update-env-vars GOOGLE_MAPS_API_KEY=<your-key>,GOOGLE_CLOUD_PROJECT=<your-project-id>,GOOGLE_CLOUD_LOCATION=us-east1 --no-confirm-project
```

### Deploy Frontend to Cloud Run

Deploy the web frontend proxy to Cloud Run:

```bash
cd frontend
gcloud run deploy travel-concierge-frontend \
  --source . \
  --region us-east1 \
  --allow-unauthenticated \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="<your-agent-engine-resource-name>",AGENT_DIRECTORY="app"
```

Grant the Cloud Run service account access to call Vertex AI Agent Engine:

```bash
gcloud projects add-iam-policy-binding <your-project-id> \
  --member="serviceAccount:<project-number>-compute@developer.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

---

## 🧪 Testing & Verification

Run unit and integration tests:

```bash
uv run pytest tests/unit tests/integration
```

Evaluate agent performance using `agents-cli`:

```bash
agents-cli eval
```
