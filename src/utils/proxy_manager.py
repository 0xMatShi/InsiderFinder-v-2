import json
import os
from fake_useragent import UserAgent

# Путь к файлу, где будем хранить связки Proxy-UA
CONFIG_FILE = "proxies_config.json"
PROXY_UA_MAP = {}

# Инициализируем генератор UA
ua_gen = UserAgent()

def load_and_assign_uas(proxy_list):
    """
    Загружает карту Proxy-UA из файла.
    Если для какого-то прокси из proxy_list нет UA, генерирует новый и сохраняет.
    """
    global PROXY_UA_MAP
    
    # 1. Загружаем существующие привязки
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                PROXY_UA_MAP = json.load(f)
        except Exception as e:
            print(f"⚠️ Ошибка чтения {CONFIG_FILE}, создаем новый. ({e})")
            PROXY_UA_MAP = {}
    
    # 2. Проверяем каждый прокси из списка
    updated = False
    for proxy in proxy_list:
        # Если этого прокси еще нет в базе или у него нет UA
        if proxy not in PROXY_UA_MAP:
            # Генерируем новый UA и закрепляем его навсегда
            try:
                new_ua = ua_gen.random
            except:
                new_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
            PROXY_UA_MAP[proxy] = new_ua
            updated = True
            print(f"🆕 Сгенерирован новый UA для прокси {proxy[:20]}...")

    # 3. Если были изменения, сохраняем в файл
    if updated:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(PROXY_UA_MAP, f, indent=4)
        print("💾 Конфигурация прокси и User-Agents успешно сохранена.")
    else:
        print("✅ Все прокси уже имеют закрепленные User-Agents.")

def get_headers_for_proxy(proxy):
    """
    Возвращает полные заголовки с закрепленным User-Agent для конкретного прокси.
    """
    # Если прокси None (работаем без прокси), выдаем рандом или дефолт
    if not proxy:
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    else:
        # Берем из памяти
        user_agent = PROXY_UA_MAP.get(proxy)
        
        # Если вдруг прокси не найден (странная ситуация), генерируем на лету
        if not user_agent:
            user_agent = ua_gen.random

    return {
        "User-Agent": user_agent,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://polymarket.com/",
        "Origin": "https://polymarket.com",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site"
    }