"""Recover literal source excerpts from strictly bounded citation formatting.

The original provider response remains unchanged in its trace. This module does
not paraphrase, repair source identifiers/locations, search outside a citation,
or turn a finding into an approved fact or rule.
"""
import copy
import io
import re
from pypdf import PdfReader
from adapters.evidence import validate_ref
from core.models import JTError


def normalized_text(text):
    chars, starts, ends = [], [], []
    for match in re.finditer(r'\s+|\S', text):
        chars.append(' ' if match[0].isspace() else match[0])
        starts.append(match.start()); ends.append(match.end())
    return ''.join(chars), starts, ends


def unique_span(text, fragments):
    """Require a unique, ordered, non-overlapping alignment of literal fragments."""
    found = []; examined = 0; exhausted = False
    def visit(index, cursor, start):
        nonlocal examined, exhausted
        if len(found) > 1 or exhausted: return
        if index == len(fragments):
            found.append((start, cursor)); return
        fragment = fragments[index]
        offset = text.find(fragment, cursor)
        while offset >= 0 and len(found) < 2 and not exhausted:
            examined += 1
            if examined > 256:
                exhausted = True; return
            visit(index+1, offset+len(fragment), offset if start is None else start)
            offset = text.find(fragment, offset+1)
    visit(0, 0, None)
    return found[0] if len(found) == 1 and not exhausted else None


def resolve_reference(reference, source, blobs, allow_omissions=False):
    """Return an exact reference plus optional provenance, or the original error.

    Whitespace recovery is available for textual citations. Explicit ellipses
    may be expanded only for review findings/questions, never raw observations.
    The complete original span between the retained fragments is restored.
    """
    if not source or reference.get('source_id') != source.get('source_id'):
        raise JTError('INVALID_INPUT', 'Unknown evidence source.')
    try:
        validate_ref(reference, source, blobs)
        return copy.deepcopy(reference), None
    except JTError as original_error:
        if source['mime'] not in ('text/plain', 'application/pdf'):
            raise original_error
        # The existing validator must first accept the same source hash and
        # locator. An empty probe validates location only; it is never saved.
        validate_ref({**reference, 'quote':''}, source, blobs)
        quote = reference['quote']
        if not isinstance(quote, str) or not quote.strip(): raise original_error
        data = blobs.get(source['blob_id'])
        if source['mime'] == 'text/plain':
            excerpt = data.decode('utf-8-sig')
            if not source.get('human'):
                match = re.fullmatch(r'line:(\d+)(?:-(\d+))?', reference['locator'])
                excerpt = '\n'.join(excerpt.splitlines()[int(match[1])-1:int(match[2] or match[1])])
        else:
            page = int(reference['locator'].split(':')[1])-1
            excerpt = PdfReader(io.BytesIO(data)).pages[page].extract_text() or ''
        text, starts, ends = normalized_text(excerpt)
        normalized_quote = re.sub(r'\s+', ' ', quote).strip()
        mode = 'whitespace_restored'
        fragments = [normalized_quote]
        span = unique_span(text, fragments)
        if span is None and allow_omissions:
            # Only explicit, spaced omission markers; decimal points, other
            # punctuation, wording, numbers, negation and case are unchanged.
            fragments = re.split(r' (?:\.\.\.|…) ', normalized_quote)
            if not 2 <= len(fragments) <= 8 or any(not x for x in fragments):
                raise original_error
            span = unique_span(text, fragments)
            mode = 'omitted_source_span_restored'
        if span is None: raise original_error
        literal = excerpt[starts[span[0]]:ends[span[1]-1]]
        if len(literal.encode('utf-8')) > 16384: raise original_error
        resolved = {**reference, 'quote':literal}
        validate_ref(resolved, source, blobs)
        return resolved, {'method':mode, 'original_reference':copy.deepcopy(reference),
                          'resolved_reference':copy.deepcopy(resolved)}
