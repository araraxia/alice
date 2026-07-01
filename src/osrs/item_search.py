#!/usr/bin/env python3

from flask import render_template
from src.util.sql_helper import get_record, fuzzy_search_records, search_records


class ItemSearch:
    def __init__(self):
        self.database = "osrs"
        self.schema = "items"
        self.table = "map"

    def search_by_id(self, item_id: int) -> dict:
        """
        Search for an item by its ID.
        Args:
            item_id (int): The item ID to search for
        Returns:
            dict: The item record or None if not found
        """
        return get_record(
            database=self.database,
            schema=self.schema,
            table=self.table,
            column="id",
            value=item_id,
        )

    def search_by_name(self, name: str, exact: bool = False) -> list:
        """
        Search for items by name.
        Args:
            name (str): The item name to search for
            exact (bool): Whether to use exact match or fuzzy search
        Returns:
            list: List of matching item records
        """
        if exact:
            return search_records(
                database=self.database,
                schema=self.schema,
                table=self.table,
                column="name",
                value=name,
            )
        else:
            # Use fuzzy search with ILIKE pattern matching
            search_pattern = f"%{name}%"
            return fuzzy_search_records(
                database=self.database,
                schema_name=self.schema,
                table_name=self.table,
                column_name="name",
                search_pattern=search_pattern,
                case_sensitive=False,
            )

    def display(self) -> str:
        """
        Render the item search interface.
        Returns:
            str: Rendered HTML template
        """
        return render_template("osrs/item_search.html")
