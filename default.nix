with import <nixpkgs> {};
with stdenv;


rec {

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
