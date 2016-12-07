with import <nixpkgs> {};
with stdenv;

rec {
  buildPack = {
    name,
    screenName,
    forge,
    manifests ? [],
    extraDirs ? [],
  }: rec {
    forgeDir = fetchForge forge;

    serverModsDir = fetchManifests {
      side = "server";
      inherit manifests;
    };

    server = symlinkJoin {
      name = name + "-server";

      inherit screenName;

      paths = [
        ../base-server
        forgeDir
        serverModsDir
      ] ++ extraDirs;

      postBuild = ''
        substituteAll $out/start.sh start.sh
        chmod +x start.sh
        rm $out/start.sh
        cp start.sh $out
      '';
    };
  };

  fetchForge = { major, minor }: runCommand "forge-${major}-${minor}" {
    inherit major minor;

    url = {
      "1.7.10" = "http://files.minecraftforge.net/maven/net/minecraftforge/forge/${major}-${minor}-${major}/forge-${major}-${minor}-${major}-installer.jar";
      "1.10.2" = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/${major}-${minor}/forge-${major}-${minor}-installer.jar";
    }.${major};

    # The installer needs web access. Since it does, let's download it w/o a
    # hash. We're using HTTPS anyway.
    #
    # If you get an error referring to this, you're probably using a strict
    # sandbox.  Disable it, or set it to 'relaxed'.
    __noChroot = 1;
    buildInputs = [ jre wget cacert ];
  } ''
    mkdir $out
    cd $out
    wget $url --ca-certificate=${cacert}/etc/ssl/certs/ca-bundle.crt
    mkdir mods
    INSTALLER=$(echo *.jar)
    java -jar $INSTALLER --installServer
    rm -r $INSTALLER mods
  '';

  fetchManifests = { side, manifests }: symlinkJoin {
    name = "manifests";
    paths = map (fetchManifest side) manifests;
  };

  fetchManifest = side: manifest: let
    allMods = builtins.fromJSON (builtins.readFile manifest);
    mods = lib.filterAttrs (n: mod: (mod.side or side) == side) allMods;
    modFile = name: mod: {
      name = mod.filename;
      path = fetchMod mod;
    };
    modFiles = linkFarm "manifest-mods" (lib.mapAttrsToList modFile mods);
  in
    runCommand "manifest" { inherit modFiles; } "mkdir -p $out/mods; ln -s $modFiles/* $out/mods/";

  fetchMod = info: fetchurl {
    url = info.src;
    md5 = info.md5;
  };

  buildServerPack = packs: {
    # TODO
  };
}
