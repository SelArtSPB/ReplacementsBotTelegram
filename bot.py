import telebot
import json
import logging
import time
import threading
from parser import get_replacements, save_to_json
from datetime import datetime
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота
with open('bot_token.txt', 'r') as f:
    bot = telebot.TeleBot(f.read().strip())

# Файл для хранения ID пользователей
USERS_FILE = 'users.json'

# Функция для загрузки списка пользователей
def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Ошибка при загрузке пользователей: {e}")
        return []

# Функция для сохранения списка пользователей
def save_users(users):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(list(set(users)), f)  # Используем set для удаления дубликатов
    except Exception as e:
        logger.error(f"Ошибка при сохранении пользователей: {e}")

# Функция для чтения данных из JSON
def read_replacements():
    try:
        with open('replacements.json', 'r', encoding='utf-8') as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Ошибка при чтении JSON: {e}")
        return None

# Функция для форматирования замен
def format_replacement(replacement):
    # Конвертируем номер урока в номер пары
    lesson_num = int(replacement['pair']) if replacement['pair'].isdigit() else 0
    pair_num = (lesson_num + 1) // 2 if lesson_num > 0 else lesson_num
    
    message = f"🕐 Пара: {pair_num}\n"
    
    if replacement['teacher'] == "Отмена пары":
        message += "❌ Статус: Пара отменена\n"
    elif replacement['teacher'] == "Перенос пары":
        message += "🔄 Статус: Пара перенесена\n"
    else:
        if replacement['new_subject']:
            message += f"📗 Предмет: {replacement['new_subject']}\n"
        
        if replacement['teacher']:
            message += f"👨‍🏫 Преподаватель: {replacement['teacher']}\n"
    
    if replacement['classroom']:
        if replacement['classroom'].upper() == 'ДО':
            message += "🏠 Форма обучения: Дистанционно\n"
        else:
            message += f"🏛 Аудитория: {replacement['classroom']}\n"
    
    return message

# Функция для группировки замен по парам
def group_replacements_by_pairs(replacements):
    # Сортируем замены по номеру урока
    sorted_replacements = sorted(replacements, key=lambda x: int(x['pair']) if x['pair'].isdigit() else float('inf'))
    
    # Группируем по парам
    pairs = {}
    for i in range(0, len(sorted_replacements), 2):
        # Получаем текущий урок
        current = sorted_replacements[i]
        # Проверяем, есть ли следующий урок
        next_lesson = sorted_replacements[i + 1] if i + 1 < len(sorted_replacements) else None
        
        # Если это последовательные уроки (например, 1-2, 3-4 и т.д.)
        if (next_lesson and 
            current['pair'].isdigit() and 
            next_lesson['pair'].isdigit() and 
            int(next_lesson['pair']) == int(current['pair']) + 1 and 
            int(current['pair']) % 2 == 1):  # Проверяем, что первый урок нечетный
            
            # Вычисляем номер пары
            pair_num = (int(current['pair']) + 1) // 2
            pairs[pair_num] = current  # Берем только первый урок, так как они одинаковые
            
        # Если это одиночный урок или уроки разные
        else:
            if current['pair'].isdigit():
                pair_num = (int(current['pair']) + 1) // 2
                pairs[pair_num] = current

    return pairs

# Создание основной клавиатуры
def get_main_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("Замена по группам", "Замена по преподавателям")
    keyboard.row("Очистить")
    return keyboard

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def start(message):
    users = load_users()
    if message.chat.id not in users:
        users.append(message.chat.id)
        save_users(users)
        logger.info(f"Новый пользователь добавлен: {message.chat.id}")
    
    bot.reply_to(message, 
                 "Добро пожаловать! Выберите тип поиска замен. Вы будете получать уведомления о новых заменах.",
                 reply_markup=get_main_keyboard())

# Обработчик кнопки "Замена по группам"
@bot.message_handler(func=lambda message: message.text == "Замена по группам")
def show_groups(message):
    data = read_replacements()
    if not data or not data['groups']:
        bot.reply_to(message, "Данные о заменах отсутствуют")
        return

    keyboard = telebot.types.InlineKeyboardMarkup(row_width=3)
    
    # Сортируем группы по номеру
    groups = sorted(data['groups'].keys(), key=lambda x: int(x))
    
    # Создаем кнопки для каждой группы
    buttons = []
    for group_number in groups:
        buttons.append(
            telebot.types.InlineKeyboardButton(
                text=group_number,
                callback_data=f"group_{group_number}"
            )
        )
    
    # Добавляем кнопки в клавиатуру по 3 в ряд
    for i in range(0, len(buttons), 3):
        row = buttons[i:min(i + 3, len(buttons))]
        keyboard.add(*row)

    bot.reply_to(message, "Выберите группу:", reply_markup=keyboard)

# Обработчик кнопки "Замена по преподавателям"
@bot.message_handler(func=lambda message: message.text == "Замена по преподавателям")
def show_teachers(message):
    data = read_replacements()
    if not data or not data['groups']:
        bot.reply_to(message, "Данные о заменах отсутствуют")
        return

    teachers = set()
    for group_replacements in data['groups'].values():
        for replacement in group_replacements:
            if (replacement['teacher'] and 
                replacement['teacher'] not in ["Отмена пары", "Перенос пары"]):
                teachers.add(replacement['teacher'])

    keyboard = telebot.types.InlineKeyboardMarkup()
    for teacher in sorted(teachers):
        keyboard.add(telebot.types.InlineKeyboardButton(
            text=teacher,
            callback_data=f"teacher_{teacher}"
        ))

    bot.reply_to(message, "Выберите преподавателя:", reply_markup=keyboard)

