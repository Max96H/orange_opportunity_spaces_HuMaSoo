from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

FRONTEND_PATH = PROJECT_ROOT / "src" / "frontend"

DB_PATH = PROJECT_ROOT / "data" / "opportunity_spaces.db"
DATA_PATH = PROJECT_ROOT / "data" / "os_example.json"
CSS_PATH = FRONTEND_PATH / "assets" / "alt_styles.css"
GITHUB_LOGO_PATH = FRONTEND_PATH / "assets" / "humasoo_logo.png"
GITHUB_URL = "https://github.com/husseinabuammar24-cloud/orange_opportunity_spaces_HuMaSoo"

ORANGE_BUSINESS_DOMAINS = [
    "Smart Industries",
    "Connectivity Solutions",
    "Cybersecurity",
    "Cloud",
    "Customer Experience",
    "Employee Experience",
    "Sustainability",
]
