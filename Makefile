PLUGINNAME = scientific_color_maps
VERSION = $(shell sed -n 's/version=//p' $(PLUGINNAME)/metadata.txt)
ZIPFILE = $(PLUGINNAME).$(VERSION).zip
.PHONY: help pylint pep8 flake zip

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  pep8        check Python code with pycodestyle (formerly pep8)"
	@echo "  pylint      check Python code with pylint"
	@echo "  flake       check Python code with flake8"
	@echo "  zip         build zip package"


pep8:
	@pycodestyle --max-line-length=100 $(PLUGINNAME)


pylint:
	@pylint --disable=C0103,C0415,E0401,R0903,W0201 $(PLUGINNAME)


flake:
	@flake8 $(PLUGINNAME)


zip:
	rm -f ${ZIPFILE}
	zip -9r $(ZIPFILE) $(PLUGINNAME)/* -x "*.git/*" "*.idea/*" "*.gitignore" "*pyc" "*__pycache__/*" "*doc/*" "*config/custom.ini" "*resources.qrc" "*Makefile" "*symbology-style.db" "*user-history.db" "*i18n/*.sh" "*stats/*" "*i18n/*.sh"
	@echo "Successfully zipped to" $(ZIPFILE)
