with import <nixpkgs> {};
with stdenv;

with import ./lib/lib.nix;

rec {

  packs = {
    TPPI3C = buildPack TPPI3C;
  };

  TPPI3C = {
    name = "TPPI3C-0.0.1";
    screenName = "tppi";  # On dev server.
    port = 25567;  # On dev server.
    forge = {
      major = "1.10.2";
      minor = "12.18.3.2185";
    };
    # These are copied to the client as well as the server.
    # Suggested use: Configs. Scripts. That sort of thing.
    extraDirs = [
      ./base-tppi3
    ];
    # Server only.
    extraServerDirs = [
      ./base-server
    ];
    # These are all the mods we'd like to include in this pack.
    # (Not yet, they're not.)
    manifests = [
      ./manifest/definitely.nix
      ./manifest/maybe.nix
      ./manifest/tools.nix
      ./manifest/dev-only.nix
    ];
    # Not all mods are equally welcome.
    blacklist = [
      # WAILA conflicts with HWYLA.
      "waila"
      # MFFS's current release is buggy, see https://github.com/nekosune/modularforcefieldsystem/issues/7
      "modular-forcefield-system"
    ];
  };

  ServerPack = buildServerPack rec {
    inherit packs;
    hostname = "tppi.brage.info";
    urlBase = "https://" + hostname + "/";
  };

  # To use:
  # nix-build -A ServerPackLocal && (cd result && python -m SimpleHTTPServer)
  ServerPackLocal = buildServerPack rec {
    inherit packs;
    hostname = "localhost";
    urlBase = "http://" + hostname + "/";
  };

  # This wraps the updater with its dependencies.
  updater = python2Packages.buildPythonPackage rec {
    name = "updater";
    version = "tppi";

    src = ./manifest;

    propagatedBuildInputs = with pythonPackages; [
      beautifulsoup lxml futures cacert
    ];
  };

}
