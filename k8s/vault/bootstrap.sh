#!/usr/bin/env bash

# in order:
#   1. Enable the Kubernetes auth method on Vault.
#   2. Configure that auth method to trust THIS cluster's API server.
#   3. Write a policy ("app-read") that grants read on secret/data/app.
#   4. Create a role ("app") that links the policy to a specific
#      ServiceAccount (the External Secrets Operator's SA).
#   5. Write the initial demo secret to secret/app.
#
# Usage:
#   bash k8s/vault/bootstrap.sh


set -euo pipefail

VAULT_NS="${VAULT_NS:-vault}"
VAULT_POD="${VAULT_POD:-vault-0}"
VAULT_TOKEN="${VAULT_TOKEN:-root}"
ESO_NAMESPACE="${ESO_NAMESPACE:-external-secrets}"
ESO_SERVICE_ACCOUNT="${ESO_SERVICE_ACCOUNT:-external-secrets}"

# Demo secret value. Pass in via env to override:
#   APP_API_KEY=mykey bash k8s/vault/bootstrap.sh
# Default is an obvious placeholder so nothing real ever lands in git history.
APP_API_KEY="${APP_API_KEY:-CHANGE_ME_DEMO_VALUE}"

exec_vault() {
  kubectl exec -n "$VAULT_NS" "$VAULT_POD" -- \
    sh -c "VAULT_TOKEN=$VAULT_TOKEN $*"
}

echo ">> 1/5 Enabling Kubernetes auth method"
exec_vault "vault auth enable kubernetes" 2>/dev/null \
  || echo "   (already enabled — continuing)"

echo ">> 2/5 Configuring Kubernetes auth to trust the in-cluster API server"
exec_vault "vault write auth/kubernetes/config \
  kubernetes_host=https://\$KUBERNETES_PORT_443_TCP_ADDR:443"

echo ">> 3/5 Writing the app-read policy"
kubectl exec -n "$VAULT_NS" "$VAULT_POD" -- sh -c "VAULT_TOKEN=$VAULT_TOKEN vault policy write app-read - <<'EOF'
path \"secret/data/app\" {
  capabilities = [\"read\"]
}
EOF
"

echo ">> 4/5 Binding the policy to the ESO ServiceAccount via a Vault role"
exec_vault "vault write auth/kubernetes/role/app \
  bound_service_account_names=$ESO_SERVICE_ACCOUNT \
  bound_service_account_namespaces=$ESO_NAMESPACE \
  policies=app-read \
  ttl=24h"

echo ">> 5/5 Writing the initial demo secret"
exec_vault "vault kv put secret/app api_key=$APP_API_KEY"

echo ""
echo "Bootstrap complete. Verify with:"
echo "  kubectl exec -n $VAULT_NS $VAULT_POD -- vault kv get secret/app"
