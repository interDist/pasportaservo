from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
import time
import copy

register = template.Library()

COMPACTED_TAG_NAME = 'compacted'

@register.tag(name=COMPACTED_TAG_NAME)
def compacted(parser, token, is_block=None):
    """
    A template tag that removes all extra whitespace from its contents and strips any whitespace at the beginning
    and at the end of the resulting string.  Any characters that can role as whitespace (including new lines) are
    replaced by a space and collapsed.
    Syntax:
        {% compacted [literal-or-var, ...] [as output-var] %} [elements] {% endcompacted %}
    Elements can be any valid template content. The literals and variables provided in the opening tag are appended
    to the elements and processed as one. When an output variable is specified, the result will be stored in that
    context variable in a same fashion as other built-in template tags behave.  The opening tag parameters can be
    used to compact (and join) already-existing context variables.
    """
    nodelist = parser.parse(('end'+COMPACTED_TAG_NAME,))
    parser.delete_first_token()
    
    bits = token.split_contents()
    target_var = None
    if len(bits) == 2 and bits[1] == 'as':
        raise template.TemplateSyntaxError("'%s' tag: Missing argument 'variable' for 'as var' syntax" % bits[0])
    if len(bits) > 2 and bits[-2] == 'as':
        target_var = bits[-1]
        bits = bits[:-2]
    bits = bits[1:]
    
    return TrimmedAndCompactedNode(nodelist, bits, target_var, is_block)


@register.tag(name='include-compacted')
def include_compacted(parser, token):
    """
    A template tag that extends the built-in 'include' tag by post-processing the included contents and compacting
    them; this is a shorthand for {% compacted %}{% include ... %}{% endcompacted %}.
    """
    token.contents = token.contents.replace('include-compacted', 'include')
    parser.tokens.insert(0, token)
    parser.tokens.insert(1, generate_token('end'+COMPACTED_TAG_NAME, token))
    
    nodelist = parser.parse(('end'+COMPACTED_TAG_NAME,))
    parser.delete_first_token()
    
    return TrimmedAndCompactedNode(nodelist, [], None, True)


@register.tag(name='block-compacted')
def block_compacted(parser, blocktoken):
    """
    A template tag that extends the built-in 'block' tag by post-processing the block contents and compacting them.
    Any semantics of the 'block' tag can be applied, including naming, "inheritance", scoping, and {{block.super}}.
    Syntax:
        {% block-compacted [name] %} [elements] {% endblock [name] %}
    See https://docs.djangoproject.com/en/dev/ref/templates/language/#template-inheritance for how blocks work.
    """
    try:
        tag_name, block_name = blocktoken.contents.split()
    except ValueError:
        raise template.TemplateSyntaxError("'%s' tag requires the block's name as the only argument" % blocktoken.contents.split()[0])
    
    token_new_cmpct = generate_token(COMPACTED_TAG_NAME, blocktoken)
    token_new_block = generate_token('block %s' % block_name, blocktoken)
    parser.tokens.insert(0, token_new_block)
    parser.tokens.insert(1, token_new_cmpct)
    
    SENTINEL_TAG_NAME = 'compactedsentinel'
    sentinel = None
    endtag = 'endblock %s' % block_name
    for index, token in enumerate(parser.tokens):
        if token.token_type == template.base.TOKEN_BLOCK and token.contents in (endtag, 'endblock'):
            token_end_cmpct = generate_token('end'+COMPACTED_TAG_NAME, token)
            sentinel = generate_token(SENTINEL_TAG_NAME + ' ' + str(time.time()), token)
            parser.tokens.insert(index+0, token_end_cmpct)
            parser.tokens.insert(index+2, sentinel)
            break
    nodelist = parser.parse((SENTINEL_TAG_NAME,))
    token = parser.next_token()
    if token != sentinel:
        raise template.TemplateSyntaxError("Unexpected error during template processing")
    
    return CompactedBlockNode(nodelist)


@register.filter(name='compact', is_safe=True)
def compacted_filter(value):
    """
    A template filter that removes all extra whitespace from the value it is applied to, and strips any whitespace
    at the beginning and at the end of the resulting string. Any characters that can role as whitespace (including
    new lines) are replaced by a space and collapsed.
    """
    return ' '.join(value.split())


def generate_token(tag_name, base_token):
    #debug_enabled = hasattr(base_token, 'source')
    #django_1_9_or_newer = hasattr(base_token, 'position')
    #if django_1_9_or_newer:
    #    new_token = template.Token(template.base.TOKEN_BLOCK, tag_name, base_token.position, base_token.lineno)
    #else:
    #    new_token = template.Token(template.base.TOKEN_BLOCK, tag_name)
    #    new_token.lineno = base_token.lineno
    #if debug_enabled:
    #    new_token.source = base_token.source
    new_token = copy.copy(base_token)
    new_token.contents = tag_name
    return new_token


class TrimmedAndCompactedNode(template.Node):
    def __init__(self, nodelist, inline_vars, target_var, is_block):
        self.nodelist = nodelist
        self.inline_vars = inline_vars
        self.target_var = target_var
        self.block = is_block

    def render(self, context):
        contents = ''
        if len(self.inline_vars):
            for var in self.inline_vars:
                try:
                    var_value = template.Variable(var).resolve(context)
                    contents += (conditional_escape(var_value) if context.autoescape else var_value) + ''
                except template.VariableDoesNotExist:
                    pass
        contents += self.nodelist.render(context)
        
        output = ' '.join(contents.split())
        output = mark_safe(output)
        if self.target_var:
            context[self.target_var] = output
            return ''
        return output

class CompactedBlockNode(template.Node):
    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        return self.nodelist.render(context)

