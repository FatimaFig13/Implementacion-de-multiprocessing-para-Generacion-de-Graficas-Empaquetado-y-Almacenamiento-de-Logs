#!/usr/bin/env bash
set -euo pipefail

mongosh --quiet \
  -u "${MONGO_INITDB_ROOT_USERNAME}" \
  -p "${MONGO_INITDB_ROOT_PASSWORD}" \
  --authenticationDatabase admin <<EOF
db.getSiblingDB("stori_logs").createUser({
  user: "${MONGO_APP_USERNAME}",
  pwd: "${MONGO_APP_PASSWORD}",
  roles: [ { role: "readWrite", db: "stori_logs" } ]
});
EOF

echo "[mongo-init] Usuario '${MONGO_APP_USERNAME}' creado con readWrite sobre 'stori_logs'."