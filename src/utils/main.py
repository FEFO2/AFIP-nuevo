# import libraries
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import os
from dotenv import load_dotenv

# import functions

# --- Download the reports ---
from download_afip_reports import download_reports
from download_bookit_reports import download_arancia_reports

# --- Process both reports ---
from afip_data_transformation import all
from bookit_data_transformation import all

# --- Compare both reports ---
from data_comparison import all

# --- Data upload ---
from data_upload import all

# ---------------------------------------------------------