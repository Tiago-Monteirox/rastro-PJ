.PHONY: build up down logs migrate migrations check test lint shell superuser

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
