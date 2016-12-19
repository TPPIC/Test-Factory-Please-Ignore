BASE="$(dirname "$(readlink -f "$0")")"
TMPDIR="$(mktemp -d)"
trap "cd /tmp; echo rm -rf $TMPDIR" EXIT
cd "$TMPDIR"
echo "Running in $(pwd)"

nix-build "${BASE}/.." -A packs.TPPI3C.server -o server
tar xvzf "${BASE}/testdata/SmokeTest.tar.gz"
echo 'eula=true' > eula.txt
cp "${BASE}/testdata/server.properties" .

export FORCE=1
server/start.sh -Dfml.queryResult=confirm &
PID="$!"

time=0
while true; do
  grep '\[@\] Hello World' logs/latest.log && {
    kill $PID
    exit 0
  }
  time=$(($time + 1))
  if [[ $time -gt 300 ]]; then
    kill $PID
    exit 1
  fi
  sleep 1
done
