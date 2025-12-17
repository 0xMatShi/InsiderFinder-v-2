import aiohttp
import asyncio
from typing import Dict, Any, List

from src.utils.constants import DATA_URL, PROXIES
from src.utils.proxy_manager import get_headers_for_proxy
from src.utils.config_loader import load_config

if not PROXIES:
    PROXIES = [None] 

async def fetch_trade_page(session, url, params, proxy, retries=3):
    request_headers = get_headers_for_proxy(proxy)
    request_kwargs = {
        "params": params, "timeout": 10, "headers": request_headers, "proxy": proxy if proxy else None
    }
    
    for attempt in range(retries):
        try:
            async with session.get(url, **request_kwargs) as response:
                if response.status == 200:
                    try:
                        return await response.json()
                    except: return []
                elif response.status in [403, 429]:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    await asyncio.sleep(1)
        except Exception:
            await asyncio.sleep(1)
    return []


async def fetch_and_extract_wallets(session: aiohttp.ClientSession, markets: List[Dict[str, Any]], max_trades_per_market: int, progress=None, task_id=None):
    LIMIT = 500

    condition_ids = [m.get('condition_id') for m in markets]
    unique_wallets_set = set()
    
    for i, market_id in enumerate(condition_ids):
        # Обновляем описание прогресс бара
        if progress and task_id:
            progress.update(
                task_id, 
                description=f"📥 Сканирование рынков ({i+1}/{len(condition_ids)}) | Wallets: {len(unique_wallets_set)}",
                advance=0 # Пока не двигаем полоску, она сдвинется в конце итерации
            )

        base_offset = 0
        market_finished = False

        while not market_finished:
            tasks = []
            active_proxies = PROXIES if PROXIES else [None]

            for p_index, proxy in enumerate(active_proxies):
                current_offset = base_offset + (p_index * LIMIT)
                params = {"market": market_id, "limit": LIMIT, "offset": current_offset, "takerOnly": "false"}
                
                task = asyncio.create_task(fetch_trade_page(session, f"{DATA_URL}/trades", params, proxy))
                tasks.append(task)

            results = await asyncio.gather(*tasks)
            
            for idx, data in enumerate(results):
                if not data:
                    if idx == 0 and len(results) > 1: market_finished = True
                else:
                    count = len(data)
                    for trade in data:
                        w = trade.get('proxyWallet')
                        if w: unique_wallets_set.add(w)
                    
                    if count < LIMIT: market_finished = True

            if not market_finished:
                base_offset += (len(active_proxies) * LIMIT)
                if base_offset >= max_trades_per_market: break
        
        # Сдвигаем прогресс на 1 рынок
        if progress and task_id:
            progress.advance(task_id, 1)

    return list(unique_wallets_set)