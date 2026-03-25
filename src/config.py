"""Constantes et configuration du jeu ERPsim."""

# --- Produits et regions (noms SAP ERPsim) ---
PRODUCTS = ["Milk", "Cream", "Yoghurt", "Cheese", "Butter", "Ice Cream"]
REGIONS = ["Nord", "Sud", "Ouest"]

# --- Mapping SAP ---
MATERIAL_IDS = {
    "Milk": "LL-T01", "Cream": "LL-T02", "Yoghurt": "LL-T03",
    "Cheese": "LL-T04", "Butter": "LL-T05", "Ice Cream": "LL-T06",
}

# --- Preferences regionales (poids relatifs) ---
REGIONAL_PREFERENCES = {
    "Nord": {"Milk": 1.5, "Cream": 1.0, "Yoghurt": 1.0, "Cheese": 1.0, "Butter": 1.0, "Ice Cream": 1.5},
    "Sud": {"Milk": 1.0, "Cream": 1.0, "Yoghurt": 1.5, "Cheese": 1.0, "Butter": 1.0, "Ice Cream": 1.5},
    "Ouest": {"Milk": 1.0, "Cream": 1.0, "Yoghurt": 1.0, "Cheese": 1.5, "Butter": 1.0, "Ice Cream": 1.0},
}

# --- Garde-fous ---
WAREHOUSE_CAPACITY = 4000
WAREHOUSE_WARNING_THRESHOLD = 3800
WAREHOUSE_PENALTY_PER_DAY = 300
CASH_MINIMUM = 50_000
MAX_PRICE_CHANGE_PCT = 0.15  # 15% max par cycle
INITIAL_ORDER_QUANTITY = 6000

# --- Finance ---
STARTING_CAPITAL = 500_000
STARTING_CASH = 250_000

# --- Phases de jeu ---
MANUAL_ROUNDS = 3  # Rounds 1-3 en mode manuel
MIN_CYCLES_FOR_ELASTICITY = 4  # Minimum de cycles pour calculer l'elasticite

# --- OpenRouter API ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4"
MAX_AGENT_TOKENS = 1024

# --- Cycle ---
DECISION_CYCLE_ORDER = ["finance_eval", "prix", "stock", "finance_veto", "display"]
