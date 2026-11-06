from dataclasses import dataclass

@dataclass
class ProviderResult:
    data:dict
    input_tokens:int
    output_tokens:int
    request_id:str=''
class ProviderError(Exception):
    def __init__(self,code,unknown=False,retry_after=0):
        self.code=code;self.unknown=unknown;self.retry_after=retry_after
        super().__init__(code)
