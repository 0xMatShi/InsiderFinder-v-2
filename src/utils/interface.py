import os
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TimeElapsedColumn,
    TaskProgressColumn,
    MofNCompleteColumn
)
from rich.table import Table
from rich.panel import Panel

# --- ИСПРАВЛЕНИЕ 1: Принудительная настройка консоли ---
# force_terminal=True заставляет Rich верить, что это умный терминал.
# soft_wrap=False предотвращает случайные переносы строк, ломающие курсор.
console = Console(force_terminal=True, soft_wrap=False)

def clear_console():
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    clear_console()
    title = "[bold magenta]PolyMarket Wallet Analyzer[/bold magenta]"
    subtitle = "[dim cyan]Advanced scraping & filtering tool[/dim cyan]"
    console.print(Panel(f"{title}\n{subtitle}", expand=False))

def create_progress():
    """
    Создает объект Progress.
    ИСПРАВЛЕНИЕ 2: redirect_stdout=False и redirect_stderr=False.
    Это запрещает прогресс-бару пытаться ловить чужой вывод, из-за чего он часто делает 'лесенку'.
    ИСПРАВЛЕНИЕ 3: bar_width=40. Фиксируем ширину, чтобы бар не скакал при изменении текста.
    """
    return Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40), # Фиксируем ширину
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
        redirect_stdout=False, # ВАЖНО: Не перехватывать принты
        redirect_stderr=False, # ВАЖНО: Не перехватывать ошибки
        refresh_per_second=10  # Ограничиваем частоту перерисовки (10 FPS достаточно)
    )

def print_summary_table(wallets_data):
    """Выводит красивую таблицу с результатами."""
    if not wallets_data:
        console.print("[yellow]Нет данных для отображения таблицы.[/yellow]")
        return

    table = Table(title="💎 Результаты фильтрации", show_header=True, header_style="bold magenta")
    
    table.add_column("Wallet", style="cyan", no_wrap=True)
    table.add_column("Traded", justify="center")
    table.add_column("Active Pos", justify="center")
    table.add_column("PnL ($)", justify="right", style="green")

    for w in wallets_data:
        pnl = w.get('realized_pnl')
        pnl_str = f"${pnl:.2f}" if pnl is not None else "N/A"
        
        table.add_row(
            w.get('wallet', 'Unknown'),
            str(w.get('total_predictions', 0)),
            str(w.get('active_predictions', 0)),
            pnl_str
        )

    console.print(table)