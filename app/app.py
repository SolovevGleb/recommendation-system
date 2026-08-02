from fastapi import FastAPI, HTTPException, Depends
import os
import pickle
from datetime import datetime
from typing import List, Dict, Any
import pandas as pd
from loguru import logger
import numpy as np
from database import postgres_connection
from helpers import get_user, get_post, get_feed
from schema import UserGet, PostGet, FeedGet

# Инициализация FastAPI-приложения — точка входа для всех маршрутов

app = FastAPI()
# Функция для создания и закрытия подключения к базе данных.
# Используется в Depends — FastAPI сам управляет подключением и закрытием.
def get_conn():
    """
        Создает подключение к PostgreSQL
        и закрывает его после выполнения запроса.
    """
    conn = postgres_connection()
    try:
        yield conn  # отдаём соединение в обработчик запроса
    finally:
        conn.close()  # закрываем соединение после завершения


@app.get("/user/{id}", response_model=UserGet)
def handle_get_user(id: int, conn=Depends(get_conn)) -> UserGet:
    """
    Получить информацию о пользователе по ID.

    Параметры:
        id (int): Уникальный идентификатор пользователя.

    Возвращает:
        UserGet: Данные пользователя в формате, пригодном для API.

    Исключения:
        HTTPException 404 — если пользователь с заданным ID не найден.
    """
    user = get_user(conn, id)
    if user == None:
        raise HTTPException(status_code=404, detail="User not found")
    else:
        return user


@app.get("/post/{id}", response_model=PostGet)
def handle_get_post(id: int, conn=Depends(get_conn)) -> PostGet:
    """
    Получить информацию о посте по его ID.

    Параметры:
        id (int): Уникальный идентификатор поста.

    Возвращает:
        PostGet: Информация о посте (текст и тема).

    Исключения:
        HTTPException 404 — если пост с заданным ID не найден.
    """
    post= get_post(conn, id)

    if post == None:
        raise HTTPException(status_code=404, detail="Post not found")
    else:
        return post


@app.get("/user/{id}/feed", response_model=List[FeedGet])
def handle_get_user_feed(
    id: int, limit: int = 10, conn=Depends(get_conn)
) -> List[FeedGet]:
    """
    Получить список действий пользователя (лайки, просмотры) по его ID.

    Параметры:
        id (int): Идентификатор пользователя.
        limit (int): Максимальное количество действий в ответе (по умолчанию 10).

    Возвращает:
        List[FeedGet]: Список действий, отсортированных от новых к старым.
    """
    return get_feed(conn, user_id = id, limit = limit)


@app.get("/post/{id}/feed", response_model=List[FeedGet])
def handle_get_post_feed(
    id: int, limit: int = 10, conn=Depends(get_conn)
) -> List[FeedGet]:
    """
    Получить список действий пользователей с заданным постом.

    Параметры:
        id (int): Идентификатор поста.
        limit (int): Максимальное количество действий (по умолчанию 10).

    Возвращает:
        List[FeedGet]: Список действий пользователей с этим постом,
        отсортированный от новых к старым.
    """
    return get_feed(conn, post_id= id, limit = limit)

# === Вспомогательные функции ===
def load_sql(query: str, dtypes: Dict[str, Any] = None) -> pd.DataFrame:
    """
    Выполняет SQL-запрос через соединение postgres_connection и возвращает DataFrame.

    Аргументы:
        query: SQL-запрос
        dtypes: словарь типов колонок для pd.read_sql (по умолчанию None)

    Возвращает:
        pd.DataFrame с результатом запроса

    Исключения:
        RuntimeError, если произошла ошибка при выполнении запроса
    """
    conn = postgres_connection()

    try:
        df = pd.read_sql(query, conn, dtype=dtypes)
    except Exception as e:
        raise RuntimeError(
            f"❌ Ошибка при выполнении SQL-запроса: {e}\nЗапрос: {query}"
        ) from e
    finally:
        conn.close()

    return df


def load_model(model_path: str = "model.pkl"):
    """
    Загружает ML-модель из pickle-файла.

    Если код запускается в LMS-окружении (IS_LMS=1),
    путь берётся из переменной окружения MODEL_PATH.
    Иначе используется локальный путь, переданный пользователем.

    Исключения:
        FileNotFoundError — если файл модели не найден.
        RuntimeError — если произошла ошибка при загрузке модели.
    """
    if os.environ.get("IS_LMS", "0") == "1":
        model_path = os.environ["MODEL_PATH"]

    logger.info(f"Загрузка модели из файла {model_path}...")

    try:
        with open(model_path, "rb") as file:
            model = pickle.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ Файл модели не найден: {model_path}")
    except Exception as e:
        raise RuntimeError(f"❌ Ошибка при загрузке модели: {e}") from e

    logger.success("Модель успешно загружена")

    return model


# === Загрузка основных ресурсов ===
logger.info("Инициализация сервиса...")


# Загружаем модель в память
model = load_model()

#загрузка сохранённых признаков пользователей из БД
query_user = """
SELECT * 
FROM public."gleb-solovev-jkh9964_user_features";
 """

