# Approved Cases No PO Alert System

A modular, production-ready alert system for monitoring ORCA purchasing requisitions
that are approved but lack a dispatched Purchase Order. Built with a plugin-based
architecture that makes it easy to create new alert types by copying and customising
the project.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Testing](#testing)
- [Creating New Alert Projects](#creating-new-alert-projects)
- [Docker Deployment](#docker-deployment)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)

---

## Overview

This system monitors a PostgreSQL database for ORCA purchasing requisitions that have
reached `PO` status and have been fully approved through the review process, but for
which no Purchase Order has yet been dispatched to the supplier.

When cases matching these criteria are found, automated email notifications are routed
to the responsible department. Each department receives a tailored email listing only
its own cases, with clickable links directly to the relevant ORCA requisition.

**Current Alert Type**: Approved Cases with no PO Dispatch

- Queries `purchasing_requisitions` for cases in `po` status where the review process
  is fully complete and no PO dispatch has occurred
- Groups results by department and routes each notification to the correct department
  primary email address
- Includes clickable `case_id` links pointing to the requisition in ORCA
- Tracks sent notifications per `department + requisition_id` to prevent duplicates
- Optional reminder system after a configurable number of days

---

## Architecture

### Core Components

```
+-------------------------------------------------------------+
|                          main.py                            |
|                       (Entry Point)                         |
+----------------------+--------------------------------------+
                       |
          +------------+------------+
          |                         |
    +-----+------+           +------+------+
    | AlertConfig|           |  Scheduler  |
    |            |           |             |
    +-----+------+           +-----+-------+
          |                        |
          |               +--------+-----------------+
          |               |                          |
    +-----+------+  +-----+------+          +--------+-----+
    |  Tracker   |  | BaseAlert  |          |    Alert     |
    |            |  | (Abstract) |          |  Subclass    |
    +------------+  +-----+------+          +------+-------+
                          |                        |
                    +-----+----------+-------------+-------+
                    |                |                     |
            +-------+----+  +--------+-----+   +-----------+----+
            |EmailSender |  | Formatters   |   |  db_utils      |
            +------------+  +--------------+   +----------------+
```

### Module Breakdown

| Module | Purpose | Reusable? |
|--------|---------|-----------|
| `src/core/` | Config, tracking, scheduling, base alert class | Yes — shared across all alerts |
| `src/notifications/` | Email and Teams notification handlers | Yes — shared across all alerts |
| `src/formatters/` | HTML and plain text email templates | Yes — shared across all alerts |
| `src/utils/` | Validation, image loading utilities | Yes — shared across all alerts |
| `src/alerts/` | Alert-specific implementations | No — customised per alert type |
| `queries/` | SQL query files | No — customised per alert type |

---

## Features

### Current Features

- **Modular Architecture**: Plugin-based design for easy extensibility
- **Department-level Routing**: Each department receives only its own records
- **Rich HTML Emails**: Company-branded emails with embedded logos and responsive layout
- **Clickable Case Links**: `case_id` column links directly to the ORCA requisition
- **Duplicate Prevention**: Tracks sent events by `department + requisition_id`
- **Optional Reminders**: Re-send alerts after a configurable number of days, or never
- **Timezone Aware**: Dates localised from UTC to configured timezone (e.g. `Europe/Athens`)
- **Dry-Run Mode**: Redirect emails to a test address without touching real recipients
- **Command-Line Overrides**: `--dry-run` and `--run-once` flags override `.env` values
- **Graceful Shutdown**: SIGTERM/SIGINT handlers for clean container termination
- **Error Recovery**: Continues running after transient failures
- **Docker Support**: Fully containerised with `docker-compose`
- **SSH Tunnel Support**: Secure remote database access via `sshtunnel` + `paramiko`
- **Atomic File Operations**: Prevents tracking file corruption on interruption
- **Configurable Scheduling**: Run on a fixed frequency or at specific times and days
- **Rotating Logs**: Configurable file size and backup count

### Planned Features

- Microsoft Teams channel notifications
- Slack channel notifications

---

## Prerequisites

### Required Software

- **Python 3.13+**
- **Docker & Docker Compose** (recommended for deployment)
- **PostgreSQL** database (remote)
- **SSH key** (if accessing the database via SSH tunnel)

### Required Python Packages

See `requirements.txt` for exact versions.

**Core Dependencies**:

- `python-decouple==3.8` — Environment variable management
- `pandas==2.3.3` — Data manipulation
- `sqlalchemy==2.0.44` — Database connection pooling
- `psycopg2-binary==2.9.11` — PostgreSQL adapter
- `sshtunnel>=0.4.0,<1.0.0` — SSH tunnel for remote database access
- `paramiko>=2.12.0,<4.0.0` — SSH protocol implementation
- `pymsteams==0.2.5` — Microsoft Teams webhook integration *(planned)*
- `apscheduler>=3.10.0,<4.0.0` — Job scheduling

**Testing Dependencies**:

- `pytest==7.4.3`
- `pytest-cov==4.1.0`
- `pytest-mock==3.12.0`
- `freezegun==1.4.0`

**Install all dependencies**:
```bash
pip install -r requirements.txt
```

**Install only production dependencies**:
```bash
grep -v "^#\|pytest\|freezegun" requirements.txt | pip install -r /dev/stdin
```

### Required Access

- SMTP server credentials
- PostgreSQL database credentials
- SSH key for the database server (if using SSH tunnel)

---

## Installation

### Docker Deployment (Recommended)

1. **Clone the repository**:
```bash
cd ~/Dev
git clone git@github.com:prominencemaritime/approved-cases-no-po.git
cd approved-cases-no-po
```

2. **Create `.env` file**:
```bash
cp .env.example .env
vi .env
```

3. **Build and run**:
```bash
export UID=$(id -u) GID=$(id -g)
docker-compose build
docker-compose up -d
```

4. **Fix directory permissions** (important on Linux servers):
```bash
sudo chown -R $(id -u):$(id -g) logs/ data/
```

This step matters when:
- Deploying to a remote Linux server
- The `logs/` or `data/` directories were created by a different user (e.g. root)
- Using this project as a template for a new alert

5. **Verify it's running**:
```bash
docker-compose logs -f alerts
```

### Local Development Setup

1. **Clone the repository**:
```bash
cd ~/Dev
git clone git@github.com:prominencemaritime/approved-cases-no-po.git
cd approved-cases-no-po
```

2. **Create virtual environment**:
```bash
python3.13 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Create `.env` file**:
```bash
cp .env.example .env
vi .env
```

5. **Test the configuration**:
```bash
python -m src.main --dry-run --run-once
```

---

## Configuration

### Environment Variables (`.env`)

```bash
# ===========================================================================
# DATABASE CONFIGURATION
# ===========================================================================
DB_HOST=your.database.host.com
DB_PORT=5432
DB_NAME=your_database
DB_USER=your_user
DB_PASS=your_password

# SSH Tunnel (set USE_SSH_TUNNEL=True if database requires SSH tunnel)
USE_SSH_TUNNEL=True
SSH_HOST=your.ssh.host.com
SSH_PORT=22
SSH_USER=your_ssh_user
SSH_KEY_PATH=/app/ssh_ubuntu_key

# ===========================================================================
# EMAIL CONFIGURATION
# ===========================================================================
SMTP_HOST=smtp.yourcompany.com
SMTP_PORT=25
SMTP_USER=alerts@yourcompany.com
SMTP_PASS=your_app_password

# Internal recipients (always CC'd on all notifications)
INTERNAL_RECIPIENTS=admin@company.com,manager@company.com

# Company-specific CC recipients (matched by email domain)
PROMINENCE_EMAIL_CC_RECIPIENTS=user1@prominencemaritime.com,user2@prominencemaritime.com
SEATRADERS_EMAIL_CC_RECIPIENTS=user1@seatraders.com,user2@seatraders.com

# ===========================================================================
# DRY-RUN / TESTING CONFIGURATION
# ===========================================================================
# DRY_RUN=True: all emails redirected to DRY_RUN_EMAIL (if set),
#               otherwise no emails are sent at all.
# --dry-run CLI flag overrides this setting.
DRY_RUN=True
DRY_RUN_EMAIL=test@company.com

# RUN_ONCE=True: run once and exit (no scheduling)
RUN_ONCE=False

# ===========================================================================
# FEATURE FLAGS
# ===========================================================================
ENABLE_EMAIL_ALERTS=True
ENABLE_TEAMS_ALERTS=False
ENABLE_SPECIAL_TEAMS_EMAIL_ALERT=False
SPECIAL_TEAMS_EMAIL=

# ===========================================================================
# CLICKABLE LINKS CONFIGURATION
# ===========================================================================
# When enabled, the case_id column in the email table becomes a clickable
# link pointing to the ORCA requisition.
ENABLE_LINKS=True
BASE_URL=https://prominence.orca.tools
# Full URL will be: {BASE_URL}{URL_PATH}/{requisition_id}
# Example: https://prominence.orca.tools/purchasing/requisitions/1234
URL_PATH=/purchasing/requisitions

# ===========================================================================
# COMPANY BRANDING
# ===========================================================================
PROMINENCE_LOGO=trans_logo_prominence_procreate_small.png
SEATRADERS_LOGO=

# ===========================================================================
# SCHEDULING
# ===========================================================================
# Leave SCHEDULE_FREQUENCY_HOURS blank to use time-based scheduling instead.
# SCHEDULE_TIMES: comma-separated HH:MM values (e.g. 11:00 or 11:00,18:00)
# SCHEDULE_DAYS: isoweekday (1=Monday ... 7=Sunday); leave blank for every day
SCHEDULE_FREQUENCY_HOURS=
SCHEDULE_TIMES=11:00
SCHEDULE_DAYS=2
SCHEDULE_TIMES_TIMEZONE=Europe/Athens
TIMEZONE=UTC

# ===========================================================================
# TRACKING & REMINDERS
# ===========================================================================
# Leave REMINDER_FREQUENCY_DAYS blank to never re-send (track forever).
# Set to a number (e.g. 7) to re-send notifications after that many days.
REMINDER_FREQUENCY_DAYS=
SENT_EVENTS_FILE=sent_alerts.json
RESEND_EVENTS_ON=True

# ===========================================================================
# ALERT-SPECIFIC CONFIGURATION
# ===========================================================================
SQL_QUERY_FILE=ApprovedCasesNoPO.sql
LOOKBACK_DAYS=730
INCLUDE_GREY_METADATA_SECTION=True

# ===========================================================================
# LOGGING
# ===========================================================================
LOG_FILE=alerts.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# ===========================================================================
# USER PERMISSIONS (for Docker)
# ===========================================================================
# Obtain with: echo UID=$(id -u) && echo GID=$(id -g)
UID=502
GID=502
```

### Configuration Notes

**SSH Tunnel**:
- Set `USE_SSH_TUNNEL=True` if the database is only reachable via SSH
- `SSH_KEY_PATH` must point to a mounted private key inside the container
- The `docker-compose.yml` mounts two SSH keys: an RSA4096 key and a `.pem` key;
  set `SSH_KEY_PATH` to whichever your server requires

**DRY_RUN Mode**:
- `DRY_RUN=True` in `.env` redirects all emails to `DRY_RUN_EMAIL` addresses
- `--dry-run` CLI flag forces dry-run mode regardless of `.env`
- Three-layer safety: `.env` setting → CLI flag → `EmailSender` runtime check

**REMINDER_FREQUENCY_DAYS**:
- Empty/blank: never re-send (events tracked permanently)
- Number (e.g. `7`): re-send notifications after that many days

**Clickable Links**:
- `ENABLE_LINKS=True` makes the `case_id` column in the email table a hyperlink
- `BASE_URL` + `URL_PATH` + `/{requisition_id}` forms the full URL
- Example: `https://prominence.orca.tools/purchasing/requisitions/5995`

**Email Routing**:
- `TO` recipients are determined by `department_primary_email` from the database
- `CC` recipients come from `email_routing` config matched by email domain, plus
  `INTERNAL_RECIPIENTS`
- Departments with no email configured are skipped and logged as warnings

**Scheduling**:
- Set `SCHEDULE_FREQUENCY_HOURS` for interval-based scheduling (e.g. `0.5` = every
  30 minutes)
- Leave it blank and set `SCHEDULE_TIMES` + `SCHEDULE_DAYS` for calendar-based
  scheduling (e.g. every Tuesday at 11:00)

---

## Usage

### Command Line Options

```bash
# Dry-run, execute once (redirects emails to DRY_RUN_EMAIL)
python -m src.main --dry-run --run-once

# Execute once and exit (uses .env DRY_RUN setting)
python -m src.main --run-once

# Run continuously on the configured schedule (production mode)
python -m src.main

# Docker equivalents
docker-compose run --rm alerts python -m src.main --dry-run --run-once
docker-compose run --rm alerts python -m src.main --run-once
docker-compose up -d
```

### Command-Line Flags

| Flag | Effect | Overrides .env? |
|------|--------|-----------------|
| `--dry-run` | Redirects all emails to `DRY_RUN_EMAIL` | Yes — forces dry-run on |
| `--run-once` | Executes once and exits | No |
| (none) | Runs continuously on schedule | No |

### Expected Output (Dry-Run)

```
======================================================================
▶ ALERT SYSTEM STARTING
======================================================================
[OK] Configuration validation passed
======================================================================
DRY RUN MODE - EMAILS REDIRECTED TO: test@company.com
======================================================================
[OK] Event tracker initialised
[OK] Email sender initialised (DRY-RUN MODE - emails redirected to test@company.com)
[OK] Formatters initialised
[OK] Registered Approved Cases No PO Alert
============================================================
▶ RUN-ONCE MODE: Executing alerts once without scheduling
============================================================
Running 1 alert(s)...
Executing alert 1/1...
============================================================
▶ ApprovedCasesNoPOAlert RUN STARTED
============================================================
--> Fetching data from database...
ApprovedCasesNoPOAlert.fetch_data() is returning a df with 14 rows
--> Applying filtering logic...
Filtered to 14 entries
--> Checking for previously sent notifications...
[OK] 14 new record(s) to notify
--> Routing notifications to recipients...
route_notifications() called with 14 record(s) across 3 department(s)
Created notification for department 'Technical' (6 invoices) -> ['tech@prominencemaritime.com'] (CC: 2)
Created notification for department 'Procurement' (5 invoices) -> ['proc@prominencemaritime.com'] (CC: 2)
Created notification for department 'Operations' (3 invoices) -> ['ops@prominencemaritime.com'] (CC: 2)
--> Sending notification 1/3...
[DRY-RUN-EMAIL] Redirecting to: test@company.com
[DRY-RUN-EMAIL] Subject: AlertDev | Technical | 6 Approved Cases with no PO
[OK] Sent notification 1/3
...
[OK] Marked 14 event(s) as sent
◼ ApprovedCasesNoPOAlert RUN COMPLETE
```

### Production Output

```
======================================================================
▶ ALERT SYSTEM STARTING
======================================================================
[OK] Configuration validation passed
[OK] Event tracker initialised
[OK] Email sender initialised
[OK] Formatters initialised
[OK] Registered Approved Cases No PO Alert
============================================================
▶ SCHEDULER STARTED
Schedule: Tuesday at 11:00 Europe/Athens
Registered alerts: 1
============================================================
[OK] Next run at: 2026-05-20 11:00:00 EEST
Running 1 alert(s)...
...
[OK] Sent notification to tech@prominencemaritime.com
[OK] CC: data@prominencemaritime.com
[OK] Marked 14 event(s) as sent
◼ ApprovedCasesNoPOAlert RUN COMPLETE
```

---

## Testing

### Running Tests

**Local**:
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term --cov-report=html

# Run a specific test file
pytest tests/test_config.py -v

# Run a specific test
pytest tests/test_tracking.py::test_tracker_marks_events_as_sent -v
```

**Docker (recommended)**:
```bash
# Run all tests
docker-compose run --rm alerts pytest tests/ -v

# Run with coverage
docker-compose run --rm alerts pytest tests/ --cov=src --cov-report=term

# Interactive shell
docker-compose run --rm alerts bash
pytest tests/ -v
exit
```

### Test Coverage

| Module | Coverage | Status |
|--------|----------|--------|
| `src/core/config.py` | 98% | Excellent |
| `src/formatters/text_formatter.py` | 95% | Excellent |
| `src/formatters/html_formatter.py` | 91% | Excellent |
| `src/alerts/approved_cases_no_po_alert.py` | 88% | Good |
| `src/core/base_alert.py` | 74% | Good |
| `src/core/tracking.py` | 71% | Acceptable |
| `src/notifications/email_sender.py` | 57% | Acceptable |
| `src/core/scheduler.py` | 47% | Needs work |
| `src/db_utils.py` | 32% | Needs work |
| `src/main.py` | 0% | Not tested (entry point) |

**Generate an HTML coverage report**:
```bash
docker-compose run --rm alerts pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### Test Structure

```
tests/
├── conftest.py                           # Shared fixtures
├── test_config.py                        # Config loading and validation
├── test_tracking.py                      # Duplicate prevention and reminders
├── test_approved_cases_no_po_alert.py    # Alert logic and routing
├── test_formatters.py                    # HTML/text email generation
├── test_email_sender.py                  # Email sending functionality
├── test_scheduler.py                     # Scheduling and execution
└── test_integration.py                   # End-to-end workflow tests
```

---

## Creating New Alert Projects

The modular design makes it straightforward to create new alert types. The recommended
approach is to copy the entire project to a new directory — one alert per container.

### Step-by-Step Guide

#### 1. Copy the Project

```bash
cd ~/Dev
cp -r approved-cases-no-po hot-works-alerts
cd hot-works-alerts
```

#### 2. Clean Up Old Data

```bash
rm -rf data/*.json logs/*.log
rm -rf .git
git init
sudo chown -R $(id -u):$(id -g) logs/ data/
```

#### 3. Update Configuration

```bash
vi .env
```

Key changes:
```bash
SCHEDULE_FREQUENCY_HOURS=1.0
REMINDER_FREQUENCY_DAYS=7
INTERNAL_RECIPIENTS=hotworks-admin@company.com
LOOKBACK_DAYS=7
URL_PATH=/hot-works
```

#### 4. Update Docker Configuration

```yaml
# docker-compose.yml
services:
  alerts:
    container_name: hot-works-alerts-app   # change this
    ...
```

#### 5. Create SQL Query

```bash
rm queries/ApprovedCasesNoPO.sql
vi queries/HotWorkPermits.sql
```

#### 6. Create Alert Implementation

```bash
rm src/alerts/approved_cases_no_po_alert.py
vi src/alerts/hot_works_alert.py
```

**Template**:
```python
"""Hot Works Alert Implementation."""
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy import text

from src.core.base_alert import BaseAlert
from src.core.config import AlertConfig
from src.db_utils import get_db_connection, validate_query_file, query_to_df


class HotWorksAlert(BaseAlert):
    """Alert for hot work permits requiring action."""

    def __init__(self, config: AlertConfig):
        super().__init__(config)
        self.sql_query_file = 'HotWorkPermits.sql'
        self.logger.info("[OK] HotWorksAlert instance created")

    def fetch_data(self) -> pd.DataFrame:
        query_path = self.config.queries_dir / self.sql_query_file
        sql = validate_query_file(query_path)
        with get_db_connection() as conn:
            df = pd.read_sql_query(text(sql), conn)
        self.logger.info(f"fetch_data() returned {len(df)} rows")
        return df

    def filter_data(self, df: pd.DataFrame) -> pd.DataFrame:
        # Add alert-specific filtering here
        return df.copy()

    def route_notifications(self, df: pd.DataFrame) -> List[Dict]:
        # Group and route to recipients
        ...

    def get_tracking_key(self, row: pd.Series) -> str:
        return f"vessel__{row['vessel_id']}__permit__{row['permit_id']}"

    def get_subject_line(self, data: pd.DataFrame, metadata: Dict) -> str:
        return f"AlertDev | Hot Works | {len(data)} Permit(s) Pending"

    def get_required_columns(self) -> List[str]:
        return ['vessel_id', 'permit_id', ...]
```

#### 7. Register the Alert in main.py

```python
# src/main.py
from src.alerts.hot_works_alert import HotWorksAlert

def register_alerts(scheduler, config):
    alert = HotWorksAlert(config)
    scheduler.register_alert(alert.run)
    logger.info("[OK] Registered HotWorksAlert")
```

#### 8. Update Tests

```bash
cp tests/test_approved_cases_no_po_alert.py tests/test_hot_works_alert.py
vi tests/test_hot_works_alert.py
```

---

## Docker Deployment

### Building and Running

```bash
# Set user permissions
export UID=$(id -u) GID=$(id -g)

# Build image
docker-compose build

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f alerts

# Stop
docker-compose down
```

### Useful Docker Commands

```bash
# Execute a dry-run inside the running container
docker-compose exec alerts python -m src.main --dry-run --run-once

# Open an interactive shell
docker-compose exec alerts bash

# Inspect the tracking file
docker-compose exec alerts cat data/sent_alerts.json | python -m json.tool

# Tail only error-level log lines
docker-compose logs alerts | grep ERROR

# Force rebuild (after dependency changes)
docker-compose build --no-cache
docker-compose up -d
```

### SSH Key Mounts

The `docker-compose.yml` mounts two SSH keys as read-only volumes:

```yaml
volumes:
  - /Users/prominence/.ssh/prominence_user_key_rsa4096:/app/ssh_key:ro
  - /Users/prominence/.ssh/datalab_prominence_prod.pem:/app/ssh_ubuntu_key:ro
```

Set `SSH_KEY_PATH` in `.env` to whichever path is used by your server
(`/app/ssh_key` or `/app/ssh_ubuntu_key`).

---

## Project Structure

```
approved-cases-no-po/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env                                    # Not committed
├── .env.example
├── README.md
│
├── queries/
│   └── ApprovedCasesNoPO.sql               # Main query
│
├── src/
│   ├── main.py                             # Entry point
│   │
│   ├── core/
│   │   ├── base_alert.py                   # Abstract base class
│   │   ├── config.py                       # AlertConfig dataclass
│   │   ├── scheduler.py                    # APScheduler wrapper
│   │   └── tracking.py                     # Duplicate prevention
│   │
│   ├── alerts/
│   │   └── approved_cases_no_po_alert.py   # Alert implementation
│   │
│   ├── notifications/
│   │   ├── email_sender.py                 # SMTP email sender
│   │   └── teams_sender.py                 # Teams webhook sender
│   │
│   ├── formatters/
│   │   ├── html_formatter.py               # HTML email builder
│   │   ├── text_formatter.py               # Plain text email builder
│   │   └── date_formatter.py               # Date utility functions
│   │
│   └── db_utils.py                         # DB connection + query helpers
│
├── media/
│   └── trans_logo_prominence_procreate_small.png
│
├── data/
│   └── sent_alerts.json                    # Tracking file (auto-created)
│
├── logs/
│   └── alerts.log                          # Rotating log file (auto-created)
│
└── tests/
    ├── conftest.py
    ├── test_config.py
    ├── test_tracking.py
    ├── test_approved_cases_no_po_alert.py
    ├── test_formatters.py
    ├── test_email_sender.py
    ├── test_scheduler.py
    └── test_integration.py
```

---

## Key Concepts

### Abstract Base Class Pattern

`BaseAlert` defines the contract all alerts must implement:

```python
class BaseAlert(ABC):
    @abstractmethod
    def fetch_data(self) -> pd.DataFrame: ...

    @abstractmethod
    def filter_data(self, df: pd.DataFrame) -> pd.DataFrame: ...

    @abstractmethod
    def route_notifications(self, df: pd.DataFrame) -> List[Dict]: ...

    @abstractmethod
    def get_tracking_key(self, row: pd.Series) -> str: ...

    @abstractmethod
    def get_subject_line(self, data: pd.DataFrame, metadata: Dict) -> str: ...

    @abstractmethod
    def get_required_columns(self) -> List[str]: ...

    def run(self) -> bool:
        """Complete workflow — already implemented in base class."""
        df = self.fetch_data()
        df_filtered = self.filter_data(df)
        # ... tracking, routing, sending
```

You implement the six abstract methods (~80 lines of alert-specific logic) and get
the full infrastructure — error handling, tracking, formatting, sending — for free.

### Tracking System

```
Requisition appears in query result
  |
  v
Check: Is tracking_key in sent_alerts.json?
  |
  +-- NO (new record)
  |     Send notification
  |     Save tracking_key + timestamp to sent_alerts.json
  |
  +-- YES (already sent)
        Check: Is record older than REMINDER_FREQUENCY_DAYS?
          |
          +-- YES  -> Send reminder, update timestamp
          +-- NO   -> Skip (notified recently)
```

**Tracking key format for this alert**:
```python
f"department__{department}__requisition_id__{requisition_id}"
# Example: "department__Technical__requisition_id__5995"
```

When `REMINDER_FREQUENCY_DAYS` is blank, notifications are sent exactly once and
the record is tracked permanently.

### Email Routing Logic

```
1. fetch_data() returns department_primary_email for each row
   |
2. route_notifications() groups by department
   |
3. For each department:
   - TO:  department_primary_email (from database)
   - CC:  email_routing config (matched by domain) + INTERNAL_RECIPIENTS
   - DATA: only that department's rows
   |
4. Departments with no email are skipped (logged as warnings)
```

### Clickable Links System

```
1. ENABLE_LINKS=True in config
   |
2. route_notifications() adds a 'url' column:
   df['url'] = df['requisition_id'].apply(self._get_url_links)
   |
3. _get_url_links() constructs:
   BASE_URL + URL_PATH + "/" + requisition_id
   -> https://prominence.orca.tools/purchasing/requisitions/5995
   |
4. html_formatter._render_cell() detects column == 'case_id'
   -> wraps value in <a href="..."> tag
   |
5. Recipient clicks case_id in email -> opens requisition in ORCA
```

### Dry-Run Safety Layers

Three independent layers prevent accidental production sends:

1. `.env` `DRY_RUN=True` — redirects emails at config load time
2. `--dry-run` CLI flag — overrides `.env`, forces dry-run mode
3. `EmailSender` runtime check — raises `RuntimeError` if `dry_run=True` and a
   real send is attempted

---

## Troubleshooting

### Common Issues

**Container exits immediately**:
```bash
docker-compose logs alerts
# Look for configuration errors or missing .env variables
```

**No emails sent, no errors**:
```bash
# Check if all departments were skipped due to missing emails
docker-compose logs alerts | grep -i "skipping\|no email\|warning"

# Inspect the tracking file — records may already be marked as sent
cat data/sent_alerts.json | python -m json.tool
```

**PermissionError on startup**:
```bash
sudo chown -R $(id -u):$(id -g) logs/ data/
export UID=$(id -u) GID=$(id -g)
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

**SSH tunnel fails**:
```bash
# Verify key permissions
chmod 600 ~/.ssh/your_key

# Test connectivity manually
ssh -i ~/.ssh/your_key your_user@your.ssh.host.com -N -L 5432:db_host:5432
```

**Query returns no rows**:
```bash
# Run the SQL directly against the database to verify
psql -h localhost -U your_user -d your_database -f queries/ApprovedCasesNoPO.sql
```

**Stale notifications (already-sent records not re-sending)**:
```bash
# If REMINDER_FREQUENCY_DAYS is blank, records are tracked forever
# To force a re-run, clear the tracking file:
echo '{}' > data/sent_alerts.json
```

### Useful Diagnostics

```bash
# Tail live logs
docker-compose logs -f alerts

# Last 50 lines
docker-compose logs --tail=50 alerts

# Check container health
docker inspect --format='{{json .State.Health}}' approved-cases-no-po-alerts-app

# Run a one-shot dry-run without disturbing the running container
docker-compose run --rm alerts python -m src.main --dry-run --run-once
```

### Pre-Deployment Checklist

- [ ] Dry-run completes without errors: `docker-compose run --rm alerts python -m src.main --dry-run --run-once`
- [ ] SQL query returns the expected columns (see `get_required_columns()`)
- [ ] Department primary emails are populated in the database
- [ ] `INTERNAL_RECIPIENTS` configured correctly in `.env`
- [ ] `DRY_RUN=False` set for production
- [ ] `DRY_RUN_EMAIL` contains valid test addresses for pre-production validation
- [ ] Company logo exists in `media/` directory
- [ ] `ENABLE_LINKS=True`, `BASE_URL` and `URL_PATH` are correct
- [ ] Tracking file is empty or contains only valid entries: `cat data/sent_alerts.json`
- [ ] No duplicate notifications on second dry-run
- [ ] Docker build succeeds: `docker-compose build`
- [ ] Container starts: `docker-compose up -d`
- [ ] Container stays running: `docker-compose ps`
- [ ] Logs show successful execution: `docker-compose logs -f alerts`
- [ ] All tests pass: `docker-compose run --rm alerts pytest tests/ -v`

---

## Key Concepts Reference

### Configuration Flow

```
.env file
  |
  v
python-decouple reads values
  |
  v
AlertConfig.from_env() parses and validates
  |
  v
AlertConfig instance injected into all components
  |
  v
Accessed via self.config throughout the application
```

---

## Support

1. Review logs: `docker-compose logs -f alerts`
2. Test in dry-run: `docker-compose run --rm alerts python -m src.main --dry-run --run-once`
3. Inspect the tracking file: `cat data/sent_alerts.json | python -m json.tool`
4. Run the test suite: `docker-compose run --rm alerts pytest tests/ -v`
5. Contact: data@prominencemaritime.com

---

## License

Proprietary — Prominence Maritime S.A. / Seatraders

---

## Quick Start Summary

```bash
# 1. Clone
git clone git@github.com:prominencemaritime/approved-cases-no-po.git
cd approved-cases-no-po

# 2. Configure
cp .env.example .env
vi .env

# 3. Build and dry-run
export UID=$(id -u) GID=$(id -g)
docker-compose build
docker-compose run --rm alerts python -m src.main --dry-run --run-once

# 4. Run tests
docker-compose run --rm alerts pytest tests/ -v

# 5. Deploy
docker-compose up -d

# 6. Monitor
docker-compose logs -f alerts
```

---

## Additional Resources

- [python-decouple](https://pypi.org/project/python-decouple/)
- [Pandas documentation](https://pandas.pydata.org/docs/)
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/)
- [Docker Compose documentation](https://docs.docker.com/compose/)
- [APScheduler documentation](https://apscheduler.readthedocs.io/)
- [pytest documentation](https://docs.pytest.org/)

---

*Last updated: May 2026*
