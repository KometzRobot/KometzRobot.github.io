#!/bin/bash
# check-balance-deploy.sh — Check if MATIC or Zora ETH arrived, auto-deploy if so
# Run periodically via cron or loop

cd /home/joel/autonomous-ai

# Check Polygon MATIC
MATIC=$(python3 -c "
import urllib.request, json
try:
    p = json.dumps({'jsonrpc':'2.0','method':'eth_getBalance','params':['0xa14eAb75AC5AaB377858b65D57F7FdC7137131b1','latest'],'id':1}).encode()
    r = urllib.request.Request('https://1rpc.io/matic', data=p, headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0'})
    d = json.loads(urllib.request.urlopen(r, timeout=8).read())
    print(int(d['result'], 16))
except:
    print(0)
" 2>/dev/null)

# Check Zora ETH
ZORA=$(python3 -c "
import urllib.request, json
try:
    p = json.dumps({'jsonrpc':'2.0','method':'eth_getBalance','params':['0xa14eAb75AC5AaB377858b65D57F7FdC7137131b1','latest'],'id':1}).encode()
    r = urllib.request.Request('https://rpc.zora.energy', data=p, headers={'Content-Type':'application/json','User-Agent':'Mozilla/5.0'})
    d = json.loads(urllib.request.urlopen(r, timeout=8).read())
    print(int(d['result'], 16))
except:
    print(0)
" 2>/dev/null)

NOW=$(date '+%Y-%m-%d %H:%M:%S')

if [ "$ZORA" -gt 0 ] 2>/dev/null; then
    echo "[$NOW] ZORA ETH DETECTED! Balance: $ZORA wei. Deploying..."
    node deploy-nft-zora.mjs 2>&1 | tee -a .deploy-log.txt
elif [ "$MATIC" -gt 0 ] 2>/dev/null; then
    echo "[$NOW] MATIC DETECTED! Balance: $MATIC wei. Deploying..."
    node deploy-nft.js 2>&1 | tee -a .deploy-log.txt
else
    echo "[$NOW] Polygon: $MATIC wei | Zora: $ZORA wei | Still waiting."
fi
