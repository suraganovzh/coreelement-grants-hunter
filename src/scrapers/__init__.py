from src.scrapers.base_scraper import BaseScraper
from src.scrapers.grants_gov import GrantsGovScraper
from src.scrapers.sbir_scraper import SBIRScraper
from src.scrapers.foundation_scraper import FoundationScraper
from src.scrapers.eu_horizon import EUHorizonScraper
from src.scrapers.world_bank import WorldBankScraper
from src.scrapers.corporate_grants import CorporateGrantsScraper
from src.scrapers.kazakhstan_scraper import KazakhstanScraper

ALL_SCRAPERS = [
    GrantsGovScraper,
    SBIRScraper,
    FoundationScraper,
    EUHorizonScraper,
    WorldBankScraper,
    CorporateGrantsScraper,
    KazakhstanScraper,
]
