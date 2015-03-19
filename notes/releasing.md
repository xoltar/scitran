# Releasing

A new release.tar can be created using `scitran/scripts/make-release.sh`. `make-release.sh` will generate
a file whitelist to limit what files are included into the release.  The file whitelist exists to
prevent ssl keys/certificates, configurations, and other sensitive information from accidentally being included.

If a new file/directory is not being included in the release.tar, then the file/directory is not
being added to the whitelist.  This could by caused by `.gitignore`.  Or `make-release.sh` does not contain
a whitelist rule that includes the file/directory.

Currently, the `make-release.sh` script depends on using GNU tar.  OSX `tar` is BSD tar, which does not support
the `--transform` option.  This requires developers on OSX to install gnutar, which is available for OSX via
macports, homebrew, or as source.


# Uploading

After running `scitran/scripts/make-release.sh`, the new release.tar needs to be made publicly available for download.
Currently, this involves uploading release-v.tar (e.g. release-0.2.1.tar), and then overwriting the existing release.tar.
The versioned release files (e.g. release-0.2.1.tar) keep a record of previous releases, while release.tar should always
represent the latest release.
