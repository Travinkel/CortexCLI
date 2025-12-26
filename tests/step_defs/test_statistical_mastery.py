from pytest_bdd import scenarios, given, when, then

# Scenarios
scenarios('../features/statistical_mastery.feature')

# Given Steps
@given('a dataset of clinical trials,')
def a_dataset_of_clinical_trials():
    print("Given a dataset of clinical trials")
    pass

# When Steps
@when('I analyze the data for publication bias,')
def i_analyze_the_data_for_publication_bias():
    print("When I analyze the data for publication bias")
    pass

# Then Steps
@then('the system should flag trials with a high risk of bias.')
def the_system_should_flag_trials_with_a_high_risk_of_bias():
    print("Then the system should flag trials with a high risk of bias")
    pass
