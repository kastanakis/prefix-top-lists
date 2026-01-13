#!/usr/bin/env bash

set -u  

OPENSSL_BIN="$HOME/oqs/bin/openssl"
PROVIDER_PATH="$HOME/oqs/lib64/ossl-modules"
DOMAIN_FILE="domains.txt"
GROUP_FILE="pqc.groups.txt"
OUTDIR="one.mil.finalPQCscan"
SUMMARY_FILE="$OUTDIR/pqc.final.summary.csv"
DEBUG_LOG="$OUTDIR/pqc.final.debug.log"
TIMEOUT_DURATION="5s"
PARALLELISM=250  

mkdir -p "$OUTDIR"
: > "$DEBUG_LOG"
echo "Domain,Group,Status,Cipher/Notes" > "$SUMMARY_FILE"

export OPENSSL_BIN PROVIDER_PATH TIMEOUT_DURATION OUTDIR SUMMARY_FILE DEBUG_LOG GROUP_FILE
scan_domain() {
  local domain="$1"

  while IFS= read -r group; do
    result=$(timeout "$TIMEOUT_DURATION" </dev/null "$OPENSSL_BIN" s_client \
      -groups "$group" \
      -connect "${domain}:443" \
      -tls1_3 \
      -provider oqsprovider \
      -provider default \
      -provider-path "$PROVIDER_PATH" 2>&1)

    cipher=$(echo "$result" | awk '/New, TLSv1.3, Cipher is / { print $NF }')

    if [[ -n "$cipher" ]]; then
      echo "$domain,$group,✅,$cipher" >> "$SUMMARY_FILE"
    else
      note=$(echo "$result" | grep -q "Command terminated" && echo "TIMEOUT" || echo "FAILED")
      echo "$domain,$group,❌,$note" >> "$SUMMARY_FILE"
      {
        echo "----"
        echo "Domain: $domain"
        echo "Group: $group"
        echo "$result" | grep -Ei 'error|alert|handshake|unable|SSL|FAIL|reject|refused|no peer|verify|timeout'
        echo ""
      } >> "$DEBUG_LOG"
    fi
  done < "$GROUP_FILE"
}

export -f scan_domain
parallel --bar -j "$PARALLELISM" scan_domain :::: "$DOMAIN_FILE"

echo "Scan complete"
echo "Summary: $SUMMARY_FILE"
echo "Debug log: $DEBUG_LOG"
