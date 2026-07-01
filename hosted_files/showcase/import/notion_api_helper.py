#!/usr/bin/env python3
# Aria Corona Jan 29th, 2025
# Notion API Helper
# This script provides a class that interacts with the Notion API. It includes functionalities to query, retrieve and update databases, retrieve pages and properties, create and update pages, and generate property dictionaries for Notion API requests.


import requests, time, json, logging


class NotionApiHelper:
    """
    NotionApiHelper is a class that provides methods to interact with the Notion API. It includes functionalities to query databases, retrieve pages and properties, create and update pages, and handle various property types.
    Attributes:
        MAX_RETRIES (int): Maximum number of retries for network requests.
        RETRY_DELAY (int): Delay between retries in seconds.
        TIMEOUT (int): Timeout for network requests in seconds.
        PAGE_SIZE (int): Default page size for queries.
        ENDPOINT (str): Base URL for the Notion API.
        counter (int): Counter for tracking retries.
    Methods:
        __init__(header_path='src/headers.json'):
            Initializes the NotionApiHelper instance with headers from a JSON file.
        query(databaseID, filter_properties=None, content_filter=None, page_num=None):
            Sends a POST request to query a Notion database and returns the results.
        _make_query_request(databaseID, filter_properties, bodyJson):
            Makes a POST request to the Notion API to query a database.

        get_page(pageID):
            Sends a GET request to retrieve a Notion page.
        get_page_property(pageID, propID):
            Sends a GET request to retrieve a property of a Notion page.
        get_url_property(url, propID):
            Fetches a JSON response from a given URL.
        create_page(databaseID, properties):
            Sends a POST request to create a new page in a Notion database.
        update_page(pageID, properties, trash=False):
            Sends a PATCH request to update a Notion page.
        append_block_children(parent_id, children):
            Appends child blocks to a specified Notion block.
        create_page_comment(page_id, rich_text, display_name=None):
            Creates a comment on a specified Notion page.
        get_database(db_id):
            Retrieves a database from the Notion API.
        update_database(db_id, property_package={}, title=None, description=None):
            Updates a Notion database with the provided properties, title, and description

        simple_prop_gen(prop_name, prop_type, prop_value):
            Generates a simple property dictionary.
        selstat_prop_gen(prop_name, prop_type, prop_value):
            Generates a property dictionary for select and multi-select properties.
        date_prop_gen(prop_name, prop_type, prop_value, prop_value2):
            Generates a property dictionary for date properties.
        files_prop_gen(prop_name, prop_type, file_names, file_urls):
            Generates a property dictionary for files with given names and URLs.
        mulsel_prop_gen(prop_name, prop_type, prop_values):
            Generates a property dictionary for multi-select properties.
        relation_prop_gen(prop_name, prop_type, prop_values):
            Generates a property dictionary for relation properties.
        people_prop_gen(prop_name, prop_type, prop_value):
            Generates a property dictionary for people properties.
        rich_text_prop_gen(prop_name, prop_type, prop_value, prop_value_link=None, annotation=None):
            Generates a property dictionary for rich text properties.
        title_prop_gen(prop_name, prop_type, prop_value, prop_value_link=None, annotation=None):
            Generates a property dictionary for title properties.
        generate_property_body(prop_name, prop_type, prop_value, prop_value2=None, annotation=None):
            Generates a property dictionary based on the property type.
        return_property_value(property, id=None):
            Returns the value of a property based on the property type.
    """

    MAX_RETRIES = 5
    RETRY_DELAY = 3  # seconds
    TIMEOUT = 120
    PAGE_SIZE = 100

    def __init__(self, header_path="src/headers.json"):
        with open(header_path, "r") as file:
            self.headers = json.load(file)

        self.ENDPOINT = "https://api.notion.com/v1"
        self.counter = 0

    def query(
        self, databaseID, filter_properties=None, content_filter=None, page_num=None
    ):
        """
        Sends a post request to a specified Notion database, returning the response as a dictionary. Will return {} if the request fails.
        query(string, list(opt.), dict(opt.),int(opt.)) -> dict

            Args:
                databaseID (str): The ID of the Notion database.
                filter_properties (list): Filter properties as a list of strings. Optional.
                    Can be used to filter which page properties are returned in the response.
                    Example: ["%7ChE%7C", "NPnZ", "%3F%5BWr"]
                content_filter (dict): Content filter as a dictionary. Optional.
                    Can be used to filter pages based on the specified properties.
                    Example:
                        {
                            "and": [
                                {
                                    "property": "Job status",
                                    "select": {
                                        "does_not_equal": "Canceled"
                                    }
                                },
                                {
                                    "property": "Created",
                                    "date": {
                                        "past_week": {}
                                    }
                                }
                            ]
                        }
                page_num (int): The number of pages to retrieve. Optional.
                    If not specified, all pages will be retrieved.

            Returns:
                list of dictionary objects: The "results" of the JSON response from the Notion API. This will cut out the pagination information, returning only the page data.

        Additional information on content filters can be found at https://developers.notion.com/reference/post-database-query-filter#the-filter-object
        Additional information on Notion queries can be found at https://developers.notion.com/reference/post-database-query
        """

        databaseJson = {}
        get_all = page_num is None

        page_size = self.PAGE_SIZE if get_all else page_num

        bodyJson = (
            {"page_size": page_size, "filter": content_filter}
            if content_filter
            else {"page_size": page_size}
        )

        filter_properties = (
            "?filter_properties=" + "&filter_properties=".join(filter_properties)
            if filter_properties
            else ""
        )

        _logger.debug(f"Body JSON: {json.dumps(bodyJson, indent=4)}")

        databaseJson = self._make_query_request(databaseID, filter_properties, bodyJson)

        if not databaseJson:
            _logger.info("No data returned.")
            self.counter = 0
            return []

        results = databaseJson["results"]
        _logger.debug("Data returned.")

        while databaseJson["has_more"] and get_all:
            _logger.debug("More data available.")
            time.sleep(0.1)  # To avoid rate limiting
            _logger.debug("Querying next page...")

            if content_filter:
                bodyJson = {
                    "page_size": page_size,
                    "start_cursor": databaseJson["next_cursor"],
                    "filter": content_filter,
                }
            else:
                bodyJson = {
                    "page_size": page_size,
                    "start_cursor": databaseJson["next_cursor"],
                }

            new_data = self._make_query_request(databaseID, filter_properties, bodyJson)

            if not new_data:
                self.counter = 0
                return []

            databaseJson = new_data
            results.extend(databaseJson["results"])

        _logger.debug("All data retrieved, returning results.")
        self.counter = 0
        return results

    def _make_query_request(self, databaseID, filter_properties, bodyJson):
        """
        Makes a POST request to the Notion API to query a database. Used by the query method to handle pagination.

        Args:
            databaseID (str): The ID of the Notion database.
            filter_properties (str): Filter properties as a query string.
            bodyJson (dict): The JSON body of the request.

        Returns:
            dict: The JSON response from the Notion API.
        """

        try:
            _logger.debug("Sending post request.")
            _logger.info(
                f"{self.ENDPOINT}/databases/{databaseID}/query{filter_properties}"
            )
            response = requests.post(
                f"{self.ENDPOINT}/databases/{databaseID}/query{filter_properties}",
                headers=self.headers,
                json=bodyJson,
                timeout=self.TIMEOUT,
            )
            _logger.info(response.status_code)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self._make_query_request(databaseID, filter_properties, bodyJson)

            else:
                _logger.error(f"Network error occurred too many times: {e}")
                return {}

        except requests.exceptions.Timeout as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Timeout occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self._make_query_request(databaseID, filter_properties, bodyJson)

            else:
                _logger.error(f"Timeout occurred too many times: {e}")
                return {}

        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP error occurred: {e}", exc_info=True)
            _logger.error("Check the database ID and try again.")
            time.sleep(1)
            self.counter = 0
            return {}

    def get_page(self, pageID):
        """
        Sends a get request to a specified Notion page, returning the response as a dictionary. Will return {} if the request fails.
        Relation properties are capped at 25 items, and will return a truncated list if the relation has more than 25 items. This is a limitation of the Notion API.
            Use the get_page_property method to retrieve the full list of relation items.

        get_object(string) -> dict

            Args:
                databaseID (str): The ID of the Notion database.

            Returns:
                dict: The JSON response from the Notion API.
        """

        try:
            time.sleep(0.1)  # To avoid rate limiting
            _logger.debug(f"{self.ENDPOINT}/pages/{pageID}")
            response = requests.get(
                f"{self.ENDPOINT}/pages/{pageID}",
                headers=self.headers,
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            self.counter = 0
            return response.json()

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_page(pageID)

            else:
                _logger.error(f"Network error occurred too many times: {e}")
                self.counter = 0
                return {}

        except requests.exceptions.Timeout as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Timeout occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_page(pageID)

            else:
                _logger.error(f"Timeout occurred too many times: {e}")
                self.counter = 0
                return {}

        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP error occurred: {e}", exc_info=True)
            _logger.error("Check the database ID and try again.")
            time.sleep(1)
            self.counter = 0
            return {}

    def get_page_property(self, pageID, propID, page_size=100):
        """
        Sends a get request to a specified Notion page property, returning the response as a JSON property item object. Will return {} if the request fails.
        https://developers.notion.com/reference/property-item-object

        get_object(string) -> dict

            Args:
                pageID (str): The ID of the Notion database.
                propID (str): The ID of the property to retrieve.

            Returns:
                dict: The JSON response from the Notion API.
        """

        try:
            time.sleep(0.5)  # To avoid rate limiting
            _logger.info(f"{self.ENDPOINT}/pages/{pageID}/properties/{propID}")
            _logger.info(f"Page size: {page_size}")
            response = requests.get(
                f"{self.ENDPOINT}/pages/{pageID}/properties/{propID}",
                headers=self.headers,
                timeout=self.TIMEOUT,
                params={"page_size": page_size},
            )
            _logger.info(response.status_code)
            response.raise_for_status()
            self.counter = 0
            return response.json()

        except requests.exceptions.HTTPError as e:
            if response.status_code == 404:
                _logger.error(f"Property not found: {e}")
                return {}
            elif response.status_code >= 500 and self.counter < self.MAX_RETRIES:
                _logger.error(f"Server Error: {response.status_code}. Retrying ...")
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_page_property(pageID, propID)
            elif response.status_code >= 500 and self.counter >= self.MAX_RETRIES:
                _logger.error(
                    f"Server Error: {response.status_code}. Too many retries. Querying DB if relation property."
                )
                page = self.get_page(pageID)
                db_id = page["parent"]["database_id"]
                db_schema = self.get_database(db_id)
                properties = db_schema["properties"]

                for key, value in properties.items():
                    if value["id"] == propID:
                        if value["type"] != "relation":
                            break

                        _logger.info(
                            "Relation property found. Attempting to query db ..."
                        )
                        relational_db = value["relation"]["database_id"].replace(
                            "-", ""
                        )

                        _logger.info(json.dumps(value, indent=4))

                        relation_type = value["relation"]["type"]

                        if value["relation"][relation_type]:

                            try:
                                synced_property_name = value["relation"][relation_type][
                                    "synced_property_name"
                                ]
                                synced_property_id = value["relation"][relation_type][
                                    "synced_property_id"
                                ]
                            except Exception as e:
                                _logger.error(
                                    "Dual property not found. Returning empty dictionary. Error: {e}"
                                )
                                return {}

                            query_filter = {
                                "property": synced_property_name,
                                "relation": {"contains": pageID},
                            }

                            response = self.query(
                                relational_db, content_filter=query_filter
                            )

                            results = {
                                "results": [
                                    {
                                        "object": "property_item",
                                        "type": "relation",
                                        "id": synced_property_id,
                                        "relation": {"id": page[id]},
                                    }
                                    for page in response
                                ]
                            }

                            fake_response = {
                                "object": "list",
                                "results": results,
                                "next_cusror": None,
                                "has_more": False,
                                "type": "property_item",
                                "property_item": {
                                    "id": propID,
                                    "next_url": None,
                                    "type": "relation",
                                    "relation": {},
                                },
                                "request_id": "fake_request_id",
                            }

                            _logger.debug(json.dumps(fake_response))

                            return fake_response

                        else:
                            _logger.error(
                                "No dual property found. Returning empty dictionary."
                            )
                            return {}

                return {}

            else:
                _logger.error(f"HTTP error occurred: {e}", exc_info=True)
                _logger.error("Check the database ID and try again.")
                time.sleep(1)
                self.counter = 0
                return {}

        except requests.exceptions.Timeout as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Timeout occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_page_property(pageID, propID)

            else:
                _logger.error(f"Timeout occurred too many times: {e}")
                time.sleep(3)
                self.counter = 0
                return {}

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_page_property(pageID, propID)

            else:
                _logger.error(f"Network error occurred too many times: {e}")
                time.sleep(3)
                self.counter = 0
                return {}

    def get_url_property(self, url, propID):
        """
        Fetches a JSON response from a given URL and returns the parsed JSON data.
        Args:
            url (str): The URL to fetch the JSON data from.
            propID (str): The property ID to be used in the request (currently unused in the function).
        Returns:
            dict: The parsed JSON data from the response if the request is successful.
                  An empty dictionary if the request fails after the maximum number of retries.
        Raises:
            requests.exceptions.RequestException: If the request fails due to network-related errors.
        """

        try:
            time.sleep(0.1)  # To avoid rate limiting
            _logger.info(f"{url}")

            response = requests.get(url, headers=self.headers, timeout=self.TIMEOUT)

            _logger.info(response.status_code)
            response.raise_for_status()

            self.counter = 0

            return response.json()

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_url_property(url, propID)
            else:
                _logger.error(f"Network error occurred too many times: {e}")
                time.sleep(3)
                self.counter = 0
                return {}

        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP error occurred: {e}", exc_info=True)

            if response.status_code >= 500 and self.counter < self.MAX_RETRIES:
                _logger.error(f"Server Error: {response.status_code}. Retrying ...")
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_url_property(url, propID)
            else:
                _logger.error("Check the database ID and try again.")
                self.counter = 0
                return {}

    def create_page(
        self, databaseID, properties
    ):  # Will update to allow icon and cover images later.
        """
        Sends a post request to a specified Notion database, creating a new page with the specified properties. Returns the response as a dictionary. Will return {} if the request fails.

        create_page(string, dict) -> dict

            Args:
                databaseID (str): The ID of the Notion database.
                properties (dict): The properties of the new page as a dictionary.

            Returns:
                dict: The dictionary response from the Notion API.
        """

        jsonBody = {"parent": {"database_id": databaseID}, "properties": properties}

        try:
            _logger.info(f"post {self.ENDPOINT}/pages")
            # _logger.info(json.dumps(jsonBody, indent=4))
            response = requests.post(
                f"{self.ENDPOINT}/pages",
                headers=self.headers,
                json=jsonBody,
                timeout=self.TIMEOUT,
            )
            _logger.info(response.status_code)
            _logger.debug(response.json())
            response.raise_for_status()
            self.counter = 0
            return response.json()

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e} {response}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.create_page(databaseID, properties)

            else:
                _logger.error(f"Network error occurred too many times: {e}")
                time.sleep(3)
                self.counter = 0
                return {}

        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP error occurred: {e}", exc_info=True)
            _logger.error("Check the database ID and try again.")
            time.sleep(1)
            self.counter = 0
            return {}

    def update_page(
        self, pageID, properties: dict = None, trash: bool = False
    ):  # Will update to allow icon and cover images later.
        """
        Sends a patch request to a specified Notion page, updating the page with the specified properties. Returns the response as a dictionary. Will return {} if the request errors out.
        Page property keys can be either the property name or property ID.

        update_page(string, dict) -> dict
            Args:
                pageID (str): The ID of the Notion page.
                properties (dict): The properties of the page as a dictionary.
                trash (bool): Optional. If True, the page will be moved to the trash. Default is False.

            Returns:
                dict: The dictionary response from the Notion API.
        """
        if trash:
            jsonBody = {"archived": True}
        elif properties is not None:
            jsonBody = {"properties": properties}
        else:
            _logger.error("No properties provided to update.")
            return {}

        _logger.debug(json.dumps(jsonBody, indent=4))

        try:
            _logger.info("Sending patch request.")
            _logger.info(f"{self.ENDPOINT}/pages/{pageID}")

            response = requests.patch(
                f"{self.ENDPOINT}/pages/{pageID}",
                headers=self.headers,
                json=jsonBody,
                timeout=self.TIMEOUT,
            )
            _logger.info(response.status_code)
            _logger.debug(response.json())
            response.raise_for_status()
            self.counter = 0
            return response.json()

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                _logger.error(f"{response.json()}")
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.update_page(pageID, properties, trash)

            else:
                _logger.error(f"Network error occurred too many times: {e}")
                time.sleep(3)
                self.counter = 0
                return {}

        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP error occurred: {e}", exc_info=True)
            _logger.error("Check the database ID and try again.")
            time.sleep(1)
            self.counter = 0
            return {}

    def append_block_children(self, parent_id: str, children: list[dict]):
        """
        Appends child blocks to a specified Notion block.

        Args:
            block_id (str): The ID of the Notion block to which children will be appended.
            children (list of dict): A list of child block objects to append.

        Returns:
            dict: The JSON response from the Notion API if the request is successful.
                  An empty dictionary if the request fails after the maximum number of retries.
        """

        endpoint = f"{self.ENDPOINT}/blocks/{parent_id}/children"
        json_body = {"children": children}

        _logger.info(f"Appending children to block: {endpoint}")
        _logger.debug(json.dumps(json_body, indent=4))

        try:
            response = requests.patch(
                endpoint, headers=self.headers, json=json_body, timeout=self.TIMEOUT
            )
            response.raise_for_status()
            self.counter = 0
            return response.json()

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds.",
                    exc_info=True,
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.append_block_children(parent_id, children)

            else:
                _logger.error(
                    f"Network error occurred too many times: {e}", exc_info=True
                )
                self.counter = 0
                return {}

        except requests.exceptions.Timeout as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Timeout occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.append_block_children(parent_id, children)

            else:
                _logger.error(f"Timeout occurred too many times: {e}", exc_info=True)
                time.sleep(3)
                self.counter = 0
                return {}

    def get_page_comments(
        self, page_id: str, start_cursor: str = None, page_size: int = 100
    ):
        """
        Retrieves all comments for a specified Notion page with automatic pagination.

        Args:
            page_id (str): The ID of the Notion page.
            start_cursor (str, optional): The cursor for pagination. Defaults to None.
            page_size (int, optional): The number of comments to retrieve per request. Defaults to 100.

        Returns:
            dict: The JSON response from the Notion API containing all comments.
                  Returns a dict with "results" containing accumulated comments.
                  An empty dictionary if the request fails after the maximum number of retries.

        Example:
            >>> notion = NotionApiHelper()
            >>> comments = notion.get_page_comments("abc123")
            >>> for comment in comments.get("results", []):
            ...     print(comment)
        """
        endpoint = f"{self.ENDPOINT}/comments"
        params = {"block_id": page_id, "page_size": page_size}
        if start_cursor:
            params["start_cursor"] = start_cursor
        _logger.info(f"Retrieving comments for page: {page_id}")

        try:
            time.sleep(0.1)  # To avoid rate limiting
            response = requests.get(
                endpoint,
                headers=self.headers,
                params=params,
                timeout=self.TIMEOUT,
            )
            _logger.info(response.status_code)
            response.raise_for_status()
            response_json = response.json()

            # Accumulate all results if pagination is needed
            all_results = response_json.get("results", [])

            # Continue fetching if there are more pages
            while response_json.get("has_more"):
                _logger.debug("More comments available, fetching next page...")
                time.sleep(0.1)  # To avoid rate limiting

                params["start_cursor"] = response_json["next_cursor"]
                response = requests.get(
                    endpoint,
                    headers=self.headers,
                    params=params,
                    timeout=self.TIMEOUT,
                )
                response.raise_for_status()
                response_json = response.json()
                all_results.extend(response_json.get("results", []))

            _logger.debug(f"All comments retrieved. Total: {len(all_results)}")
            self.counter = 0

            # Return in the same format as the original response
            return {"results": all_results, "has_more": False, "next_cursor": None}

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_page_comments(page_id, start_cursor, page_size)

            else:
                _logger.error(f"Network error occurred too many times: {e}")
                self.counter = 0
                return {}

        except requests.exceptions.Timeout as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Timeout occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_page_comments(page_id, start_cursor, page_size)

            else:
                _logger.error(f"Timeout occurred too many times: {e}")
                self.counter = 0
                return {}

        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP error occurred: {e}", exc_info=True)
            _logger.error("Check the page ID and try again.")
            time.sleep(1)
            self.counter = 0
            return {}

    def create_page_comment(self, page_id, rich_text, display_name=None):
        """
        Creates a comment on a specified Notion page.

        Args:
            page_id (str): The ID of the Notion page to comment on.
            rich_text (str): The text content of the comment.
            display_name (str, optional): The display name to show for the comment author.
                                         If not provided, uses the default from the integration.

        Returns:
            dict: The JSON response from the Notion API if the request is successful.
                  An empty dictionary if the request fails after the maximum number of retries.

        Example:
            >>> notion = NotionApiHelper()
            >>> response = notion.create_page_comment("abc123", "This is a comment", "Bot Name")
        """

        endpoint = f"{self.ENDPOINT}/comments"

        # Build the rich_text array for the comment
        rich_text_array = [{"text": {"content": rich_text}}]

        # Build the request body
        json_body = {"parent": {"page_id": page_id}, "rich_text": rich_text_array}

        # Add display_name if provided
        if display_name:
            json_body["display_name"] = {
                "type": "integration",
                "resolved_name": display_name,
            }

        _logger.info(f"Creating comment on page: {page_id}")
        _logger.debug(json.dumps(json_body, indent=4))

        try:
            response = requests.post(
                endpoint, headers=self.headers, json=json_body, timeout=self.TIMEOUT
            )
            _logger.info(response.status_code)
            response.raise_for_status()
            self.counter = 0
            return response.json()

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds.",
                    exc_info=True,
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.create_page_comment(page_id, rich_text, display_name)
            else:
                _logger.error(
                    f"Network error occurred too many times: {e}", exc_info=True
                )
                self.counter = 0
                return {}

        except requests.exceptions.Timeout as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Timeout occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.create_page_comment(page_id, rich_text, display_name)
            else:
                _logger.error(f"Timeout occurred too many times: {e}", exc_info=True)
                time.sleep(3)
                self.counter = 0
                return {}

        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP error occurred: {e}", exc_info=True)
            _logger.error("Check the page ID and try again.")
            time.sleep(1)
            self.counter = 0
            return {}

    def get_database(self, db_id):
        """
        Retrieves a database from the Notion API using the provided database ID.
        Args:
            db_id (str): The ID of the database to retrieve.
        Returns:
            dict: The JSON response from the Notion API if the request is successful.
                  An empty dictionary if the request fails after the maximum number of retries.
        Raises:
            requests.exceptions.RequestException: If a network-related error occurs.
            requests.exceptions.Timeout: If the request times out.
        Logs:
            Info: Logs the full endpoint URL and the response status code.
            Error: Logs network errors and timeouts, including retry attempts.
        """

        full_endpoint = f"{self.ENDPOINT}/databases/{db_id}"

        _logger.info(f"Getting database: {full_endpoint}")

        try:
            response = requests.get(
                full_endpoint, headers=self.headers, timeout=self.TIMEOUT
            )
            _logger.info(response.status_code)
            response.raise_for_status()

        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_database(db_id)

            else:
                _logger.error(
                    f"Network error occurred too many times: {e}", exc_info=True
                )
                self.counter = 0
                return {}

        except requests.exceptions.Timeout as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Timeout occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.get_database(db_id)

            else:
                _logger.error(f"Timeout occurred too many times: {e}", exc_info=True)
                time.sleep(3)
                self.counter = 0
                return {}

        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP error occurred: {e}", exc_info=True)
            _logger.error("Check the database ID and try again.")
            time.sleep(1)
            self.counter = 0
            return {}

        self.counter = 0
        return response.json()

    def update_database(self, db_id, property_package={}, title=None, description=None):
        """
        Updates a Notion database with the provided properties, title, and description.
        Args:
            db_id (str): The ID of the Notion database to update.
            property_package (dict, optional): A dictionary containing the properties to update in the database. Defaults to an empty dictionary.
                https://developers.notion.com/reference/property-schema-object
            title (str, optional): The new title for the database. Defaults to None.
            description (str, optional): The new description for the database. Defaults to None.
        Returns:
            dict: The JSON response from the Notion API if the update is successful.
            If a network error or timeout occurs and the maximum number of retries is reached, an empty dictionary is returned.
            If an HTTP error occurs, an empty dictionary is returned.
        Raises:
            requests.exceptions.RequestException: If a network error occurs.
            requests.exceptions.Timeout: If a timeout occurs.
            requests.exceptions.HTTPError: If an HTTP error occurs.
        Additional Information:
            https://developers.notion.com/reference/update-a-database
            https://developers.notion.com/reference/update-property-schema-object
        """

        endpoint = f"{self.ENDPOINT}/databases/{db_id}"

        # Wrap the property, title and description in the appropriate JSON structure
        title_package = {"title": [{"text": {"content": title}}]} if title else {}
        description_package = (
            {"description": [{"text": {"content": description}}]} if description else {}
        )
        wrapped_property = {"properties": property_package} if property_package else {}

        # Combine the JSON structures
        json_body = {**description_package, **title_package, **wrapped_property}

        _logger.info(f"Updating database: {endpoint}")
        _logger.debug(json.dumps(json_body, indent=4))

        try:
            response = requests.patch(
                endpoint, headers=self.headers, json=json_body, timeout=self.TIMEOUT
            )
            response.raise_for_status()
            self.counter = 0
            return response.json()

        # Retry the request if a network error occurs
        except requests.exceptions.RequestException as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Network error occurred: {e}. Trying again in {self.RETRY_DELAY} seconds.",
                    exc_info=True,
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.update_database(db_id, property_package, title, description)

            else:
                _logger.error(
                    f"Network error occurred too many times: {e}", exc_info=True
                )
                self.counter = 0
                return {}

        # Retry the request if a timeout occurs
        except requests.exceptions.Timeout as e:
            if self.counter < self.MAX_RETRIES:
                _logger.error(
                    f"Timeout occurred: {e}. Trying again in {self.RETRY_DELAY} seconds."
                )
                time.sleep(self.RETRY_DELAY)
                self.counter += 1
                return self.update_database(db_id, property_package, title, description)

            else:
                _logger.error(f"Timeout occurred too many times: {e}", exc_info=True)
                time.sleep(3)
                self.counter = 0
                return {}

        # Log and handle HTTP errors
        except requests.exceptions.HTTPError as e:
            _logger.error(f"HTTP error occurred: {e}", exc_info=True)
            _logger.error("Check the database ID and try again.")
            time.sleep(1)
            self.counter = 0
            return {}

    # Data Parsing Utilities

    def simple_prop_gen(self, prop_name, prop_type, prop_value):
        """
        Generates a simple property dictionary.
        "checkbox" | "email" | "number" | "phone_number" | "url"
        """

        return {prop_name: {prop_type: prop_value}}

    def selstat_prop_gen(self, prop_name, prop_type, prop_value):
        """
        Generates a dictionary representing a Notion property with a given name, type, and value.
        Args:
            prop_name (str): The name of the property.
            prop_type (str): The type of the property (e.g., "select", "multi_select").
            prop_value (str): The value of the property.
        Returns:
            dict: A dictionary representing the Notion property.
        """

        return {prop_name: {prop_type: {"name": prop_value}}}

    def date_prop_gen(self, prop_name, prop_type, prop_value, prop_value2):
        """
        Generates a dictionary representing a date property for a Notion API request.
        Args:
            prop_name (str): The name of the property.
            prop_type (str): The type of the property.
            prop_value (str): The start date value in ISO 8601 format.
            prop_value2 (str, optional): The end date value in ISO 8601 format. Defaults to None.
        Returns:
            dict: A dictionary with the property name as the key and a nested dictionary containing the property type and date values.
        """

        if prop_value2 is None:
            return {prop_name: {prop_type: {"start": prop_value}}}

        else:
            return {prop_name: {prop_type: {"start": prop_value, "end": prop_value2}}}

    def files_prop_gen(self, prop_name, prop_type, file_names, file_urls):
        """
        Generates a property dictionary for files with given names and URLs.
        Args:
            prop_name (str): The name of the property.
            prop_type (str): The type of the property.
            file_names (list of str): A list of file names.
            file_urls (list of str): A list of file URLs.
        Returns:
            dict: A dictionary containing the property with the given names and URLs.
                  If file_names or file_urls is None, returns an empty dictionary.
        """

        if file_names is None or file_urls is None:
            return {}

        file_body = []

        for name, url in zip(file_names, file_urls):
            file_body.append({"name": name, "external": {"url": url}})

        return {prop_name: {prop_type: file_body}}

    def mulsel_prop_gen(self, prop_name, prop_type, prop_values):
        """
        Generates a dictionary representing a multi-select property for a Notion API request.
        Args:
            prop_name (str): The name of the property.
            prop_type (str): The type of the property (e.g., "multi_select").
            prop_values (list): A list of values to be included in the property.
        Returns:
            dict: A dictionary with the property name as the key and a dictionary containing
                  the property type and a list of dictionaries with the property values.
        """

        prop_value_new = []

        for value in prop_values:
            prop_value_new.append({"name": value})

        return {prop_name: {prop_type: prop_value_new}}

    def relation_prop_gen(self, prop_name, prop_type, prop_values):
        """
        Generates a dictionary representing a relation property for a Notion API request.
        Args:
            prop_name (str): The name of the property.
            prop_type (str): The type of the property.
            prop_values (list): A list of values to be included in the property.
        Returns:
            dict: A dictionary with the property name as the key and a dictionary containing
                  the property type and a list of dictionaries with "id" keys as the value.
        """

        prop_value_new = []

        for value in prop_values:
            prop_value_new.append({"id": value})

        return {prop_name: {prop_type: prop_value_new}}

    def people_prop_gen(self, prop_name, prop_type, prop_value):
        """
        Generates a dictionary representing a Notion property for people.
        Args:
            prop_name (str): The name of the property.
            prop_type (str): The type of the property.
            prop_value (list): A list of user IDs to be included in the property.
        Returns:
            dict: A dictionary with the property name as the key and a dictionary
              containing the property type and a list of user objects as the value.
        """

        prop_value_new = []

        for value in prop_value:
            prop_value_new.append({"object": "user", "id": value})

        return {prop_name: {prop_type: prop_value_new}}

    def rich_text_prop_gen(
        self, prop_name, prop_type, prop_value, prop_value_link=None, annotation=None
    ):
        """
        Generates a rich text property for a Notion API request.
        Args:
            prop_name (str): The name of the property.
            prop_type (str): The type of the property.
            prop_value (list of str): The content of the rich text.
            prop_value_link (list of str, optional): The links associated with the content. Defaults to None.
            annotation (list of dict, optional): The annotations for the content. Defaults to None.
        Returns:
            dict: A dictionary representing the rich text property for the Notion API request.
        """

        default_annotations = {
            "bold": False,
            "italic": False,
            "strikethrough": False,
            "underline": False,
            "code": False,
            "color": "default",
        }
        rich_body = []
        if isinstance(prop_value, str) or prop_value is None:
            if prop_value is None:
                prop_value = ""
            prop_value = [prop_value]

        if len(prop_value[0]) > 2000:
            prop_value[0] = prop_value[0][0:2000]

        if annotation and prop_value_link:
            for x, y, z in zip(prop_value, prop_value_link, annotation):
                rich_body.append(
                    {
                        "type": "text",
                        "text": {"content": x, "link": y},
                        "annotations": {
                            "bold": z["bold"],
                            "italic": z["italic"],
                            "strikethrough": z["strikethrough"],
                            "underline": z["underline"],
                            "code": z["code"],
                            "color": z["color"],
                        },
                        "plain_text": x,
                        "href": y,
                    }
                )

        elif prop_value_link:
            for x, y in zip(prop_value, prop_value_link):
                rich_body.append(
                    {
                        "type": "text",
                        "text": {"content": x, "link": y},
                        "annotations": default_annotations,
                        "plain_text": x,
                        "href": y,
                    }
                )

        elif annotation:
            for x, z in zip(prop_value, annotation):
                rich_body.append(
                    {
                        "type": "text",
                        "text": {"content": x, "link": y},
                        "annotations": {
                            "bold": z["bold"],
                            "italic": z["italic"],
                            "strikethrough": z["strikethrough"],
                            "underline": z["underline"],
                            "code": z["code"],
                            "color": z["color"],
                        },
                        "plain_text": x,
                        "href": y,
                    }
                )

        else:
            for x in prop_value:
                rich_body.append(
                    {
                        "type": "text",
                        "text": {"content": x, "link": prop_value_link},
                        "annotations": default_annotations,
                        "plain_text": x,
                        "href": prop_value_link,
                    }
                )

        return {prop_name: {prop_type: rich_body}}

    def title_prop_gen(
        self, prop_name, prop_type, prop_value, prop_value_link=None, annotation=None
    ):
        """
        Generates a title property for a Notion API request with rich text formatting.
        Args:
            prop_name (str): The name of the property.
            prop_type (str): The type of the property.
            prop_value (list of str): The content of the property.
            prop_value_link (list of str, optional): The links associated with the content. Defaults to None.
            annotation (list of dict, optional): The annotations for the content. Each dictionary should contain
                                                 "bold", "italic", "strikethrough", "underline", "code", and "color" keys. Defaults to None.
        Returns:
            dict: A dictionary representing the title property with rich text formatting for a Notion API request.
        """
        if isinstance(prop_value, str) or prop_value is None:
            if prop_value is None:
                prop_value = ""
            prop_value = [prop_value]

        if not isinstance(prop_value, list):
            prop_value = [str(prop_value)]

        default_annotations = {
            "bold": False,
            "italic": False,
            "strikethrough": False,
            "underline": False,
            "code": False,
            "color": "default",
        }
        rich_body = []

        if annotation and prop_value_link:
            for x, y, z in zip(prop_value, prop_value_link, annotation):
                rich_body.append(
                    {
                        "type": "text",
                        "text": {"content": x, "link": y},
                        "annotations": {
                            "bold": z["bold"],
                            "italic": z["italic"],
                            "strikethrough": z["strikethrough"],
                            "underline": z["underline"],
                            "code": z["code"],
                            "color": z["color"],
                        },
                        "plain_text": x,
                        "href": y,
                    }
                )

        elif prop_value_link:
            for x, y in zip(prop_value, prop_value_link):
                rich_body.append(
                    {
                        "type": "text",
                        "text": {"content": x, "link": y},
                        "annotations": default_annotations,
                        "plain_text": x,
                        "href": y,
                    }
                )

        elif annotation:
            for x, z in zip(prop_value, annotation):
                rich_body.append(
                    {
                        "type": "text",
                        "text": {"content": x, "link": y},
                        "annotations": {
                            "bold": z["bold"],
                            "italic": z["italic"],
                            "strikethrough": z["strikethrough"],
                            "underline": z["underline"],
                            "code": z["code"],
                            "color": z["color"],
                        },
                        "plain_text": x,
                        "href": y,
                    }
                )

        else:
            for x in prop_value:
                rich_body.append(
                    {
                        "type": "text",
                        "text": {"content": x, "link": prop_value_link},
                        "annotations": default_annotations,
                        "plain_text": x,
                        "href": prop_value_link,
                    }
                )

        return {prop_name: {"id": prop_type, "type": prop_type, prop_type: rich_body}}

    def generate_property_body(
        self, prop_name, prop_type, prop_value, prop_value2=None, annotation=None
    ):
        """
        Accepts a range of property types and generates a dictionary based on the input.
            Accepted property types is a string from the following list:
                "checkbox" | "email" | "number" | "phone_number" | "url" | "select" | "status" | "date" | "files" | "multi_select" | "relation" | "people" | "rich_text" | "title"
            Args:
            - prop_name (string): The name of the property.
            - prop_type (string): The type of the property.
            - prop_value (string/number/bool/array of strings): The value of the property.
            - prop_value2 (string/array of strings): The second value of the property. Optional.
            - annotation (array of dict): The annotation of the property. Optional.
                - Dictionary format: [{"bold": bool, "italic": bool, "strikethrough": bool, "underline": bool, "code": bool, "color": string}]
                - default annotations: {"bold": False, "italic": False, "strikethrough": False, "underline": False, "code": False, "color": "default"}
                - Acceptable Colors: Colors: "blue", "blue_background", "brown", "brown_background", "default", "gray", "gray_background", "green", "green_background", "orange", "orange_background", "pink", "pink_background", "purple", "purple_background", "red", "red_background", "yellow", "yellow_background"
            Returns:
            - dict: The python dictionary object of a property, formatted to fit as one of the properties in a page POST/PATCH request.

            Checkbox, Email, Number, Phone Number, URL:
                Property Name: string as the name of the property field in Notion
                Property Type: string as "checkbox" | "email" | "number" | "phone_number" | "url"
                Property Value: string/number/bool to be uploaded.

            Select, Status:
                Property Name: string as the name of the property field in Notion
                Property Type: string as "select" | "status"
                Property Value: string to be uploaded. Will create a new select/status if it does not exist.

            Date:
                Property Name: string as the name of the property field in Notion
                Property Type: string as "date"
                Start Date Value: string (ISO 8601 date and optional time) as "2020-12-08T12:00:00Z" or "2020-12-08"
                End Date Value: optional string (ISO 8601 date and optional time) as "2020-12-08T12:00:00Z" or "2020-12-08"
                    End date will default to None if not provided, meaning the date is not a range.

            Files:
                Property Name: string as the name of the property field in Notion
                Property Type: string as "files"
                File Names: Array of string
                File URLs: Array of string

            Multi-Select:
                Property Name: string as the name of the property field in Notion
                Property Type: string as "multi_select"
                Property Value: Array of strings

            Relation:
                Property Name: string as the name of the property field in Notion
                Property Type: string as "relation"
                Property Value: Array of strings

            People:
                Property Name: string as the name of the property field in Notion
                Property Type: string as "people"
                Property Value: Array of strings

            Rich Text:
                Property Name: string as the name of the property field in Notion
                Property Type: string as "rich_text"
                Property Value: Array of strings
                Property Value Link: Array of strings [opt.]
                Annotation: Array of dictionaries [opt.]
                    Dictionary format: [{"bold": bool, "italic": bool, "strikethrough": bool, "underline": bool, "code": bool, "color": string}]
                    default annotations: {"bold": False, "italic": False, "strikethrough": False, "underline": False, "code": False, "color": "default"}
                    Acceptable Colors: Colors: "blue", "blue_background", "brown", "brown_background", "default", "gray", "gray_background", "green", "green_background", "orange", "orange_background", "pink", "pink_background", "purple", "purple_background", "red", "red_background", "yellow", "yellow_background"

            Title:
                Property Name: string as the name of the property field in Notion
                Property Type: string as "title"
                Property Value: Array of strings
                Property Value Link: Array of strings
                Annotation: Array of dictionaries
                    Dictionary format: [{"bold": bool, "italic": bool, "strikethrough": bool, "underline": bool, "code": bool, "color": string}]
                    default annotations: {"bold": False, "italic": False, "strikethrough": False, "underline": False, "code": False, "color": "default"}
                    Acceptable Colors: Colors: "blue", "blue_background", "brown", "brown_background", "default", "gray", "gray_background", "green", "green_background", "orange", "orange_background", "pink", "pink_background", "purple", "purple_background", "red", "red_background", "yellow", "yellow_background"
        """
        type_dict = {
            "checkbox": lambda: self.simple_prop_gen(prop_name, prop_type, prop_value),
            "email": lambda: self.simple_prop_gen(prop_name, prop_type, prop_value),
            "number": lambda: self.simple_prop_gen(prop_name, prop_type, prop_value),
            "phone_number": lambda: self.simple_prop_gen(
                prop_name, prop_type, prop_value
            ),
            "url": lambda: self.simple_prop_gen(prop_name, prop_type, prop_value),
            "select": lambda: self.selstat_prop_gen(prop_name, prop_type, prop_value),
            "status": lambda: self.selstat_prop_gen(prop_name, prop_type, prop_value),
            "date": lambda: self.date_prop_gen(
                prop_name, prop_type, prop_value, prop_value2
            ),
            "files": lambda: self.files_prop_gen(
                prop_name, prop_type, prop_value, prop_value2
            ),
            "multi_select": lambda: self.mulsel_prop_gen(
                prop_name, prop_type, prop_value
            ),
            "relation": lambda: self.relation_prop_gen(
                prop_name, prop_type, prop_value
            ),
            "people": lambda: self.people_prop_gen(prop_name, prop_type, prop_value),
            "rich_text": lambda: self.rich_text_prop_gen(
                prop_name, prop_type, prop_value, prop_value2, annotation
            ),
            "title": lambda: self.title_prop_gen(
                prop_name, prop_type, prop_value, prop_value2, annotation
            ),
        }

        return type_dict[prop_type]()

    def return_property_value(self, property, id=None):
        """
        Returns the value of a given property based on its type.
        Args:
            property (dict): The property dictionary containing the type and data.
            id (str, optional): The ID of the property. Defaults to None.
        Returns:
            The value of the property in the appropriate format based on its type.
        Property Types and their corresponding return formats:
            - 'checkbox': Returns the checkbox value.
            - 'created_by': Returns the ID of the person who created the property.
            - 'created_time': Returns the creation time.
            - 'email': Returns the email address.
            - 'number': Returns the number value.
            - 'phone_number': Returns the phone number.
            - 'people': Returns a list of names.
            - 'url': Returns the URL.
            - 'last_edited_time': Returns the last edited time.
            - 'select': Returns the name of the selected option.
            - 'status': Returns the name of the status.
            - 'formula': Returns the result of the formula.
            - 'unique_id': Returns the unique ID.
            - 'rich_text': Returns the concatenated plain text.
            - 'title': Returns the concatenated plain text of the title.
            - 'relation': Returns a list of related IDs.
            - 'date': Returns the start date.
            - 'files': Returns a list of file URLs.
            - 'last_edited_by': Returns the name of the person who last edited the property.
            - 'multi_select': Returns a list of selected names.
            - 'rollup': Returns the rollup value.
        Raises:
            Exception: If an error occurs while returning the property value.
        """

        def is_simple(data, prop_type, id):
            return data[prop_type]

        def is_uid(data, prop_type, id):
            property = data.get(prop_type, {})
            prefix = property.get("prefix", "")
            number = property.get("number", "")
            if not prefix:
                return str(number)
            else:
                return f"{prefix}_{str(number)}"

        def is_selstat(data, prop_type, id):
            if data[prop_type] is None:
                return None

            return data[prop_type]["name"]

        def is_formula(data, prop_type, id):
            form_type = data[prop_type]["type"]

            if form_type == "date":
                return is_date(data[prop_type], form_type, id)

            else:
                return data[prop_type][form_type]

        def is_rich_text(data, prop_type, id):
            text_list = []

            for text in data[prop_type]:
                text_list.append(text["plain_text"])

            return "".join(text_list)

        def is_relation(data, prop_type, id):
            def _get_more(next_url, prop_id):
                response = self.get_url_property(next_url, prop_id)
                _logger.debug(
                    f"Get_More response: {len(response['results'])} {json.dumps(response)}\n"
                )

                if not response:
                    _logger.error(f"Error getting more relation data for {prop_id}")
                    return []

                if response["has_more"] == True:
                    try:
                        _logger.info(
                            f"More data found for {prop_id}. Getting more data..."
                        )
                        result = _get_more(
                            response["property_item"]["next_url"], prop_id
                        )
                        result_list = response["results"]
                        result_list.extend(result)
                        return result_list

                    except KeyError as e:
                        _logger.error(f"KeyError: {e}\nAttempting to get more data ...")
                        result = _get_more(response["next_url"], prop_id)
                        result_list = response["results"]
                        result_list.extend(result)
                        return result_list

                    except TypeError as e:
                        _logger.error(
                            f"TypeError: {e}\nReturning empty list.", exc_info=True
                        )
                        return []

                _logger.debug(f"Get more has_more is False. Returning results.")
                return response["results"]

            def _get_prop(page_id, prop_id, data=None):
                response = self.get_page_property(page_id, prop_id)

                if not response:
                    _logger.error(f"Error getting property data for {prop_id}")
                    return []

                if response["has_more"] == True:
                    try:
                        _logger.info(
                            f"More data found for {prop_id}. Getting more data ..."
                        )
                        result_list = response["results"]

                        _logger.debug(f"Init result list: {len(result_list)}\n")
                        result = _get_more(
                            response["property_item"]["next_url"], prop_id
                        )

                        _logger.debug(
                            f"Apprending get_more result {len(result)} to result list {len(result_list)}."
                        )
                        result_list.extend(result)

                        _logger.debug(f"Returning result list. {len(result_list)}")
                        return result_list

                    except KeyError as e:
                        _logger.error(f"KeyError: {e}\nAttempting to get more data ...")
                        result = _get_more(response["next_url"], prop_id)
                        result_list = response["results"].extend(result["results"])
                        return result_list

                    except TypeError as e:
                        _logger.error(
                            f"TypeError: {e}\nReturning empty list.", exc_info=True
                        )
                        return []

                return response["results"]

            package = []

            if "has_more" in data:
                if data[
                    "has_more"
                ]:  # If there are more than 25 relations, replace data with full data.
                    _logger.info(f"Gathering full relation data for {prop_type}")
                    result_list = _get_prop(id, data["id"])

                    _logger.debug(f"Unparsed Result List:{len(result_list)}\n")

                    try:
                        if result_list:
                            for page in result_list:
                                if "relation" in page:
                                    if "id" in page["relation"]:
                                        if page["relation"]["id"]:
                                            package.append(
                                                page["relation"]["id"].replace("-", "")
                                            )
                    except Exception as e:
                        _logger.error(
                            f"Error getting full relation data: {e}", exc_info=True
                        )
                        with open("error.txt", "w") as f:
                            f.write(json.dumps(result_list))

                    return package

            for relation_id in data[prop_type]:
                package.append(relation_id["id"].replace("-", ""))

            return package

        def is_date(data, prop_type, id):
            if data[prop_type] is None:
                return None

            return data[prop_type]["start"]

        def is_files(data, prop_type, id):
            file_list = []

            for file in data[prop_type]:
                file_type = file["type"]
                file_list.append(file[file_type]["url"])

            return file_list

        def is_person(data, prop_type, id):
            package = []

            try:
                return [data[prop_type]["id"]]
            except KeyError:
                for person in data[prop_type]:
                    package.append(person["name"])
            except TypeError:
                return []

            return package

        def is_multi_select(data, prop_type, id):
            package = []

            for select in data[prop_type]:
                try:
                    package.append(select["name"])
                except KeyError:
                    package.append(select["id"])
            return package

        def is_rollup(data, prop_type, id):
            roll_type = data[prop_type]["type"]
            _logger.debug(f"Rollup Type: {roll_type}")

            if roll_type == "array":
                _logger.debug(f"Rollup Array: {data[prop_type]['array']}")
                return_list = []

                for each in data[prop_type]["array"]:
                    value = self.return_property_value(each, id)

                    if isinstance(value, list):
                        return_list.extend(value)
                    else:
                        return_list.append(value)

                return return_list

            else:
                _logger.debug(f"Rollup Value: {data[prop_type]}")
                return self.return_property_value(data[prop_type], id)

        router = {  # This is a dictionary of functions that return the data in the correct format.
            "checkbox": is_simple,
            "created_by": is_person,
            "created_time": is_simple,
            "email": is_simple,
            "number": is_simple,
            "phone_number": is_simple,
            "people": is_person,  # This will return a list of names instead of IDs.
            "url": is_simple,
            "last_edited_time": is_simple,
            "select": is_selstat,
            "status": is_selstat,
            "formula": is_formula,
            "unique_id": is_uid,
            "rich_text": is_rich_text,
            "title": is_rich_text,
            "relation": is_relation,
            "date": is_date,
            "files": is_files,
            "last_edited_by": is_selstat,  # This will return the name instead of the ID.
            "multi_select": is_multi_select,
            "rollup": is_rollup,
        }

        try:
            prop_type = property.get("type", None)
            _logger.debug(f"Property Type: {prop_type}")
            _logger.debug(f"Property {json.dumps(property)}")

            value = ""

            for key, check_router in router.items():

                if key == prop_type:
                    value = check_router(property, prop_type, id)
                    _logger.debug(f"Returning value: {value}\n")

            return value

        except Exception as e:
            _logger.error(f"Error returning property value: {e}", exc_info=True)
            return None


if __name__ == "__main__":
    page_id = "b5b01d5b9619408eb9ee07e31d2a94f5"
    prop_id = "Ul_%3D"

    notion = NotionApiHelper()

    prop = notion.get_page_property(page_id, prop_id)

    logging.info(f"Property: {json.dumps(prop, indent=4)}")
    pass
else:
    _logger = logging.getLogger(__name__)
    _logger.setLevel(logging.INFO)
    if not _logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        _logger.addHandler(handler)
        _logger.propagate = False
        _logger.info("Notion API Helper Module Loaded.")

"""
    page_id = "cc44b728898c4d3d952dce6fb5b15dba"
    prop_id = "Ul_%3D"
    
    notion = NotionApiHelper()
    
    page = notion.get_page(page_id)
    properties = page['properties']
    
    for prop_name, prop_value in properties.items():
        if prop_value['id'] == prop_id:
            _logger.info(f"Property Name: {prop_name}")
            _logger.info(f"Property Value: {prop_value}")
            value = notion.return_property_value(prop_value, page_id)
            _logger.info(f"Property Value:{len(value)} {value}")
            break
"""
