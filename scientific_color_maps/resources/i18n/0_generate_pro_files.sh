#!/usr/bin/bash
# -*- encoding: UTF-8 -*-
DIRECTORY=../..
PREFIX="plugin_translation"
I18N_LIST="ar es fr pt ru zh it gr"
FORMS="FORMS = "
SOURCES="SOURCES = "
TRANSLATIONS="TRANSLATIONS = "
for f in $DIRECTORY/resources/gui/*.gui; do
    FORMS="${FORMS} ${f}"
done
for f in $DIRECTORY/*.py; do
    echo $f
    if [[ "${f}" != "../__init__.py" ]] && [[ "${f}" != "../resources.py" ]]; then
        SOURCES="${SOURCES} ${f}"
    fi
done
for f in $DIRECTORY/gui/*.py; do
    echo $f
    if [[ "${f}" != "../__init__.py" ]] && [[ "${f}" != "../resources.py" ]]; then
        echo "2- ${f}"
        SOURCES="${SOURCES} ${f}"
    fi
done
for e in $I18N_LIST; do    
    TRANSLATIONS="${TRANSLATIONS} ${PREFIX}_${e}.ts"
done  
echo $FORMS >"${PREFIX}.pro"
echo $SOURCES >>"${PREFIX}.pro"
echo $TRANSLATIONS >>"${PREFIX}.pro"
echo ${SOURCES}
