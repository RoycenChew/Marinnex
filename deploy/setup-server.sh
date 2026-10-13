#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 24.04 x86_64 host.
#
# Run once as a user with sudo, then never again; deploy.sh handles every
# subsequent release. Safe to re-run if it fails part way: each step checks
# whether it has already been done.
set -euo pipefail

ROOT="${MARINNEX_ROOT:-/srv/marinnex}"
SERVICE_UID=10001   # matches the non-root user inside Dockerfile.app

if [ "$(id -u)" -eq 0 ]; then
    echo "setup-server: run as a normal user with sudo, not as root" >&2
    exit 2
fi

echo "==> Swap"
# 2 GB on a 2 GB box. The container limits already fit in RAM; this exists so
# that a 300 DPI render spike is slow rather than fatal, because the OOM
# killer's choice of victim is nobody's idea of a scheduling policy.
if ! swapon --show | grep -q '/swapfile'; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    # Prefer RAM; use swap as the safety net it is, not as slow memory.
    echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-marinnex.conf >/dev/null
    sudo sysctl -q -p /etc/sysctl.d/99-marinnex.conf
else
    echo "    already present"
fi

echo "==> Docker Engine and the compose plugin"
if ! command -v docker >/dev/null 2>&1; then
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin
    sudo usermod -aG docker "$USER"
    echo "    added $USER to the docker group — log out and back in for it to apply"
else
    echo "    already installed"
fi

echo "==> AWS CLI, sqlite3, unattended upgrades"
sudo apt-get install -y -qq awscli sqlite3 unattended-upgrades
# Security updates applied automatically. A one-person project will not be
# patching by hand on a Tuesday.
sudo dpkg-reconfigure -f noninteractive unattended-upgrades

echo "==> Folders"
sudo mkdir -p "$ROOT/data/blobs" "$ROOT/data/exports"
sudo chown -R "$USER:$USER" "$ROOT"
# The container runs as uid 10001 and writes to the bind mount, so the data
# directory must be owned by that uid on the host.
sudo chown -R "$SERVICE_UID:$SERVICE_UID" "$ROOT/data"
chmod 750 "$ROOT"

echo "==> Repositories"
if [ ! -d "$ROOT/Marinnex/.git" ]; then
    echo "    clone them side by side, then run deploy/scripts/deploy.sh:"
    echo "      git clone <marinnex-url> $ROOT/Marinnex"
    echo "      git clone https://github.com/RoycenChew/Toolkits_Management $ROOT/Toolkits_Management"
else
    echo "    already cloned"
fi

echo "==> Nightly file backup at 03:15 UTC"
CRON="15 3 * * * BACKUP_BUCKET=\${BACKUP_BUCKET} $ROOT/Marinnex/deploy/scripts/backup-files.sh >> /var/log/marinnex-backup.log 2>&1"
if ! crontab -l 2>/dev/null | grep -qF 'backup-files.sh'; then
    (crontab -l 2>/dev/null || true; echo "$CRON") | crontab -
    sudo touch /var/log/marinnex-backup.log
    sudo chown "$USER:$USER" /var/log/marinnex-backup.log
else
    echo "    already scheduled"
fi

cat <<'NEXT'

==> Done. What is left, and only you can do it:

  1. Attach an IAM instance role with s3:PutObject, s3:GetObject,
     s3:DeleteObject and s3:ListBucket on the backup bucket, and
     ssm:GetParametersByPath + kms:Decrypt on /marinnex/prod.
  2. Put the secrets in SSM under /marinnex/prod (SecureString for anything
     secret): FDIP_KEY_PEPPER, FDIP_SESSION_SECRET, DEEPSEEK_API_KEY,
     FDIP_AI_MONTHLY_CEILING_USD, DOMAIN, BACKUP_BUCKET.
  3. Point the domain's A record at this instance, and open 80 and 443.
  4. Run deploy/scripts/deploy.sh.
  5. Run deploy/scripts/restore-test.sh once there is real data, and again
     whenever you want to keep believing in the backups.

NEXT
