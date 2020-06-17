#!/usr/bin/bash
set -xe

# Build Santoku
cd projects/santoku
git pull
yarn
yarn build
cd ../..
rm -rf ./santoku/*
cp ./projects/santoku/dist/* ./santoku/ -r
