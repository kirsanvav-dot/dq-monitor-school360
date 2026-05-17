from src.profiler import DataProfiler, DQIssue

def test_profiler_returns_disired_df(small_dirty_df):
    profiler = DataProfiler()
    reportDataframe = profiler.profile(small_dirty_df).to_dataframe()
    assert len(reportDataframe.columns) == 2
    assert "issue_type" in reportDataframe
    assert "rows_affected" in reportDataframe

def test_DQIssue_has_rows_affected_in_list():
    assert DQIssue.__annotations__["rows_affected"] == "List[int]"

def 
