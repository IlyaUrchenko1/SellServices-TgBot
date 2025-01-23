import sqlite3
from typing import Optional, Tuple, Dict, Any, List, Union
import json
from datetime import datetime

class Database:
    def __init__(self, db_name="data/services.db"):
        try:
            self.connection = sqlite3.connect(db_name, check_same_thread=False)
            self.cursor = self.connection.cursor()
            self.create_tables()
        except sqlite3.Error as e:
            print(f"Ошибка подключения к базе данных: {e}")

    def create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE,
                username TEXT,
                number_phone TEXT,
                is_seller BOOLEAN DEFAULT 0,
                full_name TEXT,
                work_time_start TEXT DEFAULT '10:00',
                work_time_end TEXT DEFAULT '22:00',
                work_days TEXT DEFAULT '1,2,3,4,5,6,7'
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by_id TEXT,
                is_active BOOLEAN DEFAULT 1,
                required_fields TEXT NOT NULL DEFAULT '{
                    "photo": {"type": "image", "label": "Фотография услуги", "required": true, "description": "Загрузите фото, отражающее вашу услугу"},
                    "number_phone": {"type": "text", "label": "Номер телефона", "required": false, "description": "Укажите номер телефона для связи"},
                    "price": {"type": "number", "label": "Стоимость", "required": true, "description": "Укажите стоимость услуги в рублях"}
                }'
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                service_type_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                photo_id TEXT NOT NULL,
                city TEXT NOT NULL,
                district TEXT NOT NULL,
                street TEXT NOT NULL,
                house TEXT,
                number_phone TEXT NOT NULL,
                price INTEGER NOT NULL,
                custom_fields TEXT,
                status TEXT DEFAULT 'active',
                views INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (service_type_id) REFERENCES service_types(id)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK (type IN ('user', 'service')),
                creator_telegram_id TEXT NOT NULL,
                accused_telegram_id TEXT,
                accused_service_id INTEGER,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creator_telegram_id) REFERENCES users(telegram_id),
                FOREIGN KEY (accused_telegram_id) REFERENCES users(telegram_id), 
                FOREIGN KEY (accused_service_id) REFERENCES services(id)
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS banned_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK (type IN ('user', 'service')),
                admin_telegram_id TEXT NOT NULL,
                accused_telegram_id TEXT,
                accused_service_id INTEGER,
                ban_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ban_duration_hours INTEGER NOT NULL,
                is_permanent BOOLEAN DEFAULT 0,
                reason TEXT NOT NULL,
                FOREIGN KEY (admin_telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY (accused_telegram_id) REFERENCES users(telegram_id) ON DELETE CASCADE,
                FOREIGN KEY (accused_service_id) REFERENCES services(id) ON DELETE CASCADE
            )
        """)

        self.connection.commit()

    #region Методы для таблицы users

    def add_user(self, telegram_id: str, username: str, number_phone: Optional[str] = None, 
                 is_seller: bool = False, full_name: Optional[str] = None) -> Optional[int]:
        """Добавляет нового пользователя в базу данных
        Args:
            telegram_id: Telegram ID пользователя
            username: Username пользователя
            number_phone: Номер телефона (опционально)
            is_seller: Является ли продавцом
            full_name: Полное имя (опционально)
        Returns:
            ID созданного пользователя или None в случае ошибки
        """
        try:
            self.cursor.execute("""
                INSERT INTO users (telegram_id, username, number_phone, is_seller, full_name,
                                 work_time_start, work_time_end, work_days)
                VALUES (?, ?, ?, ?, ?, '10:00', '22:00', '1,2,3,4,5,6,7')
                RETURNING id
            """, (telegram_id, username, number_phone, int(is_seller), full_name))
            user_id = self.cursor.fetchone()[0]
            self.connection.commit()
            return user_id
        except sqlite3.IntegrityError:
            print(f"Пользователь с telegram_id {telegram_id} уже существует")
            return None
        except Exception as e:
            print(f"Ошибка при добавлении пользователя: {e}")
            return None

    def delete_user(self, user_id: int) -> bool:
        """Удаляет пользователя из базы данных
        Args:
            user_id: ID пользователя
        Returns:
            True если удаление успешно, False если произошла ошибка
        """
        try:
            self.cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Ошибка при удалении пользователя: {e}")
            return False

    def update_user(self, user_id: int, **kwargs) -> bool:
        """Обновляет данные пользователя
        Args:
            user_id: ID пользователя
            **kwargs: Поля для обновления (full_name, number_phone, work_time_start, 
                     work_time_end, work_days, is_seller)
        Returns:
            True если обновление успешно, False если произошла ошибка
        """
        valid_fields = {'full_name', 'number_phone', 'work_time_start', 
                       'work_time_end', 'work_days', 'is_seller'}
        updates = []
        params = []
        
        for field, value in kwargs.items():
            if field in valid_fields:
                updates.append(f"{field} = ?")
                params.append(value if field != 'is_seller' else int(value))
                
        if not updates:
            return False
            
        try:
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            self.cursor.execute(query, params)
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Ошибка при обновлении пользователя: {e}")
            return False

    def get_user(self, user_id: Optional[int] = None, telegram_id: Optional[str] = None, 
                 username: Optional[str] = None) -> Optional[Tuple]:
        """Получает информацию о пользователе
        Args:
            user_id: ID пользователя
            telegram_id: Telegram ID пользователя  
            username: Username пользователя
        Returns:
            Кортеж с данными пользователя или None
        """
        try:
            if user_id is not None:
                self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            elif telegram_id is not None:
                self.cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            elif username is not None:
                self.cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
            else:
                return None
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Ошибка при получении пользователя: {e}")
            return None

    def user_exists(self, user_id: Optional[int] = None, telegram_id: Optional[str] = None) -> bool:
        """Проверяет существование пользователя
        Args:
            user_id: ID пользователя
            telegram_id: Telegram ID пользователя
        Returns:
            True если пользователь существует, False если нет
        """
        return self.get_user(user_id, telegram_id) is not None

    def is_seller(self, user_id: Optional[int] = None, telegram_id: Optional[str] = None) -> bool:
        """Проверяет является ли пользователь продавцом
        Args:
            user_id: ID пользователя
            telegram_id: Telegram ID пользователя
        Returns:
            True если пользователь продавец, False если нет
        """
        user = self.get_user(user_id, telegram_id)
        return bool(user[4]) if user else False

    def set_is_seller(self, is_seller: bool, user_id: Optional[int] = None, 
                     telegram_id: Optional[str] = None) -> bool:
        """Устанавливает статус продавца для пользователя
        Args:
            is_seller: Новый статус
            user_id: ID пользователя
            telegram_id: Telegram ID пользователя
        Returns:
            True если обновление успешно, False если произошла ошибка
        """
        try:
            self.cursor.execute(
                "UPDATE users SET is_seller = ? WHERE id = ? OR telegram_id = ?",
                (int(is_seller), user_id, telegram_id)
            )
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Ошибка при обновлении статуса продавца: {e}")
            return False

    #endregion

    #region Методы для таблицы service_types

    def add_service_type(self, name: str, created_by_id: str, required_fields: Dict[str, Dict[str, Any]]) -> Optional[int]:
        """
        Добавляет новый тип услуги с указаниями полями
        Args:
            name: Название типа услуги
            created_by_id: Telegram ID админа, создавшего тип
            required_fields: Словарь с описанием обязательных полей
        Returns:
            ID созданного типа услуги или None в случае ошибки
        """
        try:
            # Добавляем стандартные поля, если их нет
            default_fields = {
                "photo": {"type": "image", "label": "Фотография услуги", "required": True, "description": "Загрузите фото услуги"},
                "number_phone": {"type": "text", "label": "Номер телефона", "required": False, "description": "Укажите номер телефона для связи"},
                "price": {"type": "number", "label": "Стоимость", "required": True, "description": "Укажите стоимость в рублях"},
            }
            
            # Объединяем дефолтные поля с пользовательскими
            all_fields = {**default_fields, **required_fields}
            
            self.cursor.execute("""
                INSERT INTO service_types (name, created_by_id, required_fields)
                VALUES (?, ?, ?)
                RETURNING id
            """, (name, created_by_id, json.dumps(all_fields, ensure_ascii=False)))
            
            result = self.cursor.fetchone()
            self.connection.commit()
            return result[0] if result else None
            
        except sqlite3.IntegrityError:
            print(f"Тип услуги '{name}' уже существует")
            return None
        except Exception as e:
            print(f"Ошибка при создании типа услуги: {e}")
            return None

    def get_service_type(self, type_id: int) -> Optional[Dict]:
        """
        Получает информацию о типе услуги по ID
        Returns:
            Словарь с информацией о типе услуги и его полях
        """
        try:
            self.cursor.execute("""
                SELECT id, name, created_by_id, required_fields, is_active
                FROM service_types 
                WHERE id = ?
            """, (type_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
                
            return {
                "id": row[0],
                "name": row[1],
                "created_by_id": row[2],
                "required_fields": json.loads(row[3]),
                "is_active": bool(row[4])
            }
        except Exception as e:
            print(f"Ошибка при получении типа услуги: {e}")
            return None

    def get_active_service_types(self) -> List[Dict]:
        """
        Получает список всех активных типов услуг
        Returns:
            Список словарей с информацией о типах услуг
        """
        try:
            self.cursor.execute("""
                SELECT id, name, required_fields 
                FROM service_types
                WHERE is_active = 1
                ORDER BY name
            """)
            
            types = []
            for row in self.cursor.fetchall():
                types.append({
                    "id": row[0],
                    "name": row[1],
                    "required_fields": json.loads(row[2])
                })
            return types
            
        except Exception as e:
            print(f"Ошибка при получении типов услуг: {e}")
            return []

    def deactivate_service_type(self, type_id: int) -> bool:
        """
        Деактивирует тип услуги (мягкое удаление)
        Returns:
            bool: Успешность операции
        """
        try:
            self.cursor.execute("""
                UPDATE service_types 
                SET is_active = 0
                WHERE id = ?
            """, (type_id,))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Ошибка при деактивации типа услуги: {e}")
            return False

    def increment_service_views(self, service_id: int) -> bool:
        """
        Увеличивает счетчик просмотров услуги
        Args:
            service_id: ID услуги
        Returns:
            bool: Успешность операции
        """
        try:
            self.cursor.execute("""
                UPDATE services
                SET views = views + 1
                WHERE id = ?
            """, (service_id,))
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Ошибка при обновлении просмотров: {e}")
            return False

    #endregion

    #region Методы для таблицы services

    def add_service(self, user_id: int, service_type_id: int, title: str, photo_id: str,
                   city: str, district: str, street: str, house: str, number_phone: str, price: float, 
                   custom_fields: Dict[str, Any]) -> Optional[int]:
        """
        Создает новую услугу
        Args:
            user_id: ID пользователя
            service_type_id: ID типа услуги
            title: Название услуги
            photo_id: ID фотографии
            city: Город
            district: Район
            street: Улица
            house: Номер дома
            number_phone: Номер телефона
            price: Цена
            custom_fields: Дополнительные поля
        Returns:
            ID созданной услуги или None в случае ошибки
        """
        try:
            self.cursor.execute("""
                INSERT INTO services (
                    user_id, service_type_id, title, photo_id, city, 
                    district, street, house, number_phone, price, custom_fields
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            """, (
                user_id, service_type_id, title, photo_id, city,
                district, street, house, number_phone, price,
                json.dumps(custom_fields, ensure_ascii=False)
            ))

            result = self.cursor.fetchone()
            self.connection.commit()
            return result[0] if result else None

        except Exception as e:
            print(f"Ошибка при создании услуги: {e}")
            return None

    def get_services(self,
                    service_type_id: Optional[int] = None,
                    service_id: Optional[int] = None, 
                    telegram_id: Optional[int] = None,
                    status: Optional[str] = None,
                    limit: Optional[int] = None,
                    offset: Optional[int] = None,
                    order_by: str = 'created_at DESC') -> Optional[Union[Dict, List[Dict]]]:
        """
        Получает услуги с различными фильтрами
        Args:
            service_type_id: ID типа услуги
            service_id: ID конкретной услуги
            telegram_id: Telegram ID пользователя для получения его услуг 
            status: Статус услуг ('active', 'deactive', 'deleted', None для всех)
            limit: Ограничение количества результатов
            offset: Смещение для пагинации
            order_by: Сортировка результатов
        Returns:
            Dict с информацией об услуге или список Dict или None при ошибке
        """
        try:
            query = """
                SELECT 
                    s.*,
                    st.name as service_type_name,
                    st.required_fields as service_type_fields,
                    u.username as seller_username,
                    u.number_phone as seller_phone,
                    u.work_time_start as seller_work_time_start,
                    u.work_time_end as seller_work_time_end,
                    u.work_days as seller_work_days
                FROM services s
                LEFT JOIN service_types st ON s.service_type_id = st.id
                LEFT JOIN users u ON s.user_id = u.id
                WHERE 1=1
            """
            params = []

            if service_id is not None:
                query += " AND s.id = ?"
                params.append(service_id)
            if service_type_id is not None:
                query += " AND s.service_type_id = ?"
                params.append(service_type_id)
            if telegram_id is not None:
                query += " AND s.user_id = ?"
                params.append(telegram_id)
            if status is not None:
                query += " AND s.status = ?"
                params.append(status)

            allowed_orders = {'created_at', 'updated_at', 'price', 'views', 'id'}
            order_parts = order_by.lower().split()
            if len(order_parts) >= 1 and order_parts[0] in allowed_orders:
                direction = 'DESC' if len(order_parts) > 1 and order_parts[1].upper() == 'DESC' else 'ASC'
                query += f" ORDER BY s.{order_parts[0]} {direction}"
            else:
                query += " ORDER BY s.created_at DESC"

            if limit is not None and limit > 0:
                query += " LIMIT ?"
                params.append(min(limit, 100))  # Ограничиваем до 100 записей
            if offset is not None and offset >= 0:
                query += " OFFSET ?"
                params.append(offset)
                
            self.cursor.execute(query, params)
            rows = self.cursor.fetchall()

            if not rows:
                return []  # Возвращаем пустой список вместо None

            result = []
            columns = [desc[0] for desc in self.cursor.description]
            
            for row in rows:
                item = dict(zip(columns, row))
                
                for json_field in ['custom_fields', 'service_type_fields']:
                    if item.get(json_field):
                        try:
                            item[json_field] = json.loads(item[json_field])
                        except json.JSONDecodeError:
                            item[json_field] = {}
                    else:
                        item[json_field] = {}

                result.append(item)

            return result[0] if service_id else result

        except Exception as e:
            print(f"Ошибка при получении услуг: {str(e)}")
            return []  # Возвращаем пустой список вместо None

    def update_service(self, service_id: int, **kwargs) -> bool:
        """
        Обновляет информацию об услуге
        Args:
            service_id: ID услуги
            **kwargs: Поля для обновления (title, photo_id, city, etc.)
        Returns:
            bool: Успешность операции
        """
        try:
            allowed_fields = {'title', 'photo_id', 'city', 'district', 'street', 
                            'house', 'number_phone', 'price', 'custom_fields', 'status', 'views'}
            
            updates = []
            params = []
            
            for field, value in kwargs.items():
                if field in allowed_fields:
                    updates.append(f"{field} = ?")
                    params.append(value if field != 'custom_fields' 
                                else json.dumps(value, ensure_ascii=False))
            
            if not updates:
                return False
                
            params.append(service_id)
            query = f"""
                UPDATE services 
                SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """
            
            self.cursor.execute(query, params)
            self.connection.commit()
            return True

        except Exception as e:
            print(f"Ошибка при обновлении услуги: {e}")
            return False

    def delete_service(self, service_id: int, hard_delete: bool = False) -> bool:
        """
        Удаляет услугу
        Args:
            service_id: ID услуги
            hard_delete: Если True - полное удаление из БД, если False - soft delete
        Returns:
            bool: Успешность операции
        """
        try:
            if hard_delete:
                self.cursor.execute("DELETE FROM services WHERE id = ?", (service_id,))
            else:
                self.cursor.execute("""
                    UPDATE services 
                    SET status = 'deleted', updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (service_id,))
                
            self.connection.commit()
            return True
        except Exception as e:
            print(f"Ошибка при удалении услуги: {e}")
            return False

    def filter_services(self,
                       service_type_id: Optional[int] = None,
                       city: Optional[str] = None, 
                       district: Optional[str] = None,
                       price_min: Optional[float] = None,
                       price_max: Optional[float] = None,
                       custom_fields: Optional[Dict[str, Any]] = None,
                       search_text: Optional[str] = None,
                       sort_by: str = 'created_at',
                       sort_direction: str = 'DESC',
                       limit: int = 20,
                       offset: int = 0,
                       status: str = 'active') -> List[Dict]:
        """
        Расширенный поиск и фильтрация услуг
        Args:
            service_type_id: ID типа услуги
            city: Город
            district: Район
            price_min: Минимальная цена
            price_max: Максимальная цена
            custom_fields: Фильтры по дополнительным полям в формате {"field_name": "value"}
            search_text: Текст для поиска в названии и описании
            sort_by: Поле для сортировки
            sort_direction: Направление сортировки (ASC/DESC)
            limit: Ограничение количества результатов
            offset: Смещение для пагинации
            status: Статус услуги ('active', 'deleted' и т.д.)
        Returns:
            Список услуг, соответствующих фильтрам
        """
        try:
            # Базовый запрос с основными JOIN
            query = """
                SELECT 
                    s.*,
                    st.name as service_type_name,
                    st.required_fields as service_type_fields,
                    u.username as seller_username,
                    u.number_phone as seller_phone
                FROM services s
                LEFT JOIN service_types st ON s.service_type_id = st.id
                LEFT JOIN users u ON s.user_id = u.id
                WHERE s.status = ?
            """
            params = [status]

            # Добавляем фильтры
            if service_type_id is not None:
                query += " AND s.service_type_id = ?"
                params.append(service_type_id)
            
            if city:
                query += " AND LOWER(s.city) LIKE LOWER(?)"
                params.append(f"%{city}%")
                
            if district:
                query += " AND LOWER(s.district) LIKE LOWER(?)"
                params.append(f"%{district}%")
                
            if price_min is not None:
                query += " AND s.price >= ?"
                params.append(float(price_min))
                
            if price_max is not None:
                query += " AND s.price <= ?"
                params.append(float(price_max))

            # Поиск по тексту в названии и описании
            if search_text:
                query += """ AND (
                    LOWER(s.title) LIKE LOWER(?) 
                    OR LOWER(json_extract(s.custom_fields, '$.description')) LIKE LOWER(?)
                )"""
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern, search_pattern])

            # Применяем фильтры по дополнительным полям
            if custom_fields:
                for field, value in custom_fields.items():
                    if value is not None and value != '':
                        query += f" AND json_extract(s.custom_fields, '$.{field}') LIKE ?"
                        params.append(f"%{value}%")

            # Проверяем и применяем сортировку
            allowed_sort_fields = {'created_at', 'price', 'views', 'title'}
            allowed_directions = {'ASC', 'DESC'}
            
            sort_by = sort_by.lower() if sort_by else 'created_at'
            sort_direction = sort_direction.upper() if sort_direction else 'DESC'
            
            if sort_by in allowed_sort_fields and sort_direction in allowed_directions:
                query += f" ORDER BY s.{sort_by} {sort_direction}"
            else:
                query += " ORDER BY s.created_at DESC"

            # Добавляем пагинацию
            query += " LIMIT ? OFFSET ?"
            params.extend([max(1, int(limit)), max(0, int(offset))])

            # Выполняем запрос
            self.cursor.execute(query, params)
            
            # Формируем результат
            columns = [desc[0] for desc in self.cursor.description]
            result = []
            
            for row in self.cursor.fetchall():
                item = dict(zip(columns, row))
                
                # Обрабатываем JSON поля
                for json_field in ['custom_fields', 'service_type_fields']:
                    try:
                        if item.get(json_field):
                            item[json_field] = json.loads(item[json_field])
                        else:
                            item[json_field] = {}
                    except (json.JSONDecodeError, TypeError):
                        item[json_field] = {}
                
                # Приводим числовые поля к правильному типу
                if 'price' in item:
                    item['price'] = float(item['price'])
                if 'views' in item:
                    item['views'] = int(item['views'])
                        
                result.append(item)

            return result

        except Exception as e:
            print(f"Ошибка при фильтрации услуг: {e}")
            return []

    def get_cities(self) -> List[str]:
        """
        Получает список всех городов из активных услуг
        """
        try:
            self.cursor.execute("""
                SELECT DISTINCT city 
                FROM services 
                WHERE status = 'active'
                ORDER BY city
            """)
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Ошибка при получении списка городов: {e}")
            return []

    def get_districts(self, city: str) -> List[str]:
        """
        Получает список районов для конкретного города
        """
        try:
            self.cursor.execute("""
                SELECT DISTINCT district 
                FROM services 
                WHERE status = 'active' AND LOWER(city) = LOWER(?)
                ORDER BY district
            """, (city,))
            return [row[0] for row in self.cursor.fetchall()]
        except Exception as e:
            print(f"Ошибка при получении списка районов: {e}")
            return []

    def get_price_range(self, service_type_id: Optional[int] = None, city: Optional[str] = None) -> Tuple[float, float]:
        """
        Получает минимальную и максимальную цену для заданных фильтров
        """
        try:
            query = """
                SELECT MIN(price), MAX(price)
                FROM services
                WHERE status = 'active'
            """
            params = []

            if service_type_id:
                query += " AND service_type_id = ?"
                params.append(service_type_id)
            if city:
                query += " AND LOWER(city) = LOWER(?)"
                params.append(city)

            self.cursor.execute(query, params)
            min_price, max_price = self.cursor.fetchone()
            return (min_price or 0, max_price or 0)
        except Exception as e:
            print(f"Ошибка при получении диапазона цен: {e}")
            return (0, 0)

    def get_service_by_id(self, service_id: int) -> Optional[Dict]:
        """
        Получает информацию об услуге по его ID
        """
        self.cursor.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        return self.cursor.fetchone()   

    def update_service_status(self, service_id: int, status: str) -> None:
        """
        Обновляет статус услуги по его ID
        """
        self.cursor.execute("UPDATE services SET status = ? WHERE id = ?", (status, service_id))
        self.connection.commit()
    #endregion

    #region Методы для таблицы complaints

    def add_complaint(self, type: str, creator_telegram_id: str, text: str,
                     accused_telegram_id: Optional[str] = None,
                     accused_service_id: Optional[int] = None) -> bool:
        """
        Добавляет новую жалобу в базу данных
        Args:
            type: Тип жалобы ('user' или 'service')
            creator_telegram_id: Telegram ID создателя жалобы
            text: Текст жалобы
            accused_telegram_id: Telegram ID обвиняемого пользователя (для жалоб на пользователей)
            accused_service_id: ID обвиняемой услуги (для жалоб на услуги)
        Returns:
            bool: True если жалоба успешно добавлена, False в случае ошибки
        """
        try:
            if type not in ['user', 'service']:
                raise ValueError("Неверный тип жалобы")

            if type == 'user' and not accused_telegram_id:
                raise ValueError("Для жалобы на пользователя требуется accused_telegram_id")
                
            if type == 'service' and not accused_service_id:
                raise ValueError("Для жалобы на услугу требуется accused_service_id")

            # Проверяем существование пользователей
            self.cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (creator_telegram_id,))
            if not self.cursor.fetchone():
                raise ValueError("Создатель жалобы не найден")

            if accused_telegram_id:
                self.cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (accused_telegram_id,))
                if not self.cursor.fetchone():
                    raise ValueError("Обвиняемый пользователь не найден")

            # Проверяем существование услуги
            if accused_service_id:
                self.cursor.execute("SELECT id FROM services WHERE id = ?", (accused_service_id,))
                if not self.cursor.fetchone():
                    raise ValueError("Услуга не найдена")

            # # Проверяем, не подает ли пользователь жалобу на самого себя
            # if creator_telegram_id == accused_telegram_id:
            #     raise ValueError("Нельзя подать жалобу на самого себя")

            self.cursor.execute("""
                INSERT INTO complaints (
                    type, creator_telegram_id, accused_telegram_id, 
                    accused_service_id, text, created_at
                )
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (type, creator_telegram_id, accused_telegram_id, accused_service_id, text))
            
            self.connection.commit()
            return True
            
        except Exception as e:
            print(f"Ошибка при добавлении жалобы: {e}")
            return False

    def get_complaint_by_id(self, complaint_id: int) -> Optional[Dict]:
        """
        Получает жалобу по ID
        Args:
            complaint_id: ID жалобы
        Returns:
            Dict с данными жалобы или None
        """
        try:
            self.cursor.execute("""
                SELECT 
                    c.*,
                    u1.username as creator_username,
                    u2.username as accused_username,
                    s.title as service_title
                FROM complaints c
                LEFT JOIN users u1 ON c.creator_telegram_id = u1.telegram_id
                LEFT JOIN users u2 ON c.accused_telegram_id = u2.telegram_id
                LEFT JOIN services s ON c.accused_service_id = s.id
                WHERE c.id = ?
            """, (complaint_id,))
            
            row = self.cursor.fetchone()
            if not row:
                return None
                
            columns = [description[0] for description in self.cursor.description]
            complaint = dict(zip(columns, row))
            
            if complaint['created_at']:
                complaint['created_at'] = datetime.strptime(
                    complaint['created_at'], '%Y-%m-%d %H:%M:%S'
                ).strftime('%d.%m.%Y %H:%M')
                
            return complaint
            
        except Exception as e:
            print(f"Ошибка при получении жалобы: {e}")
            return None

    def get_complaints(self, type: Optional[str] = None,
                      complaint_id: Optional[int] = None,
                      creator_telegram_id: Optional[str] = None,
                      accused_telegram_id: Optional[str] = None,
                      accused_service_id: Optional[int] = None,
                      limit: Optional[int] = None) -> List[Dict]:
        """
        Получает список жалоб с возможностью фильтрации
        Args:
            type: Тип жалобы ('user' или 'service')
            complaint_id: ID жалобы
            creator_telegram_id: Telegram ID создателя
            accused_telegram_id: Telegram ID обвиняемого
            accused_service_id: ID услуги
            limit: Ограничение количества результатов
        Returns:
            List[Dict]: Список жалоб
        """
        try:
            query = """
                SELECT 
                    c.*,
                    u1.username as creator_username,
                    u2.username as accused_username,
                    s.title as service_title
                FROM complaints c
                LEFT JOIN users u1 ON c.creator_telegram_id = u1.telegram_id
                LEFT JOIN users u2 ON c.accused_telegram_id = u2.telegram_id
                LEFT JOIN services s ON c.accused_service_id = s.id
                WHERE 1=1
            """
            params = []
            
            if type:
                query += " AND c.type = ?"
                params.append(type) 
            if complaint_id:
                query += " AND c.id = ?"
                params.append(complaint_id)
            if creator_telegram_id:
                query += " AND c.creator_telegram_id = ?"
                params.append(creator_telegram_id)
            if accused_telegram_id:
                query += " AND c.accused_telegram_id = ?"
                params.append(accused_telegram_id)
            if accused_service_id:
                query += " AND c.accused_service_id = ?"
                params.append(accused_service_id)
                
            query += " ORDER BY c.created_at DESC"

            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            self.cursor.execute(query, params)
            columns = [description[0] for description in self.cursor.description]
            complaints = []
            
            for row in self.cursor.fetchall():
                complaint = dict(zip(columns, row))
                
                if complaint['created_at']:
                    complaint['created_at'] = datetime.strptime(
                        complaint['created_at'], '%Y-%m-%d %H:%M:%S'
                    ).strftime('%d.%m.%Y %H:%M')
                    
                complaints.append(complaint)
                
            return complaints
            
        except Exception as e:
            print(f"Ошибка при получении жалоб: {e}")
            return []

    def delete_complaint(self, complaint_id: int) -> bool:
        """
        Удаляет жалобу по ID
        Args:
            complaint_id: ID жалобы
        Returns:
            bool: True если удаление успешно, False если произошла ошибка
        """
        try:
            self.cursor.execute("DELETE FROM complaints WHERE id = ?", (complaint_id,))
            
            if self.cursor.rowcount == 0:
                raise ValueError("Жалоба не найдена")
                
            self.connection.commit()
            return True
            
        except Exception as e:
            print(f"Ошибка при удалении жалобы: {e}")
            return False

    def get_complaints_count(self, type: Optional[str] = None) -> int:
        """
        Получает количество жалоб с указанным типом
        Args:
            type: Тип жалобы ('user' или 'service')
        Returns:
            int: Количество жалоб
        """
        try:
            query = "SELECT COUNT(*) FROM complaints"
            params = []
            
            if type:
                if type not in ['user', 'service']:
                    raise ValueError("Неверный тип жалобы")
                query += " WHERE type = ?"
                params.append(type)
                
            self.cursor.execute(query, params)
            result = self.cursor.fetchone()
            return result[0] if result else 0
            
        except Exception as e:
            print(f"Ошибка при получении количества жалоб: {e}")
            return 0

    #endregion

    #region Методы для таблицы banned_types

    def ban_entity(self, admin_telegram_id: str, type: str, accused_telegram_id: Optional[str] = None,
                  accused_service_id: Optional[int] = None, ban_duration_hours: int = 24,
                  is_permanent: bool = False, reason: str = "") -> bool:
        """
        Блокирует пользователя или сервис в системе
        Args:
            admin_telegram_id: Telegram ID администратора
            type: Тип блокировки ('user' или 'service')
            accused_telegram_id: Telegram ID блокируемого пользователя
            accused_service_id: ID блокируемого сервиса
            ban_duration_hours: Длительность блокировки в часах
            is_permanent: Является ли блокировка постоянной
            reason: Причина блокировки
        Returns:
            bool: True если блокировка успешна, False если произошла ошибка
        """
        try:
            if type not in ['user', 'service']:
                raise ValueError("Неверный тип блокировки")

            if type == 'user' and not accused_telegram_id:
                raise ValueError("Не указан ID пользователя для блокировки")
                
            if type == 'service' and not accused_service_id:
                raise ValueError("Не указан ID сервиса для блокировки")

            # Проверяем существование администратора
            self.cursor.execute("SELECT telegram_id FROM users WHERE telegram_id = ?", (admin_telegram_id,))
            if not self.cursor.fetchone():
                raise ValueError("Администратор не найден")

            # Проверяем, не заблокирован ли уже объект
            query = "SELECT id FROM banned_types WHERE type = ? AND "
            params = [type]
            
            if type == 'user':
                query += "accused_telegram_id = ?"
                params.append(accused_telegram_id)
            else:
                query += "accused_service_id = ?"
                params.append(accused_service_id)

            self.cursor.execute(query, params)
            if self.cursor.fetchone():
                raise ValueError(f"{'Пользователь' if type == 'user' else 'Сервис'} уже заблокирован")

            self.cursor.execute("""
                INSERT INTO banned_types (type, admin_telegram_id, accused_telegram_id, 
                                       accused_service_id, ban_duration_hours, is_permanent, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (type, admin_telegram_id, accused_telegram_id, accused_service_id, 
                 ban_duration_hours, is_permanent, reason))
            self.connection.commit()
            return True
            
        except Exception as e:
            print(f"Ошибка при блокировке: {e}")
            return False

    def unban_entity(self, type: str, accused_telegram_id: Optional[str] = None,
                    accused_service_id: Optional[int] = None) -> bool:
        """
        Разблокирует пользователя или сервис
        Args:
            type: Тип блокировки ('user' или 'service')
            accused_telegram_id: Telegram ID разблокируемого пользователя
            accused_service_id: ID разблокируемого сервиса
        Returns:
            bool: True если разблокировка успешна, False если произошла ошибка
        """
        try:
            if type not in ['user', 'service']:
                raise ValueError("Неверный тип блокировки")

            query = "DELETE FROM banned_types WHERE type = ? AND "
            params = [type]
            
            if type == 'user':
                query += "accused_telegram_id = ?"
                params.append(accused_telegram_id)
            else:
                query += "accused_service_id = ?"
                params.append(accused_service_id)

            self.cursor.execute(query, params)
            if self.cursor.rowcount == 0:
                raise ValueError(f"{'Пользователь' if type == 'user' else 'Сервис'} не найден в списке заблокированных")
            
            self.connection.commit()
            return True
            
        except Exception as e:
            print(f"Ошибка при разблокировке: {e}")
            return False

    def get_ban_info(self, type: str, accused_telegram_id: Optional[str] = None,
                    accused_service_id: Optional[int] = None) -> Optional[Dict]:
        """
        Получает информацию о блокировке
        Args:
            type: Тип блокировки ('user' или 'service')
            accused_telegram_id: Telegram ID пользователя
            accused_service_id: ID сервиса
        Returns:
            Dict с информацией о блокировке или None если объект не заблокирован
        """
        try:
            if type not in ['user', 'service']:
                raise ValueError("Неверный тип блокировки")

            query = """
                SELECT id, admin_telegram_id, accused_telegram_id, accused_service_id,
                       ban_date, ban_duration_hours, is_permanent, reason
                FROM banned_types 
                WHERE type = ? AND """
            params = [type]
            
            if type == 'user':
                query += "accused_telegram_id = ?"
                params.append(accused_telegram_id)
            else:
                query += "accused_service_id = ?"
                params.append(accused_service_id)

            self.cursor.execute(query, params)
            result = self.cursor.fetchone()
            
            if result:
                return dict(zip(['id', 'admin_telegram_id', 'accused_telegram_id',
                               'accused_service_id', 'ban_date', 'ban_duration_hours',
                               'is_permanent', 'reason'], result))
            return None
            
        except Exception as e:
            print(f"Ошибка при получении информации о блокировке: {e}")
            return None

    def get_all_bans(self, type: Optional[str] = None) -> List[Dict]:
        """
        Получает список всех блокировок
        Args:
            type: Тип блокировки ('user' или 'service'), если None - все типы
        Returns:
            List[Dict]: Список словарей с информацией о блокировках
        """
        try:
            query = """
                SELECT id, type, admin_telegram_id, accused_telegram_id, accused_service_id,
                       ban_date, ban_duration_hours, is_permanent, reason
                FROM banned_types
            """
            params = []
            
            if type:
                if type not in ['user', 'service']:
                    raise ValueError("Неверный тип блокировки")
                query += " WHERE type = ?"
                params.append(type)
                
            query += " ORDER BY ban_date DESC"
            
            self.cursor.execute(query, params)
            results = self.cursor.fetchall()
            
            return [dict(zip(['id', 'type', 'admin_telegram_id', 'accused_telegram_id',
                            'accused_service_id', 'ban_date', 'ban_duration_hours',
                            'is_permanent', 'reason'], row)) for row in results]
                            
        except Exception as e:
            print(f"Ошибка при получении списка блокировок: {e}")
            return []

    #endregion

    def __del__(self):
        self.connection.close()

