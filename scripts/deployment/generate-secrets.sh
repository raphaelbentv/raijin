#!/usr/bin/env bash
# Génère les secrets cryptographiques pour un déploiement Raijin production.
#
# Usage :
#   ./scripts/deployment/generate-secrets.sh [--out .env.production]
#
# Le script écrit dans le fichier de sortie uniquement si celui-ci n'existe pas.
# Pour rotation : supprimer le fichier ou éditer manuellement les lignes concernées.
#
set -euo pipefail

OUT_FILE="${1:-.env.production.secrets}"

if [ -f "$OUT_FILE" ]; then
    echo "⚠️  $OUT_FILE existe déjà."
    echo "    Supprime-le d'abord (ou éditer-le à la main) si tu veux régénérer."
    exit 1
fi

has_python3() { command -v python3 >/dev/null 2>&1; }

if ! has_python3; then
    echo "❌ python3 requis pour la génération."
    exit 1
fi

# Fernet (32 url-safe base64 bytes)
encryption_key=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())" 2>/dev/null || true)

if [ -z "$encryption_key" ]; then
    echo "❌ cryptography non installé. Tenter :"
    echo "   python3 -m pip install cryptography"
    exit 1
fi

jwt_secret=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
pg_password=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
minio_secret=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")

cat >"$OUT_FILE" <<EOF
# Raijin — Secrets générés le $(date +'%Y-%m-%d %H:%M:%S %Z')
# CONFIDENTIEL. Ne jamais committer.

ENCRYPTION_KEY=$encryption_key
JWT_SECRET=$jwt_secret
POSTGRES_PASSWORD=$pg_password
S3_SECRET_KEY=$minio_secret

EOF

chmod 600 "$OUT_FILE"

cat <<EOF
✅ Secrets générés dans $OUT_FILE (chmod 600)

Prochaines étapes :
  1. Concatène ce fichier avec le reste de ta config prod :
       cat .env.production.example $OUT_FILE > .env.production
       vim .env.production   # remplir les URLs, clés Azure, Google, etc.
       chmod 600 .env.production
       rm $OUT_FILE          # ne garder que .env.production

  2. Sauvegarde JWT_SECRET et ENCRYPTION_KEY dans ton gestionnaire de secrets
     (1Password, Azure Key Vault, AWS Secrets Manager…) :
     - si JWT_SECRET est perdu → tous les tokens émis deviennent invalides (users doivent se reconnecter)
     - si ENCRYPTION_KEY est perdu → les tokens OAuth chiffrés en DB deviennent illisibles
       (sources email / myDATA / ERP à reconnecter)
EOF
