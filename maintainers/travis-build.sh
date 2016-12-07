#! /usr/bin/env bash

set -e

export NIX_CURL_FLAGS=-sS

if [[ $1 == nix ]]; then
    echo "=== Installing Nix..."
    # Install Nix
    bash <(curl -sS https://nixos.org/nix/install)
    source $HOME/.nix-profile/etc/profile.d/nix.sh

    # Make sure we can use hydra's binary cache
    sudo mkdir /etc/nix
    sudo sh -c 'echo "build-max-jobs = 4" > /etc/nix/nix.conf'

    # Verify evaluation
    echo "=== Verifying that nixpkgs evaluates..."
    nix-env -qa --json >/dev/null
elif [[ $1 == build ]]; then
    source $HOME/.nix-profile/etc/profile.d/nix.sh

    if [[ $TRAVIS_OS_NAME == "osx" ]]; then
        echo "Skipping NixOS things on darwin"
    else
        # Nix builds in /tmp and we need exec support
        sudo mount -o remount,exec /run
        sudo mount -o remount,exec /run/user
        sudo mount

        echo "=== Checking all builds ==="
        nix-build
    fi
else
    echo "$0: Unknown option $1" >&2
    false
fi
