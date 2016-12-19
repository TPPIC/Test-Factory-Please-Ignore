with import <nixpkgs> {};

let
  packs = (import ../.).packs;

  smokeTest = pack: runCommand "smoketest" {
    server = pack.server;
    world = ./testdata/SmokeTest.tar.gz;
    props = ./testdata/server.properties;
    buildInputs = [ jre8 rsync procps psmisc ];
  } ''
    ln -s $server server
    tar xvzf $world
    cat $props > server.properties
    echo 'eula=true' > eula.txt

    echo | bash server/start.sh -Dfml.queryResult=confirm &

    terminate() {
      set +e
      killall java
      pkill -P $$
      sleep 5
      killall -9 java
      pkill -9 -P $$
      set -e
      wait
    }

    time=0
    while true; do
      grep '\[@\] Hello World' logs/latest.log && {
        terminate
        cp logs/latest.log $out
        exit 0
      }
      time=$(($time + 1))
      if [[ $time -gt 300 ]]; then
        terminate
        exit 1
      fi
      sleep 1
    done
  '';
in

rec {
  smokeTests = lib.mapAttrsToList (n: pack: smokeTest pack) packs;
}
