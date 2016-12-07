with import <nixpkgs> {};
with stdenv;

with import ./lib/lib.nix;

rec {

  packs = {
    TPPI3C = buildPack TPPI3C;
  };

  TPPI3C = {
    name = "TPPI3C-0.0.1";
    # For GNU Screen. Extra safety check.
    screenName = "tppi";
    forge = {
      major = "1.10.2";
      minor = "12.18.3.2185";
    };
    # These are copied to the client as well as the server.
    # Suggested use: Configs. Scripts. That sort of thing.
    extraDirs = [
      ./base-tppi3
    ];
    # These are all the mods we'd like to include in this pack.
    # (Not yet, they're not.)
    manifests = [
      ./manifest/mods.json-manifest
    ];
  };

  ServerPack = buildServerPack packs;
}
