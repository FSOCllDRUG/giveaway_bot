# Giveaway Bot

Giveaway Bot — это Telegram-бот для проведения розыгрышей и управления участниками. Проект написан на Python с использованием модульной архитектуры и полностью контейнеризирован с помощью Docker.

## Основные возможности

- **Управление розыгрышами**: создание и проведение розыгрышей с автоматическим выбором победителей.
- **Гибкая настройка**: все параметры (токен бота, настройки БД, Redis и т.д.) задаются в файле окружения `.env`.
- **Модульная архитектура**: разделение логики на независимые модули (handlers, filters, keyboards, loggers, middlewares и др.) упрощает поддержку и расширение функционала.
- **Поддержка БД и кэширования**: использование PostgreSQL (с миграциями через Alembic) и Redis.
- **Docker**: проект полностью готов к работе в контейнерах.
- **CI/CD**: автоматическая сборка Docker-образа происходит благодаря GitHub Actions.
- **Лицензия**: проект распространяется под [MIT License](./LICENSE).

## Установка и запуск с Docker Compose

### 1. Клонирование репозитория
```
git clone https://github.com/FSOCllDRUG/giveaway_bot.git
cd giveaway_bot
```
### 2. Настройка файла окружения

Скопируйте файл `example.env` в `.env` и замените все логины, пароли и адреса на свои значения:
```
cp example.env .env
```
Пример структуры `.env` (значения замените на собственные):
```
# Telegram API
BOT_TOKEN=<YOUR_TELEGRAM_BOT_TOKEN>

# Logs channel
LOGS_CHANNEL_ID=<YOUR_LOGS_CHANNEL_ID>

# Admins
ADMINS=<ADMIN_ID_1>,<ADMIN_ID_2>,<ADMIN_ID_3>

# PostgreSQL
DB_USER=<YOUR_DB_USER>
DB_PASSWORD=<YOUR_DB_PASSWORD>
DB_NAME=<YOUR_DB_NAME>
DB_URL=postgresql+asyncpg://<YOUR_DB_USER>:<YOUR_DB_PASSWORD>@postgres:5432/<YOUR_DB_NAME>

# Redis
REDIS_PASSWORD=<YOUR_REDIS_PASSWORD>
REDIS_URL=redis://:<YOUR_REDIS_PASSWORD>@redis:6379/0
```
### 3. Запуск с Docker Compose
```
docker-compose up -d
```
- Контейнер `postgres` запускает PostgreSQL.
- Контейнер `redis` запускает Redis.
- Контейнер `giveaway_bot` запускает Telegram-бота.

Проверьте логи, чтобы убедиться, что бот запустился успешно:
```
docker-compose logs -f giveaway_bot
```
## Автоматическая сборка Docker-образа

GitHub Actions настроен для автоматической сборки Docker-образа при каждом коммите в репозиторий. При корректной настройке CI/CD изменения будут автоматически применяться в контейнерном образе.

## Запуск локально (без Docker)

1. Установите Python 3.13.
2. Создайте виртуальное окружение:
```
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
```
3. Установите зависимости:
```
   pip install -r requirements.txt
```
4. Настройте файл `.env`.
5. Запустите бота:
```
   python run.py
```
## Внесение вклада

Мы приветствуем любые предложения и помощь в развитии проекта! Если вы обнаружили ошибку или хотите предложить улучшения:
1. Создайте issue: https://github.com/FSOCllDRUG/giveaway_bot/issues
2. Отправьте Pull Request с вашими изменениями.

## Лицензия

Проект распространяется под лицензией [MIT](./LICENSE).

---

Спасибо за интерес к проекту Giveaway Bot! Если у вас есть вопросы или предложения, создавайте issue или открывайте Pull Request.