# Обработчик callback-запросов
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = read_replacements()
    if not data:
        bot.answer_callback_query(call.id, "Ошибка получения данных")
        return

    if call.data.startswith('group_'):
        group_number = call.data[6:]
        response = f"📅 Замены для группы {group_number}\n"
        if data['raw_date']:
            response += f"📆 {data['raw_date']}\n\n"
        
        if group_number in data['groups']:
            replacements = data['groups'][group_number]
            if not replacements:
                response = f"Для группы {group_number} замен нет"
            else:
                # Группируем замены по парам
                pairs = group_replacements_by_pairs(replacements)
                for pair_num in sorted(pairs.keys()):
                    response += format_replacement(pairs[pair_num]) + "\n"
        else:
            response = f"Для группы {group_number} замен нет"
            
    elif call.data.startswith('teacher_'):
        teacher_name = call.data[8:]
        response = f"👨‍🏫 Замены для преподавателя {teacher_name}\n"
        if data['raw_date']:
            response += f"📆 {data['raw_date']}\n\n"
        
        # Соираем все замены для преподавателя
        teacher_replacements = []
        for group_number, replacements in data['groups'].items():
            for replacement in replacements:
                if replacement['teacher'] == teacher_name:
                    replacement_with_group = {**replacement, 'group_number': group_number}
                    teacher_replacements.append(replacement_with_group)
        
        if teacher_replacements:
            # Группируем замены по парам
            pairs = group_replacements_by_pairs(teacher_replacements)
            for pair_num in sorted(pairs.keys()):
                response += f"👥 Группа: {pairs[pair_num]['group_number']}\n"
                response += format_replacement(pairs[pair_num]) + "\n"
        else:
            response = f"Для преподавателя {teacher_name} замен нет"

    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, response)

# Функция для отправки уведомлений всем пользователям
def notify_users(new_data):
    users = load_users()
    date_str = new_data.get('raw_date', 'Неизвестная дата')
    
    # Формируем сообщение с кратким обзором замен
    message = f"🔔 Обнаружены новые замены на {date_str}\n\n"
    
    # Добавляем список групп с заменами
    groups = new_data.get('groups', {}).keys()
    if groups:
        message += "Замены есть для групп: " + ", ".join(sorted(groups, key=lambda x: int(x))) + "\n\n"
        message += "Используйте меню бота для просмотра подробной информации."
    
    # Отправляем уведомление каждому пользователю
    for user_id in users:
        try:
            bot.send_message(user_id, message, reply_markup=get_main_keyboard())
            logger.info(f"Уведомление отправлено пользователю {user_id}")
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
            # Если бот заблокирован или чат не найден, удаляем пользователя из списка
            if "Forbidden" in str(e) or "chat not found" in str(e).lower():
                users.remove(user_id)
                logger.info(f"Пользователь {user_id} удален из списка рассылки")
    
    # Сохраняем обновленный список пользователей
    save_users(users)

# Функция для периодической проверки обновлений
def check_updates():
    while True:
        try:
            current_time = datetime.now()
            
            # Проверяем, находимся ли мы в интервале 17-18 часов
            if current_time.hour == 17:
                # Получаем новые данные
                new_data = get_replacements()
                
                if new_data and 'error' not in new_data:
                    try:
                        # Читаем текущие данные
                        current_data = read_replacements()
                        
                        # Проверяем, изменилась ли дата
                        new_date = new_data.get('date')
                        current_date = current_data.get('date') if current_data else None
                        
                        # Если данные отличаются или файла нет
                        if current_data != new_data:
                            # Удаляем старый файл если он существует
                            if os.path.exists('replacements.json'):
                                os.remove('replacements.json')
                            
                            # Сохраняем новые данные
                            save_to_json(new_data)
                            logger.info("Обнаружены и сохранены новые данные замен")
                            
                            # Если дата изменилась, отправляем уведомления
                            if new_date != current_date:
                                notify_users(new_data)
                                logger.info("Уведомления о новых заменах отправлены")
                            
                    except FileNotFoundError:
                        # Если файла нет, сохраняем новые данные и отправляем уведомления
                        save_to_json(new_data)
                        notify_users(new_data)
                        logger.info("Создан новый файл с данными замен и отправлены уведомления")
                
                # Ждем 20 минут перед следующей проверкой
                time.sleep(20 * 60)
            else:
                # Если не в интервале 17-18, проверяем раз в 30 минут
                time.sleep(30 * 60)
                
        except Exception as e:
            logger.error(f"Ошибка при проверке обновлений: {e}")
            time.sleep(5 * 60)

# Добавляем новый обработчик для кнопки "Очистить"
@bot.message_handler(func=lambda message: message.text == "Очистить")
def clear_chat(message):
    try:
        # Удаляем предыдущие сообщения
        for i in range(message.message_id, 0, -1):
            try:
                bot.delete_message(message.chat.id, i)
            except:
                break
    except Exception as e:
        logger.error(f"Ошибка при очистке чата: {e}")
    
    # Отправляем новое приветственное сообщение
    bot.send_message(
        message.chat.id,
        "Диалог очищен! Выберите тип поиска замен:",
        reply_markup=get_main_keyboard()
    )

if __name__ == '__main__':
    # Запуск проверки обновлений в отдельном потоке
    update_thread = threading.Thread(target=check_updates)
    update_thread.daemon = True
    update_thread.start()
    
    # Запуск бота
    logger.info("Бот запущен")
    bot.polling(none_stop=True)
