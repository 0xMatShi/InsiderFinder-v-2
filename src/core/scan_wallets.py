import asyncio
import random
from datetime import datetime, timedelta, timezone
import aiohttp

from src.utils.constants import DATA_URL, GAMMA_URL, PROXIES
from src.utils.proxy_manager import get_headers_for_proxy

CONCURRENCY_LIMIT = len(PROXIES) if PROXIES else 10

# Глобальный кэш релевантности (чистится при каждом запуске фильтрации)
EVENT_RELEVANCE_CACHE = {}


def _get_cutoff_timestamp(time_str: str) -> float:
    if not time_str or len(time_str) < 2:
        return (datetime.now(timezone.utc) - timedelta(days=1)).timestamp()

    unit = time_str[-1].lower()
    try:
        value = int(time_str[:-1])
    except ValueError:
        value = 1

    now = datetime.now(timezone.utc)

    if unit == 'd':
        delta = timedelta(days=value)
    elif unit == 'w':
        delta = timedelta(weeks=value)
    elif unit == 'h':
        delta = timedelta(hours=value)
    else:
        delta = timedelta(days=1)

    cutoff_date = now - delta
    return cutoff_date.timestamp()


async def is_event_related(session, event_slug, keyword):
    """
    Проверяет, относится ли событие (slug) к ключевому слову.
    """
    if not event_slug: return False
    
    # 1. Проверка в кэше (быстро)
    if event_slug in EVENT_RELEVANCE_CACHE:
        return EVENT_RELEVANCE_CACHE[event_slug]

    kw_clean = keyword.lower().strip()
    slug_clean = event_slug.lower()

    # 2. Проверка по слагу (строка)
    if kw_clean in slug_clean.replace("-", " "):
        EVENT_RELEVANCE_CACHE[event_slug] = True
        return True

    # 3. API запрос (если нет в кэше и слаг не очевиден)
    try:
        proxy = random.choice(PROXIES) if PROXIES else None
        headers = get_headers_for_proxy(proxy)
        
        params = {"slug": event_slug}
        
        async with session.get(f"{GAMMA_URL}/events", params=params, proxy=proxy, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                if isinstance(data, list) and len(data) > 0:
                    event = data[0]
                elif isinstance(data, dict):
                    event = data
                else:
                    event = {}

                title = event.get("title", "").lower()
                desc = event.get("description", "").lower()
                
                is_related = (kw_clean in title) or (kw_clean in desc)
                EVENT_RELEVANCE_CACHE[event_slug] = is_related
                return is_related
            else:
                return False
    except:
        return False

    return False


async def _check_single_wallet(session, wallet, keyword, config, cutoff_timestamp, semaphore):
    # Загружаем параметры
    min_pred = config.get("min_predictions")
    max_pred = config.get("max_predictions")
    max_curr_pos = config.get("current_positions")
    min_realized_pnl = config.get("realized_pnl")
    target_kw_percent = config.get("target_keyword_percent")

    async with semaphore:
        proxy = random.choice(PROXIES) if PROXIES else None
        headers = get_headers_for_proxy(proxy)
        
        positions_count = 0
        traded_count = 0
        total_pnl = 0.0
        
        matched_events_count = 0

        # --- 1. Проверка активности ---
        try:
            trades_params = {"user": wallet, "limit": 1, "order": "timestamp", "ascending": "false"}
            async with session.get(f"{DATA_URL}/trades", params=trades_params, proxy=proxy, headers=headers) as resp:
                if resp.status != 200: return None
                trades = await resp.json()

            if not trades: return None
            last_trade_ts = trades[0].get("timestamp")
            if not last_trade_ts or float(last_trade_ts) < cutoff_timestamp:
                return None
        except: return None

        # --- 2. Проверка текущих позиций (С ФИЛЬТРОМ ПЫЛИ) ---
        # Исправление: считаем только позиции > 0.1
        try:
            pos_params = {"user": wallet, "limit": 500}
            async with session.get(f"{DATA_URL}/positions", params=pos_params, proxy=proxy, headers=headers) as resp:
                if resp.status == 200:
                    positions = await resp.json()
                    # ФИЛЬТРУЕМ МУСОР, как в analyzer.py
                    valid_positions = [p for p in positions if float(p.get("size", 0)) > 0.01]
                    positions_count = len(valid_positions)
                    
                    if max_curr_pos is not None and positions_count > max_curr_pos:
                        return None
                else:
                    if max_curr_pos is not None: return None
        except: 
            if max_curr_pos is not None: return None

        # --- 3. Проверка количества рынков ---
        try:
            traded_params = {"user": wallet}
            async with session.get(f"{DATA_URL}/traded", params=traded_params, proxy=proxy, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    traded_count = data.get("traded", 0)
                    if not (min_pred <= traded_count <= max_pred):
                        return None
        except: return None

        # --- 4. Проверка PnL и KeyWords ---
        need_pnl = min_realized_pnl is not None
        need_kw = (target_kw_percent is not None and target_kw_percent > 0)

        if need_pnl or need_kw:
            try:
                offset = 0
                limit = 50
                
                while True:
                    pnl_params = {"user": wallet, "limit": limit, "offset": offset}
                    async with session.get(f"{DATA_URL}/closed-positions", params=pnl_params, proxy=proxy, headers=headers) as resp:
                        if resp.status != 200: return None
                        closed_positions = await resp.json()
                    
                    if not closed_positions: break
                    
                    total_closed = len(closed_positions)

                    for pos in closed_positions:
                        if need_pnl:
                            val = pos.get("realizedPnl")
                            if val: total_pnl += float(val)
                        
                        if need_kw:
                            slug = pos.get("slug")
                            if slug:
                                if await is_event_related(session, slug, keyword):
                                    matched_events_count += 1
                    
                    if len(closed_positions) < limit: break
                    offset += limit
            
                # Итоговые проверки
                if need_pnl and total_pnl < min_realized_pnl:
                    return None
                
                if need_kw:
                    ratio = matched_events_count / total_closed # type: ignore
                    if ratio < target_kw_percent: return None

            except Exception: 
                return None

        return {
            "wallet": wallet,
            "total_predictions": traded_count,
            "active_predictions": positions_count,
            "realized_pnl": total_pnl if need_pnl else None
        }


async def filter_wallets(
    session: aiohttp.ClientSession, 
    wallets: list, 
    config: dict, 
    progress=None, 
    task_id=None, 
    keyword: str = "",
    known_related_slugs: dict = None # type: ignore
):
    """
    Главная функция фильтрации.
    """
    time_str = config.get("last_active_trade", "1d")
    cutoff_ts = _get_cutoff_timestamp(time_str)
    
    # Очищаем кэш и загружаем известные слаги (из поиска)
    EVENT_RELEVANCE_CACHE.clear()
    if known_related_slugs:
        EVENT_RELEVANCE_CACHE.update(known_related_slugs)
    
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    tasks = []

    for wallet in wallets:
        task = asyncio.create_task(
            _check_single_wallet(
                session, wallet, keyword, config, cutoff_ts, semaphore
            )
        )
        tasks.append(task)

    valid_wallets_data = []
    
    # Батчинг обновлений UI (50 шт)
    pending_updates = 0
    BATCH_SIZE = 50 

    for future in asyncio.as_completed(tasks):
        result = await future
        
        pending_updates += 1
        if progress and task_id is not None:
            if pending_updates >= BATCH_SIZE:
                progress.advance(task_id, pending_updates)
                pending_updates = 0
                await asyncio.sleep(0) 
            
        if result is not None:
            valid_wallets_data.append(result)
    
    if progress and task_id is not None and pending_updates > 0:
        progress.advance(task_id, pending_updates)
    
    return valid_wallets_data