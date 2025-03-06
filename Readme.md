#### Python 3.12.2

### Poetry
```Bash
# Создание requirements.txt экспорта зависимостей без хэшей
poetry export --without-hashes -f requirements.txt --output requirements.txt  

# или аналогичная команда
poetry export --without-hashes --format=requirements_dev.txt > requirements_dev.txt
```

### Delete all in docker
```bash
docker system prune -af
```

### download all packages for local install 
```bash
pip download -d vendor -r requirements.txt
```

### Install all packages localhost from folder
```bash
pip install --no-index --find-links /vendor -r requirements.txt
```
- (install wheel package) https://stackoverflow.com/questions/51748058/all-dependencies-are-not-downloaded-with-pip-download


###
main url
https://api.telegram.org/file/bot<token>/<file_path>

1) save photo
https://api.telegram.org/file/bot<token>/photos/file.jpg

2) save document
https://api.telegram.org/file/bot<token>/documents/document.exe

3) save video
https://api.telegram.org/file/bot<token>/videos/video.mp4

4) save voice
https://api.telegram.org/file/bot<token>/voice/voice.oga

#### Build prod release
```bash
docker compose -f docker-compose_prod.yaml build

или с очисткой кеша

docker compose -f docker-compose_prod.yaml build --no-cache
```

#### Create new version prod image
```bash
docker image tag ckala62rus/backend_telegram_bot_itilium_prod:latest ckala62rus/backend_telegram_bot_itilium_prod:1.0.0
```

#### Push new images to DockerHub
```bash
docker image push ckala62rus/backend_telegram_bot_itilium_prod:1.0.0
```
