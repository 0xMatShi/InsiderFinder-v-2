import sys
import aiohttp

# Импортируем console из interface
from src.utils.interface import print_banner, create_progress, print_summary_table, console
from src.utils.constants import PROXIES
from src.utils.proxy_manager import load_and_assign_uas
from src.utils.config_loader import load_config
from src.utils.export_excel import save_wallets_to_excel

from src.core.scan_keyword import scan_events, scan_markets
from src.core.scan_trades import fetch_and_extract_wallets
from src.core.scan_wallets import filter_wallets


async def start():
    print_banner()

    if PROXIES:
        load_and_assign_uas(PROXIES)
    else:
        console.print("[yellow]⚠️ Прокси не заданы, будут использоваться дефолтные заголовки.[/yellow]")

    config = load_config()
    max_events_to_search = config.get("max_events_to_search", 50)
    max_trades_per_market = config.get("max_trades_per_market", 50000)

    parsed = False

    while not parsed:
        console.print()
        kw = console.input("[bold green]🎯 Введите ключевое слово (e.g. 'trump', 'crypto'): [/bold green]")
        if not kw:
            console.print("[red]❌ Требуется ключевое слово.[/red]")
            continue
        
        connector = aiohttp.TCPConnector(limit=200, ttl_dns_cache=300)

        async with aiohttp.ClientSession(connector=connector) as session:
            
            # --- PHASE 1: SEARCH & FETCH ---
            with create_progress() as progress:
                
                # 1. Events
                task_events = progress.add_task(f"🔎 Поиск событий '{kw}'...", total=max_events_to_search)
                events = await scan_events(
                    session=session,
                    keyword=kw, 
                    max_events_to_search=max_events_to_search,
                    progress=progress,
                    task_id=task_events
                )
                
                found_count = len(events) if events else 0
                progress.update(task_events, completed=found_count, total=found_count, description=f"✅ Поиск завершен ({found_count} найдено)")

                if not events:
                    progress.console.print("[yellow]⚠️ События не найдены.[/yellow]")
                    parsed = True
                    continue

                # ИЗМЕНЕНИЕ: Получаем кэш слагов
                markets, initial_slugs_cache = scan_markets(events)
                
                # 2. Trades -> Wallets
                task_trades = progress.add_task("📥 Сбор кошельков из рынков...", total=len(markets))
                wallets = await fetch_and_extract_wallets(
                    session=session, 
                    markets=markets, 
                    max_trades_per_market=max_trades_per_market,
                    progress=progress,
                    task_id=task_trades
                )

            if not wallets:
                console.print("[red]❌ Не найдено ни одного уникального кошелька.[/red]")
                parsed = True
                continue

            # --- PHASE 2: FILTERING ---
            
            # ВЫВОДИМ ИНФО О ФИЛЬТРАХ
            min_pnl = config.get("realized_pnl")
            pnl_txt = f" | PnL > ${min_pnl}" if min_pnl else ""
            
            target_pct = config.get("target_keyword_percent", 0.0)
            pct_txt = f" | KW Match > {int(target_pct*100)}%" if target_pct > 0 else ""

            info_text = (
                f"[dim]⚙️ Критерии: Активность {config.get('last_active_trade')} | "
                f"Рынки {config.get('min_predictions')}-{config.get('max_predictions')} | "
                f"Позиции <{config.get('current_positions')}{pnl_txt}{pct_txt}[/dim]"
            )
            console.print(info_text)

            with create_progress() as progress:
                # 3. Filtering
                task_filter = progress.add_task("🕵️ Фильтрация кошельков...", total=len(wallets))
                
                filtered_data = await filter_wallets(
                    session=session, 
                    wallets=wallets, 
                    config=config,
                    progress=progress,
                    task_id=task_filter,
                    keyword=kw,
                    known_related_slugs=initial_slugs_cache  # Передаем кэш
                )

            # --- PHASE 3: RESULTS ---
            if not filtered_data:
                console.print("[red]❌ Ни один кошелек не прошел фильтрацию.[/red]")
            else:
                print_summary_table(filtered_data)
                save_wallets_to_excel(filtered_data)

            parsed = True

    console.input("\nНажмите [bold]Enter[/bold], чтобы выйти...")