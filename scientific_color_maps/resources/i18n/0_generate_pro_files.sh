#!/usr/bin/bash
# -*- encoding: UTF-8 -*-

# generate the translation profile (plugin_translation.pro) listing Python sources,
# Qt Designer forms (*.ui) and translation files (*.ts), with paths relative to
# this directory. Delegates to scripts/generate_translation_profile.py, which must
# be run from the repository root.

cd "$(dirname "$0")/../../.." && python3 scripts/generate_translation_profile.py
