#src/alerts/approved_cases_no_po_alert.py
"""Approved Cases No PO Alert Implementation.""" 
from typing import Dict, List, Optional
import pandas as pd 
from datetime import datetime, timedelta 
from zoneinfo import ZoneInfo
from sqlalchemy import text
import logging
 
from src.core.base_alert import BaseAlert 
from src.core.config import AlertConfig 
from src.db_utils import get_db_connection, validate_query_file, query_to_df


logger = logging.getLogger(__name__)


class ApprovedCasesNoPOAlert(BaseAlert):
    """Send alert to all departments about the need to move to the PO action 
        when purchases cases are approved and status is PO
    """

    def __init__(self, config: AlertConfig):
        """
        Initialise approved cases no po alert
        
        Args:
            config: AlertConfig instance
        """
        super().__init__(config)

        # Load query + lookback
        self.sql_vessel_cases_query_file = 'ApprovedCasesNoPO.sql'

        # Log instantiation
        self.logger.info("[OK] ApprovedCasesNoPOAlert instance created")

 
    def fetch_data(self) -> pd.DataFrame:
        """
        Fetch pending invoices and enrich with department-level email data.

        This method executes the following SQL query:
            1. Vessel query: retrieves pending invoice records

        Returns:
            pd.DataFrame with columns:

                - requisition_id: int
                - vessel: str
                - case_id: str
                - description: str
                - categories: str
                - supplier: str
                - rqn_status: str
                - is_approved: bool
                - created_by: str
                - updated_by: str
                - department_primary_email: str
                - department: str
                - updated_at: datetime

        Logging:
            Logs the number of rows returned after merging.
        """
        # Fetch SQL queries
        vessel_query_path = self.config.queries_dir / self.sql_vessel_cases_query_file
        vessel_query_sql = validate_query_file(vessel_query_path)

        # Convert query to sqlalchemy format
        vessel_query = text(vessel_query_sql)

        # Connect to db and execute queries
        with get_db_connection() as conn:
            df_vessel = pd.read_sql_query(vessel_query, conn)#, params=params)

        self.logger.info(f"ApprovedCasesNoPOAlert.fetch_data() is returning a df with {len(df_vessel)} rows")

        missing_emails = df_vessel[df_vessel['department_primary_email'].isna()]
        if not missing_emails.empty:
            self.logger.warning(
                f"No email mapping found for {missing_emails['department'].nunique()} "
                f"department(s): {missing_emails['department'].unique().tolist()} -- "
                f"these will be skipped during routing"
            )

        return df_vessel


    def filter_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create a custom filter - this alert does not need one, so it just ensures timezone issues are dealt with and date format
    
        Args:
            df: Raw pd.DataFrame from database
                cols:
                    requisition_id: int
                    vessel: str
                    case_id: str
                    description: str
                    categories: str
                    supplier: str
                    rqn_status: str
                    is_approved: bool
                    created_by: str
                    updated_by: str
                    department_primary_email: str
                    department: str
                    updated_at: datetime


        Returns:
            Filtered pd.DataFrame

        Note: this filter preserves the number of columns - which columns are going to be displayed is specified in formatter
        """
        if df.empty:
            return df

        # Timezone awareness
        df['updated_at'] = pd.to_datetime(df['updated_at'])

        # If the datetime is timezone-naive, localise it to UTC first, then convert to timezone specified in .env. I am assuming all times appearing are UTC, and then converting to TIMEZONE='Europe/Athens' will automatically be correct during Winter (UTC+2) and Summer (UTC+3).

        if df['updated_at'].dt.tz is None:
            df['updated_at'] = df['updated_at'].dt.tz_localize('UTC').dt.tz_convert(self.config.timezone)
        else:
            # If already timezone-aware, convert to timezone specified in .env
            df['updated_at'] = df['updated_at'].dt.tz_convert(self.config.timezone)

        """
        # Filter for invoices due in less than 31 days
        df_filtered = df[df['day_count'] <= 30].copy()

        # Include a priority column: RED & ORANGE definition
        df_filtered['priority'] = None
        df_filtered.loc[df_filtered['day_count'] <= 0, 'priority'] = 'OVERDUE'
        df_filtered.loc[(df_filtered['day_count'] > 0) & (df_filtered['day_count'] <= 30), 'priority'] = 'SOON DUE'
        """

        df_filtered = df.copy()
        df_filtered['updated_at'] = df_filtered['updated_at'].dt.strftime('%Y-%m-%d')
        self.logger.info(f"Filtered to {len(df_filtered)} entr{'y' if len(df_filtered)==1 else 'ies'}")

        return df_filtered


    def _get_url_links(self, ref: str) -> Optional[str]:
        """
        Generate URL if links are enabled.

        Constructs URL by combining:
            - BASE_URL from config (e.g. https://prominence.orca.tools)
            - URL_PATH from config (e.g. //purchasing/requisitions)
            - ref=requisition_id from database (e.g. 1234)
        Result: https://prominence.orca.tools/invoices/1234

        Args:
            ref: in PendingInvoices project, given by
                public.purchasing_requisitions.id = requisition_id

        Returns:
            Complete URL, or None if links are disabled
        """
        if not self.config.enable_links:
            return None

        # Build URL: BASE_URL + URL_PATH + link_id
        base_url = self.config.base_url.rstrip('/')
        url_path = self.config.url_path.rstrip('/')
        full_url = f"{base_url}{url_path}/{ref}"

        return full_url


    def route_notifications(self, df: pd.DataFrame) -> List[Dict]:
        """
        Route data to appropriate recipients.

        Returns list of notification jobs, where each job is a dict with:
        - 'recipients': List[str] - primary email addresses
        - 'cc_recipients': List[str] - CC email addresses
        - 'data': pd.DataFrame - data for this specific notification
        - 'metadata': Dict - any additional info (vessel name, etc.)

        Args:
            df: Filtered DataFrame
                Expected column names:
                    requisition_id: int
                    vessel: str
                    case_id: str
                    description: str
                    categories: str
                    supplier: str
                    rqn_status: str
                    is_approved: bool
                    created_by: str
                    updated_by: str
                    department_primary_email: str
                    department: str
                    updated_at: datetime

        Returns:
            List of notification job dictionaries
        """
        self.logger.info(
            f"route_notifications() called with {len(df)} record(s) "
            f"across {df['department'].nunique()} department(s)"
        )
        jobs = []

        # Group by department, keeping NaN departments visible
        grouped = df.groupby('department', dropna=False)
        self.logger.info(
            f"Grouped into {len(grouped)} department group(s): "
            f"{list(grouped.groups.keys())}"
        )

        for department, dept_df in grouped:
            self.logger.info(
                f"Processing department '{department}': "
                f"{len(dept_df)} record(s)"
            )

            # Determine cc recipients
            primary_email = dept_df['department_primary_email'].iloc[0]

            # Skip departments with no email configured
            if pd.isna(primary_email) or not primary_email:
                self.logger.warning(
                    f"No primary email for department '{department}' -- "
                    f"skipping {len(dept_df)} record(s)"
                )
                continue

            # Build to recipients: primary + secondary (if present)
            to_recipients = [primary_email]
            self.logger.info(
                f"Department '{department}': primary={primary_email}, "
                f"no secondary email"
            )

            # CC recipients: fixed internal list from config
            routing = self.config.email_routing.get('prominencemaritime.com', {})
            cc_recipients = routing.get('cc', []) + self.config.internal_recipients

            # URL
            dept_df = dept_df.copy()
            dept_df['url'] = dept_df['requisition_id'].apply(self._get_url_links)

            # Keep full data with tracking columns for the job
            full_data = dept_df.copy()

            # Specify WHICH cols to display in email and in what order here
            display_columns = [
                    'vessel',
                    'case_id',
                    'description',
                    'categories',
                    'supplier',
                    'rqn_status',
                    'created_by',
                    'updated_by',
                    'updated_at'
            ]

            # Create notification job
            job = {
                'recipients': to_recipients,
                'cc_recipients': cc_recipients,
                'data': full_data,
                'metadata': {
                    'alert_title': f'{department} Approved Cases w/out Dispatch PO to Supplier',
                    'department': department,
                    'company_name': 'Prominence Maritime S.A.',
                    'display_columns': display_columns
                }
            }

            jobs.append(job)
            self.logger.info(
                f"Created notification for department '{department}' "
                f"({len(full_data)} invoice{'' if len(full_data)==1 else 's'}) "
                f"-> {to_recipients} (CC: {len(cc_recipients)})"
            )

        if not jobs:
            self.logger.warning(
                f"route_notifications() produced 0 jobs from {len(df)} input "
                f"record(s) -- all departments were skipped"
            )

        return jobs


    def get_tracking_key(self, row:pd.Series) -> str:
        """
        Generate unique tracking key for a data row.

        This key is used to prevent duplicate notifications.

        Args:
            row: Single row from DataFrame

        Returns:
            Unique string key (e.g., "vessel_123_doc_456")
        """
        try:
            department = row['department']
            requisition_id = row['requisition_id']
            return f"department__{department}__requisition_id__{requisition_id}"
        except KeyError as e:
            self.logger.error(f"Missing column in row for tracking key: {e}")
            self.logger.error(f"Available columns: {list(row.index)}")
            raise


    def get_subject_line(self, data: pd.DataFrame, metadata: Dict) -> str:
        """
        Generate email subject line for a notification.

        Args:
            data: DataFrame for this notification
            metadata: Additional context (vessel name, etc.)

        Returns:
            Email subject string
        """
        department = metadata.get('department', 'Department')
        return f"AlertDev | {department} | {len(data)} Approved Case{'s' if len(data) != 1 else ''} with no PO"


    def get_required_columns(self) -> List[str]:
        """
        Return list of column names required in the DataFrame

        Returns:
            List of required column names
        """
        return [
                    'requisition_id',
                    'vessel',
                    'case_id',
                    'description',
                    'categories',
                    'supplier',
                    'rqn_status',
                    'is_approved',
                    'created_by',
                    'updated_by',
                    'department_primary_email',
                    'department',
                    'updated_at'
        ]
