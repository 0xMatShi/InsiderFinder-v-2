import aiohttp
from src.utils.constants import GAMMA_URL

async def scan_events(session: aiohttp.ClientSession, keyword: str, max_events_to_search: int, progress=None, task_id=None):
    """Сканируем события с обновлением Rich прогресс-бара."""
    SEARCH_URL = f"{GAMMA_URL}/public-search"

    all_events = []
    page = 1
    limit_per_page = 50
    
    try:
        while len(all_events) < max_events_to_search:
            params = {
                "q": keyword,
                "limit_per_page": limit_per_page,
                "page": page,
                "type": "event",
            }

            async with session.get(url=SEARCH_URL, params=params) as response:
                if response.status != 200:
                    # Используем progress.console.print чтобы не ломать бар
                    if progress:
                        progress.console.print(f"[red]Ошибка запроса: {response.status}[/red]")
                    break

                data = await response.json()

            if not data: break

            batch = data.get("events", [])
            all_events.extend(batch)
            
            # Обновляем прогресс бар
            if progress and task_id:
                current_len = min(len(all_events), max_events_to_search)
                progress.update(task_id, completed=current_len, description=f"🔎 Поиск событий: {keyword} ({current_len} found)")

            page += 1
        
        all_events = all_events[:max_events_to_search]
        return all_events
    
    except Exception as e:
        if progress:
            progress.console.print(f"[red]Критическая ошибка при выгрузке событий: {e}[/red]")
        return []


def scan_markets(events):
    """Извлечение рынков (без изменений логики, просто возврат)."""
    all_markets = []
    relevance_cache = {}
    for event in events:
        slug = event.get("slug")
        if slug:
            relevance_cache[slug] = True

        event_title = event.get("title", "Unknown Event")
        markets = event.get("markets", [])
        for m in markets:
            c_id = m.get("conditionId")
            if c_id:
                all_markets.append({
                    "event_title": event_title,
                    "market_question": m.get("question", m.get("slug", "Unknown")),
                    "condition_id": c_id
                })

    return all_markets, relevance_cache