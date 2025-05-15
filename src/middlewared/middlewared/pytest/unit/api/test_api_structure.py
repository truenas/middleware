def test_api_current_module_exports():
    import middlewared.api.current as api_module
    assert "BaseModel" not in dir(api_module), "__all__ must be defined in all API model modules"
