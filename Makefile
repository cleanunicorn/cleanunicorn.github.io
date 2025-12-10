# Makefile for Hugo project

HUGO ?= hugo
THEME ?= themes/terminal
PUBLIC_DIR ?= public
POSTS_DIR ?= content/posts
DATE := $(shell date +"%Y-%m-%dT%H:%M:%S%z")

.DEFAULT_GOAL := help

.PHONY: help serve serve-drafts build build-drafts clean new update-theme submodules

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"}; /^[a-zA-Z0-9_.-]+:.*?##/ {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

serve: ## Run local dev server
	$(HUGO) server -D --disableFastRender

serve-drafts: ## Run server including drafts and future posts
	$(HUGO) server -D -F --disableFastRender

build: ## Build production site into $(PUBLIC_DIR)
	$(HUGO)

build-drafts: ## Build site including drafts and future posts
	$(HUGO) -D -F

clean: ## Remove generated site
	rm -rf $(PUBLIC_DIR)

new: ## Create a new post: make new POST="My Post Title"
	@if [ -z "$(POST)" ]; then \
		echo "Usage: make new POST=\"My Post Title\""; \
		exit 1; \
	fi; \
	slug=$$(echo "$(POST)" | tr ' ' '-' | tr '[:upper:]' '[:lower:]'); \
	$(HUGO) new posts/$${slug}/index.md; \
	echo "Created $(POSTS_DIR)/$${slug}/index.md"

update-theme: ## Update theme submodule to latest
	git submodule update --init --recursive
	git submodule update --remote --merge --recursive $(THEME)

submodules: ## Initialize and update all submodules
	git submodule update --init --recursive
