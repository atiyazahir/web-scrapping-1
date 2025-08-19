import asyncio
import pandas as pd
from urllib.parse import urlencode
from playwright.async_api import async_playwright

# ------------ CONFIGURE YOUR SEARCH ------------
CITY = "Lahore"            # e.g., "Lahore", "Dubai", "London"
CHECK_IN = "2025-09-10"    # YYYY-MM-DD
CHECK_OUT = "2025-09-12"   # YYYY-MM-DD
ADULTS = 2
ROOMS = 1
CHILDREN = 0
MAX_PAGES = 2              # how many pages to scrape
OUT_CSV = "booking_results.csv"
# ------------------------------------------------

def build_search_url():
    """Build Booking.com search URL"""
    params = {
        "ss": CITY,
        "checkin_year": CHECK_IN.split("-")[0],
        "checkin_month": CHECK_IN.split("-")[1],
        "checkin_monthday": CHECK_IN.split("-")[2],
        "checkout_year": CHECK_OUT.split("-")[0],
        "checkout_month": CHECK_OUT.split("-")[1],
        "checkout_monthday": CHECK_OUT.split("-")[2],
        "group_adults": ADULTS,
        "no_rooms": ROOMS,
        "group_children": CHILDREN,
        "order": "price"  # order by price
    }
    return f"https://www.booking.com/searchresults.html?{urlencode(params)}"

async def scrape_page(page):
    """Scrape hotels from one page"""
    # Wait for page to load fully
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(5)  # extra wait for content to render

    # Try multiple selectors (Booking changes often)
    selectors = ['[data-testid="property-card"]', '.sr_property_block']
    cards = []
    for sel in selectors:
        try:
            if await page.locator(sel).count() > 0:
                cards = await page.locator(sel).all()
                break
        except:
            pass

    if not cards:
        print("⚠️ No hotel cards found on this page (maybe CAPTCHA or UI change).")
        return []

    results = []
    for card in cards:
        # Hotel name
        name = None
        if await card.locator('[data-testid="title"]').count():
            name = await card.locator('[data-testid="title"]').first.text_content()
        elif await card.locator('.sr-hotel__name').count():
            name = await card.locator('.sr-hotel__name').first.text_content()
        if name:
            name = name.strip()

        # Hotel link
        href = None
        if await card.locator('a[data-testid="title-link"]').count():
            href = await card.locator('a[data-testid="title-link"]').first.get_attribute("href")
        elif await card.locator('.sr-hotel__title a').count():
            href = await card.locator('.sr-hotel__title a').first.get_attribute("href")

        # Review score
        score = None
        if await card.locator('[data-testid="review-score"]').count():
            score = await card.locator('[data-testid="review-score"]').first.text_content()
        elif await card.locator('.bui-review-score__badge').count():
            score = await card.locator('.bui-review-score__badge').first.text_content()
        if score:
            score = score.strip()

        # Price
        price = None
        if await card.locator('[data-testid="price-and-discounted-price"]').count():
            price = await card.locator('[data-testid="price-and-discounted-price"]').first.text_content()
        elif await card.locator('.bui-price-display__value').count():
            price = await card.locator('.bui-price-display__value').first.text_content()
        if price:
            price = price.strip()

        if name:
            results.append({
                "name": name,
                "score": score,
                "price": price,
                "link": href
            })

    return results

async def click_next(page):
    """Go to next page if available"""
    if await page.locator('button[aria-label="Next page"]').count():
        next_btn = page.locator('button[aria-label="Next page"]').first
        disabled = await next_btn.get_attribute("aria-disabled")
        if disabled == "true":
            return False
        await next_btn.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        return True
    return False

async def main():
    url = build_search_url()
    print(f"🔎 Search URL: {url}")

    async with async_playwright() as pw:
        # Run in visible mode so you can debug
        browser = await pw.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle")

        all_hotels = []

        for p in range(1, MAX_PAGES + 1):
            print(f"📄 Scraping page {p}...")
            hotels = await scrape_page(page)
            print(f"✅ Found {len(hotels)} hotels")
            all_hotels.extend(hotels)

            if p < MAX_PAGES:
                moved = await click_next(page)
                if not moved:
                    break

        await browser.close()

    # Save results
    if all_hotels:
        df = pd.DataFrame(all_hotels)
        df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
        print(f"💾 Saved {len(df)} hotels to {OUT_CSV}")
    else:
        print("⚠️ No hotels scraped. Maybe blocked or wrong selectors.")

if __name__ == "__main__":
    asyncio.run(main())