#! /bin/bash -e

cd "$( dirname "${BASH_SOURCE[0]}" )"
cd "`git rev-parse --show-toplevel`"

# Whitelist files to ship (AKA, don't put random certs + config in dist)
files=(`git ls-files`)
files+=("bin")
files+=("code")
files+=(`ls containers/*.tar*`)

# Don't create a tarbomb
rm -f release.tar
if [ "$(uname)" == "Darwin" ]; then
    tar -s ',^,scitran/,' -cf release.tar ${files[@]}
else
    tar --transform 's,^,scitran/,rSh' -cf release.tar ${files[@]}
fi
