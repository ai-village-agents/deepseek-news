#!/bin/bash
feeds=(
"https://www.icc-cpi.int/rss"
"https://www.icj-cij.org/rss"
"https://hudoc.echr.coe.int/app/rss"
"https://pca-cpa.org/rss"
"https://www.itlos.org/rss"
"https://www.wto.org/rss"
"https://icsid.worldbank.org/rss"
"https://www.ohchr.org/rss"
)

for url in "${feeds[@]}"; do
  echo -n "Testing $url... "
  status=$(curl -s -o /dev/null -w "%{http_code}" -L "$url" --max-time 10)
  if [ "$status" = "200" ]; then
    echo "OK"
  else
    echo "HTTP $status"
  fi
done
