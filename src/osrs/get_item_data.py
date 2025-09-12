#!/usr/bin/env python3

import requests, json
from pathlib import Path
from src.util.independant_logger import Logger

FILE_PATH = Path(__file__).resolve()
OSRS_DIR = FILE_PATH.parent
ROOT_DIR = OSRS_DIR.parent.parent

ENDPOINTS = {
    'latest_prices': 'https://prices.runescape.wiki/api/v1/osrs/latest',
    '5min_prices': 'https://prices.runescape.wiki/api/v1/osrs/5m',
    '1h_prices': 'https://prices.runescape.wiki/api/v1/osrs/1h',
    'timeseries': 'https://prices.runescape.wiki/api/v1/osrs/timeseries',
    'mapping': 'https://prices.runescape.wiki/api/v1/osrs/mapping', 
}

with open(ROOT_DIR / 'conf' / 'osrs_item_ids.json', 'r', encoding='utf-8') as f:
    HEADERS = json.load(f)
if not HEADERS.get('User-Agent'):
    raise ValueError("User-Agent not found in osrs_item_ids.json")

class WikiDataGetter:
    def __init__(self, headers: dict = HEADERS):
        self.log = Logger(name="WikiDataGetter", log_file=ROOT_DIR / "logs" / "wiki_data_getter.log")
        self.headers = headers
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.log.debug(f"WikiDataGetter initialized with headers: {self.headers}.")

    def get_data(self, endpoint: str, id: int = None, timestamp: int = None) -> dict:
        """
        Retrieves data from the specified OSRS Wiki Prices API endpoint. 
        https://oldschool.runescape.wiki/w/RuneScape:Real-time_Prices
        
        ## Endpoints:
        - 'latest_prices': Latest item prices.
        - '5min_prices': 5-minute average item prices.
        - '1h_prices': 1-hour average item prices.
        - 'timeseries': Historical price data for items.
        - 'mapping': Item ID to name mapping.
        Args:
            endpoint (str): The key of the endpoint to retrieve data from. Must be one of the keys in the ENDPOINTS dictionary.
        Returns:
            dict: The JSON response from the API as a dictionary.
        """
        self.log.info(f"Fetching data from endpoint: {endpoint} with id: {id} and timestamp: {timestamp}")
        if endpoint not in ENDPOINTS:
            self.log.error(f"Invalid endpoint: {endpoint}")
            raise ValueError(f"Invalid endpoint: {endpoint}")
        
        params = {}
        if id is not None:
            params['id'] = id
        if timestamp is not None:
            params['timestamp'] = timestamp

        try:
            response = self.session.get(ENDPOINTS[endpoint], params=params)
            response.raise_for_status()
            self.log.info(f"Data fetched successfully from {endpoint}, code: {response.status_code}")
            return response.json()
        except requests.RequestException as e:
            self.log.error(f"Error fetching data from {endpoint}: {e}")
            return {}
