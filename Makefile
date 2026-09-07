.PHONY: build up down logs migrate migrations check test lint shell superuser prepare-map sync-cnae

build:
	docker compose build

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f web

migrate:
	docker compose run --rm web python manage.py migrate

migrations:
	docker compose run --rm web python manage.py makemigrations

check:
	docker compose run --rm web python manage.py check

test:
	docker compose run --rm web python manage.py test

lint:
	uv run ruff check .
	uv run ruff format --check .

shell:
	docker compose run --rm web python manage.py shell

superuser:
	docker compose run --rm web python manage.py createsuperuser

sync-cnae:
	docker compose run --rm web python manage.py sync_cnae_catalog

prepare-map:
	docker compose run --rm web python manage.py prepare_cartographic_projection \
		/app/var/data/cartography/cnefe-2022 \
		--download-missing-boundaries
