from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter(name='length_greater_than')
@stringfilter
def length_greater_than(value, arg):
    "Check a strings length"
    return len(value) > arg
