import contextlib
import re
from typing import Annotated, Literal, Type, TypeAlias, Union

from pydantic import AfterValidator, create_model, Field

from middlewared.api.base import LongString, match_validator, NotRequired
from middlewared.api.base.handler.accept import validate_model
from middlewared.service_exception import ValidationErrors
from middlewared.utils import filter_list

from .pydantic_utils import AbsolutePath, BaseModel, create_length_validated_hostpath, IPvAnyAddress, URI


CONTEXT_KEY_NAME = 'ix_context'
RESERVED_NAMES = [
    ('ix_certificates', dict),
    ('ix_certificate_authorities', dict),
    ('ix_volumes', dict),
    (CONTEXT_KEY_NAME, dict),
]
NOT_PROVIDED = object()
USER_VALUES: TypeAlias = dict | Literal[NOT_PROVIDED]


# Functionality we are concerned about which we would like to port over
#
# Make sure immutable types are only supported for basic types strings/booleans/integers/path
# Make sure we have tests for min/max/min_length/max_length

# Functionality to remove (these are not being used and we should remove them to reduce complexity)
# 1) Cron type
# 2) hostpathdirectory type
# 3) hostpathfile type
# 4) additional_attrs field attr is not being used
# 5) subquestions are being removed
# 6) show_subquestions_if are being removed
# 7) removing editable fields


def construct_schema(
    item_version_details: dict, new_values: dict, update: bool, old_values: USER_VALUES = NOT_PROVIDED,
) -> dict:
    schema_name = f'app_{"update" if update else "create"}'
    model = generate_pydantic_model(item_version_details['schema']['questions'], schema_name, new_values, old_values)
    verrors = ValidationErrors()
    try:
        # Validate the new values against the generated model
        new_values = validate_model(model, new_values, exclude_unset=True, expose_secrets=False)
    except ValidationErrors as e:
        # Don't add 'values' prefix - just extend the errors directly
        verrors.extend(e)

    return {
        'verrors': verrors,
        'new_values': new_values,
        'schema_name': schema_name,
    }


def generate_pydantic_model(
    dict_attrs: list[dict], model_name: str, new_values: USER_VALUES = NOT_PROVIDED,
    old_values: USER_VALUES = NOT_PROVIDED, parent_hidden: bool = False,
) -> Type[BaseModel]:
    """
    Generate a Pydantic model from a list of dictionary attributes.
    """
    fields = {}
    nested_models = {}
    show_if_attrs = {}
    for attr in dict_attrs:
        var_name = attr['variable']
        schema_def = attr['schema']
        attr_value = new_values.get(var_name, NOT_PROVIDED) if isinstance(new_values, dict) else NOT_PROVIDED
        old_attr_value = old_values.get(var_name, NOT_PROVIDED) if isinstance(old_values, dict) else NOT_PROVIDED

        # Check if this field should be visible based on its show_if
        field_hidden = parent_hidden
        if not parent_hidden and schema_def.get('show_if') and isinstance(new_values, dict):
            # Evaluate show_if condition against sibling values
            if not filter_list([new_values], schema_def['show_if']):
                field_hidden = True

        field_type, field_info, nested_model = process_schema_field(
            schema_def, f'{model_name}_{var_name}', attr_value, old_attr_value,
            field_hidden=field_hidden,
        )
        if nested_model:
            nested_models[var_name] = nested_model
        if schema_def.get('show_if'):
            show_if_attrs[var_name] = schema_def['show_if']
        fields[var_name] = (field_type, field_info)

    # Create the model dynamically
    model = create_model(model_name, __base__=BaseModel, **fields)

    if show_if_attrs and not parent_hidden:
        # What we want to do here is make sure that we are not injecting default values
        # for fields which have conditional defaults set
        provided_values = new_values if isinstance(new_values, dict) else {}
        defaults = get_defaults(model, provided_values)
        rebuild = False
        # If we were not able to get defaults, no need to do the below magic
        # It just means that a validation error occurred and we are going to raise it anyways
        # Also if a user already has provided value for some attr which has show_if set, there is
        # no need to mark that field as NotRequired etc
        for attr in filter(lambda k: k not in provided_values, [] if defaults is None else show_if_attrs):
            if not filter_list([defaults], show_if_attrs[attr]):
                # This means we should not be injecting default values here and instead mark it as NotRequired
                fields[attr][1].default = NotRequired
                fields[attr][1].default_factory = None
                rebuild = True

        if rebuild:
            model = create_model(model_name, __base__=BaseModel, **fields)

    return model


