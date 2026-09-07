#!/usr/bin/env bash
set -euo pipefail

### CONFIGURATION ###
echo "==== Reading server config ===="
touch config.local.env
source config.env
source config.local.env

KEYCLOAK_URL="${KEYCLOAK_URL_EXTERNAL:-http://localhost:8080}"
KRONOS_URL="${KRONOS_URL_EXTERNAL:-http://localhost:9625}"
MAESTRO_URL="${MAESTRO_URL_EXTERNAL:-http://localhost:8020}"
RAGNAROK_URL="${RAGNAROK_URL_EXTERNAL:-http://localhost:9696}"

REALM_NAME="${KEYCLOAK_REALM:-alquist}"
CLIENT_ID="${KEYCLOAK_CLIENT_ID:-alquist-insight-development}"
CLIENT_REDIRECT_URI="${MAESTRO_URL}/admin/*"

DEFAULT_PROJECT_ID="test"
DEFAULT_PROJECT_LANG="en-US"

# Env vars used in docker-compose.yaml
REQUIRED_DC_VARS=(
  KEYCLOAK_ADMIN_PASSWORD
  KEYCLOAK_DB_PASSWORD
  MINIO_ROOT_PASSWORD
)

for var in "${REQUIRED_DC_VARS[@]}"; do
  : "${!var:?Environment variable $var is required}"
  export "$var"
done

export KEYCLOAK_ADMIN_USER=${KEYCLOAK_ADMIN_USER:-admin}
export KEYCLOAK_DB_USER=${KEYCLOAK_DB_USER:-keycloak}
export MINIO_ROOT_USER=${MINIO_ROOT_USER:-admin}

### ASK THE USER FOR SUDO PERMISSIONS ###
echo "Some commands in this script require sudo (e.g. for initial docker volume mount folders setup)."
echo "Requesting authentication..."
sudo -v || exit 1

### CHECK DOCKER SETUP ###
echo "==== Checking docker setup ===="

if docker info > /dev/null 2>&1; then
  echo "Docker socket does not require sudo. Setting the Docker command to 'docker'."
  DOCKER="docker"
else
  echo "Docker socket requires sudo. Setting the Docker command to 'sudo docker'."
  DOCKER="sudo docker"
fi

### START DOCKER COMPOSE ###
echo "==== Preparing directories required for docker compose ===="
mkdir -p data/{alchemist/{docling,huggingface},elasticsearch,keycloak,maestro/frontend,ragnarok/models}
sudo chown -R 1000:1000 data/{elasticsearch,keycloak}
sudo chown -R 999:999 data/{alchemist,maestro,ragnarok}

echo "==== Building the app images and starting docker compose ===="
echo "The vllm-generation container waits for the vllm-embedding container to be ready before it starts."
echo "This can take some time as the vLLM containers need to download/load the models. Please be patient."
$DOCKER compose up -d --build

### WAIT FOR BACKEND SERVICES ###
echo "==== Waiting for backend services to become ready ===="

until curl -fs "$KRONOS_URL/health" > /dev/null; do
  echo "Kronos not ready yet..."
  sleep 5
done

until curl -fs "$RAGNAROK_URL/health" > /dev/null; do
  echo "Ragnarok not ready yet..."
  sleep 5
done

### UPLOAD DEFAULT RESOURCE FILES IF MISSING ###
echo "==== Uploading default dialogue/image/prompts files ===="

if curl -fs "$KRONOS_URL/resources/dialogue_fsm/" -H "X-Api-Key: $KRONOS_API_KEY" > /dev/null; then
  echo "Default dialogue FSM file already exists. Skipping."
else
  curl -X "POST" \
    "$KRONOS_URL/resources/dialogue_fsm/init" \
    -H "X-Api-Key: $KRONOS_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"language": "'$DEFAULT_PROJECT_LANG'"}'

  echo -e "\nDefault dialogue FSM file created."
fi

if curl -fs "$KRONOS_URL/resources/image/?resource_id=digital_theme.png" -H "X-Api-Key: $KRONOS_API_KEY" > /dev/null; then
  echo "Default image file already exists. Skipping."
else
  curl -X "POST" \
    "$KRONOS_URL/resources/image/?resource_id=digital_theme.png" \
    -H "X-Api-Key: $KRONOS_API_KEY" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@resources/digital_theme.png;type=image/png"

  echo -e "\nDefault image file created."
