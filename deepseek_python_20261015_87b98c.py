#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════
  7-LOGIC MAJORITY BETTING BOT — WinGo 1 M  (v3)
═══════════════════════════════════════════════════════════════
  Lottery: WinGo 1M (1-minute rounds)  ← fixed
  Logics : Golden · Jishan · Dragon · Soloprime · Safa · Devid · Akki
  Rule   : 4+ of 7 must agree → signal, else skip
  Ladder : ₹10 → ₹20 → ₹40 → ₹80 → ₹160 → ₹320   (6 levels)
  Bank   : ₹1000 starting, full P/L tracking
═══════════════════════════════════════════════════════════════
"""

import requests
import time
import sys
import json
import os
from datetime import datetime

# ═══════════════════════════════════════════
#  CONFIG
# ═══════════════════════════════════════════
BOT_TOKEN       = "6958371620:AAHrdxkgguufmymxH8zbfCnyvsQVU7pMwAI"
CHAT_ID         = "5095920393"

# ── LOTTERY: WinGo 1 M (1-minute) ──
API_URL         = "https://draw.ar-lottery01.com/WinGo/WinGo_1M/GetHistoryIssuePage.json"
GAME_LABEL      = "WinGo 1M"                 # 1-minute game
ROUND_SECONDS   = 60                         # 60-second rounds

POLL_INTERVAL   = 15
MAJORITY        = 4                          # 4+ of 7 must agree
CACHE_FILE      = "majority_cache.json"
STATE_FILE      = "majority_state.json"
HEARTBEAT_EVERY = 40

# ── Money config ──
START_BANKROLL  = 1000        # ₹1000
BASE_BET        = 10
MULTIPLIER      = 2
MAX_LEVEL       = 6           # L1=10, L2=20, L3=40, L4=80, L5=160, L6=320
PAYOUT_MULT     = 2.0

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Mobile Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.pakvip.live/",
}

def log(*a):
    print(*a, flush=True)


# ═══════════════════════════════════════════
#  PERSISTENCE
# ═══════════════════════════════════════════
def load_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def save_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        log(f"⚠️  save error: {e}")


# ═══════════════════════════════════════════
#  FETCH — WinGo 1M
# ═══════════════════════════════════════════
def fetch_latest():
    try:
        r = requests.get(f"{API_URL}?t={int(time.time()*1000)}",
                         timeout=10, headers=HEADERS)
        if r.status_code != 200: return []
        j = r.json()
        for path in (('data','list'), ('data','data'), ('list',), ('result','list')):
            cur = j; ok = True
            for k in path:
                if isinstance(cur, dict) and k in cur: cur = cur[k]
                else: ok = False; break
            if ok and isinstance(cur, list): return cur
        return []
    except Exception as e:
        log(f"   ⚠️  fetch error: {e}")
        return []


# ═══════════════════════════════════════════
#  LOGIC 1 — GOLDEN
# ═══════════════════════════════════════════
GOLDEN_MAP = {
    '0':'BIG','1':'SMALL','2':'SMALL','3':'BIG','4':'BIG',
    '5':'BIG','6':'SMALL','7':'SMALL','8':'BIG','9':'SMALL'
}
def logic_golden(hist):
    if not hist: return None
    return GOLDEN_MAP.get(str(hist[0]['issueNumber'])[-1], 'BIG')


# ═══════════════════════════════════════════
#  LOGIC 2 — JISHAN
# ═══════════════════════════════════════════
def logic_jishan(hist):
    if len(hist) < 10: return None
    r1, r10 = hist[0], hist[9]
    p1  = int(str(r1['issueNumber'])[-2:]);   v1  = int(r1['number'])
    p10 = int(str(r10['issueNumber'])[-2:]);  v10 = int(r10['number'])
    diff = abs((p1 + v1) - (p10 + v10))
    reduced = diff
    while reduced > 9:
        reduced = sum(int(d) for d in str(reduced))
    return 'BIG' if reduced >= 5 else 'SMALL'


# ═══════════════════════════════════════════
#  LOGIC 3 — DRAGON
# ═══════════════════════════════════════════
def logic_dragon(hist):
    if len(hist) < 10: return None
    seed = int(str(hist[0]['issueNumber'])[-3:])
    nums = [int(x['number']) for x in hist[:10]]
    big_bias = sum(1 for n in nums if n >= 5)
    if seed % 2 == 0:
        return 'BIG' if big_bias >= 5 else 'SMALL'
    return 'SMALL' if nums[0] >= 5 else 'BIG'


# ═══════════════════════════════════════════
#  LOGIC 4 — SOLOPRIME (alternating)
# ═══════════════════════════════════════════
def logic_soloprime(hist, state):
    if len(hist) < 5: return None
    last5 = ['BIG' if int(x['number']) >= 5 else 'SMALL' for x in hist[:5]]
    last_pred = state.get('soloprime_last')
    if last_pred is None:
        result = 'BIG' if last5.count('BIG') >= 3 else 'SMALL'
    else:
        result = 'SMALL' if last_pred == 'BIG' else 'BIG'
    state['soloprime_last'] = result
    return result


# ═══════════════════════════════════════════
#  LOGIC 5 — SAFA
# ═══════════════════════════════════════════
def logic_safa(hist):
    if len(hist) < 5: return None
    last5 = ['BIG' if int(x['number']) >= 5 else 'SMALL' for x in hist[:5]]
    return 'BIG' if last5.count('BIG') > 2 else 'SMALL'


# ═══════════════════════════════════════════
#  LOGIC 6 — DEVID
# ═══════════════════════════════════════════
def logic_devid(hist):
    if len(hist) < 8: return None
    sizes = ['BIG' if int(x['number']) >= 5 else 'SMALL' for x in hist[:8]]

    streak = 1
    for i in range(1, len(sizes)):
        if sizes[i] == sizes[0]: streak += 1
        else: break

    big = sizes.count('BIG'); small = 8 - big
    zigzag = (sizes[0] != sizes[1] and sizes[1] != sizes[2]
              and sizes[2] != sizes[3])

    if streak >= 4:
        return 'SMALL' if sizes[0] == 'BIG' else 'BIG'
    elif zigzag:
        return 'SMALL' if sizes[0] == 'BIG' else 'BIG'
    elif streak == 3:
        return sizes[0]
    else:
        return 'SMALL' if big > small else 'BIG'


# ═══════════════════════════════════════════
#  LOGIC 7 — AKKI
# ═══════════════════════════════════════════
def logic_akki(hist):
    if len(hist) < 10: return None
    nums = [int(x['number']) for x in hist[:10]]
    wb = ws = 0.0
    for i, n in enumerate(nums):
        recency = 1.22 ** (10 - i)
        if n >= 5: wb += recency
        else:      ws += recency

    highest = 'BIG' if wb >= ws else 'SMALL'

    last3 = ['BIG' if n >= 5 else 'SMALL' for n in nums[:3]]
    if last3[0] == last3[1] == last3[2]:
        return last3[0]
    return 'SMALL' if highest == 'BIG' else 'BIG'


# ═══════════════════════════════════════════
#  TELEGRAM
# ═══════════════════════════════════════════
def send_telegram(text):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text,
                  "parse_mode": "HTML",
                  "disable_web_page_preview": True},
            timeout=10)
        return r.status_code == 200
    except Exception:
        return False

def get_updates(offset=None):
    try:
        p = {"timeout": 4, "allowed_updates": json.dumps(["message"])}
        if offset: p["offset"] = offset
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params=p, timeout=10)
        return r.json().get("result", [])
    except Exception:
        return []


# ═══════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════
stats = {
    "rounds_seen":    0,
    "signals_sent":   0,
    "ties_skipped":   0,
    "current_level":  1,
    "wins":           0,
    "losses":         0,
    "skips":          0,
    "last_signal":    None,
    "last_period":    None,
    "last_bet":       None,
    "last_result":    None,
    # money
    "bankroll":       START_BANKROLL,
    "net_pl":         0,
    "total_wagered":  0,
    "peak_bankroll":  START_BANKROLL,
    "lowest_bankroll": START_BANKROLL,
    # pending / misc
    "pending_signal": None,
    "started_at":     datetime.now().isoformat(),
    "big_count":      0,
    "small_count":    0,
    "history_len":    0,
}

def bet_amount(level):
    return BASE_BET * (MULTIPLIER ** (level - 1))

def full_ladder():
    return [bet_amount(i) for i in range(1, MAX_LEVEL + 1)]

def pl_sign(v):
    return f"+₹{v}" if v > 0 else (f"−₹{abs(v)}" if v < 0 else "₹0")


def stats_text():
    up = datetime.now() - datetime.fromisoformat(stats["started_at"])
    mins, secs = divmod(int(up.total_seconds()), 60)
    hrs, mins = divmod(mins, 60)
    lvl = stats["current_level"]
    total = stats["wins"] + stats["losses"]
    acc = round(stats["wins"]/total*100, 1) if total else 0.0
    roi = round(stats["net_pl"]/max(1,stats["total_wagered"])*100, 2)
    pl = stats["net_pl"]
    pl_emoji = "📈" if pl > 0 else ("📉" if pl < 0 else "➖")
    ladder_str = " → ".join(f"₹{b}" for b in full_ladder())

    return (
        f"📊 <b>BOT STATUS — {GAME_LABEL}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱  Uptime: <code>{hrs:02d}:{mins:02d}:{secs:02d}</code>\n"
        f"🔄 Rounds: <code>{stats['rounds_seen']}</code>\n"
        f"📡 Signals: <code>{stats['signals_sent']}</code>\n"
        f"⏸  Skipped: <code>{stats['ties_skipped']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>BANKROLL</b>\n"
        f"💵 Current: <code>₹{stats['bankroll']}</code>\n"
        f"{pl_emoji} Net P/L: <code>{pl_sign(pl)}</code>\n"
        f"📊 Total Wagered: <code>₹{stats['total_wagered']}</code>\n"
        f"📈 ROI: <code>{roi}%</code>\n"
        f"🔝 Peak: <code>₹{stats['peak_bankroll']}</code>\n"
        f"🔻 Low:  <code>₹{stats['lowest_bankroll']}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Wins: <code>{stats['wins']}</code>  ❌ Losses: <code>{stats['losses']}</code>\n"
        f"🎯 Accuracy: <code>{acc}%</code>\n"
        f"🪜 Ladder: <code>{ladder_str}</code>\n"
        f"🪜 Next Level: <code>L{lvl}</code> (₹{bet_amount(lvl)})\n"
        f"🎯 Last: <code>{stats['last_signal'] or '—'}</code> @ ₹{stats['last_bet'] or '—'}\n"
        f"🕒 Period: <code>{stats['last_period'] or '—'}</code>\n"
        f"📈 Split: B={stats['big_count']} S={stats['small_count']}\n"
        f"📚 History: <code>{stats['history_len']}</code> rounds"
    )


# ═══════════════════════════════════════════
#  MAIN LOOP
# ═══════════════════════════════════════════
def run():
    print("═" * 62)
    print("   🎯  7-LOGIC MAJORITY BETTING BOT  (v3)")
    print(f"   🎮  Game: {GAME_LABEL}  ({ROUND_SECONDS}s rounds)")
    print(f"   ✅  Rule: {MAJORITY}+ of 7 must agree")
    print(f"   🪜  Ladder: " + " → ".join(f"₹{b}" for b in full_ladder()))
    print(f"   🏦  Starting bankroll: ₹{START_BANKROLL}")
    print(f"   💬  Chat ID: {CHAT_ID}")
    print("═" * 62)
    print()

    cache = load_json(CACHE_FILE, {})
    if isinstance(cache, list):
        cache = {str(x['issueNumber']): x for x in cache if x.get('issueNumber')}
    state = load_json(STATE_FILE, {})

    for k in ("current_level", "wins", "losses", "skips",
              "signals_sent", "rounds_seen", "ties_skipped",
              "last_signal", "last_period", "last_bet", "last_result",
              "big_count", "small_count",
              "bankroll", "net_pl", "total_wagered",
              "peak_bankroll", "lowest_bankroll"):
        if k in state: stats[k] = state[k]

    log(f"📁 Loaded cache: {len(cache)} rounds")
    log(f"🪜 Starting level: L{stats['current_level']}  (bet = ₹{bet_amount(stats['current_level'])})")
    log(f"💰 Starting bankroll: ₹{stats['bankroll']}  (net P/L: {pl_sign(stats['net_pl'])})")

    ladder_str = " → ".join(f"₹{b}" for b in full_ladder())
    send_telegram(
        f"🚀 <b>7-LOGIC MAJORITY BOT ONLINE (v3)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 Game: <b>{GAME_LABEL}</b>\n"
        f"✅ Majority: {MAJORITY}+ of 7\n"
        f"🪜 Ladder: <code>{ladder_str}</code>\n"
        f"🏦 Bankroll: <b>₹{stats['bankroll']}</b>\n"
        f"📊 Net P/L: <b>{pl_sign(stats['net_pl'])}</b>\n"
        f"🪜 Current Level: <b>L{stats['current_level']}</b> (₹{bet_amount(stats['current_level'])})\n"
        f"💬 /help for commands"
    )

    last_evaluated   = None
    last_update_id   = None
    rounds_since_ping = 0

    while True:
        try:
            # ── Telegram commands ──
            for u in get_updates(last_update_id):
                last_update_id = u["update_id"] + 1
                msg = u.get("message", {})
                text = (msg.get("text") or "").strip().lower()
                from_id = str(msg.get("chat", {}).get("id", ""))
                if from_id != str(CHAT_ID): continue

                if text in ("/start", "/help"):
                    send_telegram(
                        f"🎯 <b>BOT COMMANDS — {GAME_LABEL}</b>\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━\n"
                        "/status   — full stats + bankroll\n"
                        "/money    — quick P/L view\n"
                        "/ladder   — show full bet ladder\n"
                        "/reset    — reset bet level to L1\n"
                        "/resetbal — reset bankroll to ₹1000\n"
                        "/last     — repeat last signal\n"
                        "/pause    — pause signals\n"
                        "/resume   — resume\n"
                        "/ping     — health check"
                    )
                elif text == "/status":
                    send_telegram(stats_text())
                elif text == "/money":
                    pl = stats["net_pl"]
                    emoji = "📈" if pl > 0 else ("📉" if pl < 0 else "➖")
                    send_telegram(
                        f"💰 <b>MONEY SNAPSHOT — {GAME_LABEL}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"💵 Bankroll: <code>₹{stats['bankroll']}</code>\n"
                        f"{emoji} Net P/L: <code>{pl_sign(pl)}</code>\n"
                        f"📊 Wagered: <code>₹{stats['total_wagered']}</code>\n"
                        f"✅ W: <code>{stats['wins']}</code>  ❌ L: <code>{stats['losses']}</code>\n"
                        f"🪜 Next: <code>L{stats['current_level']}</code> → ₹{bet_amount(stats['current_level'])}"
                    )
                elif text == "/ladder":
                    lines = []
                    for i in range(1, MAX_LEVEL + 1):
                        marker = " ← NEXT" if i == stats["current_level"] else ""
                        lines.append(f"  L{i}: ₹{bet_amount(i)}{marker}")
                    total_exp = sum(full_ladder())
                    send_telegram(
                        f"🪜 <b>BET LADDER — {GAME_LABEL}</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━\n" +
                        "\n".join(lines) +
                        f"\n━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 Max exposure: <code>₹{total_exp}</code>\n"
                        f"🏦 Bankroll: <code>₹{stats['bankroll']}</code>"
                    )
                elif text == "/ping":
                    send_telegram("🏓 pong")
                elif text == "/reset":
                    stats["current_level"] = 1
                    save_json(STATE_FILE, stats)
                    send_telegram(f"🔄 Bet level reset to L1 (₹{bet_amount(1)})")
                elif text == "/resetbal":
                    stats["bankroll"] = START_BANKROLL
                    stats["net_pl"] = 0
                    stats["total_wagered"] = 0
                    stats["peak_bankroll"] = START_BANKROLL
                    stats["lowest_bankroll"] = START_BANKROLL
                    stats["wins"] = 0
                    stats["losses"] = 0
                    stats["current_level"] = 1
                    save_json(STATE_FILE, stats)
                    send_telegram(f"♻️ Bankroll + stats reset to ₹{START_BANKROLL} / L1 / W:0 L:0")
                elif text == "/last":
                    if stats["last_signal"]:
                        send_telegram(
                            f"🎯 Last: <b>{stats['last_signal']}</b> "
                            f"@ ₹{stats['last_bet']}"
                        )
                    else:
                        send_telegram("⏸ No signals sent yet")
                elif text == "/pause":
                    globals()["PAUSED"] = True
                    send_telegram("⏸ Paused")
                elif text == "/resume":
                    globals()["PAUSED"] = False
                    send_telegram("▶️ Resumed")

            if globals().get("PAUSED"):
                time.sleep(3)
                continue

            # ── Fetch + cache ──
            items = fetch_latest()
            if items:
                added = 0
                for it in items:
                    k = str(it.get('issueNumber', '')).strip()
                    if k and k not in cache:
                        cache[k] = {'issueNumber': k,
                                    'number': str(it.get('number', '0'))}
                        added += 1
                if added:
                    save_json(CACHE_FILE, cache)
                    log(f"   💾 +{added} new rounds (cache={len(cache)})")

            try:
                history = sorted(cache.values(),
                                 key=lambda x: int(x['issueNumber']),
                                 reverse=True)
            except Exception:
                history = []
            if not history:
                time.sleep(8); continue

            stats["history_len"] = len(history)
            latest      = str(history[0]['issueNumber'])
            next_period = str(int(latest) + 1)

            # ═══════════════════════════════════════
            #  RESOLVE PENDING SIGNAL
            # ═══════════════════════════════════════
            pending = stats.get("pending_signal")
            if pending and pending["period"] == latest:
                actual_num  = int(history[0]['number'])
                actual_side = 'BIG' if actual_num >= 5 else 'SMALL'
                won = (actual_side == pending["side"])

                bet = pending["bet"]
                stats["total_wagered"] += bet

                if won:
                    profit = int(bet * (PAYOUT_MULT - 1))
                    stats["wins"] += 1
                    stats["net_pl"]   += profit
                    stats["bankroll"] += profit
                    stats["current_level"] = 1
                    stats["last_result"] = "WIN"
                else:
                    profit = -bet
                    stats["losses"] += 1
                    stats["net_pl"]   += profit
                    stats["bankroll"] -= bet
                    # advance or wrap
                    if stats["current_level"] < MAX_LEVEL:
                        stats["current_level"] += 1
                    else:
                        stats["current_level"] = 1
                    stats["last_result"] = "LOSS"

                if stats["bankroll"] > stats["peak_bankroll"]:
                    stats["peak_bankroll"] = stats["bankroll"]
                if stats["bankroll"] < stats["lowest_bankroll"]:
                    stats["lowest_bankroll"] = stats["bankroll"]

                emoji = "✅" if won else "❌"
                next_bet = bet_amount(stats["current_level"])
                send_telegram(
                    f"{emoji} <b>RESULT — {'WIN' if won else 'LOSS'}</b>  [{GAME_LABEL}]\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🕒 Period: <code>{latest}</code>\n"
                    f"🎯 Predicted: <b>{pending['side']}</b>  |  Actual: <b>{actual_side} ({actual_num})</b>\n"
                    f"💰 Bet: ₹{bet} (L{pending['level']})\n"
                    f"💵 {'+' if won else '−'}₹{abs(profit)}  → Bankroll: <b>₹{stats['bankroll']}</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 Net P/L: <b>{pl_sign(stats['net_pl'])}</b>\n"
                    f"🪜 Next: <b>L{stats['current_level']}</b> → ₹{next_bet}\n"
                    f"📈 W:{stats['wins']} L:{stats['losses']}"
                )
                stats["pending_signal"] = None
                save_json(STATE_FILE, stats)

            if next_period == last_evaluated:
                time.sleep(POLL_INTERVAL); continue

            # ═══════════════════════════════════════
            #  RUN 7 LOGICS
            # ═══════════════════════════════════════
            preds = {
                'Golden':    logic_golden(history),
                'Jishan':    logic_jishan(history),
                'Dragon':    logic_dragon(history),
                'Soloprime': logic_soloprime(history, state),
                'Safa':      logic_safa(history),
                'Devid':     logic_devid(history),
                'Akki':      logic_akki(history),
            }
            save_json(STATE_FILE, {**stats, "soloprime_last": state.get("soloprime_last")})

            valid = {k: v for k, v in preds.items() if v}
            big_votes   = sum(1 for v in valid.values() if v == 'BIG')
            small_votes = sum(1 for v in valid.values() if v == 'SMALL')
            total_votes = big_votes + small_votes

            stats["rounds_seen"] += 1
            ts = datetime.now().strftime('%H:%M:%S')

            disp = "  ".join(f"{k[:4]}=<{v[0] if v else '?'}>" for k, v in preds.items())
            print(f"[{ts}] {GAME_LABEL}  P→{next_period}  (cache={len(cache)})")
            print(f"        {disp}")
            print(f"        Votes → BIG {big_votes} | SMALL {small_votes}  (total {total_votes})")

            # ═══════════════════════════════════════
            #  DECIDE
            # ═══════════════════════════════════════
            if big_votes >= MAJORITY:
                trend, maj = 'BIG', big_votes
            elif small_votes >= MAJORITY:
                trend, maj = 'SMALL', small_votes
            else:
                print(f"        ⏸  NO MAJORITY ({big_votes}-{small_votes}) → SKIPPED\n")
                stats["ties_skipped"] += 1
                stats["skips"] += 1
                last_evaluated = next_period
                save_json(STATE_FILE, stats)
                time.sleep(POLL_INTERVAL)
                continue

            # ═══════════════════════════════════════
            #  BET SIZING + SAFETY CHECK
            # ═══════════════════════════════════════
            level = stats["current_level"]
            bet   = bet_amount(level)

            if stats["bankroll"] < bet:
                send_telegram(
                    f"⚠️ <b>INSUFFICIENT BANKROLL</b>\n"
                    f"Bankroll: ₹{stats['bankroll']}  |  Required: ₹{bet}\n"
                    f"Resetting level to L1…"
                )
                stats["current_level"] = 1
                level = 1
                bet = bet_amount(1)
                if stats["bankroll"] < bet:
                    send_telegram(
                        f"🛑 <b>BANKROLL EXHAUSTED</b>\n"
                        f"Current: ₹{stats['bankroll']} — use /resetbal to restart"
                    )
                    last_evaluated = next_period
                    time.sleep(POLL_INTERVAL)
                    continue

            emoji = '🔴' if trend == 'BIG' else '🟢'
            src_lines = "\n".join(
                f"  • {k}: <code>{v}</code>" for k, v in preds.items() if v
            )

            msg = (
                f"🎯 <b>MAJORITY SIGNAL</b> {emoji}  [{GAME_LABEL}]\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"🎮 <b>Game:</b> {GAME_LABEL}\n"
                f"📊 <b>Period:</b> <code>{next_period}</code>\n"
                f"🔮 <b>Prediction:</b> <b>{trend}</b> {emoji}\n"
                f"💰 <b>Bet:</b> ₹{bet}  (Level L{level})\n"
                f"🏦 <b>Bankroll:</b> ₹{stats['bankroll']}\n"
                f"📊 <b>Net P/L:</b> {pl_sign(stats['net_pl'])}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📈 <b>Agreement:</b> {maj}/7\n\n"
                f"<b>Logic Breakdown:</b>\n{src_lines}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏰ {ts}"
            )

            ok = send_telegram(msg)
            print(f"        {'✅ SENT' if ok else '❌ FAILED'} → {trend} {maj}/7  ₹{bet} (L{level})  Bank=₹{stats['bankroll']}\n")

            if ok:
                stats["signals_sent"] += 1
                stats["last_signal"]  = trend
                stats["last_period"]  = next_period
                stats["last_bet"]     = bet
                stats["last_level"]   = level
                stats["pending_signal"] = {
                    "period": next_period,
                    "side":   trend,
                    "bet":    bet,
                    "level":  level,
                    "votes":  maj,
                }
                if trend == 'BIG': stats["big_count"] += 1
                else:              stats["small_count"] += 1

            last_evaluated = next_period
            save_json(STATE_FILE, stats)

            rounds_since_ping += 1
            if rounds_since_ping >= HEARTBEAT_EVERY:
                rounds_since_ping = 0
                send_telegram(stats_text())

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\n💾 Saving state…")
            save_json(CACHE_FILE, cache)
            save_json(STATE_FILE, stats)
            send_telegram("🛑 <b>Bot stopped. State saved.</b>")
            sys.exit(0)
        except Exception as e:
            log(f"   ⚠️  Loop error: {type(e).__name__}: {e}")
            time.sleep(8)


if __name__ == "__main__":
    run()