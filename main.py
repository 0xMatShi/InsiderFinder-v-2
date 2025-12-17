import asyncio
from src.pipeline import start
from src.utils.interface import clear_console


async def main():
    clear_console()

    await start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        clear_console()
        print("Программа завершена пользователем")
