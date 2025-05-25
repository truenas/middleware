from typing import Annotated, Type, Union

from pydantic import create_model, Field, Secret
from middlewared.api.base import LongString, NotRequired
from middlewared.api.base.handler.accept import validate_model
from middlewared.service_exception import ValidationErrors

from .pydantic_utils import AbsolutePath, BaseModel, IPvAnyAddress, URI


NOT_PROVIDED = object()


# Functionality we are concerned about which we would like to port over
# 1) immutable fields - lots of usages
# A field which once set is immutable and cannot be changed.
# 2) editable toggle fields - we have usage in lyrion-music-server app
# A field which has a default value and that is enforced and cannot be set by the user.
# 4) hostpath type
# 5) path type
# 6) empty attribute should be supported in fields
# 8) subquestions need to be supported
# 9) show_subquestions_if - this is used in the apps schema to show subquestions based on a field value
# 10) show_if - this is used in the apps schema to show a field based on a field value


# Functionality to remove (these are not being used and we should remove them to reduce complexity)
# 1) Cron type
# 2) hostpathdirectory type
# 3) hostpathfile type
# 4) additional_attrs field attr is not being used
# 5)


def construct_schema(
    item_version_details: dict, new_values: dict, update: bool, old_values: dict | object = NOT_PROVIDED
) -> dict:
    schema_name = f'app_{"update" if update else "create"}'
    model = generate_pydantic_model(item_version_details['schema']['questions'], schema_name)
    verrors = ValidationErrors()
    try:
        # Validate the new values against the generated model
        new_values = validate_model(model, new_values, exclude_unset=True, expose_secrets=False)
    except ValidationErrors as e:
        verrors.add_child('values', e)

    return {
        'verrors': verrors,
        'new_values': new_values,
        'model': model,
        'schema_name': schema_name,
    }


def generate_pydantic_model(dict_attrs: list[dict], model_name: str) -> Type[BaseModel]:
    """
    Generate a Pydantic model from a list of dictionary attributes.
    """
    fields = {}
    nested_models = {}
    for attr in dict_attrs:
        var_name = attr['variable']
        schema_def = attr['schema']
        field_type, field_info, nested_model = process_schema_field(schema_def, f'{model_name}_{var_name}')
        if nested_model:
            nested_models[var_name] = nested_model
        fields[var_name] = (field_type, field_info)

    # Create the model dynamically
    model = create_model(model_name, __base__=BaseModel, **fields)

    # Store nested models and schema info as class attributes for reference
    for nested_name, nested_model in nested_models.items():
        setattr(model, f'__{nested_name}_model', nested_model)

    # Store the original schema for validation purposes
    setattr(model, '__schema_attrs__', dict_attrs)

    return model


def process_schema_field(schema_def: dict, model_name: str) -> tuple[
    Type, Field, Type[BaseModel] | None
]:
    """
    Process a schema field type / field information and any nested model if applicable which was generated.
    """
    schema_type = schema_def['type']
    field_type = nested_model = None
    field_info = create_field_info_from_schema(schema_def)
    if schema_type == 'int':
        field_type = int
    elif schema_type in ('string', 'text'):
        field_type = str if schema_type == 'string' else LongString
        # We can probably have more complex logic here for string types
    elif schema_type == 'boolean':
        field_type = bool
    elif schema_type == 'ipaddr':
        field_type = IPvAnyAddress
    elif schema_type == 'uri':
        field_type = URI
    elif schema_type == 'path':
        field_type = AbsolutePath
    elif schema_type == 'dict':
        if dict_attrs := schema_def.get('attrs', []):
            field_type = nested_model = generate_pydantic_model(dict_attrs, model_name)
        else:
            # We have a generic dict type without specific attributes
            field_type = dict
    elif schema_type == 'list':
        annotated_items = []
        if list_items := schema_def.get('items', []):
            for item in list_items:
                item_type, item_info, _ = process_schema_field(
                    item['schema'], f'{model_name}_{item["variable"]}',
                )
                annotated_items.append(Annotated[item_type, item_info])

            field_type = list[Union[*annotated_items]]
        else:
            # We have a generic list type without specific items
            field_type = list
    else:
        raise ValueError(f'Unsupported schema type: {schema_type!r}')

    assert field_type is not None

    if not schema_def.get('required', False):
        # If the attr is not required, we use NotRequired
        field_type |= NotRequired

    if schema_def.get('null', False):
        field_type |= None

    if schema_def.get('private', False):
        # If the field is private, we can use Secret type
        field_type = Secret[field_type]

    if schema_ref := schema_def.get('$ref', []):
        # We can consume it under metadata later when we normalize/validate values
        # https://peps.python.org/pep-0593/?utm_source=chatgpt.com#rationale
        # Usage:
        # class A(BaseModel):
        #   f1 = Annotated[int, [{'my_dict': 1}]]
        # o = A(f1=1)
        # f = o.model_fields['f1']
        # f.metadata will show -> [[{'my_dict': 1}]]
        field_type = Annotated[field_type, schema_ref]

    return field_type, field_info, nested_model


def create_field_info_from_schema(schema_def: dict) -> Field:
    """
    Create Pydantic Field info from schema definition.
    """
    field_kwargs = {}

    if 'description' in schema_def:
        field_kwargs['description'] = schema_def['description']

    if 'title' in schema_def:
        field_kwargs['title'] = schema_def['title']

    if 'default' in schema_def:
        field_kwargs['default'] = schema_def['default']
    elif not schema_def.get('required', False):
        # This case shouldn't happen since we filter out non-required fields without defaults
        field_kwargs['default'] = None

    # Add validation constraints
    if 'min' in schema_def:
        field_kwargs['ge'] = schema_def['min']
    if 'max' in schema_def:
        field_kwargs['le'] = schema_def['max']
    if 'min_length' in schema_def:
        field_kwargs['min_length'] = schema_def['min_length']
    if 'max_length' in schema_def:
        field_kwargs['max_length'] = schema_def['max_length']

    return Field(**field_kwargs)