def get_defaults(model: Type[BaseModel], new_values: dict) -> dict | None:
    # We will try to get default values form the current model being passed by dumping values
    # if we are not able to do that, it is fine - it just probably means that we had
    # required fields and they were not found, in this case we will be raising a validation
    # error to the user anyways
    with contextlib.suppress(ValidationErrors):
        return validate_model(model, new_values)


def process_schema_field(
    schema_def: dict, model_name: str, new_values: USER_VALUES, old_values: USER_VALUES,
    field_hidden: bool = False,
) -> tuple[Type, Field, Type[BaseModel] | None]:
    """
    Process a schema field type / field information and any nested model if applicable which was generated.
    """
    schema_type = schema_def['type']
    field_type = nested_model = None
    field_info = create_field_info_from_schema(schema_def, field_hidden=field_hidden)
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
    elif schema_type == 'hostpath':
        field_type = create_length_validated_hostpath(
            min_length=schema_def.get('min_length'),
            max_length=schema_def.get('max_length'),
        )
    elif schema_type == 'path':
        field_type = AbsolutePath
    elif schema_type == 'dict':
        if dict_attrs := schema_def.get('attrs', []):
            # Pass field_hidden to nested model generation
            field_type = nested_model = generate_pydantic_model(
                dict_attrs, model_name, new_values, old_values, parent_hidden=field_hidden
            )
            if not field_hidden:
                field_info.default_factory = nested_model
        else:
            # We have a generic dict type without specific attributes
            field_type = dict
    elif schema_type == 'list':
        annotated_items = []
        if list_items := schema_def.get('items', []):
            for item in list_items:
                item_type, item_info, _ = process_schema_field(
                    item['schema'], f'{model_name}_{item["variable"]}', NOT_PROVIDED, NOT_PROVIDED,
                )
                annotated_items.append(Annotated[item_type, item_info])

            field_type = list[Union[*annotated_items]]
        else:
            # We have a generic list type without specific items
            field_type = list
    else:
        raise ValueError(f'Unsupported schema type: {schema_type!r}')

    assert field_type is not None

    if schema_def.get('null', False):
        field_type = Union[field_type, None]

    if schema_def.get('immutable') and schema_type in (
        'string', 'int', 'boolean', 'path'
    ) and old_values is not NOT_PROVIDED:
        # If we have a value for this field in old_values, we should not allow it to be changed
        field_type = Literal[old_values]
    elif schema_def.get('enum') and schema_type == 'string':
        enum_values = [v['value'] for v in schema_def['enum']]
        if enum_values:  # Only create Literal if there are actual enum values
            field_type = Literal[*enum_values]

    if schema_def.get('valid_chars'):
        # If valid_chars is specified, we can use a match_validator to ensure the value matches the regex
        field_type = Annotated[field_type, AfterValidator(match_validator(re.compile(schema_def['valid_chars'])))]

    return field_type, field_info, nested_model


def create_field_info_from_schema(schema_def: dict, field_hidden: bool = False) -> Field:
    """
    Create Pydantic Field info from schema definition.
    """
    field_kwargs = {}

    if 'description' in schema_def:
        field_kwargs['description'] = schema_def['description']

    if 'title' in schema_def:
        field_kwargs['title'] = schema_def['title']

    # If field is hidden by parent's show_if, make it NotRequired
    if field_hidden:
        field_kwargs['default'] = NotRequired
    elif 'default' in schema_def:
        field_kwargs['default'] = schema_def['default']
    elif not schema_def.get('required', False):
        # If a field is not marked as required, we set default to NotRequired
        # which means that it is fine if this field is not set/specified and will
        # not be added to normalized data
        # lists/dicts are special in our old implementation as they always have their
        # defaults populated if none are set
        if schema_def['type'] == 'list':
            field_kwargs['default_factory'] = list
        elif schema_def['type'] == 'dict':
            field_kwargs['default_factory'] = dict
        else:
            field_kwargs['default'] = NotRequired

    # Add validation constraints
    if schema_def['type'] == 'list':
        # For lists, min/max refer to the number of items
        if 'min' in schema_def:
            field_kwargs['min_length'] = schema_def['min']
        if 'max' in schema_def:
            field_kwargs['max_length'] = schema_def['max']
    elif schema_def['type'] in ('string', 'text', 'path'):
        # For string types, use min_length/max_length
        # Skip hostpath if it has length constraints (handled in type)
        if 'min_length' in schema_def:
            field_kwargs['min_length'] = schema_def['min_length']
        if 'max_length' in schema_def:
            field_kwargs['max_length'] = schema_def['max_length']
    else:
        # For numeric types (int), min/max are bounds
        if 'min' in schema_def:
            field_kwargs['ge'] = schema_def['min']
        if 'max' in schema_def:
            field_kwargs['le'] = schema_def['max']

    return Field(**field_kwargs)
