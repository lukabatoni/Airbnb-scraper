from .scraper import AirbnbScraper

if __name__ == "__main__":
    scraper = AirbnbScraper()
    scraper.scrape()