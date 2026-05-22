import src.cleaner as cleaner
import pandas as pd
import numpy as np

def test_funny_country_corrects(medium_clean_df: pd.DataFrame):
    df = medium_clean_df.copy()
    df.loc[0, "geo_country"] = 'antigua and barbuda' #invalid case
    df, index = cleaner.DataCleaner._clean_invalid_geo_country(cleaner.DataCleaner(), df)
    pd.testing.assert_index_equal(index, pd.Index([0], "int64"))
    print(type(df.loc[0, "geo_country"]))
    assert pd.notna(df.loc[0, "geo_country"])

def test_consistency_flags_right_rows(medium_clean_df: pd.DataFrame):
    df = medium_clean_df.copy()
    
    df, index = cleaner.DataCleaner._clean_inconsistency_flagged_field(cleaner.DataCleaner(), df)
    assert len(index) == 0

def test_consistency_ts_dont_breaks(medium_clean_df: pd.DataFrame):
    df = medium_clean_df.copy()
    df.loc[3, "session_end_ts"] = np.nan

    df, index = cleaner.DataCleaner._clean_inconsistency_session_timestamps(cleaner.DataCleaner(), df)
    assert len(index) == 0

def test_validity_last4(medium_clean_df: pd.DataFrame):
    df = medium_clean_df.copy()
    
    df.loc[0, "card_last4"] = "12345"
    df.loc[1, "card_last4"] = "aboba"

    df, index = cleaner.DataCleaner._clean_invalid_card_last4(cleaner.DataCleaner(), df)

    assert pd.testing.assert_index_equal(index, pd.Index([0, 1]))
