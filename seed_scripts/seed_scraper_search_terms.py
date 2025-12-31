"""
Seed initial scraper search terms for development.

Populates scraper_search_terms with one row per platform storing a search_terms array
to match the Supabase schema.
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
            "terms": [
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
            "terms": [
                "accessibility",
                "assistive+device",
                "arthritis+grip",
                "adaptive+tool",
                "mobility+aid",
                "tremor+stabilizer",
                "adaptive+utensil",
            ],
        },
        {
            # Align with Supabase migration key
            "platform": "ravelry_pa_categories",
            "terms": [
                "medical-device-access",
                "medical-device-accessory",
                "mobility-aid-accessory",
                "other-accessibility",
                "adaptive",
                "therapy-aid",
            ],
        },
    ]

    for seed in seeds:
        platform = seed["platform"]
        terms = seed["terms"]
        
        try:
            existing = db.table("scraper_search_terms").select("platform").eq("platform", platform).limit(1).execute()

            payload = {"platform": platform, "search_terms": terms}
            if not existing.data:
                db.table("scraper_search_terms").insert(payload).execute()
                print(f"Seeded search terms for platform={platform}")
            else:
                db.table("scraper_search_terms").update({"search_terms": terms}).eq("platform", platform).execute()
                print(f"Updated search terms for platform={platform}")
        except Exception as e:
            print(f"Failed to seed scraper_search_terms for platform={platform}: {e}")


if __name__ == "__main__":
    main()

