def test_modified_dataset_fixture(modified_dataset):
    assert modified_dataset
    # the test is to do nothing.
    # the dataset modification will be done, the promised capture
    # before the test starts. the test will then do nothing, and
    # the promise is reevaluated at the end and must succeed.
