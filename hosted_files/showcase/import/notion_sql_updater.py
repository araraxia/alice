#!/usr/bin/env python3
"""
Notion SQL Updater Core Logic

This module contains the core business logic for updating SQL records based on Notion page data.
It handles parsing, validation, and database operations without Flask request handling concerns.
"""

from pathlib import Path
from sys import exc_info
from extras.sql_helper import (
    map_notion_to_sql_type,
    parse_notion_data,
    add_update_record,
    get_records,
    create_or_update_table,
    add_join_records,
    get_notion_table_columns,
    ensure_join_table_exists,
    JoinTableManager,
    init_psql_connection,
    create_cursor,
)
from extras.helpers import send_discord_warning
from extras.notion_reroutes.reroute_products import reroute_products
from NotionApiHelper import NotionApiHelper
from datetime import datetime
import psycopg2
import uuid


class NotionSqlUpdater:
    """
    Core logic for updating SQL records from Notion page data.

    This class handles the business logic of:
    - Parsing Notion page data
    - Validating SQL table structures
    - Updating SQL records
    - Managing join tables and relations
    - Handling foreign key violations
    """

    def __init__(self, logger, root_path=None):
        """
        Initialize the NotionSqlUpdater.

        Args:
            logger: Logger instance for logging operations
            root_path: Root path for configuration files (optional)
        """
        self.logger = logger
        self.root_path = root_path or Path(__file__).parent.parent.parent
        self.schema = ""
        self.table = ""
        self.record_id = ""

    def update_metrics(self, schema, table, record_id):
        """
        Update metrics table with record update information.

        Args:
            schema (str): Schema name
            table (str): Table name
            record_id (str): Record ID that was updated
        """
        unique_uuid = str(uuid.uuid4())
        current_datetime = datetime.now()
        columns = [
            "primary_key_id",
            "updated_at",
            "schema_name",
            "table_name",
            "updated_record_id",
        ]
        values = [unique_uuid, current_datetime, schema, table, record_id]

        try:
            add_update_record(
                database="meno_db",
                schema="metrics",
                table="notion-sql_updates",
                columns=columns,
                values=values,
            )
        except Exception as e:
            self.logger.error(
                f"Failed to update metrics for {schema}.{table} record {record_id}: {e}"
            )
            send_discord_warning(
                f"Failed to update metrics for {schema}.{table} record {record_id}: {e}",
                username="NotionSqlUpdater",
            )

    def process_update(self, request_json, schema, table, retry=True):
        """
        Process a Notion page update and sync it to SQL database.

        Args:
            request_json (dict): The JSON payload containing Notion page data
            schema (str): Target SQL schema name
            table (str): Target SQL table name
            retry (bool): Whether to retry on missing columns (default: True)

        Returns:
            dict: Result dictionary with status and message

        Raises:
            ValueError: If required data is missing
            Exception: If update fails after retry
        """
        # Initialize Notion API helper based on schema
        self.logger.debug(f"Initializing NotionApiHelper for schema: {schema}")
        self.logger.debug(f"Root path: {self.root_path}")
        pts_header_path = str(self.root_path / "src" / "headers_pts.json")
        self.logger.debug(f"PTS header path: {pts_header_path}")
        notion = (
            NotionApiHelper()
            if schema != "Planet"
            else NotionApiHelper(pts_header_path)
        )

        self.schema = schema
        self.table = table

        join_manager = JoinTableManager(log=self.logger)

        # Parse the page data
        req_page = request_json.get("data", {})
        request_database = notion.get_database(
            req_page.get("parent", {}).get("database_id", "")
        )
        uid = req_page.get("id").replace("-", "")
        self.record_id = uid
        db_id = req_page.get("parent", {}).get("database_id", "")

        self.logger.info(
            f"Updating record with uid: {uid} in {schema}.{table} {db_id} from Notion page data"
        )

        # Validate the SQL table structure against the Notion database structure
        table_props = request_database.get("properties", {})
        table_columns = [{"name": "primary_key_id", "type": "UUID"}]
        column_template = {"name": "", "type": ""}

        for property in table_props.values():
            column = column_template.copy()
            column["name"] = property.get("name")
            column["type"] = property.get("type")

            if column["type"] == "rollup":
                continue

            # Check for duplicate column names
            for sql_prop in table_columns:
                if sql_prop["name"] == column["name"]:
                    column["name"] += "_dup"
                    break

            if column["type"] == "relation":
                join_manager.parse_relation_property(
                    property=property,
                    schema_name=schema,
                    table_name=table,
                )
                continue

            column["type"] = map_notion_to_sql_type(property)
            table_columns.append({"name": column["name"], "type": column["type"]})

        create_or_update_table(
            database="meno_db",
            log=self.logger,
            schema=schema,
            table=table,
            columns=table_columns,
        )

        # Parse the Notion page data into SQL columns and values
        columns, parsed_records, relations = parse_notion_data(
            log=self.logger,
            notion=notion,
            records=[req_page],
        )

        # Iterate through parsed records and update the SQL table
        for record_values in parsed_records:
            if not record_values:
                self.logger.warning(
                    f"No values found for record with uid: {uid} in {schema}.{table}"
                )
                continue

            try:
                self.logger.info(
                    f"Attempting to update record with uid: {uid} in {schema}.{table}"
                )
                add_update_record(
                    database="meno_db",
                    schema=schema,
                    table=table,
                    columns=columns,
                    values=record_values,
                )
            except psycopg2.errors.UndefinedColumn as e:
                self.logger.warning(
                    f"Undefined column error: {e}\nAdding columns to {schema}.{table}\nPage: {req_page}"
                )

                # If the column is missing, try to add it
                if not retry:
                    self.logger.error(
                        f"Retry is disabled, cannot add missing columns for {schema}.{table}"
                    )
                    raise e

                db_columns = get_notion_table_columns(
                    join_manager=join_manager,
                    database_id=db_id,
                    schema_name=schema,
                    table_name=table,
                    notion=notion,
                )
                create_or_update_table(
                    database="meno_db",
                    log=self.logger,
                    schema=schema,
                    table=table,
                    columns=db_columns,
                )

                # Retry the update with the new columns
                try:
                    return self.process_update(
                        request_json=request_json,
                        schema=schema,
                        table=table,
                        retry=False,
                    )
                except Exception as e:
                    self.logger.error(
                        f"Failed to update record after adding missing columns: {e}"
                    )
                    raise
            except IndexError as e:
                self.logger.error(
                    f"Index error while updating record with uid: {uid} in {schema}.{table}. len(column)={len(columns)}, len(record_values)={len(record_values)}: {e}\nCOLUMNS: {columns}",
                    exc_info=True,
                )
                raise

        # Store the relation data in the join manager
        join_manager.store_relation_data(
            relation_data=relations,
            current_table_name=table,
            current_schema_name=schema,
            notion=notion,
            notion_table_structure=request_database,
        )

        # Process join tables
        self._process_join_tables(join_manager, schema)

        self.logger.info(
            f"Successfully updated record with uid: {uid} in {schema}.{table}"
        )

        join_manager.close()
        self.update_metrics(schema, table, uid)
        try:
            self.record_reroute(request_json, schema, table)
        except Exception as e:
            self.logger.error(f"Error rerouting {schema}.{table}", exc_info=True)

        return {
            "status": "success",
            "message": "Record updated successfully",
            "record_id": uid,
        }

    def _process_join_tables(self, join_manager, schema):
        """
        Process all join tables managed by the join manager.

        Args:
            join_manager: JoinTableManager instance with relation data
            schema (str): Current schema name for foreign key handling
        """
        # Iterate through each join table in the join manager
        for join_table_name, join_dict in join_manager.join_tables.items():
            self.logger.info(f"Processing join table: {join_table_name}")

            join_columns = join_dict.get("columns", [])
            join_values = join_dict.get("values", [])

            if not join_columns or not join_values:
                self.logger.debug(
                    f"No join columns or values found for join table {join_table_name}"
                )
                continue

            # Validate the join table structure
            ensure_join_table_exists(
                database="meno_db",
                log=self.logger,
                join_dict=join_dict,
            )

            # Iterate through the join values in batches of 100
            step = 100
            for i in range(0, len(join_values), step):
                batch_values = join_values[i : i + step]

                while True:  # Retry until successful or a non-FKV error occurs
                    try:
                        self.logger.info(
                            f"Adding join records to table: {join_table_name} "
                            f"with {len(batch_values)} values"
                        )
                        add_join_records(
                            database="meno_db",
                            log=self.logger,
                            join_table=join_table_name,
                            columns=join_columns,
                            values=batch_values,
                        )
                        break
                    except psycopg2.errors.ForeignKeyViolation as e:
                        # If we fix the fkv, retry the operation. Otherwise, log the error and break.
                        self.logger.warning(
                            f"Foreign key violation error: {e}\n"
                            f"Attempting to handle foreign key violation for {join_table_name}"
                        )
                        try:
                            if join_manager.handle_fkv(
                                error_message=e,
                                current_schema=schema,
                            ):
                                self.logger.info("Foreign key violation handled")
                                continue  # Retry after handling foreign key violation
                            else:
                                self.logger.error(
                                    f"Failed to handle foreign key violation for {join_table_name}: {e}"
                                )
                                break
                        except Exception as e:
                            self.logger.error(
                                f"Error handling foreign key violation: {e}",
                                exc_info=True,
                            )
                            send_discord_warning(
                                f"Error handling foreign key violation for {join_table_name}: {e}",
                                username="NotionSqlUpdater",
                            )
                            break

                self.logger.info(
                    f"Inserted records {i} through {i+step} into join table {join_table_name}"
                )

    def record_reroute(self, request_json, schema, table):
        """
        Checks a dictionary for a new schema/table and reformats the data to that structure.

        Args:
            request_json (dict): The JSON payload containing Notion page data
            schema (str): Current schema name
            table (str): Current table name
        """
        self.logger.info(f"Checking for reroute for {schema}.{table}")
        table_map = {
            "Meno.Products": reroute_products,
            "Planet.Products": reroute_products,
        }
        return table_map.get(f"{schema}.{table}", lambda log, x, y, z: (y, z))(
            self.logger, request_json, schema, table
        )
