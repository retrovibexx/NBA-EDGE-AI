from features import rolling_projection, empirical_over_probability
def test_rolling_projection_uses_recent_values():
    rows=[{"pts":v} for v in [30,25,20,15,10]]
    result=rolling_projection(rows,"PTS")
    assert result["n"]==5 and 20<result["projection"]<30
def test_empirical_probability_smoothed():
    p=empirical_over_probability([10,11,12,13],10.5)
    assert 0<p<1
