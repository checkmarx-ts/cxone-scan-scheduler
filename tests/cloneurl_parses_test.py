import unittest
from cxone_api.util import CloneUrlParser

class TestCloneUrlUnknown(unittest.TestCase):
    def test_canary(self):
        self.assertTrue(True)

    def test_http_with_port(self):
        parse = CloneUrlParser("unknown", "http://the_host:7990/scm/the_org/the_repo.git")
        self.assertTrue(parse.scheme is None 
                        and parse.creds is None
                        and parse.org == "the_org"
                        and parse.repo == "the_repo")

class TestCloneUrlBitBucket(unittest.TestCase):

    def test_canary(self):
        self.assertTrue(True)

    def test_http_with_port(self):
        parse = CloneUrlParser("bitbucket", "http://the_host:7990/scm/the_org/the_repo.git")
        self.assertTrue(parse.scheme == "http" 
                        and parse.creds is None
                        and parse.org == "the_org"
                        and parse.repo == "the_repo")

    def test_https_with_port(self):
        parse = CloneUrlParser("bitbucket", "https://the_host:7990/scm/the_org/the_repo.git")
        self.assertTrue(parse.scheme == "https" 
                        and parse.creds is None
                        and parse.org == "the_org"
                        and parse.repo == "the_repo")

    def test_https_no_port(self):
        parse = CloneUrlParser("bitbucket", "https://the_host/scm/the_org/the_repo.git")
        self.assertTrue(parse.scheme == "https" 
                        and parse.creds is None
                        and parse.org == "the_org"
                        and parse.repo == "the_repo")

    def test_https_url_rewirte(self):
        parse = CloneUrlParser("bitbucket", "https://the_host/some/other/endpoint/scm/the_org/the_repo.git")
        self.assertTrue(parse.scheme == "https" 
                        and parse.creds is None
                        and parse.org == "the_org"
                        and parse.repo == "the_repo")

    def test_https_malformed(self):
        parse = CloneUrlParser("bitbucket", "https://the_host/some/other/endpoint/scm/the_org/the_repo")
        self.assertTrue(parse.scheme is None 
                        and parse.creds is None
                        and parse.org is None
                        and parse.repo is None)

    def test_ssh_with_port(self):
        parse = CloneUrlParser("bitbucket", "ssh://the_user@the_host:7999/the_org/the_repo.git")
        self.assertTrue(parse.scheme == "ssh" 
                        and parse.creds == "the_user"
                        and parse.org == "the_org"
                        and parse.repo == "the_repo")
        

class TestCloneUrlADO(unittest.TestCase):

    def test_canary(self):
        self.assertTrue(True)

    def test_http_with_port(self):
        parse = CloneUrlParser("azure", "http://the_server:8080/tfs/the_org/the_project/_git/the_repo")
        self.assertTrue(parse.scheme == "http" 
                        and parse.creds is None
                        and parse.org == "the_org"
                        and parse.repo == "the_repo")

    def test_https_with_port(self):
        parse = CloneUrlParser("azure", "https://someone@the_server:8080/tfs/the_org/the_project/_git/the_repo")
        self.assertTrue(parse.scheme == "https" 
                        and parse.creds == "someone"
                        and parse.org == "the_org"
                        and parse.repo == "the_repo")


    def test_ssh_with_port(self):
        parse = CloneUrlParser("azure", "ssh://the_server:22/tfs/the_org/the_project/_git/the_repo")
        self.assertTrue(parse.scheme == "ssh" 
                        and parse.creds is None
                        and parse.org == "the_org"
                        and parse.repo == "the_repo")

if __name__ == '__main__':
    unittest.main()
