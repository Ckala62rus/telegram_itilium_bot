#### Python 3.12.2

### Poetry
```Bash
# Создание requirements.txt экспорта зависимостей без хэшей
poetry export --without-hashes -f requirements.txt --output requirements.txt  

# или аналогичная команда
poetry export --without-hashes --format=requirements.txt > requirements.txt
```

### Delete all in docker
docker system prune -af
