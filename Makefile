PLUGINNAME = scientific_color_maps
VERSION = $(shell sed -n 's/^version=//p' $(PLUGINNAME)/metadata.txt)
ZIPFILE = $(PLUGINNAME).$(VERSION).zip

# GitHub release settings
GITHUB_REPO = sylsta/scientific-colour-maps
GITHUB_URL = https://github.com/$(GITHUB_REPO).git
RELEASE_BRANCH = main
TAG = $(VERSION)

.PHONY: help pylint pep8 flake zip release-check release

help:
	@echo "Please use \`make <target>' where <target> is one of"
	@echo "  pep8           check Python code with pycodestyle (formerly pep8)"
	@echo "  pylint         check Python code with pylint"
	@echo "  flake          check Python code with flake8"
	@echo "  zip            build zip package"
	@echo "  release-check  check that version $(VERSION) can be released (changes nothing)"
	@echo "  release        tag version $(VERSION) and publish the zip as a GitHub release"


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


# -- Release --------------------------------------------------------------
# GitHub is a mirror of GitLab (`git push --mirror` in .gitlab-ci.yml), which
# deletes any GitHub ref that GitLab does not have. So the tag is created and
# pushed to GitLab (origin) first, then the GitHub release is created on the
# same commit: the next mirror sync finds an identical tag and keeps it.
# Requires the GitHub CLI (https://cli.github.com), logged in: `gh auth login`.

release-check:
	@test -n "$(VERSION)" || { echo "ERROR: no version= line in $(PLUGINNAME)/metadata.txt"; exit 1; }
	@command -v gh >/dev/null || { echo "ERROR: GitHub CLI (gh) not found, see https://cli.github.com"; exit 1; }
	@gh auth status >/dev/null 2>&1 || { echo "ERROR: gh is not logged in, run: gh auth login"; exit 1; }
	@test "$$(git rev-parse --abbrev-ref HEAD)" = "$(RELEASE_BRANCH)" || { echo "ERROR: not on branch $(RELEASE_BRANCH)"; exit 1; }
	@test -z "$$(git status --porcelain)" || { echo "ERROR: uncommitted or untracked files, commit or remove them first:"; git status --short; exit 1; }
	@git fetch --quiet origin $(RELEASE_BRANCH)
	@test "$$(git rev-parse HEAD)" = "$$(git rev-parse origin/$(RELEASE_BRANCH))" || { echo "ERROR: local $(RELEASE_BRANCH) differs from origin, pull or push first"; exit 1; }
	@test "$$(git ls-remote $(GITHUB_URL) refs/heads/$(RELEASE_BRANCH) | cut -f1)" = "$$(git rev-parse HEAD)" || { echo "ERROR: GitHub mirror is not up to date yet, wait for the GitLab sync job and retry"; exit 1; }
	@if git rev-parse -q --verify "refs/tags/$(TAG)" >/dev/null; then \
		test "$$(git rev-list -n 1 $(TAG))" = "$$(git rev-parse HEAD)" || { echo "ERROR: tag $(TAG) already exists on another commit, bump version= in metadata.txt"; exit 1; }; \
	fi
	@! gh release view "$(TAG)" --repo $(GITHUB_REPO) >/dev/null 2>&1 || { echo "ERROR: GitHub release $(TAG) already exists, bump version= in metadata.txt"; exit 1; }
	@echo "OK: version $(TAG) ($$(git rev-parse --short HEAD)) can be released to $(GITHUB_REPO)"


release: release-check zip
	@# tag on GitLab first (lightweight tag = same ref value as the one GitHub creates)
	@git rev-parse -q --verify "refs/tags/$(TAG)" >/dev/null || git tag "$(TAG)"
	git push origin "refs/tags/$(TAG)"
	@# release notes = the "$(VERSION) (...)" entry of changelog= in metadata.txt
	@notes=$$(mktemp); \
	awk -v v="$(VERSION)" ' \
		/^changelog=/ { c = 1; next } \
		c && /^[^ \t]/ { c = 0 } \
		c && index($$0, "    " v " ") == 1 { p = 1; next } \
		p && /^    [^ \t]/ { p = 0 } \
		p { sub(/^[ \t]+/, ""); print } \
	' $(PLUGINNAME)/metadata.txt > "$$notes"; \
	if [ -s "$$notes" ]; then notes_opt="--notes-file $$notes"; else notes_opt="--generate-notes"; fi; \
	echo "Creating GitHub release $(TAG) with $(ZIPFILE)"; \
	gh release create "$(TAG)" "$(ZIPFILE)" --repo $(GITHUB_REPO) --target "$$(git rev-parse HEAD)" --title "$(TAG)" $$notes_opt; \
	status=$$?; rm -f "$$notes"; exit $$status
	@echo "Released: https://github.com/$(GITHUB_REPO)/releases/tag/$(TAG)"