dtypes_user = {'user_id': 'int64',
                 'gender': 'int64',
                 'age': 'int64',
                 'views': 'float64',
                 'total_likes': 'float64',
                 'share_likes_views': 'float64',
                 'share_likes_time_afternoon': 'float64',
                 'share_likes_time_evening': 'float64',
                 'share_likes_time_morning': 'float64',
                 'city_encoded': 'float64',
                 'country_Belarus': 'bool',
                 'country_Cyprus': 'bool',
                 'country_Estonia': 'bool',
                 'country_Finland': 'bool',
                 'country_Kazakhstan': 'bool',
                 'country_Latvia': 'bool',
                 'country_Russia': 'bool',
                 'country_Switzerland': 'bool',
                 'country_Turkey': 'bool',
                 'country_Ukraine': 'bool',
                 'exp_group_1': 'bool',
                 'exp_group_2': 'bool',
                 'exp_group_3': 'bool',
                 'exp_group_4': 'bool',
                 'os_iOS': 'bool',
                 'source_organic': 'bool',
                 'fav_category_likes_covid': 'bool',
                 'fav_category_likes_entertainment': 'bool',
                 'fav_category_likes_movie': 'bool',
                 'fav_category_likes_politics': 'bool',
                 'fav_category_likes_sport': 'bool',
                 'fav_category_likes_tech': 'bool'}

user_features = load_sql(query_user, dtypes_user)

dtypes_post = {'post_id': 'int64',
                 'count_likes_post': 'float64',
                 'count_views_post': 'float64',
                 'share_likes_views_post': 'float64',
                 'tfidf_mean': 'float64',
                 'tfidf_max': 'float64',
                 'tfidf_std': 'float64',
                 'long_text': 'int64',
                 'coun_word': 'int64',
                 'unique_count_word': 'int64',
                 'topic_covid': 'bool',
                 'topic_entertainment': 'bool',
                 'topic_movie': 'bool',
                 'topic_politics': 'bool',
                 'topic_sport': 'bool',
                 'topic_tech': 'bool'}
query_post = """
SELECT * 
FROM public."gleb-solovev-jkh9964_post_features";
"""

post_features = load_sql(query_post, dtypes_post)
logger.success("Сервис успешно инициализирован")

df_posts = load_sql("SELECT * FROM public.post_text_df;",{
   "post_id": "int64",
     "text": "string",
    "topic": "string"
 })

# Эндпойнт для получения рекомендаций
@app.get("/post/recommendations/", response_model=List[PostGet])
def recommended_posts(user_id: int, dt: datetime, limit: int = 10) -> List[PostGet]:
    """
    Возвращает персональную рекомендацию постов для пользователя.

    Модель оценивает вероятность взаимодействия пользователя
    с каждым постом и возвращает top-N постов с максимальным score.
    """

    # Формирование временных признаков
    # Используются циклические признаки, чтобы учитывать периодичность времени

    df_time = pd.DataFrame({
        "hour": [dt.hour],
        "week": [dt.weekday()],
        "month": [dt.month]
    })

    df_time['hour_sin'] = np.sin(2 * np.pi * df_time['hour'] / 24)
    df_time['hour_cos'] = np.cos(2 * np.pi * df_time['hour'] / 24)
    df_time['month_sin'] = np.sin(2 * np.pi * df_time['month'] / 12)
    df_time['month_cos'] = np.cos(2 * np.pi * df_time['month'] / 12)
    df_time['week_sin'] = np.sin(2 * np.pi * df_time['week'] / 7)
    df_time['week_cos'] = np.cos(2 * np.pi * df_time['week'] / 7)

    # Удаляем исходные временные признаки после преобразования
    df_time = df_time.drop(columns=["hour", "month", "week"])

    # Получаем признаки пользователя и убираем колонку user_id
    dt_user = user_features[user_features['user_id'] == user_id].drop(columns='user_id')

    # Объединяем временные признаки и признаки пользователя
    user_context  = pd.concat(
    [pd.DataFrame([df_time.iloc[0]] * len(dt_user)).reset_index(drop=True),
     dt_user.reset_index(drop=True)],
    axis=1)

    # Добавляем признаки пользователя к каждому посту
    copy_post = post_features.copy()
    copy_post = pd.concat(
        [pd.DataFrame([user_context.iloc[0]] * len(copy_post)).reset_index(drop=True),
         copy_post.reset_index(drop=True)],
        axis=1
    )

    # Сохраняем post_id и удаляем его из признаков модели
    post_ids = copy_post["post_id"].reset_index(drop=True)
    copy_post = copy_post.drop(columns=["post_id"])

    # Получаем вероятность взаимодействия пользователя с каждым постом
    scores = model.predict_proba(copy_post)[:, 1]

    # объединяем предсказания и post_id
    result = pd.DataFrame({
        "post_id": post_ids,
        "score": scores
    })
    result = result.sort_values(by='score', ascending=False)

    # Выбираем top-N постов с максимальной вероятностью взаимодействия
    post_ids = result.head(limit)["post_id"].tolist()

    # Получаем информацию о рекомендованных постах
    # и сохраняем порядок, определённый моделью по значению score
    filtered = df_posts[df_posts["post_id"].isin(post_ids)]

    # Восстанавливаем порядок постов согласно рейтингу модели
    filtered = filtered.set_index("post_id").loc[post_ids].reset_index()

    # Приводим название поля к формату API-схемы PostGet
    filtered = filtered.rename(columns={"post_id": "id"})


    # Формируем список объектов PostGet для ответа сервиса
    recs = [
        PostGet(**row) for row in filtered.to_dict("records")
     ]
    return recs