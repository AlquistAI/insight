#!/usr/bin/env bash
set -euo pipefail

### CONFIGURATION ###
APPS=("kronos" "maestro" "ragnarok")

KRONOS_URL="http://localhost:9625"
KRONOS_API_KEY=kronos123
RAGNAROK_URL="http://localhost:9696"
VLLM_EMBEDDING_URL="http://localhost:8123"

KEYCLOAK_URL="http://localhost:8080"
KEYCLOAK_USER="admin"
KEYCLOAK_PASS="admin123"

REALM_NAME="alquist"
CLIENT_ID="alquist-insight-development"
CLIENT_REDIRECT_URI="http://localhost:8020/admin/*"

DEFAULT_PROJECT_ID="test"
DEFAULT_PROJECT_LANG="en"
DEFAULT_PROJECT_LANG_CODE="en-US"

DEFAULT_RETRIEVAL_MODEL_PROVIDER="vLLM"
DEFAULT_RETRIEVAL_MODEL_NAME="Qwen/Qwen3-Embedding-0.6B"
DEFAULT_RETRIEVAL_MODEL_BASE_URL="http://vllm-embedding:8000/v1"

DEFAULT_GENERATION_MODEL_PROVIDER="vLLM"
DEFAULT_GENERATION_MODEL_NAME="Qwen/Qwen3-30B-A3B"
DEFAULT_GENERATION_MODEL_BASE_URL="http://vllm-generation:8000/v1"

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

### BUILD DOCKER IMAGES ###
# ToDo: Build the images directly through docker-compose.
echo "==== Building Docker images ===="

for APP in "${APPS[@]}"; do
  echo "Building $APP..."
  $DOCKER build -f "$APP/Dockerfile" -t "$APP:latest" .
done

### START DOCKER COMPOSE ###
echo "==== Preparing directories required for docker compose ===="
mkdir -p data/{elasticsearch,keycloak,maestro/frontend,ragnarok/models}
sudo chown -R 1000:1000 data/{elasticsearch,keycloak}
sudo chown -R 999:999 data/{maestro,ragnarok}

echo "==== Starting docker compose ===="
echo "The vllm-generation container waits for the vllm-embedding container to be ready before it starts."
echo "This can take some time as the vLLM containers need to download/load the models. Please be patient."
touch config.local.env
$DOCKER compose up -d

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

until curl -fs "$VLLM_EMBEDDING_URL/health" > /dev/null; do
  echo "vLLM embedding model not ready yet..."
  sleep 30
done

### UPLOAD DEFAULT DIALOGUE/IMAGE FILES IF MISSING ###
echo "==== Uploading default dialogue/image files ===="

if curl -fs "$KRONOS_URL/resources/dialogue_fsm/" -H "X-Api-Key: $KRONOS_API_KEY" > /dev/null; then
  echo "Default dialogue FSM file already exists. Skipping."
else
  curl -X "POST" \
    "$KRONOS_URL/resources/dialogue_fsm/" \
    -H "X-Api-Key: $KRONOS_API_KEY" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@fsm/default_$DEFAULT_PROJECT_LANG.json;type=application/json"

  echo -e "\nDefault dialogue FSM file created."
fi

if curl -fs "$KRONOS_URL/resources/image/?resource_id=digital_theme.png" -H "X-Api-Key: $KRONOS_API_KEY" > /dev/null; then
  echo "Default image file already exists. Skipping."
else
  curl -X "POST" \
    "$KRONOS_URL/resources/image/?resource_id=digital_theme.png" \
    -H "X-Api-Key: $KRONOS_API_KEY" \
    -H "Content-Type: multipart/form-data" \
    -F "file=@fsm/digital_theme.png;type=image/png"

  echo -e "\nDefault image file created."
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
      "language": "'$DEFAULT_PROJECT_LANG_CODE'",
      "ai_settings": {
        "retrieval": {
          "model": {
            "provider": "'$DEFAULT_RETRIEVAL_MODEL_PROVIDER'",
            "name": "'$DEFAULT_RETRIEVAL_MODEL_NAME'",
            "base_url": "'$DEFAULT_RETRIEVAL_MODEL_BASE_URL'"
          }
        },
        "generation": {
          "model": {
            "provider": "'$DEFAULT_GENERATION_MODEL_PROVIDER'",
            "name": "'$DEFAULT_GENERATION_MODEL_NAME'",
            "base_url": "'$DEFAULT_GENERATION_MODEL_BASE_URL'"
          }
        }
      }
    }'

  echo -e "\n\nProject '$DEFAULT_PROJECT_ID' created.\n"

  curl -X "POST" \
    "$KRONOS_URL/knowledge_base/file/bulk?project_id=$DEFAULT_PROJECT_ID&source_type=txt&language=en-US&model_provider=$DEFAULT_RETRIEVAL_MODEL_PROVIDER&model_name=$DEFAULT_RETRIEVAL_MODEL_NAME&model_base_url=$DEFAULT_RETRIEVAL_MODEL_BASE_URL" \
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
#    --user "$KEYCLOAK_USER" \
#    --password "$KEYCLOAK_PASS"

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
echo "You can now access the chatbot UI at http://localhost:8020/"
echo "It might still take a while for the generation model to load."
echo "You can check the status of all docker containers using the 'docker ps' command."
