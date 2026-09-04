class UnidadeIndisponivelError(Exception):
    """Unidade existe, mas não está com status normalizado 'disponivel'."""


class UnidadeNaoEncontradaError(Exception):
    """Unidade não encontrada no banco (id inexistente)."""


class ClienteInvalidoError(Exception):
    """cliente_id informado não corresponde a nenhum cliente cadastrado, ou
    nem cliente_id nem cliente_novo foram informados."""


class VendaNaoEncontradaError(Exception):
    """Venda não encontrada no banco."""


class VendaJaDistratadaError(Exception):
    """Venda já está distratada (esta_distratada() == True)."""
