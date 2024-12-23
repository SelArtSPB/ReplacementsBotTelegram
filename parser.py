import json
from datetime import datetime
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def get_replacements():
    url = "http://rep.spb-kit.ru/replacements/view.html"
    
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        logger.debug("Запуск Chrome в безголовом режиме")
        driver = webdriver.Chrome(options=chrome_options)
        
        try:
            logger.debug(f"Открытие страницы: {url}")
            driver.get(url)
            
            # Увеличиваем время ожидания загрузки контента
            wait = WebDriverWait(driver, 20)
            
            # Сначала ждем загрузки основного контейнера
            content = wait.until(EC.presence_of_element_located((By.ID, "content")))
            
            # Ждем появления любого текста внутри контента
            wait.until(lambda d: len(content.text.strip()) > 0)
            
            # Даем дополнительное время на рендеринг
            time.sleep(3)
            
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
            tables = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "table")))
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
            logger.error("Произошла ошибка при сохранении данных")
