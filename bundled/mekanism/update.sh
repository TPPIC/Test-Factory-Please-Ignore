#!/usr/bin/env bash

set -eu

cd $(dirname $(readlink -f "$0"))

git clone https://github.com/aidancbrady/Mekanism.git
cd Mekanism
gradle build
cp output/*.jar ..
rm -rf Mekanism
