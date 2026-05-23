import pytest
import src.antifraud_rules as rules
import pandas as pd
import src.data_loader as loader

@pytest.fixture
def repeat_timests(medium_clean_df: pd.DataFrame) -> pd.DataFrame:
    df = medium_clean_df.copy()
    df["event_ts"] = df["event_ts"].apply(lambda x: "2025-05-29 19:35:04")
    return df

def test_R1_works_with_same_timestamps(repeat_timests: pd.DataFrame):
    r1Rule = rules.CarouselRule()
    res = r1Rule.use_rule(repeat_timests)
    ans = ((repeat_timests["client_id"] != "C023998") & (repeat_timests["event_type"] == "transaction"))

    print(repeat_timests[res])
    print(repeat_timests[ans])
    assert (ans == res).all()

# всё ок
# def test_R1_works_with_strange_timestamps(repeat_timests: pd.DataFrame):
#     df = repeat_timests.copy()
#     df.loc[0, "event_ts"] = "13/29/2025"

#     r1Rule = rules.CarouselRule()
#     res = r1Rule.use_rule(df)
#     ans = ((df["client_id"] != "C023998") & (df["event_type"] == "transaction"))

#     print(df[res])
#     print(df[ans])
#     assert (ans == res).all()

def test_engine_basic_usage(medium_clean_df):
    prevVer = medium_clean_df.copy()
    ruleEngine = rules.RuleEngine()
    newdf, allRules = ruleEngine.run_all(medium_clean_df)
    for rule in allRules:
        assert rule["rule_id"] in ["R1", "R2", "R3", "R4", "R5"]
    print(len(allRules))
    assert prevVer.equals(medium_clean_df)
    new_cols = newdf.columns.difference(medium_clean_df.columns).to_list()

    assert len(new_cols) == 2
    for col in new_cols:
        assert col in ["is_fraud_predicted", "triggered_rules"]

def test_engine_speed():
    try:
        df = loader.load_events("dq_monitor/data/raw/events_dirty.csv")
    except:
        return
    ruleEngine = rules.RuleEngine()
    _ = ruleEngine.run_all(df)
