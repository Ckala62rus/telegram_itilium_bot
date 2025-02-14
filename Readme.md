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

### download all packages for local install 
pip download -d vendor -r requirements.txt

### Install all packages localhost from folder
pip install /opt/project/src/vendor/*.whl


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
