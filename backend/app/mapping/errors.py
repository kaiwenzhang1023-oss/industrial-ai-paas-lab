"""Structured, fail-closed mapping errors."""
class MappingFailure(ValueError):
    def __init__(self, code, path='', message='', source_error_code=None):
        super().__init__(message or code)
        self.code, self.path, self.message = code, path, message or code
        self.source_error_code = source_error_code
    def as_dict(self):
        result = {'code': self.code, 'path': self.path, 'message': self.message}
        if self.source_error_code: result['source_error_code'] = self.source_error_code
        return result
