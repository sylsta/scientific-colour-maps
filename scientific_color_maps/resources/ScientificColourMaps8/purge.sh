#!/bin/bash

# Chemin vers le répertoire racine à traiter
REPERTOIRE_RACINE="."

# Supprimer les fichiers non conformes
find "$REPERTOIRE_RACINE" -type f \( \
    ! -iname "*.pdf" -a \
    ! -iname "*.svg" -a \
    ! -iname "*.txt" -a \
    ! -iname "*.sh" -a \
    ! -iname "*QGIS.xml" \) -exec rm -v {} \;

# Supprimer uniquement les répertoires vides
find "$REPERTOIRE_RACINE" -type d -empty -exec rmdir -v {} \;
