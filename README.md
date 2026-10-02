# Alquist Insight

Alquist Insight is an open-source platform designed for building and deploying production-ready RAG (Retrieval-Augmented
Generation) chatbots on private or cloud infrastructure.

Developed by the Alquist Research team (winners of the Amazon Alexa Prize Socialbot Grand Challenge), it provides a
complete monorepo for managing knowledge bases, local LLM deployment, and conversational interfaces. It is specifically
built to allow organizations to automate administrative tasks and customer support using their own data without relying
on external cloud-based AI providers.

Key technical specs:

- **Infrastructure**: Built to run on-premise or in cloud using Docker and docker-compose.
- **Models**: Supports local LLM deployment via vLLM (e.g. for embedding and generation models), but can be configured
  for cloud models as well.
- **Requirements**: Optimized for Linux-based systems with Nvidia GPUs (CUDA support) and high RAM (120+ GiB for full
  local model deployment).
- **Authentication**: Integrated with Keycloak for identity and access management.
- **Capabilities**: Includes automated document processing, vector-based search, and a file-explorer-style admin console
  for knowledge base management.

## Table of Contents

- [Architecture](#architecture)
    - [Request Flow](#request-flow)
    - [RAG Pipeline](#rag-pipeline)
    - [External Services](#external-services)
    - [Repository Layout](#repository-layout)
    - [Default Resource Files](#default-resource-files)
- [Local Docker Deployment](#local-docker-deployment)
    - [Stopping, Restarting and Resetting](#stopping-restarting-and-resetting)
- [Configuration](#configuration)
    - [Key Settings](#key-settings)
    - [Using Cloud Models Instead of Local vLLM](#using-cloud-models-instead-of-local-vllm)
    - [Changing Service Ports](#changing-service-ports)
- [Keycloak Setup](#keycloak-setup)
    - [Keycloak Behind a Reverse Proxy](#keycloak-behind-a-reverse-proxy)
- [Frontend Clients](#frontend-clients)
    - [Updating the Frontend Version](#updating-the-frontend-version)
- [Knowledge Base Upload](#knowledge-base-upload)
    - [Admin Console UI](#admin-console-ui)
    - [Kronos API](#kronos-api)
    - [Querying](#querying)
- [External Access](#external-access)
    - [Reverse Proxy & HTTPS (nginx + certbot)](#reverse-proxy--https-nginx--certbot)
- [Local Development](#local-development)
    - [PyCharm Setup](#pycharm-setup)
    - [Code Conventions](#code-conventions)
- [Helper Scripts](#helper-scripts)
- [Troubleshooting](#troubleshooting)
- [Licensing and Legal Documents](#licensing-and-legal-documents)
    - [Language Versions and Precedence](#language-versions-and-precedence)
    - [The Two-Layer Model](#the-two-layer-model)

## Architecture

Alquist Insight consists of four FastAPI backend services, a shared Python module, and two frontend client apps that are
developed in separate repositories and fetched as prebuilt tarballs at runtime.

| Component      | Port   | Description                                                                            |
|----------------|--------|----------------------------------------------------------------------------------------|
| **alchemist**  | `9642` | Document conversion (Docling PDF to Markdown); stateless, called by Kronos             |
| **kronos**     | `9625` | Projects, knowledge bases, sessions/turns, resources; owns Mongo & storage             |
| **maestro**    | `8020` | Chatbot interaction, FSM dialogue, analytics; serves the client apps                   |
| **ragnarok**   | `9696` | The RAG engine: chunking, embeddings, search, reranking, generation; owns the ES index |
| **common**     | –      | Shared module imported by every app: config, models, logging, API calls                |
| **admin**      | –      | Admin console client app, served by Maestro at `/admin/`                               |
| **interactor** | –      | Chatbot client app, served by Maestro at `/` and `/interactor/`                        |

### Request Flow

```
browser ──► maestro ──► kronos ──► ragnarok ──► Elasticsearch / embedding & LLM models
   │           │           │
   │           │           └──► MongoDB (projects, sessions, turns, KB metadata)
   │           │           └──► MinIO / Azure Blob (source documents, resources)
   │           │           └──► alchemist (advanced PDF conversion)
   │           └──► Elasticsearch (analytics, logs)
   └──► keycloak (Admin console login)
```

Maestro never calls Ragnarok directly for RAG (only for search-result highlights); it goes through Kronos, which fetches
the conversation history and project settings and forwards the request to Ragnarok. Ragnarok calls back into Kronos for
one thing only: fetching the project's LLM prompts.

Inter-service calls use `httpx`/`requests` against the `*_URL` config values and authenticate with an `X-Api-Key` header
(Kronos, Alchemist) or an `Authorization` header (Ragnarok). All of these API call functions are shared and live in
`common/common/services/{alchemist,kronos,ragnarok}.py`.

### RAG Pipeline

The pipeline lives in `ragnarok/ragnarok/rag.py`:

1. **Query rewrite** — reformulate the user query using the conversation context.
2. **Retrieval** — KNN (cosine similarity) search over the vector index + BM25 keyword search.
3. **Fusion** — reciprocal rank fusion of both result sets.
4. **Reranking** (optional) — cross-encoder reranking of the fused candidates.
5. **Generation** — answer generation from the selected chunks.

Provider-specific implementations (embeddings, generation, reranking) are selected at runtime via `Singleton`-backed
factories (`*Factory.get_model(provider=...)`) keyed on `ModelProvider`. Supported providers: `Cohere`, `JinaAI`,
`OpenAI` (incl. Azure OpenAI), `Triton`, `vLLM`.

LLM prompts are not hardcoded — they live in a `prompts.md` resource file stored per project by Kronos, with a fallback
to the default file in `resources/prompts.md`.

### External Services

| Service           | Container ports        | Purpose                                                             |
|-------------------|------------------------|---------------------------------------------------------------------|
| Elasticsearch     | `9200`, `9300`         | Vector index, BM25 index, highlight chunks, application logs        |
| MongoDB           | `27017`                | Projects, knowledge base metadata, sessions, turns, migration locks |
| MinIO             | `9000`, `9001`         | Object storage for source documents and resources (S3-compatible)   |
| Keycloak          | `8080`                 | Identity provider for the Admin console                             |
| PostgreSQL        | `5432`                 | Keycloak's database                                                 |
| vLLM (embedding)  | `8000`                 | Local embedding model server                                        |
| vLLM (generation) | `8000`                 | Local LLM server                                                    |
| Triton            | `8000`, `8001`, `8002` | Alternative local model server (disabled by default)                |

Azure Blob Storage can be used instead of MinIO (`STORAGE_TYPE=AZURE_BLOB_STORAGE`).

### Repository Layout

```
alchemist/          # Alchemist app (Dockerfile, Pipfile, run.py, start.sh)
common/common/      # Shared module imported by all apps
kronos/             # Kronos app
legal/              # License, EULA, privacy notice & co. (EN + CZ), client legal info page
maestro/            # Maestro app
ragnarok/           # Ragnarok app
resources/          # Default resource files: FSM dialogues, images, prompts.md
scripts/            # Deployment and maintenance scripts
config.env          # Committed config template with safe defaults (NO SECRETS)
config.local.env    # Local secrets & overrides (gitignored, not committed)
docker-compose.yaml # Full local deployment
LICENSE             # MIT license (symlinked from legal/LICENSE)
Pipfile             # Convenience union of all app dependencies for local development
```

### Default Resource Files

The default (project independent) resource files are created in the storage by the Kronos prestart script
(`kronos/kronos/prestart.py`) before every Kronos start. The files they are created from live in the `resources`
folder, which is copied into the Kronos image (the individual files needed are listed in `.dockerignore`):

| Resource       | Created from                           | Created                                          |
|----------------|----------------------------------------|--------------------------------------------------|
| `dialogue_fsm` | built by `common.utils.fsm.build_qa()` | when missing, or on every start (see flag below) |
| `image`        | `resources/default.png`                | only when missing                                |
| `prompts`      | `resources/prompts.md`                 | when missing, or on every start (see flag below) |

`OVERWRITE_DEFAULT_RESOURCES` (`true` by default) makes Kronos replace the stored default dialogue FSM and prompts
files with the current version on every start. Set it to `false` to keep default files edited through the Admin
console/API — they are then only created when missing. The default image is always uploaded only once, so it can be
freely replaced.

Project-specific resource files are never touched and always take precedence over the default ones. Images live in an
`images` folder — inside the project folder for project-specific images, in the storage root for the default ones.

## Local Docker Deployment

Prerequisites:

- Docker with the docker-compose plugin installed.
- Linux-based system able to run bash scripts.
- HW requirements for fully local deployment:
    - Nvidia GPU with CUDA support and the Nvidia Container Toolkit installed
    - 120 GiB RAM
    - ~100 GiB free disk space (model weights, Elasticsearch data, uploaded documents)
    - (tested on Nvidia DGX Spark machine)
- HW requirements while using cloud models:
    - 2 vCPUs
    - 8 GiB RAM
    - (tested on Standard D2ds v4 Kubernetes node on Azure)

> **Note for servers without an Nvidia GPU:** Several services request GPU access in the `docker-compose.yaml` file
> (`gpus: all` and the `deploy.resources.reservations.devices` block) — the vLLM services, which require a GPU, and
> Alchemist, which uses one only if available. Docker Compose cannot make a GPU reservation conditional, so these
> containers fail to start with a "could not select device driver" error on a machine with no Nvidia GPU (or without the
> Nvidia Container Toolkit installed). Comment out the GPU access lines of the affected services in the
> `docker-compose.yaml` file before deploying. Alchemist then automatically falls back to the CPU; the vLLM services
> should be disabled entirely and replaced with cloud models (see step 5 below).

Clone the repository:

```shell
git clone https://github.com/AlquistAI/insight.git
cd insight
```

Prepare a `config.local.env` file in the project root with the server configuration and secrets. The default/sample
values are provided in the `config.env` file. The servers will run even with the default configuration, but setting up
secrets etc. manually is strongly recommended. See [Configuration](#configuration) for details.

Run the deployment script from the repository root:

```shell
./scripts/deployment-full.sh
```

The script will:

1. Read server configuration from the `config.env` & `config.local.env` files.
    - An empty/dummy `config.local.env` file is created if it doesn't exist.
    - The script also handles env vars required for docker compose. These env vars can be changed using the
      `config.local.env` file.
2. Ask for sudo permissions. Sudo is required for:
    - `docker` commands in case the current user doesn't have access to the Docker socket.
    - Initial setup of volume mount folder ownership for `docker compose` services.
3. Prepare directories for docker compose.
4. Build Docker images for all apps and run all required services.
5. Run the vLLM services for embedding & generation models.
    - These services are resource-heavy. If you intend to use cloud models instead, disable the vLLM containers in the
      `docker-compose.yaml` file (i.e. comment out the "vllm..." lines in the "services" section).
    - The vLLM containers might take a long time to start up, since they need to download the models on the first run.
      The default generation model has ~60 GB. It is recommended to do the initial setup on a wired/fast connection.
    - After the first run, the models are persisted in the `data` folder. Any subsequent start of the vLLM services
      should only take a few minutes.
    - The script does not wait for the vLLM generation model to be ready, since it can take longer and the model is not
      required for finishing the initial setup. However, you should wait for it to be ready before interacting with the
      chatbot UI. You can check the status of all Docker containers using the `docker ps` command.
6. Create the default "test" project and upload the Alquist Insight docs as its knowledge base.

The script is idempotent — every step checks whether it has already been completed and is skipped if so.

The default resource files (dialogue FSM, image, prompts) are not uploaded by the script — Kronos creates them
in the storage on every start, see [Default Resource Files](#default-resource-files).

After the script finishes execution, you should be able to open the chatbot with the default "test" project in your
browser at `http://localhost:8020/`. Note that the generation model can still take some time to load.

Useful endpoints of a running deployment:

| URL                              | Description                         |
|----------------------------------|-------------------------------------|
| `http://localhost:8020/`         | Chatbot UI (default project)        |
| `http://localhost:8020/admin/`   | Admin console                       |
| `http://localhost:9642/docs`     | Alchemist Swagger UI                |
| `http://localhost:9625/docs`     | Kronos Swagger UI                   |
| `http://localhost:8020/docs`     | Maestro Swagger UI                  |
| `http://localhost:9696/docs`     | Ragnarok Swagger UI                 |
| `http://localhost:8080/`         | Keycloak admin console              |
| `http://localhost:<port>/health` | Healthcheck of any of the four apps |

### Stopping, Restarting and Resetting

```shell
# The env files are needed for the ${...} interpolation in docker-compose.yaml (see Configuration below)
DC="docker compose --env-file config.env --env-file config.local.env"

$DC down                       # stop the deployment (data is preserved)
./scripts/deployment-full.sh   # start it again; skips already-finished steps
$DC logs -f kronos             # follow the logs of a single service
$DC up -d --build kronos       # rebuild & restart a single app after a code change
$DC restart maestro            # restart without rebuilding (e.g. after a config change)
```

All state is persisted in the `data` folder on the host:

| Path                    | Content                                           |
|-------------------------|---------------------------------------------------|
| `data/alchemist`        | Docling & HuggingFace model caches                |
| `data/elasticsearch`    | Elasticsearch indices (vectors, highlights, logs) |
| `data/keycloak`         | Keycloak data directory                           |
| `data/maestro/frontend` | Extracted frontend client apps                    |
| `data/minio`            | Uploaded source documents and resources           |
| `data/mongo`            | MongoDB database files                            |
| `data/postgres`         | Keycloak's PostgreSQL database                    |
| `data/ragnarok/models`  | HuggingFace model cache                           |
| `data/vllm-*/models`    | vLLM model weights (large!)                       |

To reset a specific part of the deployment, stop the containers, delete the corresponding folder and start again. The
deployment script recreates the folders with the correct ownership. To wipe everything (including the downloaded
models), remove the whole `data` folder.

## Configuration

All config is read by `common/common/config.py` into two `pydantic-settings` singletons that are imported everywhere:

- `CONFIG` (class `Config`) — runtime config required at startup: service URLs, secrets, Elastic/Mongo/MinIO connection
  settings, feature flags. Fails fast on a missing required value.
- `DF` (class `Defaults`) — default RAG/model settings, env prefix `DEFAULT_`. These can be overridden per project.

Env files are layered, with later files overriding earlier ones:

1. `/config/config.local.env` — used in Kubernetes deployments (mounted secret).
2. `config.env` — **committed to git, must never contain secrets.** Holds the defaults for a local deployment.
3. `config.local.env` — gitignored; put your real secrets and overrides here.

Both `config.env` and `config.local.env` are passed to the app containers via `env_file` in `docker-compose.yaml`.

When adding a new setting, add it to the appropriate class in `config.py` *and* document its default in `config.env`.

> **Running `docker compose` directly:** `docker-compose.yaml` also interpolates a few variables (`${...}`) for the
> infrastructure services — the Keycloak and MinIO credentials. Docker Compose does *not* read `config.env` /
> `config.local.env` for those on its own (it only looks at `.env`), so a bare `docker compose up -d` would recreate
> Keycloak, PostgreSQL and MinIO with **blank passwords**. `scripts/deployment-full.sh` exports the variables before
> calling compose; when running compose yourself, pass both files explicitly:
>
> ```shell
> docker compose --env-file config.env --env-file config.local.env up -d
> ```

### Key Settings

Backend services — internal URLs (on the compose network) and API keys used for inter-service authentication:

```dotenv
ALCHEMIST_URL=http://alchemist:9642
ALCHEMIST_API_KEY=<secret>
KRONOS_URL=http://kronos:9625
KRONOS_API_KEY=<secret>
MAESTRO_URL=http://maestro:8020
MAESTRO_API_KEY=<secret>
RAGNAROK_URL=http://ragnarok:9696
RAGNAROK_API_KEY=<secret>
```

External URLs — the addresses the *browser* uses. They are baked into the frontend client config at Maestro startup, so
they must be reachable from the client machine (see [External Access](#external-access)):

```dotenv
KEYCLOAK_URL_EXTERNAL=http://localhost:8080
KRONOS_URL_EXTERNAL=http://localhost:9625
MAESTRO_URL_EXTERNAL=http://localhost:8020
```

Infrastructure services and their credentials:

```dotenv
ES_URL=http://elasticsearch:9200
# security is disabled in the local Elasticsearch container
ES_PASSWORD=NOT_USED
# internal URL, used by Kronos to fetch the realm public key
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=alquist
KEYCLOAK_CLIENT_ID=alquist-insight-development
KEYCLOAK_ADMIN_PASSWORD=<secret>
KEYCLOAK_DB_PASSWORD=<secret>
MINIO_URL=http://minio:9000
MINIO_ROOT_PASSWORD=<secret>
MINIO_SECRET_KEY="${MINIO_ROOT_PASSWORD}"
MONGO_CONN_STR=mongodb://mongo:27017
```

Feature flags and default models:

```dotenv
# send the conversation history to the LLM
CONTEXT_ENABLED=false
# number of latest turns used as context (0 = unlimited)
CONTEXT_WINDOW_SIZE=10

DEFAULT_LANG=en-US
DEFAULT_PROVIDER_EMB=vLLM
DEFAULT_MODEL_EMB=Qwen/Qwen3-Embedding-0.6B
DEFAULT_BASE_URL_EMB=http://vllm-embedding:8000/v1
DEFAULT_PROVIDER_LLM=vLLM
DEFAULT_MODEL_LLM=Qwen/Qwen3-30B-A3B
DEFAULT_BASE_URL_LLM=http://vllm-generation:8000/v1
```

The following secrets have no usable default and should always be set in `config.local.env`:
`ALCHEMIST_API_KEY`, `KRONOS_API_KEY`, `MAESTRO_API_KEY`, `RAGNAROK_API_KEY`, `KEYCLOAK_ADMIN_PASSWORD`,
`KEYCLOAK_DB_PASSWORD`, `MINIO_ROOT_PASSWORD`.

### Using Cloud Models Instead of Local vLLM

1. Comment out the `vllm-embedding` and `vllm-generation` entries in the `services` section of `docker-compose.yaml`.
2. Set the provider credentials and defaults in `config.local.env`, e.g. for OpenAI:

    ```dotenv
    # or AzureOpenAI (then OPENAI_ENDPOINT is also required)
    OPENAI_TYPE=OpenAI
    OPENAI_KEY=<secret>

    DEFAULT_PROVIDER_EMB=OpenAI
    DEFAULT_MODEL_EMB=text-embedding-3-large
    DEFAULT_BASE_URL_EMB=None

    DEFAULT_PROVIDER_LLM=OpenAI
    DEFAULT_MODEL_LLM=gpt-5.6-luna
    DEFAULT_BASE_URL_LLM=None
    ```

3. Optionally enable reranking with `COHERE_KEY` (`DEFAULT_PROVIDER_RERANK=Cohere`) or `JINAAI_KEY`
   (`DEFAULT_PROVIDER_RERANK=JinaAI`).
4. Restart the deployment. Note that changing the embedding model invalidates existing vector indices — the knowledge
   base has to be re-uploaded (or a new `ES_INDEX_EMBEDDINGS` used).

### Changing Service Ports

If some of the default ports are already taken on your server, you have to change the **published (host) ports** in
`docker-compose.yaml` and then update the matching `*_URL_EXTERNAL` values in `config.local.env`.

Check which ports are already in use:

```shell
ss -tulpn | grep -E ':(8020|8080|9625|9642|9696)\b'
```

1. **Change the host port in `docker-compose.yaml`.** The service definitions live in the `x-services` section as YAML
   anchors and are only referenced from the `services` section, so this is where the `ports:` blocks are. Every
   published port is written as `"127.0.0.1:<host_port>:<container_port>"` — only ever change the **middle** (host)
   value:

    ```yaml
    x-services:
     kronos:
       ports:
         - "127.0.0.1:19625:9625"   # host port 19625 -> container port 9625
    ```

2. **Update the external URLs in `config.local.env`** so that the frontend clients (and the deployment script) use the
   new ports:

    ```dotenv
    KRONOS_URL_EXTERNAL=http://localhost:19625
    MAESTRO_URL_EXTERNAL=http://localhost:18020
    KEYCLOAK_URL_EXTERNAL=http://localhost:18080
    ```

3. **Do not change the internal `*_URL` values** (`KRONOS_URL`, `ES_URL`, `KEYCLOAK_URL`, `MINIO_URL`,
   `MONGO_CONN_STR`, `DEFAULT_BASE_URL_*`, …). Those resolve service names on the compose network and always use the
   **container** ports, which are unaffected by the host-side mapping.

4. **Restart the deployment** (`docker compose down && ./scripts/deployment-full.sh`). Maestro regenerates the frontend
   client config from the `*_URL_EXTERNAL` values on every start.

Notes:

- The infrastructure services (Elasticsearch, MinIO, MongoDB, PostgreSQL, Triton, vLLM) have their `ports:` blocks
  commented out — they are only reachable from within the compose network. Uncomment a mapping (and pick a free host
  port) if you need direct access from the host, e.g. for debugging.
- Published ports are bound to `127.0.0.1`, so they are not reachable from outside the server. That is intentional —
  external access should go through a reverse proxy (see [Reverse Proxy & HTTPS](#reverse-proxy--https-nginx--certbot)).
- If you also need to change a **container** port (rarely necessary), set the corresponding
  `<APP>_CONTAINER_PORT` variable in `config.local.env` (read by the app's `start.sh` and by `config.py` as
  `<APP>_PORT`), and update the container side of the `ports:` mapping, the `healthcheck` URL and the internal
  `<APP>_URL` in `docker-compose.yaml`/`config.local.env` to match.

## Keycloak Setup

The Admin console authenticates users against Keycloak using the OIDC authorization code flow; Kronos then validates the
resulting JWT (`common/common/api/security_jwt.py`). A fresh Keycloak container has no realm/client/user configured, so
this has to be done once manually before the first Admin console login.

Three config values have to match the Keycloak configuration exactly (they are read by both the backend and the frontend
clients):

| Config variable         | Keycloak field                    | Default value                 |
|-------------------------|-----------------------------------|-------------------------------|
| `KEYCLOAK_REALM`        | Realm → **Realm name**            | `alquist`                     |
| `KEYCLOAK_CLIENT_ID`    | Client → **Client ID**            | `alquist-insight-development` |
| `KEYCLOAK_URL_EXTERNAL` | –  (URL the browser uses)         | `http://localhost:8080`       |
| `KEYCLOAK_URL`          | –  (URL the backend services use) | `http://keycloak:8080`        |

> The Keycloak UI distinguishes between an object's **ID/name** (used in URLs and tokens — this is what the config
> variables refer to) and its **display name** (a cosmetic label). Always fill in the *Realm name* and *Client ID*
> fields; the *Display name* / *Name* fields can be left empty or set to anything.

#### 1. Log in to the Keycloak admin console

Open `http://localhost:8080/` and click **Administration console**. Log in with the credentials from your config:

- Username: `KEYCLOAK_ADMIN_USER` (default `admin`)
- Password: `KEYCLOAK_ADMIN_PASSWORD` (sample value `admin123` — change it in `config.local.env`)

#### 2. Create the realm

1. Open the realm selector in the top-left corner and click **Create realm**.
2. **Realm name**: `alquist` (must equal `KEYCLOAK_REALM`; it appears in the OIDC URLs and is case-sensitive).
3. Leave *Enabled* on and click **Create**.

Make sure the newly created realm (not `master`) is selected for the following steps.

#### 3. Create the client

1. Go to **Clients** → **Create client**.
2. *General settings*:
    - **Client type**: `OpenID Connect`
    - **Client ID**: `alquist-insight-development` (must equal `KEYCLOAK_CLIENT_ID`)
    - *Name* / *Description*: optional, display only
3. *Capability config*:
    - **Client authentication**: `Off` — the Admin console is a browser SPA, so it must be a **public** client
      (authorization code flow with PKCE, no client secret)
    - **Authentication flow**: keep **Standard flow** checked; the other flows are not needed
4. *Login settings* — replace `http://localhost:8020` with your `MAESTRO_URL_EXTERNAL` value:
    - **Root URL**: `http://localhost:8020` (optional)
    - **Home URL**: `/admin/` (optional)
    - **Valid redirect URIs**: `http://localhost:8020/admin/*`
    - **Valid post logout redirect URIs**: `http://localhost:8020/admin/*`
    - **Web origins**: `*` (allow all origins; alternatively set the exact `http://localhost:8020` origin)
5. Click **Save**.

Leave the default *client scopes* (`acr`, `basic`, `email`, `profile`, `roles`, `web-origins`) assigned. The `roles`
scope adds the `account` audience to issued access tokens, which is what Kronos expects when validating the JWT.

#### 4. Create a user

1. Go to **Users** → **Create new user**.
2. Fill in the **Username** (and optionally email/first/last name), then click **Create**.
3. Open the **Credentials** tab → **Set password**, enter the password twice and set **Temporary** to `Off` (otherwise
   the user is forced into a password-change screen that the Admin console cannot render natively).

You should now be able to log in to the Admin console at `http://localhost:8020/admin/` using these credentials.

ToDo: Do this setup as part of the deployment script.

#### 5. Apply config changes

If you used different values than the defaults, set `KEYCLOAK_REALM` / `KEYCLOAK_CLIENT_ID` in `config.local.env` and
restart Maestro so it regenerates the frontend client config:

```shell
docker compose restart maestro
```

### Keycloak Behind a Reverse Proxy

Keycloak derives the absolute URLs it publishes (the OIDC issuer, the authorization/token endpoints in its discovery
document, the admin console asset URLs, and the redirect it sends the browser to) from the incoming request. Behind a
reverse proxy the request it receives is the internal, plain-HTTP one. Without extra configuration it advertises
`http://` URLs built from whatever host name the proxy forwards — which the browser either cannot reach or refuses to
use — and it may reject the request outright because it considers the connection insecure.

To fix that, add these two environment variables to the `keycloak` service in `docker-compose.yaml`:

```yaml
x-services:
  keycloak:
    environment:
      # ... existing variables ...
      KC_HOSTNAME: "keycloak.example.com"   # public base URL of Keycloak
      KC_PROXY_HEADERS: "xforwarded"        # trust X-Forwarded-* headers from the proxy
```

- `KC_HOSTNAME` pins the public base URL used in all generated URLs and in the token issuer.
- `KC_PROXY_HEADERS=xforwarded` makes Keycloak trust the `X-Forwarded-Proto`, `X-Forwarded-Host` and `X-Forwarded-For`
  headers, so it knows the original request arrived over HTTPS. Your proxy **must** actually set those headers (the
  nginx config below does) — only enable this when Keycloak is not directly reachable from outside.

Then set the matching external URL in `config.local.env` and recreate the containers:

```dotenv
KEYCLOAK_URL_EXTERNAL=https://keycloak.example.com
```

```shell
docker compose --env-file config.env --env-file config.local.env up -d
```

Keep `KEYCLOAK_URL` (the internal URL used by Kronos to fetch the realm's public key) pointing at
`http://keycloak:8080` — it does not go through the proxy.

Remember to update the client's **Valid redirect URIs**, **Valid post logout redirect URIs** and **Web origins** in
Keycloak to the public Maestro URL (e.g. `https://insight.example.com/admin/*`).

> The compose file runs Keycloak with the `start-dev` command, which enables plain HTTP and relaxes hostname checks.
> This is convenient for a self-hosted deployment behind a TLS-terminating proxy, but it is not a hardened production
> setup — for production, switch to `start` and configure TLS, `KC_HOSTNAME_STRICT` and a proper admin account.

## Frontend Clients

The Admin console and the chatbot Interactor are built in separate repositories and published as `dist.tar.gz` generic
packages. At startup, Maestro (`maestro/maestro/utils/frontend.py`):

1. Downloads each client package (using `PACKAGE_REGISTRY_TOKEN`) and extracts it into `/home/app/frontend`, which is
   bind-mounted to `data/maestro/frontend` on the host — **but only if the client directory does not exist yet.**
2. Regenerates each client's `dist/config.json` with the current external URLs, Keycloak realm/client ID and default
   project — this happens on **every** start.

Relevant config:

```dotenv
ADMIN_CONSOLE_PACKAGE_NAME=admin
ADMIN_CONSOLE_VERSION=latest
INTERACTOR_PACKAGE_NAME=chatbot_js
INTERACTOR_VERSION=latest
PROJECT_ID=test
PROJECT_TITLE="Test Project"
```

### Updating the Frontend Version

Because the download is skipped when the extracted files are already present, a new client build is **not** picked up
automatically on restart. To force a re-fetch, delete the frontend data folder:

```shell
docker compose down
sudo rm -rf data/maestro/frontend        # the folder is owned by the container user (uid 999)
./scripts/deployment-full.sh             # recreates the folder with the right ownership and starts everything
```

If you prefer not to run the full deployment script:

```shell
docker compose stop maestro
sudo rm -rf data/maestro/frontend
mkdir -p data/maestro/frontend
sudo chown -R 999:999 data/maestro
docker compose --env-file config.env --env-file config.local.env up -d maestro
```

Notes:

- As long as `ADMIN_CONSOLE_VERSION` / `INTERACTOR_VERSION` are left at `latest` (the default), this pulls the newest
  published build. If a specific version is pinned, that exact version is downloaded again instead.
- Only one of the two clients can be refreshed by removing just its subfolder (`data/maestro/frontend/admin` or
  `data/maestro/frontend/interactor`).
- Changes to URLs, Keycloak settings or the default project do **not** require deleting anything — a
  `docker compose restart maestro` is enough, since `config.json` is rewritten on every start.
- Watch the Maestro logs (`docker compose logs -f maestro`) to confirm the download succeeded; a failed fetch prevents
  the app from starting.

## Knowledge Base Upload

For creating your own projects and uploading knowledge base documents, you can either use the Kronos API or the Admin
console UI.

You can open the chatbot for a custom project at `http://localhost:8020/?project_id=<project_id>`.

### Admin Console UI

The Admin console is available at `http://localhost:8020/admin/` and requires a Keycloak login (see
[Keycloak Setup](#keycloak-setup)). It allows creating new projects and managing the related knowledge base in a similar
fashion as a regular file explorer, as well as editing project settings, prompts and the dialogue definition.

### Kronos API

The easiest way to use the API is through the Swagger UI at `http://localhost:9625/docs`, which also serves as the API
documentation. Authenticate with the `X-Api-Key` header using your `KRONOS_API_KEY` value (a Keycloak JWT in the
`Authorization` header works as well).

Use `POST /projects/` to create a project, then one of the knowledge base endpoints to add documents:

| Endpoint                            | Description                                                               |
|-------------------------------------|---------------------------------------------------------------------------|
| `POST /knowledge_base/file/`        | Upload a single file (`pdf`, `docx`, `pptx`, `xlsx`, `md`, `txt`, `html`) |
| `POST /knowledge_base/file/bulk`    | Upload multiple files at once                                             |
| `POST /knowledge_base/pdf/advanced` | PDF upload with Docling conversion via Alchemist (streamed progress)      |
| `POST /knowledge_base/file/marker`  | Upload a pre-converted paginated Markdown + its source PDF                |
| `POST /knowledge_base/url/`         | Fetch and index the content of a single URL                               |
| `POST /knowledge_base/url/bulk`     | Fetch and index multiple URLs                                             |
| `POST /knowledge_base/url/crawl`    | Crawl a seed URL and index all discovered pages/files                     |

Common query parameters: `project_id` (required), `kb_id`, `name`, `description`, `language`, `custom_metadata` (JSON
string) and `enable_highlights` (build the extra chunk index needed for highlighting answers in the source document).

See the `CREATE EXAMPLE PROJECT IF MISSING` section of `scripts/deployment-full.sh` for a working `curl` example.

### Querying

- `POST /projects/{project_id}/nlp/rag/` (Kronos) — full RAG answer for a query.
- `POST /projects/{project_id}/nlp/rag/stream` (Kronos) — the same, streamed token by token.
- `POST /projects/{project_id}/query/rag` (Maestro) — the endpoint used by the chatbot client.

## External Access

If you want external users to be able to access the Admin/Chatbot UI, you will need to expose the following services to
them:

- **Maestro** (default port `8020`) — serves both client apps and the chatbot API.
- **Kronos** (default port `9625`) — required for Admin console access only.
- **Keycloak** (default port `8080`) — required for Admin console access only.

Ragnarok and Alchemist are internal-only and should **not** be exposed.

The public URLs then need to be set in `config.local.env` using the `<NAME>_URL_EXTERNAL` variables, because they are
baked into the frontend client configuration:

```dotenv
KEYCLOAK_URL_EXTERNAL=https://keycloak.example.com
KRONOS_URL_EXTERNAL=https://kronos.example.com
MAESTRO_URL_EXTERNAL=https://insight.example.com
```

The Admin console uses several browser APIs that are only available in a [secure context], meaning the services have to
be served over `https`. For quick testing this requirement can be bypassed by telling your browser to treat the origins
as secure (in Chrome: `chrome://flags/#unsafely-treat-insecure-origin-as-secure`), but the proper solution is a
TLS-terminating reverse proxy as described below.

[secure context]: https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts

### Reverse Proxy & HTTPS (nginx + certbot)

This section sets up nginx as a TLS-terminating reverse proxy in front of Maestro, Kronos and Keycloak, with free Let's
Encrypt certificates issued and auto-renewed by certbot. The example uses three subdomains:

| Public URL                     | Upstream                    |
|--------------------------------|-----------------------------|
| `https://insight.example.com`  | `127.0.0.1:8020` (Maestro)  |
| `https://kronos.example.com`   | `127.0.0.1:9625` (Kronos)   |
| `https://keycloak.example.com` | `127.0.0.1:8080` (Keycloak) |

Prerequisites:

- A domain with DNS `A`/`AAAA` records for all three subdomains pointing at the server's public IP.
- Ports `80` and `443` open in the firewall / cloud security group.
- The deployment running, with its ports published on `127.0.0.1` (the default). If nginx runs on a *different* host,
  change the bind address of the published ports in `docker-compose.yaml` from `127.0.0.1` to the interface reachable by
  the proxy, and firewall them accordingly.

#### 1. Install nginx and certbot

```shell
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

#### 2. Create the nginx site

First create the shared proxy header snippet `/etc/nginx/snippets/insight-proxy.conf`. The `X-Forwarded-*` headers are
what makes `KC_PROXY_HEADERS=xforwarded` work for Keycloak; keeping them in a snippet lets all three server blocks stay
identical:

```nginx
proxy_http_version 1.1;
proxy_set_header Host              $host;
proxy_set_header X-Real-IP         $remote_addr;
proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-Host  $host;
proxy_set_header X-Forwarded-Port  $server_port;
```

Then create the site itself, `/etc/nginx/sites-available/insight.conf`:

```nginx
server {
    server_name keycloak.example.com;
    listen 80;

    location / {
        proxy_pass http://127.0.0.1:8080;
        include snippets/insight-proxy.conf;
    }
}

server {
    server_name kronos.example.com;
    listen 80;

    # Uploaded documents can be large; RAG streaming responses can take minutes.
    client_max_body_size 256m;
    proxy_read_timeout   600s;
    proxy_send_timeout   600s;

    location / {
        proxy_pass http://127.0.0.1:9625;
        proxy_buffering off;    # do not buffer server-sent events (streamed chatbot answers)
        include snippets/insight-proxy.conf;
    }
}

server {
    server_name insight.example.com;
    listen 80;

    # Uploaded documents can be large; RAG streaming responses can take minutes.
    client_max_body_size 256m;
    proxy_read_timeout   600s;
    proxy_send_timeout   600s;

    location / {
        proxy_pass http://127.0.0.1:8020;
        proxy_buffering off;    # do not buffer server-sent events (streamed chatbot answers)
        include snippets/insight-proxy.conf;
    }
}
```

Enable the site and reload nginx:

```shell
sudo ln -s /etc/nginx/sites-available/insight.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

#### 3. Issue the certificates

Certbot's nginx plugin validates the domains over HTTP, obtains the certificates and rewrites the site config to
redirect HTTP to HTTPS and serve TLS on port 443:

```shell
sudo certbot --nginx \
    --cert-name insight \
    -d keycloak.example.com \
    -d kronos.example.com \
    -d insight.example.com
```

Renewal is handled automatically by the `certbot.timer` systemd unit installed with the package. Verify it:

```shell
systemctl list-timers | grep certbot
sudo certbot renew --dry-run
```

#### 4. Point the deployment at the public URLs

In `config.local.env`:

```dotenv
KEYCLOAK_URL_EXTERNAL=https://keycloak.example.com
KRONOS_URL_EXTERNAL=https://kronos.example.com
MAESTRO_URL_EXTERNAL=https://insight.example.com
```

In `docker-compose.yaml`, add the proxy-related variables to the `keycloak` service (see
[Keycloak Behind a Reverse Proxy](#keycloak-behind-a-reverse-proxy)):

```yaml
KC_HOSTNAME: "keycloak.example.com"
KC_PROXY_HEADERS: "xforwarded"
```

In the Keycloak admin console, update the client's **Valid redirect URIs** and **Valid post logout redirect URIs** to
`https://insight.example.com/admin/*`.

Finally recreate the containers so the new configuration is applied:

```shell
docker compose --env-file config.env --env-file config.local.env up -d
```

The Admin console should now be reachable at `https://insight.example.com/admin/` and the chatbot at
`https://insight.example.com/`.

## Local Development

Prerequisites:

- Python 3.11 (you can use e.g. `pyenv` for managing multiple Python versions on your machine).
- `pipenv` Python package manager.

You can install the Python requirements for all apps using pipenv (omit the `dev` flag for purely runtime dependencies):

```shell
pipenv install --dev
```

The shared `common` module is not a Python package installed by pipenv — it is a plain module directory that every app
imports directly. Its dependencies are listed in the `## Common module dependencies ##` section of each `Pipfile`. To
make it importable, the `/common` folder has to be on the Python path:

```shell
export PYTHONPATH="$PWD/common"
```

Prepare a `config.local.env` configuration file (see [Configuration](#configuration) for details). Note that when
running an app directly on the host, the service URLs must point at `localhost` and the published host ports instead of
the compose service names, e.g. `MONGO_CONN_STR=mongodb://localhost:27017` — which also means the corresponding `ports:`
mappings have to be uncommented in `docker-compose.yaml`.

You can run the individual apps using the provided `run.py` scripts, e.g.:

```shell
PYTHONPATH="$PWD/common" pipenv run python kronos/run.py
```

There are no automated tests in this repository. Validate changes by running the relevant service and exercising its
Swagger UI at `/docs`.

Each app has its own `Pipfile`, used to build its Docker image; the root `Pipfile` is a convenience union of all
dependencies for local development only. Every `Pipfile` splits `[packages]` into a `## Common module dependencies ##`
group (what `common/common` imports, limited to the parts the app actually uses) and a `## Component dependencies ##`
group. When adding an import to `common`, add the dependency to the common group of *every* `Pipfile` that needs it
(`sort_pipfile` is disabled to keep the grouping intact) and re-run `pipenv lock` there. The `common` module itself is
copied into the image in the Dockerfile's runtime stage, so changing it does not rebuild the dependency layers.

### PyCharm Setup

This section describes the recommended way how to work with this monorepo in the PyCharm IDE.

1. Open the monorepo folder in PyCharm, you can let it install the pipenv dependencies automatically.
2. Mark the `/common` folder and other app folders (`/alchemist`, `/kronos`, etc.) as Sources Root. This makes both the
   `common` module and the app modules importable without setting `PYTHONPATH` manually.
3. Either use the pipenv environment from the root folder, or follow steps 4-6 for individual app envs.
4. Setup pipenv for each app: e.g. `cd kronos/ && pipenv install --dev`.
5. Add the created Python envs manually for each app:
    1. Open `Settings` -> `Python` -> `Interpreter`.
    2. Select `Add Interpreter` -> `Add Local Interpreter...` -> `Select existing`.
    3. Add a Python env with a custom path to the created virtual env. For pipenv it should be at
       `~/.local/share/virtualenvs/<name>-<hash>/bin/python`.
6. You will have to switch between active Python envs depending on the project you work with.

### Code Conventions

- **Every module** starts with `# -*- coding: utf-8 -*-` and an rST-style module docstring: the dotted module path, a
  `~~~` underline of matching length, then a one-line summary.
- **API endpoint docstrings** use rST fields (`:param x:`, `:return:`) and are parsed by
  `common/common/utils/swagger.py` to populate the Swagger UI descriptions — keep the format intact. Mark
  logging-only/unused endpoint params with `# noqa`.
- **API endpoints** wrap their handler in `@error_handler` / `@error_handler_async` (from `common.utils.api`), which
  maps domain exceptions (`common/common/utils/exceptions.py`) to HTTP status codes via `EXC_TO_STATUS`. Raise those
  exceptions rather than `HTTPException` for domain errors. Routers are assembled in each app's `api/router.py`.
- **Pydantic models** extend `common.models.base.CustomBaseModel` (alias-aware, validate-on-assign). Cross-service
  request/response models live in `common/common/models/api_{kronos,maestro,ragnarok}.py`.
- **Persisted Mongo models** (project, session, turn, knowledge_base) carry a `model_version` (`VER_*` constant).
  Bumping a model means adding a migration branch in `kronos/kronos/prestart.py`, which runs under a Mongo lock before
  Kronos starts. The same script also creates the default resource files, see
  [Default Resource Files](#default-resource-files).
- **Logging:** get the logger with `common.core.get_component_logger()`; never instantiate one. Structured fields go in
  `extra={...}`. Each app sets up its component logger in its `__init__.py`.
- **Singletons / factories** use the `Singleton` / `SingletonABC` metaclass from `common.utils.singleton` (identity
  keyed on init args).
- **LLM prompts are not hardcoded** — they live in the `prompts` resource file (`prompts.md`), stored per project by
  Kronos with a fallback to the default file (`resources/prompts.md`). Ragnarok fetches them via
  `common/common/services/kronos.py` (TTL cache keyed on project & session ID) and parses them with
  `common.utils.prompts.parse_prompts`; Kronos validates uploads the same way. Adding a prompt means adding a field to
  `common.models.prompts.Prompts`, its runtime variables to `PROMPT_VARIABLES`, and a `## <prompt_name>` section to
  `resources/prompts.md`.

## Helper Scripts

| Script                               | Description                                                        |
|--------------------------------------|--------------------------------------------------------------------|
| `scripts/deployment-full.sh`         | Full local Docker deployment (build, start, seed the test project) |
| `scripts/find_orphaned_resources.py` | Report resources not belonging to any project / knowledge base     |
| `scripts/migrate_es_index.py`        | Copy an Elasticsearch index to another (already created) index     |
| `scripts/marker_pdf/`                | Standalone marker-pdf PDF pipeline (see its own `README.md`)       |

## Troubleshooting

- **`could not select device driver ... with capabilities: [[gpu]]`** — the host has no Nvidia GPU or no Nvidia
  Container Toolkit. Comment out the GPU access lines as described in
  [Local Docker Deployment](#local-docker-deployment).
- **A container exits immediately with a permission error on a mounted folder** — the `data` subfolder ownership is
  wrong. Re-run `./scripts/deployment-full.sh`, or fix it manually:
  `sudo chown -R 1000:1000 data/{elasticsearch,keycloak}` and `sudo chown -R 999:999 data/{alchemist,maestro,ragnarok}`.
- **An app fails at startup with a pydantic `ValidationError`** — a required config value is missing or invalid.
  `CONFIG` fails fast; the error message names the offending variable.
- **The chatbot answers with an error / times out** — the vLLM generation container is probably still loading the model.
  Check `docker compose logs -f vllm-generation` and `docker ps` (health status).
- **Admin console login redirects back to a blank page or shows a CORS/redirect error** — the Keycloak client's redirect
  URIs / web origins do not match `MAESTRO_URL_EXTERNAL`, or `KEYCLOAK_REALM` / `KEYCLOAK_CLIENT_ID` do not match the
  Keycloak configuration. See [Keycloak Setup](#keycloak-setup).
- **Admin console loads but every request fails with 401** — Kronos cannot validate the JWT. Verify that `KEYCLOAK_URL`
  is reachable from the Kronos container and that the client's default scopes (incl. `roles`) are still assigned.
- **A frontend change is not visible after a restart** — the client tarball is only downloaded when missing; see
  [Updating the Frontend Version](#updating-the-frontend-version).
- **Port is already allocated** — see [Changing Service Ports](#changing-service-ports).

## Licensing and Legal Documents

The `legal` folder holds the license and the legal documents of Alquist Insight. Each document comes in an English and a
Czech version (the Czech one has a `-cz` suffix):

| File                | Czech version          | What it covers                                                                                                                       | Who it binds                                        |
|---------------------|------------------------|--------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------|
| `LICENSE`           | `LICENSE-cz`           | MIT license for the published source code of the client apps and the server                                                          | anyone who obtains the code, including self-hosters |
| `AUTHORS.md`        | `AUTHORS-cz.md`        | Copyright holder, contributor credits, third-party components                                                                        | –                                                   |
| `EULA.md`           | `EULA-cz.md`           | Terms of the **hosted service**: AI transparency, acceptable use, IP, liability, Customer (Admin console) & anonymous End User terms | Provider ↔ Customers ↔ End Users                    |
| `PRIVACY-NOTICE.md` | `PRIVACY-NOTICE-cz.md` | GDPR Art. 13/14 information: processed data, legal bases, sub-processors, transfers, retention, data subject rights                  | – (informational, part of the EULA)                 |

`legal/LICENSE` is only a symlink to the `LICENSE` file in the repository root, which is where GitHub looks for it to
show the license in its repository UI. Always edit the root file.

`legal/client-legal-info.html` is a standalone, dependency-free information page for the users of the chatbot client.
It summarizes the important points of the EULA and the privacy notice in plain language (AI-generated answers, what is
stored and for how long, why anonymous queries cannot be deleted on request, sub-processors, contacts). It is in both
languages, with Czech as the default and a language toggle. Its footer links to the privacy notice, the EULA and the
source code in the public GitHub repository, so the `legal` files must not be renamed or moved without updating these
links.

### Language Versions and Precedence

- **MIT license:** only the **English** text (`LICENSE`) is legally operative. This is standard practice for
  open-source licenses — a translation risks unintentionally altering the scope of the grant. `LICENSE-cz` is
  informational only.
- **EULA and privacy notice:** the **Czech** version prevails for consumers habitually resident in the Czech Republic
  and for Customers established there, the English one prevails otherwise (see EULA clause 9.5).

Both language versions must be kept in step — make every substantive change in both files at once (and in the matching
parts of `client-legal-info.html`).

### The Two-Layer Model

The code is MIT-licensed and imposes no conditions beyond attribution. The EULA and the privacy notice govern only the
**service operated by the Provider** (CIIRC CTU) — they cannot and do not add restrictions to the open-source grant.
Anyone who clones the repository and runs their own instance is bound by `LICENSE` only, and becomes the controller of
their own deployment's data. The EULA, the privacy notice and `client-legal-info.html` describe the Provider's hosted
service (operator, sub-processors, retention periods), so self-hosters should replace them with their own documents.
