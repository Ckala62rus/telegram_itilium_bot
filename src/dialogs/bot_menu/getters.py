from aiogram_dialog import DialogManager


async def get_categories(dialog_manager: DialogManager, **middleware_data):
    fruits = [
        ('яблоки', '1'),
        ('бананы', '2'),
    ]

    return {
        "categories": fruits,
        "count": len(fruits),
    }
