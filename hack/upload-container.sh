#!/usr/bin/env bash

baseimagename="ghcr.io/$GITHUB_REPO"
imagename="$baseimagename:$GITHUB_REF_NAME"

# Create a new manifest
mapfile -d $'\0' references < <(find containers -name '*.tar.gz' -print0 | sed -z 's,^,docker-archive:,')
echo "Creating new manifest as $imagename"
echo "Reference images: ${references[*]}"
PODMAN="podman"
if [[ -v GITHUB_ACTIONS ]]; then
  PODMAN="sudo $(which podman)"
fi
echo "Using podman: $PODMAN"
$PODMAN manifest create \
  --annotation "org.opencontainers.image.vendor=EMFCamp" \
  --annotation "org.opencontainers.image.title=Orga Home" \
  --annotation "org.opencontainers.image.created=$(date --iso-8601=seconds)" \
  --annotation "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
  --annotation "org.opencontainers.image.url=https://github.com/$GITHUB_REPO" \
  --annotation "org.opencontainers.image.source=https://github.com/$GITHUB_REPO" \
  --all \
  "$imagename" \
  "${references[@]}"

# Dump out the manifest we created
$PODMAN manifest inspect "$imagename"

# Log into GHCR
echo "$GITHUB_TOKEN" | $PODMAN login ghcr.io -u "$GITHUB_ACTOR" --password-stdin

# Upload the container, tagging it with the branch name
$PODMAN manifest push --all --format oci "$imagename" "docker://$imagename"
