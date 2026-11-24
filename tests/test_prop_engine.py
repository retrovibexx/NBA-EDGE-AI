from prop_engine import american_prob
def test_american_probability():
    assert round(american_prob(-110),3)==0.524
    assert round(american_prob(150),3)==0.4
