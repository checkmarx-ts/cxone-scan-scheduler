class AuthException(BaseException):
    pass
    
class CommunicationException(BaseException):

    @staticmethod
    def __clean(content):
        if type(content) is list:
            return [CommunicationException.__clean(x) for x in content]
        elif type(content) is tuple:
            return (CommunicationException.__clean(x) for x in content)
        elif type(content) is dict:
            return {k:CommunicationException.__clean(v) for k,v in content.items()}
        elif type(content) is str:
            if re.match("^Bearer.*", content):
                return "REDACTED"
            else:
                return content
        else:
            return content

    def __init__(self, op, *args, **kwargs):
        BaseException.__init__(self, f"Operation: {op.__name__} args: [{CommunicationException.__clean(args)}] kwargs: [{CommunicationException.__clean(kwargs)}]")

class ResponseException(BaseException):
    pass

class ScanException(BaseException):
    pass