fi

if curl -fs "$KRONOS_URL/resources/prompts/" -H "X-Api-Key: $KRONOS_API_KEY" > /dev/null; then
  echo "Default prompts file already exists. Skipping."
else
  curl -X "POST" \
    "$KRONOS_URL/resources/prompts/" \
    -H "X-Api-Key: $KRONOS_API_KEY" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@resources/prompts.md;type=text/markdown"

  echo -e "\nDefault prompts file created."
fi

### CREATE EXAMPLE PROJECT IF MISSING ###
echo "==== Creating '$DEFAULT_PROJECT_ID' project ===="

if curl -fs "$KRONOS_URL/projects/$DEFAULT_PROJECT_ID/" -H "X-Api-Key: $KRONOS_API_KEY" > /dev/null; then
  echo "Project '$DEFAULT_PROJECT_ID' already exists. Skipping."
else
  curl -X "POST" \
    "$KRONOS_URL/projects/" \
    -H "X-Api-Key: $KRONOS_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{
      "_id": "'$DEFAULT_PROJECT_ID'",
      "name": "Default Test Project",
      "language": "'$DEFAULT_PROJECT_LANG'"
    }'

  echo -e "\n\nProject '$DEFAULT_PROJECT_ID' created.\n"

  curl -X "POST" \
    "$KRONOS_URL/knowledge_base/file/bulk?project_id=$DEFAULT_PROJECT_ID&source_type=txt&language=$DEFAULT_PROJECT_LANG" \
    -H "X-Api-Key: $KRONOS_API_KEY" \
    -H "Content-Type: multipart/form-data" \
    -F "files=@common/common/config.py;type=text/x-python" \
    -F "files=@config.env" \
    -F "files=@docker-compose.yaml;type=application/yaml" \
    -F "files=@README.md;type=text/markdown"

  echo -e "\n\nExample documents uploaded to '$DEFAULT_PROJECT_ID' project."
fi

### WAIT FOR KEYCLOAK ###
#echo "==== Waiting for Keycloak to become ready ===="
#
#until curl -fs "$KEYCLOAK_URL/realms/master" > /dev/null; do
#    echo "Keycloak not ready yet..."
#    sleep 5
#done

### LOGIN TO KEYCLOAK ###
#echo "==== Logging in to Keycloak admin CLI ===="
#
#$DOCKER exec keycloak kc.sh \
#    login \
#    --server "$KEYCLOAK_URL" \
#    --realm master \
#    --user "$KEYCLOAK_ADMIN" \
#    --password "$KEYCLOAK_ADMIN_PASSWORD"

### CREATE REALM IF MISSING ###
#echo "==== Creating realm '$REALM_NAME' if it does not exist ===="
#
#if $DOCKER exec keycloak kc.sh get realms/"$REALM_NAME" > /dev/null 2>&1; then
#    echo "Realm '$REALM_NAME' already exists. Skipping."
#else
#    $DOCKER exec keycloak kc.sh create realms -s realm="$REALM_NAME" -s enabled=true
#    echo "Realm '$REALM_NAME' created."
#fi

### CREATE CLIENT IF MISSING ###
#echo "==== Creating client '$CLIENT_ID' if missing ===="
#
#CLIENT_EXISTS=$($DOCKER exec keycloak kc.sh \
#  get clients -r "$REALM_NAME" --fields clientId | grep -c "\"$CLIENT_ID\"" || true)
#
#if [ "$CLIENT_EXISTS" -gt 0 ]; then
#    echo "Client '$CLIENT_ID' already exists. Skipping."
#else
#    $DOCKER exec keycloak kc.sh create clients \
#        -r "$REALM_NAME" \
#        -s clientId="$CLIENT_ID" \
#        -s enabled=true \
#        -s publicClient=true \
#        -s 'redirectUris=["'"$CLIENT_REDIRECT_URI"'"]'
#
#    echo "Client '$CLIENT_ID' created."
#fi

echo "==== Deployment completed successfully ===="
echo "You can now access the chatbot UI at $MAESTRO_URL"
echo "It might still take a while for the generation model to load."
echo "You can check the status of all docker containers using the 'docker ps' command."
