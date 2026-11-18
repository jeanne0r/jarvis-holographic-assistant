"""Strict bounded JSON-schema subset; fail closed for unsupported keywords."""
import json
import math


def loads(raw):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('Duplicate JSON key')
            obj[key] = value
        return obj
    if len(raw) > 64000:
        raise ValueError('Response too large')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def validate(value, schema, depth=0):
    if depth > 12:
        raise ValueError('JSON nesting limit')
    allowed = {'type', 'properties', 'required', 'additionalProperties', 'items', 'enum', 'minItems', 'maxItems', 'minLength', 'maxLength', 'minimum', 'maximum'}
    if set(schema) - allowed:
        raise ValueError('Unsupported schema keyword')
    kind = schema.get('type')
    types = {'object': dict, 'array': list, 'string': str, 'boolean': bool, 'integer': int, 'number': (int, float), 'null': type(None)}
    if kind not in types or not isinstance(value, types[kind]) or (kind in {'integer', 'number'} and isinstance(value, bool)):
        raise ValueError('JSON type mismatch')
    if kind == 'object':
        props = schema.get('properties', {})
        if not set(schema.get('required', [])) <= value.keys():
            raise ValueError('Required field missing')
        if schema.get('additionalProperties') is False and set(value) - props.keys():
            raise ValueError('Unknown field')
        if len(value) > 64:
            raise ValueError('Too many fields')
        for key, item in value.items():
            if key in props:
                validate(item, props[key], depth + 1)
            elif schema.get('additionalProperties') is not False:
                # Free-form content remains JSON data with independent bounds.
                bounded(item, depth + 1)
    elif kind == 'array':
        if not schema.get('minItems', 0) <= len(value) <= schema.get('maxItems', 64):
            raise ValueError('Array limit')
        for item in value:
            validate(item, schema['items'], depth + 1)
    elif kind == 'string':
        if not schema.get('minLength', 0) <= len(value) <= schema.get('maxLength', 16000):
            raise ValueError('String limit')
    elif kind in {'integer', 'number'}:
        if not math.isfinite(value) or not schema.get('minimum', -1e12) <= value <= schema.get('maximum', 1e12):
            raise ValueError('Number limit')
    if 'enum' in schema and value not in schema['enum']:
        raise ValueError('Enum mismatch')
    return value


def bounded(value, depth=0):
    if depth > 12:
        raise ValueError('JSON nesting limit')
    if isinstance(value, dict):
        if len(value) > 64:
            raise ValueError('Content size')
        for k, v in value.items():
            if not isinstance(k, str) or len(k) > 200:
                raise ValueError('Content key')
            bounded(v, depth + 1)
    elif isinstance(value, list):
        if len(value) > 64:
            raise ValueError('Content size')
        for v in value: bounded(v, depth + 1)
    elif isinstance(value, str):
        if len(value) > 8000: raise ValueError('Content string')
    elif type(value) in (float, int):
        if not math.isfinite(value): raise ValueError('Content number')
    elif value is not None and not isinstance(value, bool):
        raise ValueError('Unsupported content')


def obj(properties, required=None):
    return {'type': 'object', 'properties': properties, 'required': list(properties) if required is None else required, 'additionalProperties': False}


TEXT = {'type': 'string', 'minLength': 1, 'maxLength': 200}
SKILL = obj({
    'name': {'type': 'string', 'minLength': 3, 'maxLength': 64},
    'version': {'type': 'integer', 'minimum': 1},
    'description': {'type': 'string', 'minLength': 1, 'maxLength': 2000},
    'allowed_tools': {'type': 'array', 'minItems': 1, 'maxItems': 2,
                      'items': {'type': 'string', 'enum': ['memory.search', 'report']}},
    'checks': {'type': 'array', 'minItems': 1, 'maxItems': 2,
               'items': {'type': 'string', 'enum': ['flow', 'freshness']}}})
FACT = obj({'type': {'type': 'string', 'enum': ['identity', 'knowledge', 'episode', 'project', 'skill', 'lesson']},
            'subject': TEXT, 'predicate': TEXT, 'content': {'type': 'object'},
            'event_id': TEXT, 'evidence': {'type': 'string', 'minLength': 1, 'maxLength': 800}})
EXTRACTION = obj({'candidates': {'type': 'array', 'maxItems': 16, 'items': FACT},
                  'summary': {'type': 'string', 'maxLength': 2000},
                  'skill_suggestions': {'type': 'array', 'maxItems': 4, 'items': {'type': 'string', 'maxLength': 800}}})
