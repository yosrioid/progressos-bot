from uuid import uuid4


class CorrelationIdFactory:
    def new(self) -> str:
        return uuid4().hex
