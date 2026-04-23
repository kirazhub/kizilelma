"""Manuel duman testi: gerçek API'leri çağır ve sonuçları yazdır.

KULLANIM:
    python scripts/smoke_test.py

Bu script gerçek TEFAS ve haber kaynaklarına bağlanır.
İnternet bağlantısı gerekir.
"""
import asyncio
from kizilelma.collectors.tefas import TefasCollector
from kizilelma.collectors.news import NewsCollector


async def main():
    print("=== TEFAS testi ===")
    try:
        tefas = TefasCollector()
        funds = await tefas.fetch()
        print(f"  ✓ {len(funds)} fon çekildi")
        if funds:
            print(f"  Örnek: {funds[0].code} - {funds[0].name} - {funds[0].price}")
    except Exception as exc:
        print(f"  ✗ TEFAS hatası: {exc}")

    print("\n=== Haberler testi ===")
    try:
        news = NewsCollector()
        items = await news.fetch()
        print(f"  ✓ {len(items)} haber çekildi")
        if items:
            print(f"  Örnek: [{items[0].source}] {items[0].title}")
    except Exception as exc:
        print(f"  ✗ Haberler hatası: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
