from nutri_shared.i18n.middleware import LocaleMiddleware as _Base


class LocaleMiddleware(_Base):
    SUPPORTED_LOCALES = {"fr", "en"}
