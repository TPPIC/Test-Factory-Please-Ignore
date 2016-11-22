with import <nixpkgs> {};
with stdenv;


rec {

  # This wraps the updater with its dependencies.
  updater = buildPythonPackage rec {
    name = "updater";
    version = "tppi";

    src = ./manifest;

    propagatedBuildInputs = with pythonPackages; [
      beautifulsoup lxml futures cacert
    ];
  };

}
