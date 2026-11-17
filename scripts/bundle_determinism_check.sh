#!/usr/bin/env bash
set -euo pipefail

cd "${HOME}"

rm -f aelitium-v3_bundle.tar.gz aelitium-v3_bundle.tar.gz.sha256
rm -rf aelitium-v3_bundle

cp -r aelitium-v3 aelitium-v3_bundle
tar --sort=name \
    --mtime='UTC 2024-01-01' \
    --owner=0 --group=0 --numeric-owner \
    -czf aelitium-v3_bundle.tar.gz aelitium-v3_bundle
sha1="$(sha256sum aelitium-v3_bundle.tar.gz | awk '{print $1}')"

rm -f aelitium-v3_bundle.tar.gz aelitium-v3_bundle.tar.gz.sha256
rm -rf aelitium-v3_bundle

cp -r aelitium-v3 aelitium-v3_bundle
tar --sort=name \
    --mtime='UTC 2024-01-01' \
    --owner=0 --group=0 --numeric-owner \
    -czf aelitium-v3_bundle.tar.gz aelitium-v3_bundle
sha2="$(sha256sum aelitium-v3_bundle.tar.gz | awk '{print $1}')"

echo "BUNDLE_SHA_RUN1=$sha1"
echo "BUNDLE_SHA_RUN2=$sha2"
test "$sha1" = "$sha2"
