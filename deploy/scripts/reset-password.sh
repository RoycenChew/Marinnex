#!/usr/bin/env bash
# Set a new password on an existing account.
#
# There is no password-reset email, so this is the recovery path when someone
# locks themselves out. It changes the stored hash and nothing else. The new
# password is printed once, here, for you to pass on out of band — it is never
# mailed, logged or stored in plain text.
set -euo pipefail

EMAIL="${1:-}"
PASSWORD="${2:-}"

if [ -z "$EMAIL" ]; then
    echo "usage: reset-password.sh <email> [new-password]" >&2
    exit 2
fi

if [ -z "$PASSWORD" ]; then
    # 24 random characters. Generated here rather than asked for, because a
    # password a human invents under time pressure is the one they reuse.
    PASSWORD="$(python3 -c 'import secrets,string;a=string.ascii_letters+string.digits;print("".join(secrets.choice(a) for _ in range(24)))')"
fi

ROOT="${MARINNEX_ROOT:-/srv/marinnex}"
COMPOSE=(docker compose -f "$ROOT/Marinnex/deploy/docker-compose.prod.yml" --env-file "$ROOT/.env")

"${COMPOSE[@]}" run --rm --no-deps api \
    python -m fdip.cli reset-password --email "$EMAIL" --password "$PASSWORD"

echo
echo "Password reset."
echo "  email:    ${EMAIL}"
echo "  password: ${PASSWORD}"
echo
echo "Give these to the person directly, and ask them to change it."
