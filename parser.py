import json
from datetime import datetime
import logging
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_replacements_xhr():
    """Получение данных через XHR-запрос"""
    try:
        url = "http://rep.spb-kit.ru/replacements/api/fetch-rep"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Charset': 'utf-8'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'  # Явно указываем кодировку
        response.raise_for_status()
        
        # Получаем HTML-контент
        content = response.text
        
        if content and 'error' not in content.lower():
            # Проверяем наличие данных в ответе
            if '<table' in content and '</table>' in content:
                logger.debug(f"Получены данные через XHR: {content[:200]}...")  # Логируем первые 200 символов для проверки
                return content
            else:
                logger.warning("XHR-ответ не содержит таблицу с данными")
                return None
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при XHR-запросе: {str(e)}")
        return None

def get_replacements():
    """Основная функция получения замен"""
    url = "http://rep.spb-kit.ru/replacements/view.html"
    
    try:
        # Сначала пробуем получить данные через XHR
        xhr_content = get_replacements_xhr()
        if xhr_content:
            logger.info("Данные успешно получены через XHR")
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            
            driver = webdriver.Chrome(options=chrome_options)
            try:
                # Создаем базовую HTML-структуру с указанием кодировки
                html_template = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                </head>
                <body>
                    <div id="content">
                        {xhr_content}
                    </div>
                </body>
                </html>
                """
                
                # Загружаем контент через data URL для сохранения кодировки
                driver.get(f"data:text/html;charset=utf-8,{html_template}")
                
                # Ждем загрузки контента
                wait = WebDriverWait(driver, 10)
                content = wait.until(EC.presence_of_element_located((By.ID, "content")))
                
                # Далее используем существующий код для парсинга...
                result = {
                    "date": None,
                    "raw_date": None,
                    "groups": {}
                }
                
                # Получаем весь текст из контента
                content_text = content.text.strip()
                logger.debug(f"Текст контента: {content_text}")
                
                # Ищем дату в первых строках текста
                lines = content_text.split('\n')
                for line in lines[:3]:  # Проверяем первые 3 строки
                    if any(word in line.lower() for word in ['замены', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота']):
                        result["raw_date"] = line.strip()
                        logger.debug(f"Найдена сырая дата: {result['raw_date']}")
                        
                        # Ищем дату в формате DD.MM.YY
                        import re
                        date_match = re.search(r'\d{2}\.\d{2}\.\d{2}', line)
                        if date_match:
                            date_str = date_match.group(0)
                            date_obj = datetime.strptime(date_str, "%d.%m.%y")
                            result["date"] = date_obj.strftime("%Y-%m-%d")
                            logger.debug(f"Обработана дата: {result['date']}")
                        break
                
                # Ждем появления таблиц
                tables = driver.find_elements(By.TAG_NAME, "table")
                logger.debug(f"Найдено таблиц: {len(tables)}")
                
                current_group = None
                for table in tables:
                    rows = table.find_elements(By.TAG_NAME, "tr")
                    
                    for row in rows:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        
                        if not cells:
                            continue
                        
                        # Пропускаем заголовки и служебные записи
                        first_cell = cells[0].text.strip()
                        if (first_cell == "№ пары" or 
                            "директор" in first_cell.lower() or
                            any("венедиктова" in cell.text.lower() for cell in cells)):
                            continue
                        
                        # Если это строка с номером группы
                        if len(cells) == 1:
                            group_number = first_cell
                            if group_number.isdigit():
                                current_group = group_number
                                result["groups"][current_group] = []
                                logger.debug(f"Обработка группы: {current_group}")
                        
                        # Если это строка с заменами
                        elif len(cells) >= 4 and current_group and current_group in result["groups"]:
                            replacement = {
                                "pair": cells[0].text.strip(),
                                "original_subject": cells[1].text.strip(),
                                "teacher": cells[2].text.strip(),
                                "new_subject": cells[3].text.strip(),
                                "classroom": cells[4].text.strip() if len(cells) > 4 else ""
                            }
                            
                            # Добавляем только если есть реальные данные
                            if any(v for v in replacement.values() if v and "венедиктова" not in v.lower()):
                                result["groups"][current_group].append(replacement)
                                logger.debug(f"Добавлена замена для группы {current_group}: {replacement}")
                
                # Удаляем пустые группы
                result["groups"] = {k: v for k, v in result["groups"].items() if v}
                
                logger.info(f"Всего обработано групп: {len(result['groups'])}")
                return result
                
            finally:
                logger.debug("Закрытие браузера")
                driver.quit()
                
        else:
            # Если XHR не сработал, используем оригинальный метод через Selenium
            logger.info("XHR не удался, переключаемся на Selenium")
            # ... (оставшийся оригинальный код)

    except Exception as e:
        logger.error(f"Ошибка при обработке данных: {str(e)}", exc_info=True)
        return {"error": f"Ошибка при обработке данных: {str(e)}"}

def save_to_json(data, filename="replacements.json"):
    """Сохраняет данные в JSON файл"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Данные успешно сохранены в файл {filename}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении в JSON: {str(e)}")
        return False

if __name__ == "__main__":
    # Получаем данные
    logger.info("Начало работы парсера")
    data = get_replacements()
    
    # Проверяем наличие ошибок
    if "error" in data:
        logger.error(f"Парсер завершился с ошибкой: {data['error']}")
    else:
        # Сохраняем в JSON
        if save_to_json(data):
            logger.info("Парсер успешно завершил работу")
        else:
            logger.error("Произошла ошибка при сохранении да��ных")
