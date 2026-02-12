from extras.sql_helper import get_record, update_existing_record, add_update_record
from extras.helpers import generate_token, hash_string
from AutomatedEmails import AutomatedEmails
from NotionApiHelper import NotionApiHelper

class Organizations:
    def __init__(self, app, organization_id):
        self.app = app
        self.log = app.logger
        self.organization_id = organization_id
        self.api_token = None
        self.company_name = None
        self.company_phone = None
        self.company_address1 = None
        self.company_address2 = None
        self.company_city = None
        self.company_state = None
        self.company_zip = None
        self.company_country = None
        self.default_first_name = None
        self.default_last_name = None
        self.default_email = None
        self.default_phone = None
        self.default_address1 = None
        self.default_address2 = None
        self.default_city = None
        self.default_state = None
        self.default_zip = None
        self.default_country = None
        self.billing_first_name = None
        self.billing_last_name = None
        self.billing_email = None
        self.billing_phone = None
        self.billing_address1 = None
        self.billing_address2 = None
        self.billing_city = None
        self.billing_state = None
        self.billing_zip = None
        self.billing_country = None
        self.order_update_first_name = None
        self.order_update_last_name = None
        self.order_update_email = None
        self.ship_notif_first_name = None
        self.ship_notif_last_name = None
        self.ship_notif_email = None
        self.tech_first_name = None
        self.tech_last_name = None
        self.tech_email = None
        
        self.billing_terms = None
        self.pricing_tier = None
        
        self.init_records()
        
    def init_records(self):
        auth_record = get_record(
            database="meno_accounts",
            schema="auth",
            table="organizations",
            column="primary_key_id",
            value=self.organization_id,
        )
        if not auth_record:
            self.log.warning(f"No auth record found for organization ID {self.organization_id}.")
            auth_record = {}
        else:
            self.log.debug(f"Organization auth retrieved.")
        account_record = get_record(
            database="meno_accounts",
            schema="accounts",
            table="organizations",
            column="primary_key_id",
            value=self.organization_id,
        )
        if not account_record:
            self.log.warning(f"No account record found for organization ID {self.organization_id}.")
            account_record = {}
        else:
            self.log.debug(f"Organization account retrieved.")

        self.is_active = auth_record.get("is_active", False)
        self.init_user = auth_record.get("init_user", None)
        self.in_review = auth_record.get("in_review", True)
        self.cs_validation_code = auth_record.get("cs_validation_code", None)
        self.activation_code = auth_record.get("activation_code", None)
        self.members = account_record.get("members", [])
        self.administrators = account_record.get("administrators", [])
        self.company_name = account_record.get("company_name", "Unknown Organization")
        self.company_phone = account_record.get("company_phone", None)
        self.company_address1 = account_record.get("company_address1", None)
        self.company_address2 = account_record.get("company_address2", None)
        self.company_city = account_record.get("company_city", None)
        self.company_state = account_record.get("company_state", None)
        self.company_zip = account_record.get("company_zip", None)
        self.company_country = account_record.get("company_country", None)
        self.default_first_name = account_record.get("default_first_name", None)
        self.default_last_name = account_record.get("default_last_name", None)
        self.default_email = account_record.get("default_email", None)
        self.default_phone = account_record.get("default_phone", None)
        self.default_address1 = account_record.get("default_address1", None)
        self.default_address2 = account_record.get("default_address2", None)
        self.default_city = account_record.get("default_city", None)
        self.default_state = account_record.get("default_state", None)
        self.default_zip = account_record.get("default_zip", None)
        self.default_country = account_record.get("default_country", None)
        self.billing_first_name = account_record.get("billing_first_name", None)
        self.billing_last_name = account_record.get("billing_last_name", None)
        self.billing_email = account_record.get("billing_email", None)
        self.billing_phone = account_record.get("billing_phone", None)
        self.billing_address1 = account_record.get("billing_address1", None)
        self.billing_address2 = account_record.get("billing_address2", None)
        self.billing_city = account_record.get("billing_city", None)
        self.billing_state = account_record.get("billing_state", None)
        self.billing_zip = account_record.get("billing_zip", None)
        self.billing_country = account_record.get("billing_country", None)
        self.order_update_first_name = account_record.get("order_update_first_name", None)
        self.order_update_last_name = account_record.get("order_update_last_name", None)
        self.order_update_email = account_record.get("order_update_email", None)
        self.ship_notif_first_name = account_record.get("ship_notif_first_name", None)
        self.ship_notif_last_name = account_record.get("ship_notif_last_name", None)
        self.ship_notif_email = account_record.get("ship_notif_email", None)
        self.tech_first_name = account_record.get("tech_first_name", None)
        self.tech_last_name = account_record.get("tech_last_name", None)
        self.tech_email = account_record.get("tech_email", None)
        self.company_code = account_record.get("company_code", None)
        
        
    def is_exists(self):
        return bool(get_record(
            database="meno_accounts",
            schema="auth",
            table="organizations",
            column="primary_key_id",
            value=self.organization_id,
        ))
        
    def add_organization(self):
        if self.is_exists():
            self.log.warning(f"Organization {self.organization_id} already exists. Skipping add.")
            raise ValueError("Organization already exists.")
        
        if not self.api_token:
            self.api_token = generate_token()
        self.token_hash = hash_string(self.api_token)
        auth_columns = (
            "primary_key_id",
            "is_active",
            "activation_code",
            "init_user",
            "api_token",
            "token_hash"
        )
        auth_values = (
            self.organization_id,
            self.is_active,
            self.activation_code,
            self.init_user,
            self.api_token,
            self.token_hash
        )
        try:
            add_update_record(
                database="meno_accounts",
                schema="auth",
                table="organizations",
                columns=auth_columns,
                values=auth_values,
                conflict_target=["primary_key_id"],
                on_conflict="DO NOTHING",
            )
            self.log.info(f"Organization {self.company_name} added to auth database.")
        except Exception as e:
            self.log.error(f"Error adding organization to auth database: {e}", exc_info=True)
            raise e
        
        account_columns = (
            "primary_key_id",
            "members",
            "administrators",
            "company_name",
            "company_phone",
            "company_address1",
            "company_address2",
            "company_city",
            "company_state",
            "company_zip",
            "company_country",
            "default_first_name",
            "default_last_name",
            "default_email",
            "default_phone",
            "default_address1",
            "default_address2",
            "default_city",
            "default_state",
            "default_zip",
            "default_country",
            "billing_first_name",
            "billing_last_name",
            "billing_email",
            "billing_phone",
            "billing_address1",
            "billing_address2",
            "billing_city",
            "billing_state",
            "billing_zip",
            "billing_country",
            "order_update_first_name",
            "order_update_last_name",
            "order_update_email",
            "ship_notif_first_name",
            "ship_notif_last_name",
            "ship_notif_email",
            "tech_first_name",
            "tech_last_name",
            "tech_email",
            "company_code",
        )
        account_values = (
            self.organization_id,
            self.members,
            self.administrators,
            self.company_name,
            self.company_phone,
            self.company_address1,
            self.company_address2,
            self.company_city,
            self.company_state,
            self.company_zip,
            self.company_country,
            self.default_first_name,
            self.default_last_name,
            self.default_email,
            self.default_phone,
            self.default_address1,
            self.default_address2,
            self.default_city,
            self.default_state,
            self.default_zip,
            self.default_country,
            self.billing_first_name,
            self.billing_last_name,
            self.billing_email,
            self.billing_phone,
            self.billing_address1,
            self.billing_address2,
            self.billing_city,
            self.billing_state,
            self.billing_zip,
            self.billing_country,
            self.order_update_first_name,
            self.order_update_last_name,
            self.order_update_email,
            self.ship_notif_first_name,
            self.ship_notif_last_name,
            self.ship_notif_email,
            self.tech_first_name,
            self.tech_last_name,
            self.tech_email,
            self.company_code
        )
        try:
            add_update_record(
                database="meno_accounts",
                schema="accounts",
                table="organizations",
                columns=account_columns,
                values=account_values,
                conflict_target=["primary_key_id"],
                on_conflict="DO NOTHING",
            )
            self.log.info(f"Organization {self.company_name} added to accounts database.")
        except Exception as e:
            self.log.error(f"Error adding organization to accounts database: {e}", exc_info=True)
            raise e
        
    def _generate_notion_package(self, notion: NotionApiHelper):
        account_health_package = notion.generate_property_body(
            prop_name="Account health",
            prop_type="select",
            prop_value="Healthy",
        )
        an_confirmation_package = notion.generate_property_body(
            prop_name="Auto-notify: Confirmation",
            prop_type="rich_text",
            prop_value=self.order_update_email or "",
        )
        an_it_package = notion.generate_property_body(
            prop_name="Auto-notify: IT",
            prop_type="rich_text",
            prop_value=self.tech_email or "",
        )
        an_shipping_package = notion.generate_property_body(
            prop_name="Auto-notify: Shipping",
            prop_type="rich_text",
            prop_value=self.ship_notif_email or "",
        )
        bt_address1_package = notion.generate_property_body(
            prop_name="BT: Address 1",
            prop_type="rich_text",
            prop_value=self.billing_address1 or "",
        )
        bt_address2_package = notion.generate_property_body(
            prop_name="BT: Address 2",
            prop_type="rich_text",
            prop_value=self.billing_address2 or "",
        )
        bt_city_package = notion.generate_property_body(
            prop_name="BT: City",
            prop_type="rich_text",

            prop_value=self.billing_city or "",
        )
        bt_country_package = notion.generate_property_body(
            prop_name="BT: Country",
            prop_type="rich_text",
            prop_value=self.billing_country or "",
        )
        bt_email_package = notion.generate_property_body(
            prop_name="BT: Email",
            prop_type="email",
            prop_value=self.billing_email or "",
        )
        bt_name_package = notion.generate_property_body(
            prop_name="BT: Name",
            prop_type="rich_text",
            prop_value=f"{self.billing_first_name or ''} {self.billing_last_name or ''}".strip(),
        )
        bt_phone_package = notion.generate_property_body(
            prop_name="BT: Phone",
            prop_type="phone_number",
            prop_value=self.billing_phone or "",
        )
        bt_postal_code_package = notion.generate_property_body(
            prop_name="BT: Postal code",
            prop_type="rich_text",
            prop_value=self.billing_zip or "",
        )
        bt_state_package = notion.generate_property_body(
            prop_name="BT: State/Providence",
            prop_type="rich_text",
            prop_value=self.billing_state or "",
        )
        billing_terms_package = notion.generate_property_body(
            prop_name="Billing Terms",
            prop_type="select",
            prop_value=self.billing_terms or "",
        )
        business_package = notion.generate_property_body(
            prop_name="Business",
            prop_type="title",
            prop_value=self.company_name or "Unknown Organization",
        )
        customer_id_package = notion.generate_property_body(
            prop_name="Customer ID",
            prop_type="rich_text",
            prop_value=self.company_code or "",
        )
        default_contact_email_package = notion.generate_property_body(
            prop_name="Default contact email",
            prop_type="email",
            prop_value=self.default_email or "",
        )
        default_phone_package = notion.generate_property_body(
            prop_name="Default phone",
            prop_type="phone_number",
            prop_value=self.default_phone or "",
        )
        organization_uuid_package = notion.generate_property_body(
            prop_name="Organization UUID",
            prop_type="rich_text",
            prop_value=self.organization_id,
        )
        pricing_tier_package = notion.generate_property_body(
            prop_name="Pricing tier",
            prop_type="select",
            prop_value=self.pricing_tier or "",
        )
        system_status_package = notion.generate_property_body(
            prop_name="System status",
            prop_type="select",
            prop_value="Active",
        )
        tags_package = notion.generate_property_body(
            prop_name="Tags",
            prop_type="multi_select",
            prop_value=["MOD"],
        )
        notion_package = {
            **account_health_package,
            **an_confirmation_package,
            **an_it_package,
            **an_shipping_package,
            **bt_address1_package,
            **bt_address2_package,
            **bt_city_package,
            **bt_country_package,
            **bt_email_package,
            **bt_name_package,
            **bt_phone_package,
            **bt_postal_code_package,
            **bt_state_package,
            **billing_terms_package,
            **business_package,
            **customer_id_package,
            **default_contact_email_package,
            **default_phone_package,
            **organization_uuid_package,
            **pricing_tier_package,
            **system_status_package,
            **tags_package,
        }
        return notion_package

    def activate_organization(self, billing_terms, pricing_tier):
        from extras.helpers import get_html_email_str
        from flask import url_for
        automated_emails = AutomatedEmails()
        notion = NotionApiHelper()

        self.billing_terms = billing_terms
        self.pricing_tier = pricing_tier
        raw_api_token = self.api_token
        try:
            update_existing_record(
                database="meno_accounts",
                schema="auth",
                table="organizations",
                update_columns=["is_active", "in_review", "cs_validation_code", "activation_code"],
                update_values=[True, False, None, None],
                where_column="primary_key_id",
                where_value=self.organization_id,
            )
            self.is_active = True
            self.in_review = False
            self.cs_validation_code = None
            self.activation_code = None
            self.log.info(f"Organization {self.company_name} activated successfully.")
        except Exception as e:
            self.log.error(f"Error activating user: {e}", exc_info=True)
            raise e
        
        # Update customers DB and Notion table
        query_filter = {
            "property": "Customer ID",
            "rich_text": {
                "equals": str(self.company_code)
            }
        }
        existing_customers = notion.query(
            databaseID="23f50a59b54049259b36d33df9408eff",
            filter_properties=query_filter
        )
        if not existing_customers: # Create new record
            self.log.info(f"No existing Notion customer found for {self.company_name}. Creating new entry.")
            
            notion_package = self._generate_notion_package(notion)
            notion_page = notion.create_page(
                databaseID="23f50a59b54049259b36d33df9408eff",
                properties=notion_package,
            )
            if not notion_page:
                self.log.error(f"Failed to create Notion page for organization {self.company_name}.")
                raise Exception("Notion page creation failed")
            else:
                self.log.info(f"Notion page created for organization {self.company_name}.")
            
            customer_id = notion_page.get("id", None)
            if not customer_id:
                self.log.error(f"Notion page ID missing for organization {self.company_name}.")
                raise Exception("Notion page ID missing")
            
            customer_columns = (
                "primary_key_id",
                "Account health",
                "Auto-notify: Confirmation",
                "Auto-notify: IT",
                "Auto-notify: Shipping",
                "BT: Address 1",
                "BT: Address 2",
                "BT: City",
                "BT: Country",
                "BT: Email",
                "BT: Name",
                "BT: Phone",
                "BT: Postal code",
                "BT: State/Providence", #sic
                "Billing Terms",
                "Business", # Organization name
                "Customer ID", # Customer code
                "Default contact email",
                "Default phone",
                "Organization UUID", # UUID for the organization
                "Pricing tier",
                "System status",
                "Tags", # List
            )
            customer_values = (
                customer_id,
                "Healthy",
                self.order_update_email,
                self.tech_email,
                self.ship_notif_email,
                self.billing_address1,
                self.billing_address2,
                self.billing_city,
                self.billing_country,
                self.billing_email,
                f"{self.billing_first_name} {self.billing_last_name}".strip(),
                self.billing_phone,
                self.billing_zip,
                self.billing_state,
                self.billing_terms,
                self.company_name,
                self.company_code,
                self.default_email,
                self.default_phone,
                self.organization_id,
                self.pricing_tier,
                "Active",
                ["MOD"],
            )
            try:
                add_update_record(
                    database="meno_db",
                    schema="Meno",
                    table="Customers",
                    columns=customer_columns,
                    values=customer_values,
                    conflict_target=["primary_key_id"],
                    on_conflict="DO UPDATE SET",
                )
                self.log.info(f"Organization {self.company_name} added/updated in customers database.")
            except Exception as e:
                self.log.error(f"Error adding/updating organization in customers database: {e}", exc_info=True)
                raise e

        else: # Update existing record
            notion_package = self._generate_notion_package(notion)
            notion_package.pop("Tags")
            notion_package.pop("Account health")
            notion_package.pop("Customer ID")
            notion_page = notion.update_page(
                pageID=existing_customers[0].get("id"),
                properties=notion_package
            )
            if not notion_page:
                self.log.error(f"Failed to update Notion page for organization {self.company_name}.")
                raise Exception("Notion page update failed")
            else:
                self.log.info(f"Notion page updated for organization {self.company_name}.")
            
            customer_columns = (
                "Organization UUID", # UUID for the organization
                "Pricing tier",
                "Billing Terms",
                "Auto-notify: Confirmation",
                "Auto-notify: IT",
                "Auto-notify: Shipping",
                "BT: Address 1",
                "BT: Address 2",
                "BT: City",
                "BT: Country",
                "BT: Email",
                "BT: Name",
                "BT: Phone",
                "BT: Postal code",
                "BT: State/Providence", #sic
                "Business", # Organization name
                "Default contact email",
                "Default phone",
                "Organization UUID", # UUID for the organization
                "System status",
            )
            customer_values = (
                self.organization_id,
                self.pricing_tier,
                self.billing_terms,
                self.order_update_email,
                self.tech_email,
                self.ship_notif_email,
                self.billing_address1,
                self.billing_address2,
                self.billing_city,
                self.billing_country,
                self.billing_email,
                f"{self.billing_first_name} {self.billing_last_name}".strip(),
                self.billing_phone,
                self.billing_zip,
                self.billing_state,
                self.company_name,
                self.default_email,
                self.default_phone,
                self.organization_id,
                "Active",
            )
            
            try:
                update_existing_record(
                    database="meno_db",
                    schema="Meno",
                    table="Customers",
                    update_columns=customer_columns,
                    update_values=customer_values,
                    where_column="primary_key_id",
                    where_value=existing_customers[0].get("id"),
                )
            except Exception as e:
                self.log.error(f"Error updating organization in customers database: {e}", exc_info=True)
                raise e
        
        columns = ['company_code', "billing_terms", "pricing_tier"]
        values = [self.company_code, self.billing_terms, self.pricing_tier]
        try:
            update_existing_record(
                database="meno_accounts",
                schema="accounts",
                table="organizations",
                update_columns=columns,
                update_values=values,
                where_column="primary_key_id",
                where_value=self.organization_id,
            )
            self.log.info(f"Organization {self.company_name} account record updated with activation details.")
        except Exception as e:
            self.log.error(f"Error updating organization account record: {e}", exc_info=True)
            raise e
        
        # Send approval email
        subject = "Your Organization has been approved!"
        html_email_body = get_html_email_str(
            content_path="emails/organization-approved.html",
            support_email="mod-customer-service@menoenterprises.com",
            content_context={
                "company_name": self.company_name.capitalize(),
                "login_url": url_for("internal_portal.login", _external=True),
                "company_code": self.company_code,
                "api_token": raw_api_token
            },
            sender_name="The Meno On-Demand Team",
        )
        
        email_list = [self.default_email]
        for email in [self.billing_email, self.order_update_email, self.ship_notif_email, self.tech_email]:
            if email and email not in email_list:
                email_list.append(email)
                
        automated_emails.email_from_memory(
            from_name="Meno No-Reply",
            from_email="no-reply@menoenterprises.com",
            to_email=email_list,
            subject=subject,
            body=html_email_body,
            is_html=True,
        )
        self.log.info(f"Approval email sent to {', '.join(email_list)}")
