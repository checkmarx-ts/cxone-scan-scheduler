import re

class CloneUrlParser:

    __parsers = {
        "bitbucket" : re.compile("^(?P<scheme>.+)://((?P<cred>.+)@)?.+/(scm/)?(?P<org>.+)/(?P<repo>.+)(\\.git)?$"),
        "azure" : re.compile("^(?P<scheme>.+)://((?P<cred>.+)@)?.+/(?P<org>.+)/(?P<project>.+)/_git/(?P<repo>.+)(\\.git)?$")
    }

    __default = re.compile("^.*[/:]{1}(?P<org>.+)/(?P<repo>.+)(\\.git)?$")

    def __init__(self, repo_type, clone_url):
        matcher = CloneUrlParser.__parsers[repo_type] if repo_type in CloneUrlParser.__parsers.keys() else CloneUrlParser.__default
        computed_match = matcher.match(clone_url)
        self.__the_match = computed_match.groupdict() if computed_match is not None else {}

    def __get_prop_or_none(self, name):
        return  self.__the_match[name] if name in self.__the_match.keys() else None

    @property
    def scheme(self):
        return self.__get_prop_or_none("scheme")

    @property
    def creds(self):
        return self.__get_prop_or_none("cred")

    @property
    def org(self):
        return self.__get_prop_or_none("org")

    @property
    def repo(self):
        return self.__get_prop_or_none("repo")
