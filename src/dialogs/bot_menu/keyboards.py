import operator

from aiogram_dialog.widgets.kbd import ScrollingGroup, Select
from aiogram_dialog.widgets.text import Format

SCROLLING_HEIGHT = 6

def paginated_categories(on_click):
    return ScrollingGroup(
        Select(
            Format('{item[0]} ({pos}/{data[count]})'),
            id='s_scroll_categories',
            item_id_getter=operator.itemgetter(1),
            items='categories',
            on_click=on_click,
        ),
        id='categories_ids',
        width=1,
        height=SCROLLING_HEIGHT,
    )
