from typing import List, Optional
from psycopg2.extensions import connection
from psycopg2.extras import DictCursor

from models import User, Post, Feed


def get_user(conn: connection, user_id: int) -> Optional[User]:
    """
    Загружает одного пользователя из базы данных по его Id.

    Возвращает объект User, если пользователь найден.
    Если пользователь с таким id отсутствует — возвращает None.
    """
    query = (f"SELECT *"
             "FROM public.user "
             f"WHERE id = %s")

    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, (user_id,))
        row = cur.fetchone()
        #Преобразовать результат в объект User, если строка найдена
        if row is None:
            return None
        else:
            return User(**row)

def get_post(conn: connection, post_id: int) -> Optional[Post]:
    """
    Загружает один пост из базы данных по его Id.

    Возвращает объект Post, если пост найден.
    Если пост с таким id отсутствует — возвращает None.
    """
    query = (f"SELECT *"
             "FROM public.post "
             f"WHERE id = %s")


    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, (post_id,))
        row = cur.fetchone()

        #Преобразовать результат в объект Post, если строка найдена

        if row is None:
            return None
        else:
            return Post(**row)

def get_feed(conn: connection, user_id: int = None, post_id: int = None, limit: int = 10) -> List[Feed]:
    """
    Получает список действий пользователей с постами, включая данные о пользователях и постах.

    - Необходимо указать хотя бы один фильтр: user_id или post_id.
    - Возвращает не более `limit` записей.
    - Действия сортируются по времени: от самых свежих к более старым.
    - Используется для получения последних активностей пользователя или взаимодействий с постом.
    """
    if user_id is None and post_id is None:
        raise ValueError("Необходимо указать хотя бы user_id или post_id")

    query = (f"SELECT public.post.id AS post_id, * "
             "FROM public.feed_action "
             "JOIN public.user on public.feed_action.user_id = public.user.id "
             "JOIN public.post on public.feed_action.post_id = public.post.id "
             f"WHERE user_id = %s "
             f"ORDER BY public.feed_action.time DESC "
             f"LIMIT %s;")

    result = []
    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, (user_id, limit))
        rows = cur.fetchall()

        for row in rows:
            user = User(**{key: row[key] for key in User.__annotations__ if key in row})
            post = Post(**{key: row[key] for key in Post.__annotations__ if key in row})
            feed = {key: row[key] for key in Feed.__annotations__ if key in row}
            feed['user'] = user
            feed['post'] = post
            result.append(Feed(**feed))


        #обработка post_id
        query = (f"SELECT public.post.id AS post_id, * "
             "FROM public.feed_action "
             "JOIN public.user on public.feed_action.user_id = public.user.id "
             "JOIN public.post on public.feed_action.post_id = public.post.id "
             f"WHERE post_id = %s "
             f"ORDER BY public.feed_action.time DESC "
             f"LIMIT %s;")

        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(query, (post_id, limit))
            rows = cur.fetchall()

        for row in rows:
            user = User(**{key: row[key] for key in User.__annotations__ if key in row})
            post = Post(**{key: row[key] for key in Post.__annotations__ if key in row})
            feed = {key: row[key] for key in Feed.__annotations__ if key in row}
            feed['user'] = user
            feed['post'] = post
            result.append(Feed(**feed))

    return result

def get_recommended_feed(conn: connection, id: int, limit: int) -> List[Post]:
    """
    Возвращает список top-N постов с наибольшим числом лайков.

    Это базовая реализация рекомендательной системы (baseline),
    которая не учитывает индивидуальные предпочтения, а показывает
    одинаковые популярные посты всем пользователям.

    Параметры:
        conn (connection): подключение к базе данных.
        id (int): ID пользователя (в этой версии не используется,
                  но оставлен для совместимости с будущей логикой).
        limit (int): количество постов в выдаче.

    Возвращает:
        List[Post]: список объектов Post, отсортированных по убыванию популярности.
    """
    query = (f"SELECT fa.post_id AS id, p.topic, p.text "
    f"FROM ( "
    f"    SELECT public.feed_action.post_id, "
    f"           COUNT(public.feed_action.user_id) AS likes "
    f"    FROM public.feed_action "
    f"    WHERE action = 'like' "
    f"    GROUP BY public.feed_action.post_id "
    f"    ORDER BY likes DESC "
    f"    LIMIT %s "
    f") fa "
    f"JOIN public.post p ON fa.post_id = p.id;")



    with conn.cursor(cursor_factory=DictCursor) as cur:
        cur.execute(query, (limit,))
        rows = cur.fetchall()
        result = []
        for row in rows:
            result.append(Post(**row))
        return result