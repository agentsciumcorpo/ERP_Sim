"""Constantes et configuration du jeu ERPsim."""

# --- Produits et regions ---
PRODUCTS = ["Lait", "Creme", "Yaourt", "Fromage", "Beurre", "Glace"]
REGIONS = ["Nord", "Sud", "Ouest"]

# --- Preferences regionales (poids relatifs) ---
REGIONAL_PREFERENCES = {
    "Nord": {"Lait": 1.5, "Creme": 1.0, "Yaourt": 1.0, "Fromage": 1.0, "Beurre": 1.0, "Glace": 1.5},
    "Sud": {"Lait": 1.0, "Creme": 1.0, "Yaourt": 1.5, "Fromage": 1.0, "Beurre": 1.0, "Glace": 1.5},
    "Ouest": {"Lait": 1.0, "Creme": 1.0, "Yaourt": 1.0, "Fromage": 1.5, "Beurre": 1.0, "Glace": 1.0},
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
