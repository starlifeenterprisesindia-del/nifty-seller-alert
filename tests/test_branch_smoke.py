from market_behaviour import MarketBehaviourDirector
from market_psychology import MarketPsychologyDirector
from option_intelligence import OptionIntelligenceDirector
from price_action import PriceActionDirector
from risk_department import RiskDirector
from smart_money import SmartMoneyDirector
from strategy_department import StrategyDirector


def test_primary_dsp_pipeline_smoke():
    movement = {
        "phase": "RECOVERY", "sample_count": 5, "recent_sample_count": 5,
        "continuity_status": "LIVE_SEQUENCE", "recovery_points": 12,
        "pullback_points": 0, "one_minute_points": 4, "three_minute_points": 9,
        "five_minute_points": 12,
    }
    price = PriceActionDirector().build_report(
        data_available=True, source="Dhan 5m candles", price=24080,
        ema20=24100, ema50=24120, vwap=24110, atr=80,
        current_range=110, support=24050, resistance=24150,
        support_source="Pivot S1", resistance_source="Pivot R1",
        open_price=24060, high=24090, low=24040, close=24080,
        points_moved_from_open=20, day_high=24150, day_low=24020,
        movement=movement,
    )
    option = OptionIntelligenceDirector().build_report(
        availability="READY", price_change=20, oi_change=100000,
        current_volume=2000000, average_volume=1500000,
        pcr=1.02, ce_oi=5000000, pe_oi=5200000,
        option_bias=18, bullish_score=36, bearish_score=24,
        support_score=70, resistance_score=52,
        ce_writing_score=52, pe_writing_score=70,
        conflict_score=35, flow_state="PE_SUPPORT_DOMINANT",
        snapshot_ready=True, barrier_touched=False, barrier_respected=True,
    )
    behaviour = MarketBehaviourDirector().build_report(price.details, option.details, 12)
    psychology = MarketPsychologyDirector().build_report(
        price=24080, change_pct=-0.5, vix=13.6, ema20=24100, vwap=24110,
        day_high=24150, day_low=24020, pcr=1.02,
        candle_open=24060, candle_high=24090, candle_low=24040, candle_close=24080,
        support=24050, resistance=24150, atr=80,
        price_action_details=price.details, option_details=option.details,
        behaviour_details=behaviour.details,
    )
    money = SmartMoneyDirector().build_report(
        0, 0, 4, 4, 4, 4, state={}, nifty_change_pct=-0.5,
        futures_bias="Neutral", options_bias="Neutral", journal_records=[],
        observed_at="2026-07-14T12:50:15+05:30",
    )
    risk = RiskDirector().build_report(13.6, False, True, "", -0.5)
    strategy = StrategyDirector().build_report(price, option, behaviour, money, risk)

    assert price.confidence >= 0
    assert option.details["flow"]["snapshot_ready"] is True
    assert behaviour.details["movement"]["phase"] == "RECOVERY"
    assert psychology.details.get("authority") == "EVIDENCE_ONLY_TO_CO"
    assert money.details.get("execution_instruction") == "NONE"
    assert risk.confidence > 0
    assert strategy.recommended_strategy in {"WAIT", "SELL CE", "SELL PE", "IRON CONDOR"}
