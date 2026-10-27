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


def get_cluster_conflicts(symbol: str, active_symbols: List[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """Check if 'symbol' conflicts with any currently active symbols in the same cluster.
    
    Returns:
        (is_blocked, cluster_name, conflicting_active_symbol)
    """
    sym = str(symbol or "").upper().replace(".M", "").replace("_", "").strip()
    cluster = get_symbol_cluster(sym)
    if not cluster:
        # Jika simbol tidak termasuk kluster khusus, hanya blokir jika simbol yang sama persis sedang aktif
        for act in active_symbols:
            act_clean = str(act or "").upper().replace(".M", "").replace("_", "").strip()
            if act_clean == sym:
                return True, "EXACT_SYMBOL", act_clean
        return False, None, None

    cluster_members = CURRENCY_CLUSTERS[cluster]
    for act in active_symbols:
        act_clean = str(act or "").upper().replace(".M", "").replace("_", "").strip()
        if not act_clean:
            continue
        # 1. Jika simbol yang sama persis sedang aktif
        if act_clean == sym:
            return True, cluster, act_clean
        # 2. Jika simbol lain dalam kluster yang sama sedang aktif (Correlation Shield)
        if act_clean in cluster_members:
            return True, cluster, act_clean

    return False, None, None
