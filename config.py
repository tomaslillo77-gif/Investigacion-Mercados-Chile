"""Configuration for Portfolio Dashboard"""

# Data sources
EXCEL_DATA_PATH = "data/portfolio_data.xlsx"

# API Configuration
API_HOST = "127.0.0.1"
API_PORT = 8000

# Risk America API (to be integrated)
RISK_AMERICA_API_KEY = ""  # Set this in .env
RISK_AMERICA_API_URL = "https://api.riskamerica.com"  # Example URL

# Investment Advisors (6 advisors + 1 director)
ADVISORS = [
    "advisor_1",
    "advisor_2",
    "advisor_3",
    "advisor_4",
    "advisor_5",
    "advisor_6"
]

MANAGING_DIRECTOR = "managing_director"

# Portfolio Architectures (4 architectures × 5 risk profiles = 20 possible portfolios)
ARCHITECTURES = ["Conservative", "Balanced", "Growth", "Aggressive"]
RISK_PROFILES = ["Low", "Low-Medium", "Medium", "Medium-High", "High"]

# Rebalancing threshold (deviation in %)
REBALANCE_THRESHOLD = 5.0

# Dashboard settings
STREAMLIT_THEME = "light"
STREAMLIT_PAGE_TITLE = "Client Portfolio Dashboard"
