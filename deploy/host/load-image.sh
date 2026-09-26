#!/usr/bin/env bash
# Put this bundle's BioManager app image into Docker, from the release's
# files rather than a registry:
#
#   deploy/host/load-image.sh                 download the right one for this machine
#   deploy/host/load-image.sh image.tar.gz    load a file you already have
#
# Each release carries biomanager-image-amd64.tar.gz (Intel and AMD) and
# biomanager-image-arm64.tar.gz (ARM, e.g. Oracle's Ampere VMs). The image is
# tagged as compose.yaml expects (ghcr.io/gaspolymerase/biomanager:<version>),
# so `docker compose up -d` then finds it here and downloads nothing more.
# Run it after unpacking a bundle, before the first start and each update.
set -euo pipefail

here=$(cd "$(dirname "$0")/.." && pwd)
version=$(cat "$here/VERSION" 2>/dev/null || true)
[ -n "$version" ] || { echo "No VERSION file in $here: this is not a server bundle (a checkout builds its own image)."; exit 1; }

if [ $# -ge 1 ]; then
  file=$1
else
  case "$(uname -m)" in
    x86_64 | amd64) arch=amd64 ;;
    aarch64 | arm64) arch=arm64 ;;
    *) echo "No BioManager image for $(uname -m); it runs on x86-64 and ARM64."; exit 1 ;;
  esac
  url="https://github.com/gaspolymerase/biomanager-app/releases/download/v$version/biomanager-image-$arch.tar.gz"
  file=$(mktemp "${TMPDIR:-/tmp}/biomanager-image.XXXXXX")
  trap 'rm -f "$file"' EXIT
  echo "Downloading BioManager $version for $arch…"
  curl -fL --retry 3 -o "$file" "$url" || { echo "Could not download $url"; exit 1; }
fi

docker load -i "$file"
echo "Loaded. Start or update with: cd $here && docker compose up -d"
