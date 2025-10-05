# core/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def to_float(value):
    try:
        return float(value)
    except:
        return 0.0

@register.filter
def dict_get(d, key):
    # Safe get for dictionary-lookup in template
    return d.get(key)

@register.filter
def get_item(queryset, pk):
    """
    Given a queryset and a primary key, return the matched item or None.
    Usage in template:
    {{ my_queryset|get_item:pk }}
    """
    try:
        return queryset.get(pk=pk)
    except queryset.model.DoesNotExist:
        return None
