#!/bin/bash
find . -type d -name .git -exec git -C "{}/.." pull \;
