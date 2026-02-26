import re


RE_DOMAIN_WILDCARD = re.compile(r'\*|\?|\[|\]')


def get_domain(hostname):
    """
    return the 'domain' part of the hostname
    e.g. gruff.billy.goat will return 'billy.goat'
    and  gruffbillygoat will return None
    """
    lst = hostname.split('.', 1)
    if len(lst) > 1:
        return lst[1]
    return None


def leftmost_has_wildcards(hostname):
    """
    A bool that returns True if the left most level contains wildcards
    """
    return bool(RE_DOMAIN_WILDCARD.search(hostname.split('.')[0]))


def get_wildcard_domain(hostname):
    """
    If the left most level of the supplied hostname contains valid wildcard characters
       and there is more than one level in the name,
    then return the domain part.
    e.g. asdf-* will return None
         asdf-*.example.com will return example.com
         fred.example.com will return None
    """
    if leftmost_has_wildcards(hostname):
        return get_domain(hostname)
    return None
