# Makefile for Hugo project

HUGO ?= hugo
THEME ?= themes/terminal
PUBLIC_DIR ?= public
STATIC_DIR ?= static
POSTS_DIR ?= content/posts

.DEFAULT_GOAL := help

.PHONY: help serve serve-drafts build build-drafts check-positioning check-alt-text check-build check-built-meta clean new update-theme submodules cv cv-pdf books

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"}; /^[a-zA-Z0-9_.-]+:.*?##/ {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dev: ## Run server (drafts+future). For remote access set HOST=<lan-ip>, e.g. make dev HOST=192.168.1.50
	$(HUGO) server -D -F --bind 0.0.0.0 --disableFastRender --ignoreCache --gc --noHTTPCache $(if $(HOST),--baseURL http://$(HOST))

build: check-positioning check-alt-text ## Build production site into $(PUBLIC_DIR), then check the output and its metadata
	$(HUGO) --cleanDestinationDir
	$(MAKE) --no-print-directory check-build
	$(MAKE) --no-print-directory check-built-meta

build-drafts: ## Build site including drafts and future posts
	$(HUGO) -D -F

clean: ## Remove generated site
	rm -rf $(PUBLIC_DIR)

new: ## Create a new post: make new POST="My Post Title"
	@if [ -z "$(POST)" ]; then \
		echo "Usage: make new POST=\"My Post Title\""; \
		exit 1; \
	fi; \
	slug=$$(echo "$(POST)" | tr ' ' '-' | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9-]+//g'); \
	$(HUGO) new posts/$${slug}/index.md; \
	echo "Created $(POSTS_DIR)/$${slug}/index.md"

update-theme: ## Update theme submodule to latest
	git submodule update --init --recursive
	git submodule update --remote --merge --recursive $(THEME)

submodules: ## Initialize and update all submodules
	git submodule update --init --recursive

check-positioning: ## Assert the identity copy leads builder-first, llms.txt still matches the pages, and descriptions fit in 160 characters
	python3 scripts/check_positioning.py

check-build: ## Assert the built site: posts-only feed, no taxonomies, no cv.css, profile links from data
	python3 scripts/check_build.py --public $(PUBLIC_DIR)

check-alt-text: ## Fail if an image has placeholder alt text ("Untitled", "image 2", "alt text", or a filename)
	@if grep -rniE '!\[((untitled|image|alt text)([ _-]?[0-9]+)?|[^]]*\.(png|jpe?g|gif|webp|svg))\]\(' content; then \
		echo "check-alt-text: placeholder alt text found above; describe the image instead (or use ![] if decorative)"; \
		exit 1; \
	fi; \
	echo "check-alt-text: no placeholder alt text"

check-built-meta: ## Assert the built site's search and social metadata (run after a build)
	python3 scripts/check_built_meta.py $(PUBLIC_DIR)

cv: ## Generate CV as HTML into static/ (served by Hugo at /cv.html)
	python3 scripts/generate_cv.py -o $(STATIC_DIR)/cv.html

cv-pdf: cv ## Generate CV as PDF into static/ (served by Hugo at /cv.pdf)
	@CHROME=$$(command -v chromium || command -v google-chrome) || { echo "cv-pdf: need chromium or google-chrome on PATH" >&2; exit 1; }; \
	rm -f $(STATIC_DIR)/cv.pdf; \
	"$$CHROME" --headless --disable-gpu --print-to-pdf=$(STATIC_DIR)/cv.pdf --no-margins --no-pdf-header-footer $(STATIC_DIR)/cv.html || exit 1; \
	test -s $(STATIC_DIR)/cv.pdf || { echo "cv-pdf: $(STATIC_DIR)/cv.pdf was not produced" >&2; exit 1; }; \
	echo "PDF written to $(STATIC_DIR)/cv.pdf"

books: ## Refresh the About page Books list: top 10 from Goodreads + existing, by rating/popularity. ARGS="--top 12" etc.
	python3 scripts/update_books.py $(ARGS)
