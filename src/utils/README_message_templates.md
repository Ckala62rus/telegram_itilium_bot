# Шаблоны сообщений

Модуль `message_templates.py` предоставляет централизованное управление текстами сообщений в боте.

## Структура

### MessageTemplates
Enum с константами для всех текстов сообщений, разделенных по категориям:
- Общие сообщения
- Сообщения о заявках
- Сообщения о согласовании
- Сообщения о загрузке
- Сообщения о пользователях
- Сообщения о меню
- Сообщения об оценке
- Сообщения админа
- Кнопки

### ButtonTemplates
Класс со статическими методами для создания словарей кнопок:
- `hide_info()` - кнопка "Скрыть информацию"
- `hide_and_change_status(sc_number)` - кнопки "Скрыть" и "Поменять статус"
- `cancel()` - кнопка "Отмена"
- `grade_actions()` - кнопки для оценки заявки

### MessageFormatter
Класс для форматирования сообщений с подстановкой переменных:
- `format(template, **kwargs)` - общий метод форматирования
- Специализированные методы для конкретных случаев

## Использование

### Простые сообщения
```python
from utils.message_templates import MessageTemplates

await message.answer(MessageTemplates.ACTIONS_CANCELED)
```

### Сообщения с переменными
```python
from utils.message_templates import MessageFormatter

# Используя специализированный метод
await message.answer(MessageFormatter.issue_not_found("0000012345"))

# Или напрямую
await message.answer(MessageFormatter.format(
    MessageTemplates.ISSUE_NOT_FOUND, 
    sc_number="0000012345"
))
```

### Кнопки
```python
from utils.message_templates import ButtonTemplates

# Простая кнопка отмены
reply_markup=get_callback_btns(btns=ButtonTemplates.cancel())

# Кнопки для оценки
reply_markup=get_callback_btns(btns=ButtonTemplates.grade_actions())
```

## Преимущества

1. **Централизация** - все тексты в одном месте
2. **Консистентность** - одинаковые сообщения везде
3. **Легкость изменений** - изменить текст в одном месте
4. **Типизация** - IDE подсказывает доступные шаблоны
5. **Многоязычность** - легко добавить поддержку других языков
6. **Безопасность** - защита от KeyError при форматировании

## Добавление новых шаблонов

1. Добавьте константу в `MessageTemplates`
2. Если нужны переменные, добавьте метод в `MessageFormatter`
3. Если нужны кнопки, добавьте метод в `ButtonTemplates`
4. Обновите документацию

## Примеры миграции

### Было:
```python
await message.answer("Действия отменены")
await callback.answer("Во время согласования, произошла ошибка. Обратитесь к администратору")
```

### Стало:
```python
await message.answer(MessageTemplates.ACTIONS_CANCELED)
await callback.answer(MessageTemplates.AGREEMENT_ERROR)
``` 