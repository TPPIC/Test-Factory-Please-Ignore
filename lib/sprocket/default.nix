with import <nixpkgs> {};
with import ../lib.nix;

rec {
  sprocket = fetchFromGitHub {
    owner = "reteo";
    repo = "Sprocket";
    rev = "714c1793721c464f291da2971da8ac9cd97f62c3";
    sha256 = "0pacsp3sy52zw8jnb6nnhgicgqhj35xjc8hg84m5vp4g3vkjbics";
  };

  generateCustomOreGenConfig = src: runLocally "COG-Config" {
    inherit sprocket src;
    buildInputs = [ python ];
    config = ./CustomOreGen_Config.xml;
  } ''
    mkdir -p $out/config/CustomOreGen
    cd $out/config/CustomOreGen
    cat $config > CustomOreGen_Config.xml
    mkdir -p modules/tppi
    cd modules/tppi
    find "$src" -type f -exec python $sprocket/sprocket.py {} \;
  '';
}
