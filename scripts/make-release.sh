#! /bin/bash -e

tar=tar
if [ "$(uname)" == "Darwin" ]; then
    gnutar --version >/dev/null 2>&1
    if [ $? != 0 ]; then
        printf "\nOSX bsdtar is not compatible with this operation."
        printf "\ngnutar is required. aborting...\n"
        exit 1
    else
        tar=gnutar
    fi
fi

cd "$( dirname "${BASH_SOURCE[0]}" )"
cd "`git rev-parse --show-toplevel`"

# Whitelist files to ship (AKA, don't put random certs + config in dist)
files=(`git ls-files`)
files+=("bin")
files+=("code")
files+=(`ls containers/*.tar*`)

# Don't create a tarbomb
rm -f release.tar
$tar --transform 'flags=rSh;s,^,scitran/,' -cf release.tar ${files[@]}
