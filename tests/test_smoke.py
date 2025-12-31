def test_import_package():
    import cymise

    assert hasattr(cymise, "__version__") is False
