"""Currency Cluster and Correlation Shield definitions for AI Trading Bot.

Prevents multi-asset correlation over-exposure (e.g. simultaneous trades on USDJPY, GBPJPY, EURJPY).
Enforces maximum 1 active trade per currency cluster.
"""

from typing import Dict, List, Optional, Set, Tuple

# Pemetaan Simbol ke Kluster Korelasi Utama
# Aturan: Hanya boleh ada maksimal 1 posisi aktif per kluster di seluruh akun.
CURRENCY_CLUSTERS: Dict[str, Set[str]] = {
    "JPY_CLUSTER": {
        "USDJPY", "GBPJPY", "EURJPY", "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY"
    },
    "EUR_GBP_MAJORS": {
        "EURUSD", "GBPUSD", "EURGBP"
    },
    "COMMODITY_FX": {
        "USDCAD", "AUDUSD", "NZDUSD", "AUDCAD"
    },
    "EUR_CROSSES": {
        "EURCAD", "EURAUD", "EURCHF"
    },
    "GBP_CROSSES": {
        "GBPCAD", "GBPAUD"
    },
    "GOLD_METALS": {
        "XAUUSD", "GOLD", "XAGUSD", "SILVER"
    },
    "CHF_CLUSTER": {
        "USDCHF"
    }
}


def get_symbol_cluster(symbol: str) -> Optional[str]:
    """Return the cluster name for a given symbol, or None if unclustered."""
    sym = str(symbol or "").upper().replace(".M", "").replace("_", "").strip()
    for cluster_name, members in CURRENCY_CLUSTERS.items():
        if sym in members:
            return cluster_name
    return None


def get_cluster_conflicts(
    symbol: str,
    active_symbols: List[str],
    max_per_cluster: int = 2
) -> Tuple[bool, Optional[str], Optional[str]]:
    """Check if 'symbol' conflicts with any currently active symbols in the same cluster.
    
    Rules:
    1. STRICT Max 1 Active Position per EXACT Symbol:
       A symbol can never have >1 open position (e.g. no 2 active USDJPY trades).
    2. Cluster Cap (default: max 2 active positions per cluster):
       Allows up to max_per_cluster positions from the same cluster (e.g. 1 USDJPY + 1 GBPJPY is allowed,
       but a 3rd JPY pair like EURJPY will be blocked).
    
    Returns:
        (is_blocked, cluster_name, conflicting_active_symbol_or_details)
    """
    sym = str(symbol or "").upper().replace(".M", "").replace("_", "").strip()
    
    # 1. ATURAN MUTLAK: Dilarang keras membuka 2 posisi pada simbol yang sama persis (Anti-Duplicate Orders)
    for act in active_symbols:
        act_clean = str(act or "").upper().replace(".M", "").replace("_", "").strip()
        if act_clean == sym:
            return True, "EXACT_SYMBOL", act_clean

    cluster = get_symbol_cluster(sym)
    if not cluster:
        return False, None, None

    # 2. ATURAN KLUSTER: Hitung berapa banyak posisi aktif yang saat ini berjalan di kluster yang sama
    cluster_members = CURRENCY_CLUSTERS[cluster]
    cluster_active = [
        act for act in active_symbols
        if str(act or "").upper().replace(".M", "").replace("_", "").strip() in cluster_members
    ]

    if len(cluster_active) >= max_per_cluster:
        conflicting_desc = ", ".join(cluster_active)
        return True, cluster, f"{conflicting_desc} (Batas Kuota Kluster: {max_per_cluster})"

    return False, None, None
