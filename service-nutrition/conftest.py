def pytest_configure(config):
    markexpr = getattr(config.option, "markexpr", "") or ""
    if "smoke" in markexpr and "not smoke" not in markexpr:
        try:
            config.option.cov_fail_under = 0.0
        except AttributeError:
            pass
