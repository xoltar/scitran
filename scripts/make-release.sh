#! /bin/bash -e

cd "$( dirname "${BASH_SOURCE[0]}" )"
cd "`git rev-parse --show-toplevel`"

# Whitelist files to ship (AKA, don't put random certs + config in dist)
files=(`git ls-files`)
files+=("bin")
files+=("code")
files+=(`ls containers/*.tar*`)

rm -f release.tar
tar -cf release.tar ${files[@]}
