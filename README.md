# Alquist Insight

Monorepo for the Alquist Insight platform.

## Local Docker Deployment

Prerequisites:

- Docker with docker-compose plugin installed.
- Linux-based system able to run bash scripts.
- Nvidia GPU with CUDA support & 120 GB or more RAM for local embedding/generation models deployment.

Clone the repository:

```shell
git clone https://github.com/AlquistAI/insight.git
cd insight
```

Prepare `config.local.env` file in project root with the server configuration and secrets.
The default/sample values are provided in the `config.env` file.
The servers will run even with the default configuration, but setting up secrets etc. manually is recommended.
For available configuration vars, you can have a look at `common/common/config.py`.

Run the deployment script (update the settings in the script if you made any server config changes):

```shell
./scripts/deployment-full.sh
```

The script will:

1. Ask for sudo permissions. Sudo is required for:
    - `docker` commands in case the current user doesn't have access to the Docker socket.
    - Initial setup of volume mount folder ownership for `docker compose` services.
2. Build Docker images for all apps.
3. Create an empty/dummy `config.local.env` file if it doesn't exist.
4. Prepare directories for docker compose and run all required services.
5. Run the vLLM services for embedding & generation models.
    - These services are resource-heavy. If you intend to use cloud models instead, disable the vLLM containers
      in the `docker-compose.yaml` file (i.e. comment out "vllm..." lines in the "services" section).
    - The vLLM containers might take a long time to start up, since they need to download the models on the first run.
      The default generation model has ~60 GB. It is recommended to do the initial setup on a wired/fast connection.
    - After the first run, the models are persisted in the `data` folder. Any subsequent start of the vLLM services
      should only take a few minutes.
    - The script does not wait for the vLLM generation model to be ready, since it can take longer and
      the model is not required for finishing the initial setup. However, you should wait for it to be
      ready before interacting with the chatbot UI. You can check the status of all Docker containers
      using the `docker ps` command.
6. Create default "test" project and upload the Alquist Insight docs as knowledge base.

After the script finishes execution, you should be able to open the chatbot with the default "test" project
in your browser at `http://localhost:8020/`.

After the first deployment, you can use the usual `docker compose [up|down|...]` commands to stop/run the deployment.
The data is persisted in the `data` folder.

### Knowledge Base Upload

For creating your own projects/uploading knowledge base (documents), you can either use the Kronos APIs
or the Admin console UI.

You can open the chatbot for your custom projects at `http://localhost:8020/?project_id=<project_id>`.

#### Kronos API

The easiest way to use the API is through the Swagger UI accessible at `http://localhost:9625/docs`.
This UI also serves as the API documentation.

You can use the `POST /project/` endpoint for creating a new project and the `POST /knowledge_base/` endpoints
for uploading the documents. You can check the `scripts/deployment-full.sh` script (section
`CREATE EXAMPLE PROJECT IF MISSING`) for an example how to use these endpoints.

#### Admin Console UI

The Admin UI is available at `http://localhost:8020/admin/`. It allows creating new projects and
managing the related knowledge base in a similar fashion as a regular file explorer.

To be able to log in to the admin console, you will have to first set up KeyCloak and create a user:

1. Log in to the KeyCloak admin console at `http://localhost:8080/` (default credentials `admin` & `admin123`).
2. (OPTIONAL) Create a new realm (default name `alquist`).
3. Create a new client (default name `alquist-insight-development`).
    - Use `http://localhost:8020/admin/*` as the valid redirect/post logout URI.
    - Use `*` as allowed origins (i.e. allow all origins).
4. Create a new user/password combination.

ToDo: Do this setup as part of the deployment script.

You should now be able to log in to the admin console at `http://localhost:8020/admin/` using the created credentials.

## Local Development

Prerequisites:

- Python 3.11 (you can use e.g. `pyenv` for managing multiple Python versions on your machine).
- `pipenv` Python package manager.

You can install the Python requirements for all apps using pipenv
(omit the `dev` flag for purely runtime dependencies):

```shell
pipenv install --dev
```

The `common` module is installed in editable mode. I.e. all changes in the common code will manifest immediately.

Prepare `config.local.env` configuration file (see [Local Docker Deployment](#local-docker-deployment) for details).
You can run the individual apps using the provided `run.py` scripts, e.g. `kronos/run.py`.

### PyCharm Setup

This section describes the recommended way how to work with this monorepo in the PyCharm IDE.

1. Open the monorepo folder in PyCharm, you can let it install the pipenv dependencies automatically.
2. Mark the `/common` folder and other app folders (`/kronos`, `/ragnarok`, etc.) as Sources Root.
3. Either use the pipenv environment from the root folder, or follow steps 4-6 for individual app envs.
4. Setup pipenv for each app: e.g. `cd kronos/ && pipenv install --dev`.
5. Add the created Python envs manually for each app:
    1. Open `Settings` -> `Python` -> `Interpreter`.
    2. Select `Add Interpreter` -> `Add Local Interpreter...` -> `Select existing`.
    3. Add a Python env with a custom path to the created virtual env.
       For pipenv it should be at `~/.local/share/virtualenvs/<name>-<hash>/bin/python`.
6. You will have to switch between active Python envs depending on the project you work with.
