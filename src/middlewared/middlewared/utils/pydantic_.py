from middlewared.api.base.model import ensure_model_ready


def model_json_schema(model, *args, **kwargs):
    ensure_model_ready(model)
    return model.model_json_schema(*args, **kwargs)
