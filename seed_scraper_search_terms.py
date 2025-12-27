"""
Seed initial scraper search terms for development.

Creates a default row for the GitHub platform in the unified database adapter
so dev (SQLite) and Supabase can both read/write search terms consistently.
"""
from config import get_settings
from database_adapter import DatabaseAdapter


def main():
    settings = get_settings()
    db = DatabaseAdapter(settings)
    db.init()

    seeds = [
        {
            "platform": "github",
            "search_terms": [
                "assistive technology",
                "screen reader",
                "eye tracking",
                "speech recognition",
                "switch access",
                "alternative input",
                "text-to-speech",
                "voice control",
                "accessibility aid",
                "mobility aid software",
            ],
        },
        {
            "platform": "thingiverse",
            "search_terms": [
                "accessibility",
                "assistive device",
                "arthritis grip",
                "adaptive tool",
                "mobility aid",
                "tremor stabilizer",
                "adaptive utensil",
            ],
        },
        {
            "platform": "ravelry_pa_categories",
            "search_terms": [
                "medical-device-access",
                "medical-device-accessory",
                "mobility-aid-accessor",
                "other-accessibility",
                "therapy-aid",
            ],
        },
    ]

    for seed in seeds:
        try:
            existing = db.table("scraper_search_terms").select("platform,search_terms").eq("platform", seed["platform"]).limit(1).execute()
            if not existing.data:
                db.table("scraper_search_terms").upsert(seed).execute()
                print(f"Seeded scraper_search_terms for platform={seed['platform']}")
            else:
                print(f"scraper_search_terms already seeded for platform={seed['platform']}")
        except Exception as e:
            print(f"Failed to seed scraper_search_terms for platform={seed['platform']}: {e}")


if __name__ == "__main__":
    main()
